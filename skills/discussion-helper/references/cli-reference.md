# discussion-helper CLI reference

One command line, `discussion-helper`, built with click, with two commands:
`rehearse` and `talk`.

```bash
discussion-helper --help      # -h works too
discussion-helper -V          # or --version
```

## `rehearse` — start here

```bash
discussion-helper rehearse 'bonjour' 'ça va ?'
```

Runs the whole loop with fake parts: no microphone, no model, no speaker,
nothing installed beyond the base package. **This is the first command to
reach for**, because the question a voice agent always raises first is *"is it
the loop or is it the room"*, and this answers it in about a second.

| Option | Effect |
|---|---|
| `[TURNS]...` | The user's lines, in order. |
| `--interrupt-after SECONDS` | Stage a barge-in this far into the agent's reply. |
| `--sentences INTEGER` | How long the fake reply runs. |
| `--max-sentences INTEGER` | Cap on reply length; `0` is none. |
| `--grace SECONDS` | Delay before an interruption is believed. |
| `--no-barge-in` | Strict half-duplex: the user may not interrupt. |
| `--json` | Emit JSON. |

Staging an interruption is the useful trick here:

```bash
discussion-helper rehearse 'bonjour' --sentences 5 --interrupt-after 0.2
```

The reply is five sentences long and is cut 200 ms in:

```
 you: bonjour
  it: bonjour bonjour (2) bonjour (3) (cut off)

turn 1: 0 ms to first audio, slowest stage think
```

Three got out before the interruption landed, because the fake voice reads at
no cost; the two after it never started, and `(cut off)` is the loop saying the
cut sentence does not count as said. If all five appear, the queue is draining
instead of being discarded — which is exactly what makes an agent feel deaf.
`--json` reports the same thing as `"interrupted": true` with an
`interruption_rate` of `1.0`.

## `talk` — the microphone

```bash
pip install 'discussion-helper[all]'
discussion-helper talk
```

Needs the hardware and the three siblings: `[listen]` (vocal-helper +
capture-helper), `[think]` (best-engine-ai-helper), `[speak]` (speaker-helper),
`[play]` (a sound card). `[all]` is the lot.

| Option | Effect |
|---|---|
| `--voice TEXT` | Voice to read with, e.g. `ff_siwis`. |
| `--language TEXT` | Language hint; empty lets the recogniser detect. |
| `--device TEXT` | Microphone name substring. |
| `--silence-timeout SECONDS` | Give up after this much silence. |
| `--max-sentences INTEGER` | Cap on reply length; `0` is none. |
| `--grace SECONDS` | Delay before an interruption is believed. |
| `--no-barge-in` | Strict half-duplex: the user may not interrupt. |
| `--json` | Emit JSON. |

### The two options that decide how it feels

**`--grace`** absorbs the agent's own first syllable. Without echo
cancellation that syllable is the loudest thing the microphone hears, and it
looks exactly like the user speaking — so on open speakers every reply would
interrupt itself after one word. It is a trade, not a fix: raise it on a
speakerphone, lower it on a headset.

**`--no-barge-in`** is the other end of the same trade. Rude, and right on a
speakerphone with no AEC, where the alternative is a conversation that cannot
get a sentence out.

If the agent keeps interrupting itself, those two are the dials. If it talks
over the *user*, read the latency breakdown instead.

## Reading the result

Both commands report a per-exchange latency breakdown rather than a total, and
name the `slowest_stage` — on every surface: the text output, `--json`, and the
HTTP event stream all carry the same six fields.

The number to watch is **time to first audio**, not total speaking time: a fast
engine reading a long sentence must not look slower than a slow engine reading
a short one. And watch the interruption rate — a high one usually means replies
that run too long, so `--max-sentences` is the fix, not a faster model.

`KNOWLEDGE.md` explains the latency budget, turn detection, and why echo
decides your defaults.
