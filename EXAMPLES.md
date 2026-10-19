# discussion-helper Examples

A cookbook of common uses. Every Python block runs with **nothing installed
beyond the base package** — no microphone, no model, no sound card — because
the parts are protocols and `discussion_helper.testing` ships a known-good fake
of each. Paste any of them into a file and watch it work.

That is not a testing convenience, it is the point. The behaviour hardest to
get right in a voice agent is also the hardest to observe in a room: whether
the audio really stopped, whether what was queued was discarded or quietly
played, whether the floor came back.

- [1. The loop, with nothing behind it](#1-the-loop-with-nothing-behind-it)
- [2. Cut the agent off](#2-cut-the-agent-off)
- [3. Prove the queued audio was discarded](#3-prove-the-queued-audio-was-discarded)
- [4. Read the latency breakdown](#4-read-the-latency-breakdown)
- [5. Cap the reply](#5-cap-the-reply)
- [6. Strict half-duplex](#6-strict-half-duplex)
- [7. The grace period, and echo](#7-the-grace-period-and-echo)
- [8. End on silence](#8-end-on-silence)
- [9. Bring your own part](#9-bring-your-own-part)
- [10. The real thing: microphone, model, voice](#10-the-real-thing-microphone-model-voice)
- [11. Command line](#11-command-line)
- [12. HTTP, and an agent that can interrupt](#12-http-and-an-agent-that-can-interrupt)

## 1. The loop, with nothing behind it

Listen, answer, speak, repeat. `Conversation` comes back carrying what was
said, which floor state it ended on, and the timings.

```python
import asyncio

from discussion_helper import Discussion, Floor
from discussion_helper.testing import EchoResponder, ScriptedListener, SilentVoice


async def main():
    talk = Discussion(ScriptedListener(["bonjour", "ça va ?"]), EchoResponder(), SilentVoice())
    conversation = await talk.run()
    for u in conversation.utterances:
        print(f"{u.speaker}: {u.text}")
    print("ended on:", conversation.floor)


asyncio.run(main())
# user: bonjour
# agent: bonjour
# user: ça va ?
# agent: ça va ?
# ended on: Floor.IDLE
```

`Floor.IDLE` at the end matters more than it looks: an agent still holding the
floor is an agent nobody can answer.

## 2. Cut the agent off

The behaviour the whole package exists for. `interrupt_after_s` stages a
barge-in that far into the agent's reply.

```python
import asyncio

from discussion_helper import Discussion, Policy
from discussion_helper.testing import EchoResponder, ScriptedListener, SilentVoice


async def main():
    conversation = await Discussion(
        ScriptedListener(["bonjour"], interrupt_after_s=0.05),
        EchoResponder(sentences=5),
        SilentVoice(seconds_per_sentence=1.0),
        Policy(barge_in_grace_s=0.0),
    ).run()
    agent = [u for u in conversation.utterances if u.speaker == "agent"][0]
    print("interrupted:", agent.interrupted)
    print("interruption rate:", conversation.interruption_rate)


asyncio.run(main())
# interrupted: True
# interruption rate: 1.0
```

`barge_in_grace_s=0.0` is only right in a test. See example 7.

The **interruption rate** is a diagnostic worth watching in production: a high
one usually means answers that run too long, which a transcript will never
show you, because the text of an interrupted answer looks complete.

## 3. Prove the queued audio was discarded

A reply is synthesised ahead of playback, so an interruption always finds audio
made and not yet heard. Playing it out — because it exists, because it was paid
for — is what makes an agent feel deaf.

```python
import asyncio

from discussion_helper import Discussion, Policy
from discussion_helper.testing import EchoResponder, ScriptedListener, SilentVoice


async def main():
    voice = SilentVoice(seconds_per_sentence=1.0)
    await Discussion(
        ScriptedListener(["bonjour"], interrupt_after_s=0.05),
        EchoResponder(sentences=5),
        voice,
        Policy(barge_in_grace_s=0.0),
    ).run()
    print("started:", len(voice.spoken))  # of 5
    print("completed:", voice.completed)  # the cut one does not count
    print("stops:", voice.stops)


asyncio.run(main())
# started: 1
# completed: []
# stops: 1
```

Two assertions in one: the sentences after the interruption never start, and
the sentence that was cut is **not** counted as said. If `completed` held the
cut sentence, every transcript would claim the user heard something they did
not.

## 4. Read the latency breakdown

Per exchange, not a total — a single number says a conversation feels slow and
nothing about why.

```python
import asyncio

from discussion_helper import Discussion
from discussion_helper.testing import EchoResponder, ScriptedListener, SilentVoice


async def main():
    conversation = await Discussion(
        ScriptedListener(["bonjour"]),
        EchoResponder(delay_s=0.05),
        SilentVoice(seconds_per_sentence=0.40, first_audio_s=0.02),
    ).run()
    timing = conversation.timings[0]
    print("slowest stage:", timing.slowest_stage)
    print("to first audio:", round(timing.to_first_audio_s, 3), "s")
    print("speak:", round(timing.speak_s, 3), "s")
    print(timing.as_dict())


asyncio.run(main())
# slowest stage: think
# to first audio: 0.072 s
# speak: 0.02 s
# {'endpoint_s': 0.0, 'recognise_s': 0.0, 'think_s': 0.052, 'speak_s': 0.02,
#  'to_first_audio_s': 0.072, 'slowest_stage': 'think'}
```

These are measured durations, so the last digit moves between runs — `think_s`
lands a hair above the 0.05 the fake was asked to spend. What is stable is the
shape: which stage is slowest, and the split below.

Note `speak_s` is **0.02** and not 0.40: it measures the silence before the
sound, not the playback. Lump them together and a fast engine reading a long
sentence looks slower than a slow engine reading a short one — the one
measurement mistake that makes a latency budget useless.

`as_dict()` is the same six fields the CLI's `--json` and the HTTP event
stream report, so a reader gets the same breakdown whichever door they came
through.

## 5. Cap the reply

An agent that talks for ninety seconds is one the user *has* to interrupt. The
cheapest latency fix is usually a shorter answer, not a faster model.

```python
import asyncio

from discussion_helper import Discussion, Policy
from discussion_helper.testing import EchoResponder, ScriptedListener, SilentVoice


async def main():
    voice = SilentVoice()
    await Discussion(
        ScriptedListener(["bonjour"]),
        EchoResponder(sentences=10),
        voice,
        Policy(max_reply_sentences=2),
    ).run()
    print("sentences spoken:", len(voice.spoken))


asyncio.run(main())
# sentences spoken: 2
```

## 6. Strict half-duplex

Rude, and right on a speakerphone with no acoustic echo cancellation. Without
it, the agent's own voice reaching its own microphone looks exactly like the
user speaking, so every reply interrupts itself after one syllable.

```python
import asyncio

from discussion_helper import Discussion, Policy
from discussion_helper.testing import EchoResponder, ScriptedListener, SilentVoice


async def main():
    voice = SilentVoice(seconds_per_sentence=0.02)
    conversation = await Discussion(
        ScriptedListener(["bonjour"], interrupt_after_s=0.0),
        EchoResponder(sentences=3),
        voice,
        Policy(allow_barge_in=False),
    ).run()
    agent = [u for u in conversation.utterances if u.speaker == "agent"][0]
    print("interrupted:", agent.interrupted)
    print("completed:", len(voice.completed))


asyncio.run(main())
# interrupted: False
# completed: 3
```

## 7. The grace period, and echo

The middle ground, and the default. An interruption arriving inside the grace
window is treated as the agent's own first syllable rather than the user.

```python
import asyncio

from discussion_helper import Discussion, Policy
from discussion_helper.testing import EchoResponder, ScriptedListener, SilentVoice


async def main():
    conversation = await Discussion(
        ScriptedListener(["bonjour"], interrupt_after_s=0.0),
        EchoResponder(sentences=3),
        SilentVoice(seconds_per_sentence=0.05),
        Policy(barge_in_grace_s=0.5),
    ).run()
    agent = [u for u in conversation.utterances if u.speaker == "agent"][0]
    print("interrupted:", agent.interrupted)


asyncio.run(main())
# interrupted: False
```

Crucially the watcher keeps watching rather than returning, or one echo would
disable barge-in for the rest of the turn. Raise it on a speakerphone, lower it
on a headset; 350 ms is the default. It is a trade, not a fix — echo
cancellation is the real answer.

## 8. End on silence

An open microphone in an empty room is an ordinary ending, not an error.

```python
import asyncio

from discussion_helper import Discussion, Policy
from discussion_helper.testing import EchoResponder, ScriptedListener, SilentVoice


async def main():
    conversation = await Discussion(
        ScriptedListener(["bonjour"], pace_s=5.0),
        EchoResponder(),
        SilentVoice(),
        Policy(silence_timeout_s=0.05),
    ).run()
    print("utterances:", conversation.utterances)


asyncio.run(main())
# utterances: []
```

Use `async with` when you want the three parts released on the way out — a
microphone left open outlives the program that opened it:

```python
import asyncio

from discussion_helper import Discussion
from discussion_helper.testing import EchoResponder, ScriptedListener, SilentVoice


async def main():
    listener, responder, voice = ScriptedListener([]), EchoResponder(), SilentVoice()
    async with Discussion(listener, responder, voice):
        pass
    print(listener.closed, responder.closed, voice.closed)


asyncio.run(main())
# True True True
```

## 9. Bring your own part

`Listener`, `Responder` and `Voice` are **structural** protocols — no base
class to inherit, no registration. A cloud recogniser, a scripted model for a
demo, a phone line instead of a speaker: each is one class, and the loop does
not change.

```python
import asyncio
from collections.abc import AsyncIterator

from discussion_helper import Discussion, Responder
from discussion_helper.testing import ScriptedListener, SilentVoice


class RuleBasedResponder:
    """Answers without a model at all."""

    def __init__(self) -> None:
        self.closed = False

    async def reply(self, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        heard = messages[-1]["content"].lower()
        yield "Bonsoir." if "soir" in heard else "Bonjour."

    async def stop(self) -> None:
        pass

    async def aclose(self) -> None:
        self.closed = True


async def main():
    print("conforms:", isinstance(RuleBasedResponder(), Responder))
    voice = SilentVoice()
    await Discussion(ScriptedListener(["bonsoir"]), RuleBasedResponder(), voice).run()
    print(voice.spoken)


asyncio.run(main())
# conforms: True
# ['Bonsoir.']
```

The one method to get right is `Voice.stop()`: it must **discard** what was
synthesised and not yet heard, never drain it. Example 3 is the test for that.

## 10. The real thing: microphone, model, voice

Needs the hardware and the siblings, so this one does not run on a bare
install:

```bash
pip install 'discussion-helper[all]'
```

```python
import asyncio

from discussion_helper import Discussion, Policy
from discussion_helper.adapters import LocalResponder, SpeakerVoice, VocalListener


async def main():
    async with Discussion(
        VocalListener(language="fr"),
        LocalResponder(),
        SpeakerVoice(voice="ff_siwis", language="fr"),
        Policy(barge_in_grace_s=0.35, max_reply_sentences=3),
    ) as talk:
        conversation = await talk.run()
    print(conversation.interruption_rate)


asyncio.run(main())
```

Each adapter imports its sibling **inside** the method that needs it, so a base
install carries the loop and nothing else — and a missing extra raises a
message naming the install command rather than an `ImportError` about a package
you have never heard of.

`VocalListener` builds a real `vocal_helper.Pipeline` (VAD, then recognition)
for the transcript, and reads speech onset off the raw frames separately. Those
are two different questions with two different deadlines: a barge-in that
waited for a transcript would arrive a second late, by which time the agent has
been talking over somebody for a whole sentence. `onset_rms` tunes the onset
detector for a noisy room.

## 11. Command line

```bash
# The loop, with no hardware. Start here.
discussion-helper rehearse 'bonjour' 'ça va ?'

# Stage an interruption 200 ms into a five-sentence reply.
discussion-helper rehearse 'bonjour' --sentences 5 --interrupt-after 0.2

# The microphone.
discussion-helper talk --voice ff_siwis --language fr
discussion-helper talk --no-barge-in          # strict half-duplex
discussion-helper talk --json                 # machine-readable
```

`discussion-helper-argparse` is the same commands over the standard library
alone. See `skills/discussion-helper/references/cli-reference.md`.

## 12. HTTP, and an agent that can interrupt

```bash
pip install 'discussion-helper[server]'
python -m discussion_helper.api        # 127.0.0.1:8000, docs at /docs
```

```bash
curl -X POST localhost:8000/sessions
curl localhost:8000/sessions/{id}/events      # transcript, floor and timings as they grow
curl -X POST localhost:8000/sessions/{id}/interrupt
curl -X DELETE localhost:8000/sessions/{id}
```

`POST /turn` takes a single turn as text, which is the only way to ask the
conversation's own model something directly.

With `[mcp]` installed, `discussion-helper-mcp` republishes those same routes
as agent tools — one implementation, so the two surfaces cannot drift into
disagreeing. An agent cannot *hold* a conversation (it has no ears), but it can
start one, watch it, take a turn, and **interrupt** it. That last one is why
the surface exists: "stop talking" is a thing people say to an agent, and
routing it through the same `Voice.stop` the microphone's barge-in uses means
it stops the same way — discarding what was synthesised rather than letting it
drain.
