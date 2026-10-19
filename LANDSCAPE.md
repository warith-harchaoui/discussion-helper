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
<!-- TABLE:END -->

## Positioning map

<!-- FIGURE:START -->
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
