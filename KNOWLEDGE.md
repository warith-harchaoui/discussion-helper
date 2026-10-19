# Holding a spoken conversation: what actually decides whether it works

This is the design notebook for `discussion-helper`. It is not a tutorial and
not an API reference — it is the set of things that are true about spoken
conversation whether or not your code acknowledges them, written down so the
next person does not have to rediscover them in a room with a microphone.

Everything here is either measured, cited, or marked as a judgement call.
Where the field disagrees, the disagreement is stated rather than resolved.

---

## 1. The one-paragraph version

A voice agent has roughly **800 milliseconds** between the user's last word
and its own first sound before the conversation feels broken. That budget is
spent in four places, and only one of them is the part people optimise. A
well-tuned local pipeline lands near **600 ms**; under **700 ms** is a good
target to build toward. Separately, when the user interrupts, the agent must be
silent within about **150 ms** — and the audio it had already made must be
*thrown away*, not played out. Almost every bad voice agent is bad at one of
those two numbers.

---

## 2. The latency budget

### Where the 800 ms goes

| Stage | Typical | What it is |
|---|---|---|
| **Endpointing** | 150–350 ms | Deciding the user has *finished*, not just paused |
| **Recognition** | 100–150 ms | Finalising the transcript once the turn is closed |
| **First token** | 150–400 ms | The language model producing the start of an answer |
| **First audio** | 100–200 ms | Synthesising the first sentence to the first sample |

Two things follow from this table, and both are counter-intuitive.

**The largest line is not the model.** Endpointing is, and it is the one most
teams never look at because it has no API bill attached. A rigid 500 ms
silence threshold spends half the budget before anything has been asked.

**Sequential thinking is the wrong frame.** "How long until everything is
done" is not what a conversation measures. It measures *when the first sound
comes out*. Stages that overlap — the model still generating while the first
sentence is already being spoken — recover most of the budget without making
any single stage faster. Pipelines that overshoot at 1,180 ms land under 800
by overlapping alone.

### Measured on this stack, not quoted

Everything above is from published work. These are from this machine, a
laptop running Ollama with `gemma3:12b`, and they changed the design:

| What | Cold | Warm |
|---|---|---|
| First token, streamed | 4.78 s | **0.25 s** |
| Whole answer, `chat()` | 4.53 s | — |
| First *sentence*, through the responder | — | **1.03 s** |
| Content-safety scan alone | 4.45 s | 0.16 s |

Two things fall out of that table.

**Streaming is not a refinement here, it is the difference between a
conversation and a wait.** A whole answer costs seconds; the first sentence
costs one. The sentence can be spoken while the rest is still being written,
so only its share lands in the budget.

**The cold column is a first-call cost, and it lands in the worst possible
place.** 4.8 s of it is the safety classifier loading, once per process.
Unwarmed, the user pays it on their *first question* — the one turn where
somebody is deciding whether this thing works. So the loop warms every part
that offers a `warmup()` before it opens the microphone, and by the time
anybody speaks the cost is gone. See `parts.Warmable`.

### What this package measures

Every exchange returns a `TurnTiming` with the four stages split out and a
`slowest_stage` property, because a single total tells you a conversation
feels slow and nothing about why.

The split that matters most, and the one easiest to get wrong: **time to first
audio is not how long speaking took.** A fast engine playing a long sentence
would otherwise look slower than a slow engine playing a short one. Only the
voice knows when sound actually left, so `Voice.speak` reports both numbers
(`SpokenSentence.first_audio_s` and `played_s`) rather than one.

---

## 3. Turn detection: the hardest part, and the least discussed

### Why a silence threshold is not enough

The naive endpoint is "500 ms of silence means they stopped". It is wrong in
both directions, and both failures are bad:

- **Too eager.** A speaker who takes a 350 ms breath mid-sentence gets cut
  into two turns. The recogniser sees two fragments, the model answers half a
  question, and the user has to start again.
- **Too patient.** Every turn pays the full threshold, and the conversation
  acquires a uniform half-second of dead air that nobody can point at.

Measured on the AMI corpus, roughly **15 % of utterances are under 400 ms** —
mostly back-channels ("mm", "oui") and breaths, not finished turns. A
threshold cannot tell those apart, because the difference is not in the
silence. It is in the words.

### The 2026 stack

The current answer is not one model but a layered decision:

1. **Voice activity detection** — Silero VAD is the near-universal default:
   it scores a 30 ms window in under a millisecond on a single CPU thread. It
   answers "is this speech or not", and nothing more.
2. **Semantic end-of-turn** — a small model (LiveKit's `turn-detector`
   fine-tunes Qwen2.5-0.5B; Pipecat ships Smart Turn) scores a *partial
   transcript* for whether it looks like a completed thought, in about 10 ms.
   LiveKit reports a **39 % reduction in false-positive interruptions** when
   this is fused with VAD.
