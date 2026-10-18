# Discussion Helper

[🇫🇷](https://github.com/warith-harchaoui/discussion-helper/blob/main/LISEZMOI.md) · [🇬🇧](https://github.com/warith-harchaoui/discussion-helper/blob/main/README.md)

[![License: BSD-3-Clause](https://img.shields.io/badge/License-BSD%203--Clause-blue.svg)](LICENSE) [![Python](https://img.shields.io/badge/python-3.10%E2%80%933.13-blue.svg)](#) [![Local-first](https://img.shields.io/badge/privacy-local--first-2f6f5e.svg)](#the-promise)

`Discussion Helper` belongs to a collection of libraries called `AI Helpers`
developed for building Artificial Intelligence.

[🌍 AI Helpers](https://deraison.ai/ai-helpers)

**Hold a spoken conversation at the microphone: listen, answer, speak — and
stop the moment the user cuts in.**

`vocal-helper` hears. `speaker-helper` speaks. A local language model answers.
None of them knows whose turn it is. This package is the loop between the
three, and the three questions it has to get right:

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

## The promise

**Local-first.** The microphone, the recogniser, the model and the voice all
run on your machine. No audio leaves it, no account, no per-minute billing.

**Testable without a room.** The three parts are protocols, so the whole loop
runs in CI with no microphone, no model and no sound card. That is not
tidiness: interruption handling is exactly the behaviour a real room makes
impossible to assert. You cannot *hear* whether the queued audio was
discarded.

## Install

```bash
pip install 'discussion-helper[all]'      # hearing, thinking, speaking, playing
speaker-helper install-voice --engine kokoro   # the voice's weights, once
```

On Linux and macOS the voice also needs `espeak-ng`
(`apt install espeak-ng`, `brew install espeak-ng`).

Each half installs on its own if you only want some of it: `[listen]`,
`[think]`, `[speak]`, `[play]`.

## Try it with nothing installed

```bash
pip install discussion-helper
discussion-helper rehearse "bonjour" "comment ça va ?"
```

`rehearse` runs the **same loop** with the microphone, model and speaker
replaced by fakes. When a voice agent misbehaves the first question is always
"is it the loop or is it the room", and this answers it in a second:

```bash
# stage an interruption a quarter of a second into the reply
discussion-helper rehearse "dis-moi tout" --sentences 6 --interrupt-after 0.25 --grace 0
```

```
 you: dis-moi tout
  it: dis-moi tout dis-moi tout (2) (cut off)
```

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

## Read this before tuning anything

**[KNOWLEDGE.md](KNOWLEDGE.md)** is the design notebook: the 800 ms latency
budget and where it actually goes, why a silence threshold is not turn
detection, the two mistakes everyone makes with barge-in, why replies are
chunked at sentences and not tokens, and why acoustic echo is the problem that
decides your defaults.

The short version: a voice agent has about 800 ms before the conversation
feels broken, the largest line in that budget is endpointing rather than the
model, and the agent's own voice reaching its own microphone looks exactly
like the user speaking.

## How this differs from its neighbours

| You have | Reach for |
|---|---|
| A recording somebody needs as text | [`vocal-helper`](https://github.com/warith-harchaoui/vocal-helper) |
| Text somebody needs as speech | [`speaker-helper`](https://github.com/warith-harchaoui/speaker-helper) |
| A live camera or microphone as frames | [`capture-helper`](https://github.com/warith-harchaoui/capture-helper) |
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

BSD-3-Clause. See [LICENSE](LICENSE).
