"""
What crosses the boundaries of a spoken conversation.

Module summary
--------------
A discussion is not a transcript and not a playlist. It is a sequence of
*turns*, each held by exactly one party, with a measurable gap between the
moment one ends and the moment the next is audible. The types here name those
three things — the turn, the floor, and the gap — because every design
question in this package turns out to be about one of them.

Nothing here imports a model, a microphone or a network. The whole state of a
conversation is plain data, which is what lets the loop be tested with no
hardware at all.

Author
------
Warith HARCHAOUI — https://linkedin.com/in/warith-harchaoui
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal

#: Who said a thing. ``"user"`` and ``"agent"`` rather than ``"human"`` and
#: ``"assistant"``: the words a speech system needs are about *who holds the
#: floor*, not about what either party is.
Speaker = Literal["user", "agent"]


class Floor(Enum):
    """Who may speak, right now.

    A spoken conversation has exactly one floor and exactly one holder. Most
    of the failures in a voice agent are two parties believing they hold it:
    the agent talking over the user is the obvious one, and both waiting in
    silence is the one nobody notices until a recording is played back.

    The states are deliberately few. ``THINKING`` is separate from
    ``SPEAKING`` because they are interrupted differently — thinking can be
    abandoned silently, speaking has to be *stopped*, and the audio already
    queued has to be thrown away rather than drained.
    """

    #: Nothing is happening. The loop has not started or has been stopped.
    IDLE = "idle"
    #: The user has the floor. The microphone is open and nothing is playing.
    LISTENING = "listening"
    #: The user has finished and the answer is being produced. Silence, and
    #: the part of the budget the listener cannot shorten.
    THINKING = "thinking"
    #: The agent has the floor. Audio is playing and a barge-in may arrive.
    SPEAKING = "speaking"


@dataclass(frozen=True)
class Utterance:
    """One thing somebody said, with when it was said.

    Parameters
    ----------
    speaker : str
        ``"user"`` or ``"agent"``.
    text : str
        What was said. For the user this is the transcript and may be wrong;
        for the agent it is exactly what was synthesised.
    started_s, ended_s : float
        Seconds since the conversation began. For the user these bound the
        speech itself, not the recognition — the gap between the two is the
        single largest line in the latency budget, and conflating them would
        hide it.
    interrupted : bool
        Set on an agent turn the user cut into. Worth keeping: an agent that
        is interrupted often is usually one that answers at too great a
        length, and that is invisible in a transcript.
    """

    speaker: Speaker
    text: str
    started_s: float = 0.0
    ended_s: float = 0.0
    interrupted: bool = False

    @property
    def duration_s(self) -> float:
        """How long the speaking took."""
        return max(0.0, self.ended_s - self.started_s)


@dataclass(frozen=True)
class SpokenSentence:
    """What came of asking the voice to say one sentence.

    Two durations, because they answer different questions and the budget
    needs the first one. ``first_audio_s`` is the silence before the sound —
    the part of the gap the listener feels. ``played_s`` is how much audio
    they then heard, which says nothing about latency and everything about
    whether an interruption landed.

    Collapsing the two into "how long did speaking take" is the measurement
    mistake this type exists to prevent: it makes a fast engine playing a long
    sentence look slower than a slow engine playing a short one.

    Parameters
    ----------
    text : str
        The sentence, as it was handed to the engine.
    first_audio_s : float
        From the call to the first sample leaving the speaker.
    played_s : float
        Seconds of audio actually heard. Less than the sentence's full length
        when it was cut.
    cut : bool
        Whether the sentence was stopped before it finished.
    """

    text: str
    first_audio_s: float = 0.0
    played_s: float = 0.0
    cut: bool = False


@dataclass
class TurnTiming:
    """Where one turn's latency went.

    The number a listener feels is ``to_first_audio_s``: the silence between
    their last word and the agent's first sound. Everything else here is the
    breakdown that says which stage to fix, and the breakdown is the point —
    a single total tells you a conversation feels slow and nothing about why.

    Typical shares, from the published budgets this package was built
    against: endpointing 150–350 ms, recognition 100–150 ms, the language
    model's first token 150–400 ms, synthesis to first audio 100–200 ms. Under
    800 ms end to end is the usual target; a well-tuned local pipeline lands
    near 600.

    Parameters
    ----------
    endpoint_s : float
        From the user's last word to the decision that they had finished.
        The largest line, and the one a semantic turn detector shortens.
    recognise_s : float
        Finishing the transcript once the turn is closed.
    think_s : float
        To the first token of the answer. Not the whole answer: a reply is
        spoken sentence by sentence, so only the first one is on this path.
    speak_s : float
        From that first sentence to the first sample leaving the speaker.
    """

    endpoint_s: float = 0.0
    recognise_s: float = 0.0
    think_s: float = 0.0
    speak_s: float = 0.0

    @property
    def to_first_audio_s(self) -> float:
        """The silence the user actually sits through."""
        return self.endpoint_s + self.recognise_s + self.think_s + self.speak_s

    @property
    def slowest_stage(self) -> str:
        """Which stage to fix first. Naming it is most of fixing it."""
        stages = {
            "endpoint": self.endpoint_s,
            "recognise": self.recognise_s,
            "think": self.think_s,
            "speak": self.speak_s,
        }
        return max(stages, key=lambda name: stages[name])

    def as_dict(self) -> dict[str, float | str]:
        """The breakdown plus its total, for a log line or a report.

        ``slowest_stage`` belongs in here rather than being bolted on by each
        caller. It was not, and the three doors disagreed: the text CLI named
        the stage to fix, the HTTP event stream merged the key in by hand, and
        the CLI's own ``--json`` — the one a script reads — omitted it. One
        serialisation, so a reader gets the same breakdown whichever door they
        came through.
        """
        return {
            "endpoint_s": round(self.endpoint_s, 3),
            "recognise_s": round(self.recognise_s, 3),
            "think_s": round(self.think_s, 3),
            "speak_s": round(self.speak_s, 3),
            "to_first_audio_s": round(self.to_first_audio_s, 3),
            "slowest_stage": self.slowest_stage,
        }


@dataclass
class Conversation:
    """Everything said so far, and whose turn it is.

    The history is what the language model is shown, so it is kept as
    utterances rather than as a rendered prompt: a prompt is one consumer's
    view of this, and building it here would make every other consumer read
    somebody else's formatting.
    """

    utterances: list[Utterance] = field(default_factory=list)
    floor: Floor = Floor.IDLE
    timings: list[TurnTiming] = field(default_factory=list)

    def add(self, utterance: Utterance) -> None:
        """Append a turn."""
        self.utterances.append(utterance)

    @property
    def last_user_text(self) -> str:
        """What the user most recently said, or ``""``."""
        for utterance in reversed(self.utterances):
            if utterance.speaker == "user":
                return utterance.text
        return ""

    @property
    def interruption_rate(self) -> float:
        """Share of agent turns the user cut into.

        A diagnostic, not a score. A high rate usually means the agent
        answers at too great a length — which a transcript will not show,
        because the text of an interrupted answer looks complete.
        """
        agent_turns = [u for u in self.utterances if u.speaker == "agent"]
        if not agent_turns:
            return 0.0
        return sum(1 for u in agent_turns if u.interrupted) / len(agent_turns)

    def as_messages(self) -> list[dict[str, str]]:
        """The history in the shape chat models expect."""
        return [
            {"role": "user" if u.speaker == "user" else "assistant", "content": u.text}
            for u in self.utterances
            if u.text.strip()
        ]
