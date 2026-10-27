# Changelog: discussion-helper

## Unreleased

### Documentation

- **The six documents now carry the suite spine** (CODING.md 16–18). The
  README and the LISEZMOI gained a real `## Quick start` /
  `## Prise en main rapide` — the shortest path from `pip install` to a
  conversation on screen, with the transcript it actually prints — and the
  rehearsal section that used to stand in for one keeps the part only it could
  say: staging the interruption, and reading `(cut off)` as proof the queue was
  discarded rather than drained.

- **LANDSCAPE and PAYSAGE say where their stars came from.** A comparison with
  undated claims about other people's software is the one document that rots
  into being wrong about somebody, so `## Sources and as-of date` /
  `## Sources et date de relevé` names the date it was read, links each
  project's own documentation, and points `discussion-helper`'s own column at
  the tests that assert it. No competitor version number and no benchmark
  figure is quoted, because none was measured here.

- **EXAMPLES and EXEMPLES gained a `## Setup`, a `## Command line` and a
  `## Troubleshooting`,** and the HTTP section is now correct. It told readers
  to run `python -m discussion_helper.api`, which has never worked: the module
  is an ASGI factory with no `__main__`, so that command exits 0 having served
  nothing. It also showed `curl -X POST /sessions` with no body, which answers
  `422`. Both are replaced by commands that were run — `uvicorn
  discussion_helper.api:build --factory`, and the `fake` transport driven end
  to end — with the real JSON pasted in. `references/surfaces.md` carried the
  same wrong launch line and is fixed with them.

- **The README names where the model comes from.** Nothing here hardcodes one:
  `LocalResponder` calls `best_engine_ai_helper.llm.chat_stream`, and which
  model fits the machine is `best-engine-ai-helper`'s decision. That was true
  in the code and absent from the entry point.

## v0.4.1 (2026-10-25): the MCP launcher joins the click one

### Changed

- **`discussion-helper-mcp` was still argparse.** v0.4.0 put *the* command
  line on click and left the second console script behind, so the wheel
  published yesterday ships two parsing libraries and two answers to `-h`:
  `discussion-helper -h` prints help, `discussion-helper-mcp -h` answered
  `unrecognized arguments: -h`. Both are click now, both carry
  `help_option_names = ["-h", "--help"]`.

  Nothing a reader types changed. `--host` and `--port` keep their spellings
  and their defaults — the Dockerfile's `CMD` passes them, and the README, the
  LISEZMOI and `references/surfaces.md` all name the command — and
  `main(argv)` still **returns** an exit code rather than exiting, which is
  what `[project.scripts]` calls. click runs with `standalone_mode=False` for
  exactly that reason: left to itself it exits by raising, and a console
  script that raises instead of returning its code is a different contract.

  Two improvements come with the move. The environment defaults
  (`DISCUSSION_HELPER_MCP_HOST`, `DISCUSSION_HELPER_MCP_PORT`) are `envvar=`
  declarations rather than `os.environ.get` calls, so they are read per
  invocation instead of once at import, and they appear in `--help`. And a
  non-numeric `DISCUSSION_HELPER_MCP_PORT` used to raise `ValueError` out of
  `int()` while the parser was still being built — before `--help` could
  print — where it now reports `Invalid value for '--port'` and exits 2.

  `argparse` is now imported nowhere in this package.

### Added

- `tests/test_a_bare_install_can_run_its_commands.py` covers what the launcher
  *does*, not only how its source reads: `main` returns `0` for `-h` and
  `--help` and `2` for an unknown flag rather than raising, and a missing
  `[mcp]` extra returns `2` after naming the extra. Proven by breaking them —
  `standalone_mode=True` turns the first red.

## v0.4.0 (2026-10-25): one command line, built with click

### Changed

- **One command line, and it is the click one.** `discussion-helper` now runs
  the click implementation and is the only CLI this package ships;
  `discussion-helper-argparse` and the parser behind it are gone. `click` was
  already a base dependency rather than an extra, so a plain
  `pip install discussion-helper` carries the command exactly as before —
  there is no `[cli]` extra here to remove.

  A name that advertises the parsing library describes the implementation, not
  the interface, and two parsers over two commands cost more to keep in step
  than the second door was worth.

- **The handlers moved before the file was deleted.** They were never in the
  click module: `_policy`, `_report`, `_cmd_talk` and `_cmd_rehearse` all
  lived in the argparse half, and the click half imported them across the
  module boundary. Deleting the module the suffixed command pointed at would
  have taken the surviving CLI's whole body with it. `_report` and `_policy`
  carried over unchanged; the two command bodies now read their own click
  parameters instead of an `argparse.Namespace` assembled to look like what
  the other parser produced.

- `cli_click.py` is now `cli.py`, and the argparse module is deleted with the
  parser declaration, the `_version_string` helper, the `_HANDLERS` table and
  the `main(argv)` dispatcher: 398 lines across two modules became 276 in one.

- `click` capped below 9, which it never was here, matching the rest of the
  suite. The decorators this CLI is written against (`group`,
  `version_option`, `argument(nargs=-1)`) are exactly what a major bump is
  allowed to move, and the dependency is no longer one an extra could shield.

- `os-helper` cap widened to `<4`. os-helper 3.0.0 is the release that deleted
  its own command line and nothing else; the three names this package reads —
  `init_logging`, `warning`, `Prompts` — are all still exported, and none of
  them was ever reached through a shell. The floor stays at 2.9.0, where
  `Prompts` landed.

