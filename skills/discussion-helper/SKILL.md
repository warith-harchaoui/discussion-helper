---
name: discussion-helper
description: >-
  Hold a spoken conversation at the microphone — listen, answer, speak, and
  stop the moment the user cuts in. The loop over vocal-helper (hearing), a
  local language model (answering) and speaker-helper (speaking): one floor
  holder at a time, barge-in under 150 ms that discards queued audio rather
  than draining it, and a per-exchange latency breakdown naming which stage to
  fix. Runs entirely on the machine. Use when the user says "talk to it", "a
  voice assistant", "voice agent", "have a conversation out loud", "let me
  interrupt it", "it talks over me", "it answers too slowly", "barge-in",
  "turn taking", "push to talk", "hands-free", or names `discussion-helper`,
  `import discussion_helper`, `Discussion(...)`. Do NOT use to transcribe a
  recording (vocal-helper), to read a document aloud (speaker-helper), or to
  open a camera or microphone as frames (capture-helper). The design notes —
  latency budget, turn detection, echo — are in `KNOWLEDGE.md`.
license: BSD-3-Clause
metadata:
  author: Warith HARCHAOUI
  package: discussion-helper
  suite: ai-helpers
  homepage: https://deraison.ai/ai-helpers
---

# discussion-helper — the loop between hearing and speaking

Three packages already do the work. `vocal-helper` hears, `speaker-helper`
speaks, a local model answers. None of them knows whose turn it is, and that
gap is this package.

## Start here, before touching hardware

```bash
discussion-helper rehearse "bonjour" "comment ça va ?"
```

This runs the **real loop** with the microphone, model and speaker replaced by
fakes. It needs nothing installed and finishes in a second. When a voice agent
misbehaves the first question is always "is it the loop or is it the room" —
rehearse answers it, and a room never will.

Stage an interruption to see barge-in work:

```bash
discussion-helper rehearse "dis-moi tout" --sentences 6 --interrupt-after 0.25 --grace 0
```

## Then talk to it

```bash
pip install 'discussion-helper[all]'
speaker-helper install-voice --engine kokoro
discussion-helper talk --voice ff_siwis --json
```

## The two numbers that decide whether it works

**800 ms** from the user's last word to the agent's first sound, before the
conversation feels broken. **150 ms** from an interruption to silence.

When the first is missed, read the breakdown rather than the total — every
exchange reports `endpoint_s`, `recognise_s`, `think_s`, `speak_s` and names
the `slowest_stage`. It is usually endpointing, which is silent by
construction and therefore invisible in a log.

## Three things that look like bugs and are not

- **It interrupts itself one syllable in.** That is echo: the agent's own
  voice reaching its own microphone looks exactly like the user speaking.
  Headphones confirm the diagnosis in ten seconds. Raise `--grace`, or use
  `--no-barge-in` on a speakerphone.
- **It answers half a question.** Endpointing fired early. That lives in
  `vocal-helper`'s semantic end-of-turn stage, not here.
- **It talks for ninety seconds.** A prompt problem that becomes a latency
  problem, because the user then *has* to interrupt. `--max-sentences` is a
  backstop, not a fix.

## Writing your own part

`Listener`, `Responder` and `Voice` are protocols. A cloud recogniser, a
scripted model for a demo, a phone line instead of a speaker — each is one
class, and the loop does not change. `discussion_helper.testing` ships a
known-good fake of each, so a new one can be dropped into a working loop.

The one method to get right is `Voice.stop()`: it must **discard** what was
synthesised and not yet heard, never drain it.

## Reading further

- `KNOWLEDGE.md` — the latency budget, turn detection, barge-in, echo. Sourced.
- `references/triggers.md` — when this is the answer, and when it is not.
- `references/cli-reference.md` — both front doors, and the two options
  (`--grace`, `--no-barge-in`) that decide how a conversation feels.
- `references/surfaces.md` — the library, the HTTP routes, and what an
  agent can and cannot do with a conversation it has no ears for.
