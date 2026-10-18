"""
discussion-helper — a spoken conversation, with the floor handled properly.

Module summary
--------------
``vocal-helper`` hears. ``speaker-helper`` speaks. A language model answers.
None of them knows whose turn it is, and that is what this package is: the
loop between the three, and the three questions it has to get right.

**Who holds the floor.** Exactly one party at a time. Most voice-agent
failures are two parties believing they hold it — the agent talking over the
user is the obvious one, both waiting in silence is the one nobody notices.

**What happens when the user cuts in.** Under 150 ms from their first syllable
to the agent's silence, and the audio already synthesised and not yet heard is
*discarded*, not drained. Playing it out because it exists is what makes an
agent feel deaf.

**Where the latency went.** A single total says a conversation feels slow and
nothing about why. Every exchange reports its breakdown — endpointing,
recognition, first token, first audio — and names the stage to fix.

The three parts are protocols, so the whole loop runs in a test with no
microphone, no model and no sound card. That is not tidiness: interruption
handling is exactly the behaviour a real room makes impossible to assert.

Usage example
-------------
>>> import asyncio
>>> from discussion_helper import Discussion
>>> from discussion_helper.testing import ScriptedListener, EchoResponder, SilentVoice
>>> talk = Discussion(ScriptedListener(["bonjour"]), EchoResponder(), SilentVoice())
>>> [u.text for u in asyncio.run(talk.run()).utterances]
['bonjour', 'bonjour']

See ``KNOWLEDGE.md`` for the design notes: the latency budget, turn detection,
barge-in, and why acoustic echo is the problem that decides your defaults.

Author
------
Warith HARCHAOUI — https://linkedin.com/in/warith-harchaoui
"""

from __future__ import annotations

__version__ = "0.1.0"
__author__ = "Warith HARCHAOUI"
__email__ = "warithmetics@deraison.ai"
__license__ = "BSD-3-Clause"

from discussion_helper.discussion import Discussion, Policy
from discussion_helper.parts import Listener, Responder, Voice
from discussion_helper.types import (
    Conversation,
    Floor,
    Speaker,
    TurnTiming,
    Utterance,
)

__all__ = [
    # the loop
    "Discussion",
    "Policy",
    # the parts it is written against
    "Listener",
    "Responder",
    "Voice",
    # what crosses the boundaries
    "Conversation",
    "Floor",
    "Speaker",
    "TurnTiming",
    "Utterance",
    "__version__",
]