### Fixed

- **The surviving `--help` had lost the examples.** The argparse door carried
  an epilog with three worked command lines and the pointer to KNOWLEDGE.md;
  the click door never had one, so the help on the command everybody actually
  runs was a bare option list. Found by running `--help` rather than reading
  it. Ported, with a `\b` line so click stops reflowing the block into a
  paragraph.

- **Four flags had been documented on one door and not the other.** The click
  copies of `--no-barge-in`, `--grace`, `--silence-timeout` and `--json` were
  one-line summaries of the argparse wording, and dropped what the flag is
  *for*: that `--no-barge-in` is correct on a speakerphone where every reply
  would otherwise interrupt itself, that `--grace` absorbs the agent's own
  voice when there is no echo cancellation, that an open microphone in an
  empty room is an ordinary ending. The fuller text is now the only text, and
  `show_default=True` restores the defaults argparse printed with
  `%(default)s` and click was not showing at all.

- `-V` had no short form on the click door until earlier today (`249ba0a`,
  unreleased). It ships here, with the version read from `__version__` rather
  than from the installed distribution's metadata — which reports whatever was
  last pip-installed, a step behind the code in every editable checkout.

### Tests

73 pass, down from 74. The two twin-drift tests — the two doors offering the
same commands, the two doors reporting the same version — had nothing left to
compare, and `test_the_command_imports_on_a_bare_install` lost one
parametrised case with the third console script.

What replaced them is stronger than what went: the command list is now
asserted against a literal (`{"talk", "rehearse"}`, the only place that says
out loud what the CLI offers), and the handler-table test, which only ever
read a dict, became a `CliRunner` call that stages a barge-in and checks the
JSON transcript comes back cut off with an `interruption_rate` of 1.0. Both
new guards were proven by breaking what they watch: sabotaging `rehearse` into
a no-op and pointing `version_option` back at the install metadata each turn
the matching test red. No scenario existed only on the argparse side, so
nothing was dropped.

### Migration

`discussion-helper-argparse <cmd>` becomes `discussion-helper <cmd>` — same
two commands, same flags, same output. `pip install "discussion-helper[cli]"`
fails on an unknown extra, as it always did here: the CLI has never been
optional in this package.

### Also in this release

Changes made since v0.3.0 and unreleased until now: `EXEMPLES.md`, the French
twin of the cookbook; a CI job that runs the declared 3.10 floor instead of
only 3.12; and README's "The Promise" and "Installation" sections brought into
line with the rest of the suite.

## v0.3.0 (2026-10-22): the spoken prompt speaks French too

### Added

- **The system prompt now exists in French**, in
  `discussion_helper/locales/i18n.yaml`, read through `os_helper.Prompts` —
  the prompt loader the suite shares as of os-helper 2.9.0. Pass
  `LocalResponder(language="fr")`, or call `default_system("fr")`.

  For a package whose whole job is holding a spoken conversation, an
  English-only instruction was a real defect rather than a missing nicety: a
  model told "You are speaking out loud, not writing" answers a French
  speaker in English, or in written-register French. The two versions are
  **written per language, not translated** — what makes a model answer in
  spoken French is not the French words of the English sentence.

  A regional tag reaches its base language (`fr-CA` → `fr`) and an unknown
  one falls back to English, both through the shared loader.

### Changed

- The prompt moved out of `LocalResponder.DEFAULT_SYSTEM`, a hardcoded class
  attribute, into the catalogue. An explicit `system=` argument still wins
  over everything.

### Fixed

- **The catalogue would not have shipped.** This package declared no
  `[tool.setuptools.package-data]` at all, so the new `locales/i18n.yaml` was
  absent from the built wheel — verified by building one — and every answer
  would have been generated under the English prompt however the caller
  asked, while a source checkout worked perfectly. Declared, and held by a
  test that reads the build config plus one that asks git whether the file is
  tracked.

## v0.2.1 (2026-10-20): room for vocal-helper 3

### Changed

- **`[listen]` admits vocal-helper 3.x** — `>=2.0.0,<4` instead of `<3`.
  The ceiling moved only after 3.0.0 was actually run here rather than read
  about: both of its breaking changes land somewhere this package does not
  stand. `Pipeline.run()` raising `StageCrashed` instead of yielding nothing
  is what this adapter wanted all along — a recogniser that died used to
  reach the responder as *silence*, which a conversation loop cannot tell
  from a user who said nothing — and the pyannote default moves the offline
  checkpoint, which the listening path never loads. The 63 tests pass against
  3.0.0.

  Left at `<3`, `pip install discussion-helper[listen]` would have pinned the
  2.x line indefinitely while the package it exists to drive moved on.

### Note

v0.2.0 was published to PyPI on 2026-10-19 without a git tag. The tag now
exists and points at `9503c0a`, the commit that wheel was built from.

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

- **The two front doors reported different versions.** `--version` on the click
  door answered from the installed distribution's metadata (`version_option`
  with only `package_name=`), while the argparse door read `__version__`. Three
  places can state this package's version and the two doors read two of them,
  so they diverged the moment an editable install fell a step behind the code,
  which is the normal state mid-development: measured in one checkout, click
  said 0.1.0 and argparse said 0.2.0. Both read `__version__` now, and a test
  compares the numbers the two commands actually print.

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
