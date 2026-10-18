# Changelog: discussion-helper

## v0.1.0 (2026-10-18): the loop, and the two numbers it has to hit

`vocal-helper` hears, `speaker-helper` speaks, a local model answers — and
none of them knows whose turn it is. This package is what was missing between
them.

### Added

- **`Discussion`**, the loop: listen, answer, speak, and stop the moment the
  user cuts in. Four floor states, and `THINKING` is separate from `SPEAKING`
  because they are interrupted differently — thinking can be abandoned
  silently, speaking has to be *stopped* and its queued audio thrown away.
- **Barge-in that discards rather than drains.** A reply is synthesised ahead
  of playback, so an interruption always finds audio made and not yet heard.
  Playing it out — because it exists, because it was paid for — is what makes
  an agent feel deaf. Held by a test that asserts both halves: the cut
  sentence must not count as said, and the ones after it must never start.
- **A grace period for echo.** The agent's own voice reaching its own
  microphone looks exactly like the user speaking, and on open speakers every
  reply would interrupt itself after one syllable. 350 ms by default, and it
  is a trade rather than a fix — `allow_barge_in=False` is there for the
  speakerphone case, and acoustic echo cancellation is the real answer.
- **A latency breakdown per exchange**, not a total. Endpointing, recognition,
  first token, first audio, and the `slowest_stage` that names what to fix.
  `SpokenSentence` reports time-to-first-audio *and* playback separately: one
  number would make a fast engine reading a long sentence look slower than a
  slow engine reading a short one.
- **Three protocols, not a pipeline.** `Listener`, `Responder`, `Voice`. The
  whole loop runs in CI with no microphone, no model and no sound card — and
  that is the point, because interruption handling is precisely what a real
  room makes impossible to assert.
- **`discussion-helper rehearse`**, which runs that same loop from the command
  line with fake parts. When a voice agent misbehaves the first question is
  always "is it the loop or is it the room"; this answers it in a second.
- **KNOWLEDGE.md** — the latency budget and where it really goes, why a
  silence threshold is not turn detection, the two mistakes everyone makes
  with barge-in, why replies chunk at sentences and not tokens. Sourced.

### Deliberately absent

No wake word, no diarization, no telephony, no echo cancellation, and **no
turn detection**: `vocal-helper` ships Silero VAD and a semantic end-of-turn
stage, and a second copy here would give that behaviour two owners.

There is also no HTTP or MCP surface yet. A live microphone loop over HTTP is
a different product — it wants WebRTC, not a request — and declaring a
`discussion-helper-mcp` command with no module behind it is exactly the defect
this suite keeps finding elsewhere. It will arrive as a control plane (start a
session, read the transcript and timings live) or not at all.
