# discussion-helper non-CLI surfaces

## 1. Library — the primary surface

```python
from discussion_helper import Discussion, Policy
from discussion_helper import Listener, Responder, Voice
from discussion_helper import Conversation, Floor, Speaker, TurnTiming, Utterance
```

Public API (`discussion_helper.__all__`): `Discussion`, `Policy`, `Listener`,
`Responder`, `Voice`, `Conversation`, `Floor`, `Speaker`, `TurnTiming`,
`Utterance`, `__version__`.

### Three protocols, not a pipeline

`Discussion` is written against `Listener`, `Responder` and `Voice` — three
structural protocols, not three concrete classes. That is what lets the hard
part be tested with no microphone, no model and no sound card anywhere, and it
is what lets somebody bring their own recogniser without uninstalling ours.

```python
async with Discussion(listener, responder, voice, Policy()) as talk:
    conversation = await talk.run()
```

The shipped implementations live in `discussion_helper.adapters` and each
imports its sibling **inside a function**, so a base install carries the loop
and nothing else:

| class | needs | extra |
|---|---|---|
| `VocalListener` | `vocal-helper` + a microphone | `[listen]` |
| `LocalResponder` | `best-engine-ai-helper` | `[think]` |
| `SpeakerVoice` | `speaker-helper` | `[speak]` |

`discussion_helper.testing` ships the fakes the test suite uses, and they are
public for the same reason: `ScriptedListener`, `EchoResponder`, `SilentVoice`.

### What comes back is the evidence

`Conversation` carries the `utterances`, the `floor` it ended on, the
`timings`, and `interruption_rate`. The last one is a diagnostic: a high rate
usually means answers that run too long, which a transcript will not show
because the text of an interrupted answer looks complete.

`TurnTiming` splits each exchange rather than totalling it — `think_s`,
`to_first_audio_s`, `speak_s`, and `slowest_stage` naming what to fix.
Time-to-first-audio and playback are separate on purpose: one number would
make a fast engine reading a long sentence look slower than a slow engine
reading a short one.

### Dependencies

`os-helper` and `click` at base — the command line is built with click and is
not optional, so neither is click. Everything that hears, thinks or speaks is
optional.

## 2. CLI — click

`discussion-helper`, with two commands: `talk` and `rehearse`. One command
line, one parser. See `cli-reference.md`.

## 3. HTTP API — FastAPI (`[server]`)

```bash
pip install 'discussion-helper[server]'
python -m discussion_helper.api     # 127.0.0.1:8000, OpenAPI docs at /docs
```

| Method | Route | `operation_id` |
|---|---|---|
| GET | `/health` | `health` |
| POST | `/sessions` | `start_session` |
| GET | `/sessions` | `list_sessions` |
| GET | `/sessions/{session_id}` | `read_session` |
| GET | `/sessions/{session_id}/events` | `follow_session` |
| POST | `/sessions/{session_id}/interrupt` | `interrupt_session` |
| POST | `/sessions/{session_id}/say` | `say_to_session` |
| DELETE | `/sessions/{session_id}` | `end_session` |
| POST | `/turn` | `take_turn` |

Plus one WebSocket, `/sessions/{session_id}/audio`, which carries a remote
client's audio both ways — the browser or phone-line case, where the machine
holding the model is not the machine holding the microphone.

`interrupt_session` routes through the same `Voice.stop` the microphone's
barge-in uses, so audio already synthesised is **discarded rather than
drained**. An interrupt that let the queue play out would be the API quietly
disagreeing with the loop.

## 4. MCP — mounted on that same app (`[mcp]`)

```bash
pip install 'discussion-helper[mcp]'
discussion-helper-mcp
```

No second implementation: `fastapi-mcp` turns the routes above into a tool
catalogue, so an agent calling a tool and a shell calling `POST /sessions`
reach the same function and the two surfaces cannot drift into disagreeing.

An agent **cannot hold** a conversation — it has no microphone and no ears.
What it gets is the other verbs, which are the useful ones for an assistant
sitting beside a person: start a session and end it, watch the transcript and
the latency as they grow, **interrupt** it, and take one turn as text (the
only way to ask the conversation's own model something directly).

"Stop talking" is a thing people say to an agent, and it is the reason the
interrupt tool exists.
