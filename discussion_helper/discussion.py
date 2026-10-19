"""
The loop: who holds the floor, and what happens when the user cuts in.

Module summary
--------------
Everything else in this package is a part. This is the thing the parts are
for: listen, decide the user has finished, answer, speak — and, at any moment
while speaking, stop because the user started again.

The hard part is not the sequence. It is the interruption, and three
properties of it that a first implementation gets wrong:

**It has to be fast.** The published bar is under 150 ms from the user's first
syllable to the agent's silence. Past that the agent is audibly talking over
somebody, which is the single rudest thing a voice interface does.

**It has to discard, not drain.** A reply is synthesised ahead of playback, so
when the user interrupts there is audio already made and not yet heard.
Playing it out — because it exists, because it was paid for — is what makes an
agent feel deaf. :meth:`Voice.stop` throws it away.

**It has to be hard to trigger by accident.** The agent's own voice reaching
its own microphone looks exactly like the user speaking. Without acoustic echo
cancellation the honest default is to ask more of a barge-in than of ordinary
speech, and to say so — see :data:`Policy.barge_in_grace_s`.

What this module does not do
----------------------------
It does not recognise speech, generate text or synthesise audio. Those live in
``vocal-helper``, a language model, and ``speaker-helper`` respectively, and
are reached through the protocols in :mod:`discussion_helper.parts`. The loop
below is written entirely against those protocols, which is why it can be
tested without a microphone.

Author
------
Warith HARCHAOUI — https://linkedin.com/in/warith-harchaoui
"""

from __future__ import annotations

import asyncio
import contextlib
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass

from discussion_helper.parts import Listener, Responder, Voice
from discussion_helper.types import (
    Conversation,
    Floor,
    SpokenSentence,
    TurnTiming,
    Utterance,
)


@dataclass
class Policy:
    """The few decisions a conversation needs made for it.

    Parameters
    ----------
    allow_barge_in : bool
        Whether the user may interrupt the agent at all. ``False`` is strict
        half-duplex: rude, and the right choice on a speakerphone with no echo
        cancellation, where every reply would otherwise interrupt itself.
    barge_in_grace_s : float
        How long after the agent starts speaking before an interruption is
        believed. This exists because of echo: the agent's first syllable is
        the loudest thing the microphone will hear, and without AEC it reads
        as the user starting to talk. A short grace period costs a listener
        almost nothing and removes the whole class of self-interruption.
    max_reply_sentences : int
        A ceiling on how long an answer may run. Not a style preference: an
        agent that talks for ninety seconds is one the user has to interrupt,
        and interruption is the expensive path. Zero means no ceiling.
    silence_timeout_s : float
        How long to wait for the user before giving up on the turn. Zero waits
        forever, which is correct for a push-to-talk session and wrong for an
        open microphone in an empty room.
    """

    allow_barge_in: bool = True
    barge_in_grace_s: float = 0.35
    max_reply_sentences: int = 0
    silence_timeout_s: float = 0.0