3. **Recogniser hints** — some streaming recognisers now fold end-of-turn into
   recognition itself and emit turn-complete transcripts directly.
4. **A commit delay** — a short, configurable wait after all of the above,
   because being 100 ms late is much cheaper than being wrong.

Reported operating points for semantic endpointing: trigger latency 60–120 ms
at roughly **F1 0.92**, at the cost of running another model.

### What this package does

Nothing. Deliberately. `vocal-helper` already ships `vad.py` (Silero) and
`eot.py` (semantic end-of-turn, modelled on LiveKit's work, with merge-and-
re-evaluate when a turn looks incomplete). Reimplementing any of it here would
give it two owners and let the two drift. The `Listener` protocol is the seam:
it yields *completed* turns, and whatever decided they were complete is
somebody else's business.

---

## 4. Barge-in: the feature that makes an agent feel alive or deaf

### The bar

**Under 150 ms** from the user's first syllable to the agent's silence. Past
that, the agent is audibly talking over somebody.

### The mistake everyone makes once

A reply is synthesised ahead of playback — that is the whole point of
streaming it. So at the moment of an interruption there is always audio that
has been made and not yet heard.

Playing it out is the mistake. It is tempting (it exists, it was paid for, it
is only another second) and it is exactly what makes an agent feel deaf: the
user speaks, and the machine keeps talking for a sentence before noticing.
**Discard, do not drain.**

In this package that is `Voice.stop()`, and the test that holds it asserts two
things rather than one: the sentence that was cut must not be counted as said,
and the sentences after it must never start.

### The second mistake: interrupting yourself

The agent's own voice reaching its own microphone looks *exactly* like the
user speaking — same loudness profile, same onset, same everything a VAD
measures. On a laptop with open speakers, every reply interrupts itself after
one syllable.

There are three honest answers and one dishonest one:

| Answer | Cost | When |
|---|---|---|
| **Headphones** | Social | The only complete fix. Free, and nobody likes it. |
| **Acoustic echo cancellation** | A dependency and some CPU | The real fix. `speexdsp-python`, `pyaec` (Rust bindings), or an NLMS/RLS adaptive filter. |
| **A grace period** | The opening of a reply cannot be interrupted | What this package does by default: 350 ms after the first sample before a barge-in is believed. |
| ~~Raising the VAD threshold~~ | Quiet users stop being heard at all | Dishonest: it trades a visible failure for an invisible one. |

`Policy.barge_in_grace_s` is the third. It is a trade, it is documented as a
trade, and `allow_barge_in=False` is there for the speakerphone case where
even that is not enough. **Strict half-duplex is rude and sometimes correct.**

---

## 5. Streaming the reply: chunk at sentences, not at tokens

Synthesis models use sentence-level context to shape intonation. Splitting
mid-sentence — at a comma, at a clause, at a token count — routinely produces
flat or oddly stressed audio, because the model never sees where the sentence
was going.

So the unit is **one sentence**: long enough to be read well, short enough
that waiting for it does not dominate the budget. The usual refinement is to
make the *first* chunk deliberately small (one sentence, sometimes one clause)
and let later chunks be longer, because only the first one is on the latency
path.

`speaker-helper` implements exactly this (`chunk_for_streaming`,
`first_chunk_sentences`), which is why the `Responder` protocol here yields
sentences rather than tokens: the seam is placed where the two agree.

---

## 6. The floor: one holder, always

A spoken conversation has exactly one floor. Most voice-agent failures are two
parties believing they hold it:

- both talking — the obvious one;
- **both silent** — the one nobody notices until a recording is played back,
  and the one that makes users hang up.

This package models it as four states, and the smallness is the point:

```
IDLE ──► LISTENING ──► THINKING ──► SPEAKING ──┐
           ▲                                    │
           └────────────────────────────────────┘
                   (or a barge-in, from SPEAKING)
```

`THINKING` is separate from `SPEAKING` because **they are interrupted
differently**. Thinking can be abandoned silently — nobody heard it start.
Speaking has to be *stopped*, and its queued audio discarded. Collapsing the
two states collapses that distinction, and the queue survives the
interruption.

---

## 7. Architecture: why three protocols and not one pipeline

The two reference frameworks both model a voice agent as a pipeline of frame
processors — audio in, through VAD → STT → LLM → TTS, audio out — with
interruption as a cancel signal propagating through it. That is a good design
for a framework that owns every stage.

This package owns none of them. Hearing is `vocal-helper`, speaking is
`speaker-helper`, answering is a language model. What is left when you take
those out is the loop, and the loop is small — a few hundred lines. So the
three are **protocols**, not stages, and the benefits are concrete:

- **The hard part gets tested.** Interruption handling, floor transitions and
  the latency split all run in CI with no microphone, no model and no sound
  card. A test in a real room can assert almost none of it — you cannot hear
  whether the queue was discarded.
