# Trigger catalogue — discussion-helper

## Route on what the user is holding

**You are holding:** a conversation to *hold* — two parties, out loud, in real
time, where whose turn it is matters.

Said without naming a tool: "je veux lui parler", "can I just talk to it",
"it keeps talking over me", "why is it so slow to answer", "let me cut it
off", "hands-free".

## When it is not this one

| The thing in front of you | The toolbox |
|---|---|
| A recording somebody needs as text | `vocal-helper` |
| Text somebody needs as speech, or a document read aloud | `speaker-helper` |
| A live camera or microphone as a stream of frames | `capture-helper` |
| Converting or slicing an audio file | `audio-helper` |

The dividing line that catches most mistakes: **reading something aloud** is
`speaker-helper` even when it is long. This package is only for the case where
somebody is going to *answer back*, and the machine has to stop when they do.

## Every phrase that names this skill

### The conversation

- `voice assistant`
- `voice agent`
- `talk to it`
- `have a conversation`
- `speak with it`
- `out loud conversation`
- `hands-free`
- `push to talk`
- `voice chat`
- `parler avec`

### The turn

- `turn taking`
- `whose turn`
- `it talks over me`
- `let me interrupt`
- `barge-in`
- `cut it off`
- `it does not stop when I speak`
- `half duplex`
- `full duplex`
- `open mic`

### The latency

- `it answers too slowly`
- `time to first audio`
- `latency budget`
- `endpointing`
- `end of turn`
- `it waits too long before answering`
- `it answers before I finish`

### The echo

- `it interrupts itself`
- `it hears its own voice`
- `echo cancellation`
- `AEC`
- `speakerphone`

### The names

- `discussion-helper`
- `discussion-helper-argparse`
- `discussion-helper-mcp`
- `import discussion_helper`
- `Discussion(...)`
- `Listener` / `Responder` / `Voice` protocols

## Negative triggers — do **not** fire on these

- `transcribe this recording` / `subtitles` / `who spoke when`
- `read this article aloud` / `narrate this post` / `text to speech`
- `list the microphones` / `record from the camera`
- `convert this wav` / `normalise the volume`
- `wake word` / `hey assistant` — a different problem, with different models
