# Discussion Helper

[🇫🇷](https://github.com/warith-harchaoui/discussion-helper/blob/main/LISEZMOI.md) · [🇬🇧](https://github.com/warith-harchaoui/discussion-helper/blob/main/README.md)

[![License: BSD-3-Clause](https://img.shields.io/badge/License-BSD%203--Clause-blue.svg)](https://github.com/warith-harchaoui/discussion-helper/blob/main/LICENSE) [![Python](https://img.shields.io/badge/python-3.10%E2%80%933.13-blue.svg)](#) [![Local-first](https://img.shields.io/badge/privacy-local--first-2f6f5e.svg)](#the-promise)

`Discussion Helper` belongs to a collection of libraries called `AI Helpers`
developed for building Artificial Intelligence.

[🌍 AI Helpers](https://deraison.ai/ai-helpers)

**Hold a spoken conversation at the microphone: listen, answer, speak — and
stop the moment the user cuts in.**

`vocal-helper` hears. `speaker-helper` speaks. A local language model answers,
chosen by `best-engine-ai-helper`, which sizes the machine — no model name is
written down here. None of the three knows whose turn it is. This package is
the loop between them, and the three questions it has to get right:

- **Who holds the floor.** Exactly one party at a time. Most voice-agent
  failures are two parties believing they hold it — the agent talking over the
  user is the obvious one; both waiting in silence is the one nobody notices
  until a recording is played back.
- **What happens when the user cuts in.** Under **150 ms** from their first
  syllable to the agent's silence, and the audio already synthesised and not
  yet heard is *discarded*, not drained. Playing it out because it exists is
  what makes an agent feel deaf.
- **Where the latency went.** A single total says a conversation feels slow
  and nothing about why. Every exchange reports its breakdown — endpointing,
  recognition, first token, first audio — and names the stage to fix.

## The Promise

**Local-first.** The microphone, the recogniser, the model and the voice all
run on your machine. No audio leaves it, no account, no per-minute billing.

**Testable without a room.** The three parts are protocols, so the whole loop
runs in CI with no microphone, no model and no sound card. That is not
tidiness: interruption handling is exactly the behaviour a real room makes
impossible to assert. You cannot *hear* whether the queued audio was
discarded.

## How it works

![How discussion-helper works: the loop that listens, answers and speaks — and stops the moment you cut in](https://raw.githubusercontent.com/warith-harchaoui/discussion-helper/main/assets/diagrams/how-it-works.png)

## Installation

```bash
pip install 'discussion-helper[all]'      # hearing, thinking, speaking, playing
speaker-helper install-voice --engine kokoro   # the voice's weights, once
```

On Linux and macOS the voice also needs `espeak-ng`
(`apt install espeak-ng`, `brew install espeak-ng`).

Each half installs on its own if you only want some of it: `[listen]`,
`[think]`, `[speak]`, `[play]`.

## Quick start

The loop runs on a bare install — no model, no microphone, no sound card. The
three parts are protocols and the package ships a known-good fake of each, so
there is a conversation to look at before any weights are downloaded:

```bash
pip install discussion-helper
discussion-helper rehearse 'bonjour' 'ça va ?'
```

```
 you: bonjour
  it: bonjour bonjour (2) bonjour (3)
 you: ça va ?
  it: ça va ? ça va ? (2) ça va ? (3)

turn 1: 0 ms to first audio, slowest stage think
turn 2: 0 ms to first audio, slowest stage think
```

Two exchanges, the floor changing hands four times, and the latency reported
per turn with the stage to fix named. Then, with the extras above installed,
the same loop at the microphone:

```bash
discussion-helper talk
```

Speak, and it answers. Cut in, and it stops. `--json` replaces the prose with
the transcript and the latency breakdown as machine-readable JSON, and
[As a library](#as-a-library) is the same conversation driven from Python.

## Is it the loop or is it the room?

That is the first question a misbehaving voice agent raises, and without
something like `rehearse` the only way to ask it is to change one thing and
listen again. It runs the **same loop** with the microphone, model and speaker
replaced by fakes, so it can also stage the interruption for you:

```bash
# stage an interruption a quarter of a second into the reply
discussion-helper rehearse "dis-moi tout" --sentences 6 --interrupt-after 0.25 --grace 0
```

```
 you: dis-moi tout
  it: dis-moi tout dis-moi tout (2) (cut off)

turn 1: 0 ms to first audio, slowest stage think
```

`(cut off)` is the loop saying that the sentence it was cut on does **not**
count as said. If all six appeared, the queue would be draining instead of
being discarded — which is exactly what makes an agent feel deaf.

## Talk to it

```bash
discussion-helper talk --voice ff_siwis
discussion-helper talk --no-barge-in        # strict half-duplex
discussion-helper talk --json               # transcript + latency breakdown
```

## As a library

```python
import asyncio
from discussion_helper import Discussion, Policy
from discussion_helper.adapters import VocalListener, LocalResponder, SpeakerVoice


async def main():
    async with Discussion(
        VocalListener(language="fr"),
        LocalResponder(),
        SpeakerVoice(voice="ff_siwis"),
        Policy(barge_in_grace_s=0.35),
    ) as talk:
        conversation = await talk.run()

    for turn in conversation.utterances:
        print(turn.speaker, turn.text)
    print(conversation.timings[0].as_dict())


asyncio.run(main())
```

Bring your own parts by implementing `Listener`, `Responder` or `Voice` — a
cloud recogniser, a scripted model for a demo, a phone line instead of a
speaker. Each is one class, and the loop does not change.

## Over HTTP, and over a socket

A conversation does not fit a request — it has no single answer and lasts
minutes — so the HTTP surface is a session you create, a stream you follow and
a button you press:

```bash
pip install 'discussion-helper[server]'
discussion-helper-mcp            # or: uvicorn discussion_helper.api:build --factory
```

| Route | What it is |
|---|---|
| `GET /health` | whether each of the three parts could run here, and what is missing |
| `POST /sessions` | start one; returns an id immediately |
| `GET /sessions` | every conversation this process is holding |
| `GET /sessions/{id}` | the transcript, the floor and the timings, as they stand |
| `GET /sessions/{id}/events` | follow it — floor, turns, latency, as they happen |
| `POST /sessions/{id}/say` | push a user turn in as text, for a remote session |
| `POST /sessions/{id}/interrupt` | stop the agent, through the same path a barge-in uses |
| `DELETE /sessions/{id}` | end it, and get what was said |
| `WS /sessions/{id}/audio` | **the microphone at the other end** |
| `POST /turn` | one exchange, no audio — the shape an agent can use |
| `/mcp` | the same routes as agent tools |

The WebSocket carries real audio both ways: the client sends PCM and control
frames, the server sends events and WAV. That is how every hosted voice agent
works, and it means the browser can hold the microphone while this end holds
the model. Two duties fall on the client and are not optional — send
`{"type":"speaking"}` on the **first syllable** so a barge-in can travel, and
**drop** buffered audio on `{"kind":"stop"}`. A client that plays its buffer
out reproduces, at the far end, exactly the deafness that stopping it here
was meant to prevent.

### In a container

```bash
docker compose up -d
curl -s localhost:8090/health
```

The image serves the **remote** transport — the caller owns the microphone and
sends frames — and that is the honest half of this package a container can
run. It does **not** open a microphone of its own: `--transport local` reads
the machine's sound card, and a container has none. Passing one in is
`--device /dev/snd` on Linux and impossible on macOS, which is a per-machine
arrangement rather than an image, so the `listen` extra is deliberately left
out and the refusal happens at install time instead of at the first call.

The port is bound to the loopback, and the reason is in `discussion-helper-mcp
--help` as well: this server can open a microphone. One worker, also
deliberately — the voice backend loads its ONNX graph once per process and a
second worker pays for its own copy, and sessions are stateful besides.

## Read this before tuning anything

**[KNOWLEDGE.md](https://github.com/warith-harchaoui/discussion-helper/blob/main/KNOWLEDGE.md)** is the design notebook: the 800 ms latency
budget and where it actually goes, why a silence threshold is not turn
detection, the two mistakes everyone makes with barge-in, why replies are
chunked at sentences and not tokens, and why acoustic echo is the problem that
decides your defaults.

The short version: a voice agent has about 800 ms before the conversation
feels broken, the largest line in that budget is endpointing rather than the
model, and the agent's own voice reaching its own microphone looks exactly
like the user speaking.

## The rest of the documentation

| File | What is in it |
|---|---|
| **[EXAMPLES.md](https://github.com/warith-harchaoui/discussion-helper/blob/main/EXAMPLES.md)** | A cookbook. Everything up to the section where the real microphone arrives runs on a bare install — no microphone, no model, no sound card — because the parts are protocols with shipped fakes. |
| **[KNOWLEDGE.md](https://github.com/warith-harchaoui/discussion-helper/blob/main/KNOWLEDGE.md)** | The design notebook, above. |
| **[LANDSCAPE.md](https://github.com/warith-harchaoui/discussion-helper/blob/main/LANDSCAPE.md)** / **[PAYSAGE.md](https://github.com/warith-harchaoui/discussion-helper/blob/main/PAYSAGE.md)** | Where this sits against LiveKit Agents, Pipecat, OpenAI's Realtime API and six others, with a positioning map. It scores ⭐ on telephony and scale, which is the honest answer. |
| **[TRIGGERS.md](https://github.com/warith-harchaoui/discussion-helper/blob/main/TRIGGERS.md)** | The exhaustive catalogue of what should, and should not, reach for this helper. Mirrored into the agent skill, with a gate that fails when the two drift apart. |
| **[CHANGELOG.md](https://github.com/warith-harchaoui/discussion-helper/blob/main/CHANGELOG.md)** | What changed, and why. |

## How this differs from its neighbours

| You have | Reach for |
|---|---|
| A recording somebody needs as text | [`vocal-helper`](https://github.com/warith-harchaoui/vocal-helper) |
| Text somebody needs as speech | [`speaker-helper`](https://github.com/warith-harchaoui/speaker-helper) |
| A live camera or microphone as frames | [`capture-helper`](https://github.com/warith-harchaoui/capture-helper) |
| A question a local model should answer | [`best-engine-ai-helper`](https://github.com/warith-harchaoui/best-engine-ai-helper) |
| **A conversation to hold** | this one |

## What is deliberately not here

No wake word, no speaker diarization, no telephony, no acoustic echo
cancellation, and no turn detection — that last one lives in `vocal-helper`,
which ships Silero VAD and a semantic end-of-turn stage. Reimplementing it
here would give it two owners. KNOWLEDGE.md §10 explains each.

## Author

[Warith HARCHAOUI](https://warith-harchaoui.github.io/) —
warithmetics@deraison.ai

## License

BSD-3-Clause. See [LICENSE](https://github.com/warith-harchaoui/discussion-helper/blob/main/LICENSE).
