# Changelog: discussion-helper

## v0.2.0 (2026-10-19): the microphone was never connected

Joining the AI Helpers suite, and the audit that came with it found that the
package's two headline promises — hear the user, stop when they cut in — were
both inert on the only path that uses a real microphone.

### Fixed

- **`VocalListener` now builds the pipeline it always claimed to.** It was
  consuming `voh.sources.from_microphone` directly: the *raw PCM source*, not
  the pipeline, so no VAD, no recogniser, no turn boundaries. It then looked
  for a transcript on frames that carry none.

  What made it invisible rather than noisy: `PcmFrame` is a `TypedDict`, so at
  runtime it is a plain `dict`, and `getattr(frame, "text", "")` cannot raise
  on a dict — it answers `""` forever. The loop skipped every frame and the
  listener yielded nothing at all, with no exception and no log line. The
  class docstring described the correct architecture the whole time; only the
  body never built it. Every field is read by subscript now, so a renamed key
  fails loudly.

- **Barge-in from a real microphone never fired.** Same cause, same silence:
  `getattr(frame, "is_speech", False)` was permanently `False`. The published
  bar is 150 ms from the first syllable to silence, and the pipeline cannot
  answer that — its earliest event is a `VoicedSegment`, emitted when speech
  *ends*, after 300 ms of trailing silence and before the recogniser runs. So
  the onset is now read off the raw frames as they pass: one 20 ms frame of
  latency, on level rather than Silero, because vocal-helper exposes no public
  single-frame probe and a second VAD would double the cost of the first. The
  new `onset_rms` knob tunes it; `Policy.barge_in_grace_s` already existed to
  absorb exactly this kind of detector hearing the agent's own first syllable.

- **Three tests on the microphone path, which had none.** They run with no
  microphone, against a `vocal_helper` stand-in shaped like the real one in
  the way that mattered — events are dicts. Two of them fail against v0.1.0:
  one finds nothing yielded, the other times out waiting for the interruption.

- **`tomllib` on Python 3.10.** The package declares `>=3.10` and the
  console-script guard imported `tomllib`, which is stdlib only from 3.11.
  Skipping it there was the easy fix and the wrong one — that guard is what
  caught a `discussion-helper-mcp` script pointing at a module nobody had
  written — so it falls back to `tomli` and keeps running on the oldest Python
  we claim to support.

### Changed

- **Dependency floors now name versions this package has actually run on.**
  `vocal-helper` was pinned `>=0.4.4`, two major boundaries below the 2.x it
  is written against; `best-engine-ai-helper` `>=0.4.0`, below the 1.0 line
  entirely. Both are corrected and capped, as are `capture-helper` and
  `speaker-helper`, and `os-helper` moves from `>=1.7.2` to the suite's
  `>=2.0.0,<3`.

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
