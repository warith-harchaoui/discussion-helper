"""
The three parts a discussion is made of, as protocols.

Module summary
--------------
A spoken conversation needs something that hears, something that answers, and
something that speaks. This package owns none of those: hearing is
``vocal-helper``'s job, answering is a language model's, speaking is
``speaker-helper``'s. What it owns is the *loop* — who holds the floor, what
happens when the user cuts in, and where the latency went.

So the three are protocols, and the loop is written against them. That is not
abstraction for its own sake:

* it is what lets the whole conversation loop be tested with no microphone,
  no model and no network, which is the only way the interruption and
  floor-handling logic gets exercised in CI at all;
* it is what lets somebody swap the recogniser for a cloud one, or the
  language model for a scripted one, without this package knowing;
* and it is what keeps the hard-won behaviour of the two sibling packages
  where it belongs — reimplementing any of it here would give it two owners.

The adapters that bind these protocols to the real siblings live in
:mod:`discussion_helper.adapters`.

Author
------
Warith HARCHAOUI — https://linkedin.com/in/warith-harchaoui
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol, runtime_checkable

from discussion_helper.types import SpokenSentence, Utterance


@runtime_checkable
class Listener(Protocol):
    """Turns an open microphone into finished user turns.

    One method and one event, because those are two different questions and
    conflating them is how barge-in gets built wrong.

    :meth:`utterances` answers "what did they say, and when did they stop" —
    it yields only *completed* turns, after whatever endpointing the
    implementation does.

    :meth:`speech_started` answers "is somebody talking *right now*", which
    has to be available while the agent is speaking and long before any
    transcript exists. A barge-in cannot wait for a transcript: by the time
    one exists the agent has been talking over the user for a second.
    """

    def utterances(self) -> AsyncIterator[Utterance]:
        """Yield completed user turns, in order."""
        ...

    async def speech_started(self) -> None:
        """Return as soon as the user starts speaking.

        Awaited only while the agent holds the floor. An implementation that
        cannot detect this should never return, which degrades the
        conversation to strict half-duplex rather than breaking it.
        """
        ...

    async def aclose(self) -> None:
        """Release the microphone."""
        ...


@runtime_checkable
class Responder(Protocol):
    """Turns the conversation so far into an answer, a sentence at a time.

    Yielding sentences rather than returning an answer is the whole design.
    Waiting for a complete reply before speaking adds its entire generation
    time to the silence the user sits through; yielding the first sentence as
    soon as it is complete removes all but its own share.

    Sentence-sized, specifically — not token-sized. Synthesis models use
    sentence context to shape intonation, so a chunk cut at a comma comes out
    flat or oddly stressed. The unit that is both fast enough and prosodically
    whole is one sentence.
    """

    def reply(self, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        """Yield the answer, one speakable sentence at a time."""
        ...

    async def aclose(self) -> None:
        """Release whatever the model holds."""
        ...


@runtime_checkable
class Warmable(Protocol):
    """A part with a first call that costs more than its later ones.

    Measured, not assumed: the local model client's content-safety scan takes
    **4.8 seconds** on its first call in a process — it loads a classifier —
    and **0.25 seconds** on every call after. The speech engine behaves the
    same way, loading an ONNX graph once.

    Unwarmed, that cost lands on the user's first question, which is the worst
    possible place: the one turn where somebody is deciding whether this thing
    works. Warmed while the microphone is opening, it costs nothing at all,
    because the user has not finished deciding to speak.

    Optional. :class:`~discussion_helper.discussion.Discussion` warms whatever
    offers it and ignores whatever does not.
    """

    async def warmup(self) -> None:
        """Pay the first-call cost now, before anybody is waiting."""
        ...


@runtime_checkable
class Voice(Protocol):
    """Speaks a sentence, and can be stopped in the middle of it.

    :meth:`stop` is the method that matters, and the one a naive
    implementation gets wrong by draining the queue instead of discarding it.
    When the user interrupts, every sentence already synthesised and not yet
    heard must be thrown away. Playing it out "because it was already
    generated" is exactly the behaviour that makes an agent feel deaf.
    """

    async def speak(self, sentence: str) -> SpokenSentence:
        """Speak one sentence and report what it cost.

        The return type carries *two* durations on purpose. The loop needs
        the time to the first sample — that is the silence the listener sits
        through — and reporting only "how long speaking took" would make a
        fast engine playing a long sentence look slower than a slow engine
        playing a short one.
        """
        ...

    async def stop(self) -> None:
        """Stop immediately and discard anything queued."""
        ...

    async def aclose(self) -> None:
        """Release the audio device and the engine."""
        ...