- **Parts are swappable.** A cloud recogniser, a scripted model for a demo, a
  phone line instead of a speaker: each is one class.
- **Nothing is reimplemented.** The behaviour the siblings fought for stays
  theirs.

---

## 8. The local-first constraint, and what it costs

Everything here runs on the machine. That is a deliberate constraint, and it
changes the budget in both directions:

**Cheaper:** no network leg (30–80 ms each way, and a tail that is much worse
than its median). No per-call cost, so there is no incentive to batch, and
nothing to stop you running the semantic turn detector on every partial.

**More expensive:** the first token comes from a model sharing your CPU with
the recogniser and the vocoder. Kokoro synthesises at roughly a fifth of real
time on a laptop CPU — comfortable — but it is competing for the same cores.

**The practical consequence:** on a local stack, the stage to watch is the
language model's first token, and the lever that works is a smaller model
rather than a faster one. `best-engine-ai-helper` picks the largest model that
fits the machine's memory, which is the right default for quality and not
always the right one for a conversation.

**And the client has to stream.** It did not, when this package was written —
`best_engine_ai_helper.llm.chat` returned a finished string — which put the
*whole* generation inside the 800 ms budget rather than the first sentence's
share. `chat_stream` was added to that package rather than worked around
here: every model call in this suite routes through one function, and a second
path reaching for Ollama directly would be a second place to fix. It speaks
Ollama only, and refuses other backends rather than silently returning a whole
answer — a "stream" that does not stream makes a caller's latency measurement
lie about its own mode.

One honest cost comes with it. `chat` scans its reply for content-policy
problems before returning; a stream cannot, because seeing the text as it
arrives is the point. The scan therefore runs when the stream ends: a caller
that buffers is protected exactly as before, a caller that *speaks* each chunk
has already said it. There is no version of this that is both streaming and
pre-scanned.

---

## 9. Things that look like bugs and are not

**The agent answers a sentence the user did not finish.** Endpointing fired
early. Lengthen the commit delay, or enable semantic end-of-turn, which is
what it is for.

**The agent interrupts itself one syllable in.** Echo. See §4. Headphones will
confirm the diagnosis in ten seconds.

**The reply is correct but sounds flat.** The chunker is splitting
mid-sentence. See §5.

**Everything is fast but the conversation feels slow.** Check the breakdown
rather than the total: it is usually endpointing, and endpointing is silent by
construction, so nothing in a log points at it.

**The agent talks for ninety seconds.** Not a latency problem — a prompt
problem that becomes a latency problem, because the user has to interrupt, and
interruption is the expensive path. `Policy.max_reply_sentences` is a backstop,
not a fix.

---

## 10. What is deliberately not here

- **No wake word.** A different problem, with different models.
- **No speaker diarization.** `vocal-helper` has it; a two-party conversation
  with an open microphone does not need it.
- **No telephony.** SIP, WebRTC and jitter buffers are a separate world.
- **No acoustic echo cancellation.** It belongs in the capture path, i.e. in
  `capture-helper`, not in a loop that never sees a sample. This package
  documents the problem and ships the grace period; the real fix is upstream.
- **No turn detection.** See §3.

---

## Sources

The latency and turn-detection figures above come from published 2026 work and
documentation, not from this package's own measurements:

- [The voice agent latency budget: where your 800ms goes](https://soniox.com/wiki/voice-agent-latency-budget)
- [Latency budgets for real-time voice](https://thepromptbench.com/voice-and-realtime/latency-budgets-for-realtime-voice/)
- [Streaming TTS: why time-to-first-audio decides UX](https://soniox.com/wiki/streaming-tts)
- [LiveKit — turns overview](https://docs.livekit.io/agents/logic/turns/)
- [LiveKit — sequential pipeline architecture for voice agents](https://livekit.com/blog/sequential-pipeline-architecture-voice-agents)
- [Voice agent barge-in: VAD levers under 150 ms](https://www.syncsoft.ai/en/blog/voice-agent-barge-in-vad-tuning-2026)
- [What is endpointing in voice AI? A guide to turn detection](https://www.cekura.ai/blogs/endpointing-in-voice-ai-turn-detection)
- [Text chunking for TTS](https://developers.deepgram.com/docs/tts-text-chunking)
- [Building enterprise realtime voice agents from scratch](https://arxiv.org/pdf/2603.05413)
- [Next-Turn: duration-aware streaming endpoint detection](https://arxiv.org/pdf/2606.18094)
- [speexdsp-python](https://github.com/xiongyihui/speexdsp-python) · [pyaec](https://pypi.org/project/pyaec/)

The AMI figure (~15 % of utterances under 400 ms) is quoted from
`vocal-helper`'s own `eot.py`, which measured it on the AMI dev slice.