class Discussion:
    """A spoken conversation between a user and an agent.

    Parameters
    ----------
    listener, responder, voice
        The three parts. See :mod:`discussion_helper.parts`.
    policy : Policy
        What to do about interruptions and length.

    Examples
    --------
    >>> # Every part is injectable, so a whole conversation runs in a test
    >>> # with no microphone, no model and no sound card.
    >>> from discussion_helper.testing import ScriptedListener, EchoResponder, SilentVoice
    >>> import asyncio
    >>> talk = Discussion(
    ...     ScriptedListener(["bonjour"]), EchoResponder(), SilentVoice()
    ... )
    >>> conversation = asyncio.run(talk.run())
    >>> [u.text for u in conversation.utterances]
    ['bonjour', 'bonjour']
    """

    def __init__(
        self,
        listener: Listener,
        responder: Responder,
        voice: Voice,
        policy: Policy | None = None,
    ) -> None:
        self.listener = listener
        self.responder = responder
        self.voice = voice
        self.policy = policy or Policy()
        self.conversation = Conversation()
        self._started = time.perf_counter()

    # -- the loop ----------------------------------------------------------

    async def run(self) -> Conversation:
        """Hold the conversation until the listener stops yielding turns.

        Returns
        -------
        Conversation
            Everything said, with a :class:`~discussion_helper.types.TurnTiming`
            per exchange.
        """
        await self.warmup()
        self.conversation.floor = Floor.LISTENING
        try:
            async for utterance in self._user_turns():
                if not utterance.text.strip():
                    # A turn that recognised to nothing. Answering it would
                    # mean answering silence, which is how an agent starts
                    # talking to an empty room.
                    continue
                self.conversation.add(utterance)
                await self._answer(utterance)
        finally:
            self.conversation.floor = Floor.IDLE
        return self.conversation

    async def warmup(self) -> None:
        """Pay every part's first-call cost before the user says anything.

        Concurrently, and never fatally. A part that cannot warm up may still
        work — and a conversation that refused to start because a *pre*-load
        failed would be refusing over something that was optional by
        construction.

        The numbers that make this worth doing are in
        :class:`~discussion_helper.parts.Warmable`: 4.8 seconds on the first
        model call in a process, 0.25 on the rest. Unwarmed, the whole of that
        lands on the user's first question.
        """
        warmable = [
            part for part in (self.listener, self.responder, self.voice) if hasattr(part, "warmup")
        ]
        if not warmable:
            return
        await asyncio.gather(
            *(part.warmup() for part in warmable),  # type: ignore[attr-defined]
            return_exceptions=True,
        )

    async def _user_turns(self) -> AsyncIterator[Utterance]:
        """Yield user turns, giving up after ``silence_timeout_s`` of nothing."""
        stream = self.listener.utterances()
        while True:
            try:
                if self.policy.silence_timeout_s > 0:
                    turn = await asyncio.wait_for(
                        stream.__anext__(), timeout=self.policy.silence_timeout_s
                    )
                else:
                    turn = await stream.__anext__()
            except StopAsyncIteration:
                return
            except TimeoutError:
                # Not an error: an open microphone in an empty room is the
                # ordinary end of a session, and raising here would make
                # every caller write the same `except`.
                return
            yield turn

    async def _answer(self, to: Utterance) -> None:
        """Produce and speak one reply, stopping if the user cuts in."""
        timing = TurnTiming(endpoint_s=0.0)
        self.conversation.floor = Floor.THINKING

        think_started = time.perf_counter()
        sentences = self.responder.reply(self.conversation.as_messages())

        spoken: list[str] = []
        interrupted = False
        measured_first_audio = False
        turn_started = self._elapsed()

        # Armed before the first sentence is spoken, not after: the watcher
        # has to already exist when the audio starts, or the first syllable of
        # an interruption is missed and the barge-in arrives a sentence late.
        # It waits on `speaking` below rather than on the clock, so the grace
        # period is measured from the first sample and not from here — the
        # model may take half a second to produce that first sentence.
        speaking = asyncio.Event()
        barge_in = self._watch_for_barge_in(speaking)

        try:
            async for index, sentence in _enumerate(sentences):
                if self.policy.max_reply_sentences and index >= self.policy.max_reply_sentences:
                    break
                if index == 0:
                    timing.think_s = time.perf_counter() - think_started
                    self.conversation.floor = Floor.SPEAKING
                    speaking.set()

                result = await self._speak_or_be_cut(sentence, barge_in)
                spoken.append(sentence)
                if result is None:
                    # Cancelled mid-sentence: the voice never returned, so
                    # there is nothing it could have reported.
                    interrupted = True
                    break
                if not measured_first_audio:
                    # The voice is the only thing that knows when sound
                    # actually left; the loop can time the call but not the
                    # speaker.
                    timing.speak_s = result.first_audio_s
                    measured_first_audio = True
                if result.cut:
                    interrupted = True
                    break
        finally:
            if barge_in is not None and not barge_in.done():
                barge_in.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await barge_in
            await _aclose_iterator(sentences)

        self.conversation.add(
            Utterance(
                speaker="agent",
                text=" ".join(spoken).strip(),
                started_s=turn_started,
                ended_s=self._elapsed(),
                interrupted=interrupted,
            )
        )
        self.conversation.timings.append(timing)
        self.conversation.floor = Floor.LISTENING

    async def _speak_or_be_cut(
        self, sentence: str, barge_in: asyncio.Task[None] | None
    ) -> SpokenSentence | None:
        """Speak one sentence; ``None`` when it was cancelled outright.

        The race is deliberate and the loser is cancelled rather than awaited:
        waiting for the sentence to finish "because it has started" is the
        drain-instead-of-discard mistake, one sentence further down.
        """
        speaking = asyncio.ensure_future(self.voice.speak(sentence))
        if barge_in is None:
            return await speaking

        done, _ = await asyncio.wait({speaking, barge_in}, return_when=asyncio.FIRST_COMPLETED)
        if speaking in done:
            return speaking.result()

        # The user started talking. Stop the audio first and tidy up second:
        # every millisecond between here and silence is the agent talking
        # over somebody.
        await self.voice.stop()
        speaking.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await speaking
        return None

    def _watch_for_barge_in(self, speaking: asyncio.Event) -> asyncio.Task[None] | None:
        """A task that completes when the user interrupts, or ``None``.

        ``None`` when barge-in is switched off, which the caller reads as "do
        not race" rather than as "wait forever" — an off switch that works by
        never resolving is an off switch that leaks a task per turn.

        The grace period is spent *before* listening, not checked afterwards.
        Both orders reject the echo; only this one does it without asking the
        listener a question whose answer is going to be thrown away — and a
        listener that reports speech continuously, as a real one does while
        the agent's voice is in the room, would turn the "check and keep
        watching" version into a hot loop.
        """
        if not self.policy.allow_barge_in:
            return None

        async def watch() -> None:
            # Measured from the first sample, which is why this waits on the
            # event rather than starting a timer here: producing the first
            # sentence can take longer than the grace period itself.
            await speaking.wait()
            if self.policy.barge_in_grace_s > 0:
                # The agent's own first syllable is the loudest thing the
                # microphone will hear, and without acoustic echo
                # cancellation it reads as the user starting to talk. The
                # cost of this window is that the opening of a reply cannot
                # be interrupted; the cost of not having it is a reply that
                # interrupts itself.
                await asyncio.sleep(self.policy.barge_in_grace_s)
            await self.listener.speech_started()

        return asyncio.ensure_future(watch())

    def _elapsed(self) -> float:
        """Seconds since the conversation began."""
        return time.perf_counter() - self._started

    # -- lifecycle ---------------------------------------------------------

    async def aclose(self) -> None:
        """Release the microphone, the model and the audio device."""
        for part in (self.listener, self.responder, self.voice):
            with contextlib.suppress(Exception):
                await part.aclose()

    async def __aenter__(self) -> Discussion:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()


async def _enumerate(iterator: AsyncIterator[str]) -> AsyncIterator[tuple[int, str]]:
    """``enumerate`` for an async iterator, which the stdlib does not have."""
    index = 0
    async for item in iterator:
        yield index, item
        index += 1


async def _aclose_iterator(iterator: AsyncIterator[str]) -> None:
    """Close a generator the loop stopped consuming early.

    Breaking out of ``async for`` leaves the generator suspended, and a
    responder holding a model connection would keep it until garbage
    collection — which in a long conversation means one leaked connection per
    interruption.
    """
    close = getattr(iterator, "aclose", None)
    if close is not None:
        with contextlib.suppress(Exception):
            await close()
