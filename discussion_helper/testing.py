"""
Fake parts, so the loop can be tested without a room.

Module summary
--------------
The behaviour worth testing in this package is the behaviour that is hardest
to observe: what happens when somebody interrupts, whether the queued audio is
thrown away, whether the floor ends up back where it belongs. None of that is
about a microphone, a model or a sound card — and a test that needs all three
is a test that runs on one machine, once, by hand.

So the three parts have fakes, and they ship in the package rather than in the
test directory. Somebody writing their own responder or their own voice wants
to drop it into a loop whose other two parts are known-good, and they should
not have to copy them out of a test file to do it.

Each fake is deliberately *observable*: :class:`SilentVoice` records what it
was asked to say and what it was cut off mid-way through, because "did the
interruption actually stop the audio" is exactly the assertion that matters
and exactly the one a real voice makes impossible.

Author
------
Warith HARCHAOUI — https://linkedin.com/in/warith-harchaoui
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Sequence

from discussion_helper.types import SpokenSentence, Utterance


class ScriptedListener:
    """Yields the turns it was given, then stops.

    Parameters
    ----------
    turns : sequence of str
        What the user says, in order.
    interrupt_after_s : float or None
        When set, :meth:`speech_started` resolves this many seconds after it
        is awaited — which is how a barge-in is staged in a test. ``None``
        never resolves, which is a user who waits politely.
    pace_s : float
        A pause before each turn, so a timing test has something to measure.
    """

    def __init__(
        self,
        turns: Sequence[str],
        *,
        interrupt_after_s: float | None = None,
        pace_s: float = 0.0,
    ) -> None:
        self.turns = list(turns)
        self.interrupt_after_s = interrupt_after_s
        self.pace_s = pace_s
        self.closed = False

    async def utterances(self) -> AsyncIterator[Utterance]:
        """Yield each scripted turn as a finished utterance."""
        for text in self.turns:
            if self.pace_s:
                await asyncio.sleep(self.pace_s)
            yield Utterance(speaker="user", text=text)

    async def speech_started(self) -> None:
        """Resolve when the staged interruption happens, or never."""
        if self.interrupt_after_s is None:
            # A future that is never resolved: the honest shape of "this
            # implementation cannot tell you", and what degrades a
            # conversation to half-duplex rather than breaking it.
            await asyncio.Event().wait()
            return  # unreachable: nothing ever sets that Event
        await asyncio.sleep(self.interrupt_after_s)

    async def aclose(self) -> None:
        self.closed = True


class EchoResponder:
    """Answers with what it was told, one sentence per call.

    The simplest responder that still exercises the loop: it proves the
    history reached the model, because what comes back is what went in.
    """

    def __init__(self, sentences: int = 1, delay_s: float = 0.0) -> None:
        self.sentences = sentences
        self.delay_s = delay_s
        self.closed = False
        self.seen: list[list[dict[str, str]]] = []

    async def reply(self, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        """Echo the last user message, as many sentences as configured."""
        self.seen.append(list(messages))
        last = messages[-1]["content"] if messages else ""
        for index in range(self.sentences):
            if self.delay_s:
                await asyncio.sleep(self.delay_s)
            yield last if index == 0 else f"{last} ({index + 1})"

    async def aclose(self) -> None:
        self.closed = True


class SilentVoice:
    """Plays nothing, and remembers exactly what it was asked to play.

    Parameters
    ----------
    seconds_per_sentence : float
        How long a sentence "takes". Real time, so a barge-in staged at
        0.1 s lands inside a 1 s sentence the way it would in a room.

    Attributes
    ----------
    spoken : list of str
        Every sentence it was asked for, including the one that was cut.
    completed : list of str
        Only the sentences that finished. The difference between the two
        lists is the assertion that matters: audio that was started and not
        heard must not be counted as said.
    stops : int
        How many times it was told to stop.
    """

    def __init__(self, seconds_per_sentence: float = 0.05, first_audio_s: float = 0.0) -> None:
        self.seconds_per_sentence = seconds_per_sentence
        self.first_audio_s = first_audio_s
        self.spoken: list[str] = []
        self.completed: list[str] = []
        self.stops = 0
        self.closed = False
        self._stopped = asyncio.Event()

    async def speak(self, sentence: str) -> SpokenSentence:
        """ "Play" one sentence, returning early if stopped."""
        self.spoken.append(sentence)
        self._stopped.clear()
        if self.first_audio_s:
            await asyncio.sleep(self.first_audio_s)
        try:
            await asyncio.wait_for(self._stopped.wait(), timeout=self.seconds_per_sentence)
        except TimeoutError:
            # Nobody stopped us: the sentence finished.
            self.completed.append(sentence)
            return SpokenSentence(
                text=sentence,
                first_audio_s=self.first_audio_s,
                played_s=self.seconds_per_sentence,
            )
        return SpokenSentence(text=sentence, first_audio_s=self.first_audio_s, cut=True)

    async def stop(self) -> None:
        """Cut the current sentence and discard what was queued."""
        self.stops += 1
        self._stopped.set()

    async def aclose(self) -> None:
        self.closed = True
