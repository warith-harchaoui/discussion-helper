# Landscape

[🇫🇷 PAYSAGE.md](https://github.com/warith-harchaoui/discussion-helper/blob/main/PAYSAGE.md) · 🇬🇧 English

Related and competing tools in the "hold a spoken conversation out loud, in
real time, where whose turn it is matters" space, benchmarked against
`discussion-helper`. Ratings run ⭐ (1) to ⭐⭐⭐⭐⭐ (5), scored against
`discussion-helper`'s intended job: a **library-shaped**, **local-first**
conversation loop whose interruption behaviour is **correct and observable**,
composing with the rest of the AI Helpers stack (`vocal-helper`,
`speaker-helper`, `best-engine-ai-helper`). A project optimised for a very
different job — a telephony platform carrying ten thousand concurrent calls,
say — is not penalised; the score just reflects fit to *this* niche.

The last column is there on purpose. `discussion-helper` scores ⭐ on
telephony and scale, and would be a poor choice for a call centre. A table
where the leader wins every column is a scoreboard, not a landscape.

## At a glance

<!-- TABLE:START -->
| Spoken Conversation | Runs locally | Barge-in discards queued audio | Per-stage latency breakdown | Library-shaped | Testable with no hardware | Swappable parts | Telephony and scale |
| --- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **discussion-helper** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ |
| LiveKit Agents | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| Pipecat | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| OpenAI Realtime API | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐ |
| Vocode | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| Vapi | ⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐ | ⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| Amazon Lex | ⭐ | ⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐⭐ |
| Rasa | ⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ |
| speech_recognition + pyttsx3 | ⭐⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐ |
<!-- TABLE:END -->

## Positioning map

<!-- FIGURE:START -->
2D representation of the table above.

![Positioning map](https://raw.githubusercontent.com/warith-harchaoui/discussion-helper/main/assets/landscape.png)

The map is a 2-D summary of the seven criteria, so read it as a shape, not a scoreboard. `discussion-helper` is at the top-right corner. The axes read **Horizontal: Adaptable ↔ Modular** and **Vertical: Resourceful ↔ Insightful**.

The map reveals a fundamental tension between approaches that prioritize flexibility and those that emphasize a more structured design. Options clustered on the left side of the map tend to offer greater adaptability, excelling in areas like local operation and integration with existing telephony systems. Conversely, those on the right demonstrate a focus on modularity, allowing for easier component swapping and expansion, particularly when considering features like speech recognition and scalable telephony.

The vertical dimension highlights a difference in how these systems handle information. Those positioned higher on the map demonstrate a capacity for deeper understanding and analysis, providing insights into performance and user interaction. Lower on the map, options prioritize efficient resource utilization and straightforward implementation, often at the expense of more complex analytical capabilities. Notably, discussion-helper leads on the insight axis, but not the adaptability one, suggesting a strength in understanding but less inherent flexibility.

Several options find themselves in interesting positions. For example, both Vapi and Amazon Lex occupy the lower-left corner, indicating a shared emphasis on adaptability and resourcefulness, while OpenAI Realtime API joins them for similar reasons. Conversely, Vocode, Rasa, and speech_recognition + pyttsx3 are grouped in the lower-right, sharing a focus on modularity and a more pragmatic approach to implementation. Discussion-helper and Pipecat both sit in the upper-right, demonstrating a combination of modular design and insightful capabilities, though for different reasons.
<!-- FIGURE:END -->

## Positioning

Three packages already did the work before this one existed. `vocal-helper`
hears, `speaker-helper` speaks, a local model answers. **None of them knows
whose turn it is**, and that gap — not hearing, not speaking — is the whole of
`discussion-helper`. It deliberately does *no* turn detection of its own:
`vocal-helper` ships Silero VAD and a semantic end-of-turn stage modelled on
LiveKit's `turn-detector`, and reimplementing either here would give it two
owners.

What it adds is the floor: four states, one holder at a time, and the rule that
`THINKING` is interrupted differently from `SPEAKING` — thinking can be
abandoned silently, speaking has to be *stopped* and its queued audio thrown
away. That last clause is the one differentiator worth the table above. A reply
is synthesised ahead of playback, so an interruption always finds audio made
and not yet heard, and playing it out — because it exists, because it was paid
for — is exactly what makes an agent feel deaf. Draining instead of discarding
is the single most common way to get this wrong, and it is invisible in a
transcript: the text of an interrupted answer looks complete.

The second differentiator is that none of it needs a room. `Listener`,
`Responder` and `Voice` are structural protocols with shipped fakes, so the
floor logic, the interruption and the latency accounting all run in CI with no
microphone, no model and no sound card. The behaviour hardest to get right in a
voice agent is also the hardest to *hear*: whether the audio really stopped,
whether the queue was discarded, whether the floor came back. A test with a
real voice can observe none of that.

Third, the latency breakdown is per stage rather than a total, and it names the
`slowest_stage`. One number says a conversation feels slow and nothing about
why. Time-to-first-audio and playback are reported separately, because lumping
them together makes a fast engine reading a long sentence look slower than a
slow engine reading a short one.

Each alternative carries nuance the stars compress. **LiveKit Agents** is the
reference implementation of this category and better than this package at most
things that are not the above: WebRTC transport, SIP telephony, a *trained*
turn-detector rather than a VAD threshold, and real horizontal scale. It is
framework-shaped, though — you deploy a worker, you do not import a loop — and
its comfortable path runs through cloud providers. **Pipecat** is similarly
capable and more integration-rich, built as a pipeline of frame processors; it
supports local models but the pipeline is the unit of composition, not a
protocol you implement in one class. **OpenAI's Realtime API** has the best
interruption behaviour in the table and the lowest latency, because the VAD,
the model and the voice are one server-side system — and it is also entirely
cloud, offers you almost no breakdown of where the time went, and cannot be
exercised without the API. **Vocode** is the closest in shape to this package,
open-source and Python-first, with telephony via Twilio, but its interruption
and observability are thinner. **Vapi** is a hosted platform: excellent time to
first demo, configuration rather than code. **Amazon Lex** belongs to an older
generation — intents and slots, telephony-first through Connect, barge-in as a
setting rather than a design. **Rasa** is dialogue management, text-first and
genuinely good at it; voice is a connector, and the floor is not its problem.
**`speech_recognition` + `pyttsx3`** is the hand-rolled baseline everybody
tries first: local, trivially library-shaped, and blocking all the way down, so
the user cannot interrupt at all.

## When to pick what

- **`discussion-helper`**: one person, one machine, a conversation that has to
  stop when they cut in — and you want to read why it felt slow. Composes with
  the rest of the AI Helpers suite.
- **LiveKit Agents**: you need WebRTC or telephony, many concurrent sessions,
  or a trained turn-detector rather than a VAD threshold. The right answer at
  scale.
- **Pipecat**: you want a rich pipeline with many ready-made service
  integrations and are happy composing processors.
- **OpenAI Realtime API**: lowest latency wins and the cloud is acceptable.
  Speech-to-speech in one hop, with interruption handled server-side.
- **Vocode**: an open-source Python voice agent with Twilio telephony, and you
  do not need the floor accounting.
- **Vapi**: you want a working voice agent this afternoon and would rather
  configure than build.
- **Amazon Lex**: you are already inside AWS Connect and think in intents and
  slots.
- **Rasa**: the hard part is *dialogue management*, not turn-taking, and most
  of your traffic is text.
- **`speech_recognition` + `pyttsx3`**: a demo where nobody will interrupt.

## Sources and as-of date

**Read on 2026-10-27.** The stars are a judgement of fit to *this* niche — a
library-shaped, local-first conversation loop whose interruption behaviour is
correct and observable — and not a benchmark result. They were scored by
reading each project's own documentation, and its source where that is public.
Nothing in the table was timed on a bench here, so no latency number, no
throughput number and no version number is quoted against anybody else's
software: those are precisely the claims that rot into being wrong about
somebody.

| Project | Read from |
|---|---|
| LiveKit Agents | [docs.livekit.io/agents](https://docs.livekit.io/agents/) · [turn detector](https://docs.livekit.io/agents/build/turns/turn-detector/) |
| Pipecat | [docs.pipecat.ai](https://docs.pipecat.ai/) |
| OpenAI Realtime API | [platform.openai.com — Realtime](https://platform.openai.com/docs/guides/realtime) |
| Vocode | [vocodedev/vocode-core](https://github.com/vocodedev/vocode-core) |
| Vapi | [docs.vapi.ai](https://docs.vapi.ai/) |
| Amazon Lex | [docs.aws.amazon.com/lex](https://docs.aws.amazon.com/lex/) |
| Rasa | [rasa.com/docs](https://rasa.com/docs/) |
| `speech_recognition` + `pyttsx3` | [SpeechRecognition](https://pypi.org/project/SpeechRecognition/) · [pyttsx3](https://pypi.org/project/pyttsx3/) |

`discussion-helper`'s own row is read off this repository rather than asserted.
*Barge-in discards queued audio* is
`tests/test_the_floor.py::test_what_was_queued_and_not_heard_is_discarded`,
which stages an interruption into a five-sentence reply and requires that the
sentence it landed on is counted as started and not as said, with the four
after it never starting; the companion
`test_the_interruption_is_fast` holds the whole stop under 150 ms against a
one-second sentence. *Testable with no hardware* is the suite itself, which
runs with no microphone, no model and no sound card. *Per-stage latency
breakdown* is `TurnTiming.as_dict()` — the same six fields the CLI's `--json`
and the HTTP event stream report. The ⭐ on *Telephony and scale* is measured
in the only sense available: there is no code here for either.

The published figures this package was designed against — the 800 ms budget,
the 150 ms barge-in bar, the reported 39 % drop in false interruptions when
semantic end-of-turn is fused with VAD — are other people's numbers, and each
is cited individually in
[KNOWLEDGE.md § Sources](https://github.com/warith-harchaoui/discussion-helper/blob/main/KNOWLEDGE.md#sources).
They are not re-derived here.

## Ideas worth stealing

Researched rather than guessed: what each neighbour does better, and what this library would have to change to match it. Nothing here is a commitment — it is the reading list the next version starts from.

- **`LiveKit Agents` — a turn detector that listens to the audio, not the transcript** — Deciding the user has finished from the text alone arrives a transcription-latency too late and mistakes a pause for an ending. An audio-based detector is the single change that makes a spoken loop feel like a conversation.

- **`LiveKit Agents` — roll back the interrupted LLM turn, do not just stop the voice** — When VAD fires on the caller while the agent is speaking, cancelling TTS is the obvious half. The half that is usually missed is rolling the interrupted turn out of the history, so the model is not later convinced it said a sentence the user never heard.

- **`Pipecat` — Smart Turn, an open end-of-turn model** — An openly available turn-detection model, rather than a silence threshold tuned by hand. A fixed timeout is wrong in both directions: it clips a thinking speaker and lags a decisive one.

- **`LiveKit Agents` — built-in testing and simulation** — A conversational loop is the hardest thing in this suite to regression-test, and this is the only neighbour that ships an answer. Scripted sessions replayed against the pipeline would catch a turn-taking regression that no unit test reaches.
