"""
Binding the three protocols to the real siblings.

Module summary
--------------
:mod:`discussion_helper.parts` says what a listener, a responder and a voice
must do. This module says who actually does it: ``vocal-helper`` hears,
``best-engine-ai-helper`` answers, ``speaker-helper`` speaks.

Every import here is inside a function. A base install of this package carries
the loop and nothing else — no recogniser, no model, no sound card — and that
is what lets the floor and interruption logic be tested in CI. An adapter that
imported its sibling at module scope would take that away from everyone who
only wanted the loop.

Each adapter is thin on purpose. When one of them starts holding logic, the
behaviour it holds has two owners — the sibling that fought for it and the
copy here — and the two drift. The one thing these are allowed to own is
*shape*: turning a stream of recogniser events into completed turns, or a
stream of tokens into speakable sentences.

Author
------
Warith HARCHAOUI — https://linkedin.com/in/warith-harchaoui
"""

from __future__ import annotations

import asyncio
import functools
import re
import time
from collections.abc import AsyncIterator
from pathlib import Path

import os_helper as osh

from discussion_helper.types import SpokenSentence, Utterance

#: A sentence ends at ``.``, ``?`` or ``!`` followed by space or end of text.
#: Deliberately not a clause boundary: synthesis models use sentence context
#: to shape intonation, and a chunk cut at a comma comes out flat or oddly
#: stressed. See KNOWLEDGE.md §5.
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


def split_sentences(text: str) -> list[str]:
    """Split ``text`` into speakable sentences.

    Used to turn a token stream into the unit a voice reads well. Kept here
    rather than imported from ``speaker-helper`` so a caller can stream a
    reply without the speech extra installed — the rule is four lines, and a
    dependency for four lines is a worse trade than the duplication.
    """
    parts = [part.strip() for part in _SENTENCE_END.split(text or "")]
    return [part for part in parts if part]


class VocalListener:
    """Hears, through ``vocal-helper`` and the microphone ``capture-helper`` opens.

    The two questions in the :class:`~discussion_helper.parts.Listener`
    protocol are answered by two different parts of that pipeline, and keeping
    them apart is the point: completed turns come from the end of it (VAD, then
    semantic end-of-turn, then recognition), while "is somebody talking right
    now" comes from the VAD stage alone. A barge-in that waited for a
    transcript would arrive a second late — by which time the agent has been
    talking over the user for a sentence.

    Parameters
    ----------
    language : str
        Hint for the recogniser. Empty lets it detect.
    device_name, device_index : str or int, optional
        Which microphone. Resolved by ``capture-helper``.
    onset_rms : float
        Level above which a frame counts as somebody starting to talk, used
        only to answer :meth:`speech_started`. The default suits a headset at
        a normal distance; raise it in a noisy room, where the cost of getting
        it wrong is an agent that interrupts itself.

    Notes
    -----
    This package does **no** turn detection of its own. ``vocal-helper`` ships
    Silero VAD and a semantic end-of-turn stage modelled on LiveKit's
    ``turn-detector``; reimplementing either here would give it two owners.
    """

    def __init__(
        self,
        *,
        language: str = "",
        device_name: str | None = None,
        device_index: int | None = None,
        onset_rms: float = 0.02,
    ) -> None:
        self.language = language
        self.device_name = device_name
        self.device_index = device_index
        self.onset_rms = onset_rms
        self._speech = asyncio.Event()
        self._pipeline: object | None = None

    async def utterances(self) -> AsyncIterator[Utterance]:
        """Yield each completed user turn, as the pipeline closes it."""
        try:
            import numpy as np
            import vocal_helper as voh
        except ImportError as exc:  # pragma: no cover - dependency guard
            raise RuntimeError(
                "hearing needs vocal-helper and a microphone. Install them with:\n"
                "    pip install 'discussion-helper[listen]'"
            ) from exc

        # `from_microphone` is a *source*: an async iterator of raw PCM frames.
        # It is not the pipeline, and it carries no transcript — the VAD, the
        # recogniser and the turn boundaries all live in `voh.Pipeline`, which
        # this method used not to build. Reading `.text` off a frame that never
        # had one is the kind of mistake that cannot raise: `PcmFrame` is a
        # TypedDict, so it is a plain dict at runtime, and `getattr(frame,
        # "text", "")` quietly answers `""` forever. The loop then skipped
        # every frame and this listener yielded nothing at all, with no
        # exception and no log line. Hence subscript access below, never
        # getattr: a renamed key has to fail loudly.
        def _tapped_microphone() -> AsyncIterator[object]:
            """The mic, passed through to the pipeline, with an onset tap."""

            async def frames() -> AsyncIterator[object]:
                async for frame in voh.sources.from_microphone(
                    device_name=self.device_name, device_index=self.device_index
                ):
                    # Barge-in cannot be answered from the pipeline's output.
                    # Its earliest event is a VoicedSegment, which Silero emits
                    # when speech *ends* — after `min_silence_ms` (300 ms by
                    # default) of trailing silence, and before the recogniser
                    # has even run. The published bar here is 150 ms from the
                    # first syllable to silence, so the onset has to be read off
                    # the raw frames as they go past: one 20 ms frame of
                    # latency. Level, not Silero, because vocal-helper exposes
                    # no public single-frame probe (`_score_window` is private)
                    # and running a second VAD would double the cost of the
                    # first. A crude detector is also already accounted for:
                    # `Policy.barge_in_grace_s` exists precisely because,
                    # without echo cancellation, the loudest thing any such
                    # detector hears is the agent's own first syllable.
                    pcm = frame["pcm"]
                    if float(np.sqrt(np.mean(np.square(pcm)))) >= self.onset_rms:
                        self._speech.set()
                    yield frame

            return frames()

        pipeline = voh.Pipeline(
            source=_tapped_microphone,
            config=voh.PipelineConfig(
                # "" means "let the recogniser decide", which whisper spells
                # "auto".
                asr={"language": self.language or "auto"},
                # Both default to None, i.e. off, and both stay off. The LLM
                # analyst keeps a rolling summary this package has no use for —
                # it brings its own responder — and semantic end-of-turn buys
                # ~39 % fewer mid-sentence breaks at the price of an LLM hop per
                # voiced segment, which is the one currency a voice loop cannot
                # spend.
                llm=None,
                eot=None,
            ),
        )
        self._pipeline = pipeline

        async for event in pipeline.run():
            # The stream mixes Utterance with SummarySnapshot; only the former
            # carries text. With `llm=None` no snapshot is produced, but the
            # check costs nothing and keeps this honest if that ever changes.
            text = event.get("text", "") if isinstance(event, dict) else ""
            if not text:
                continue
            self._speech.clear()
            yield Utterance(
                speaker="user",
                text=text,
                started_s=event["t0"],
                ended_s=event["t1"],
            )

    async def speech_started(self) -> None:
        """Return as soon as the level tap says somebody is talking."""
        self._speech.clear()
        await self._speech.wait()

    async def aclose(self) -> None:
        """Release the microphone."""
        closing = getattr(self._pipeline, "aclose", None)
        if closing is not None:  # pragma: no cover - depends on the sibling
            await closing()


@functools.lru_cache(maxsize=1)
def _prompts() -> osh.Prompts:
    """The shared prompt loader, bound to this package's locale file."""
    return osh.Prompts.from_path(Path(__file__).resolve().parent / "locales" / "i18n.yaml")


def default_system(language: str = "") -> str:
    """The instruction every answer is generated under, in *language*.

    Written per language rather than translated: what makes a model answer in
    spoken French register is not the French words of the English sentence.
    A language with no prompt falls back to English, and a regional tag finds
    its base language, both through :class:`os_helper.Prompts`.

    Parameters
    ----------
    language : str
        Language code; empty means the file's default.

    Returns
    -------
    str
        The system prompt.
    """
    return _prompts().text("default_system", language or None)


class LocalResponder:
    """Answers, with whatever model fits this machine.

    Parameters
    ----------
    system : str
        The instruction the model is given. The default asks for brevity, and
        that is a latency decision rather than a style one — see below.
    max_sentences : int
        Stop after this many sentences even if the model keeps going.

    The streaming that is not here, and what it costs
    -------------------------------------------------
    ``best_engine_ai_helper.llm.chat`` returns a finished string. It does not
    stream tokens, so the usual trick of speaking the first sentence while the
    rest is still being written is **not available on this path**, and it
    would be dishonest to pretend otherwise by yielding sentences from a
    string that is already complete.

    The consequence is concrete and belongs in the budget: ``think_s`` here is
    the *whole* generation, not a first token. A stack with a streaming client
    spends 150–400 ms on that line; this one spends however long the answer
    takes. Which is exactly why the default system prompt asks for one or two
    sentences, and why ``max_sentences`` exists — on a non-streaming client,
    answer length is latency, directly and entirely.

    Sentences are still the unit yielded, and that still earns its keep: it is
    what gives a barge-in somewhere to land, and what keeps the synthesiser
    reading whole sentences rather than clauses.
    """

    def __init__(
        self,
        *,
        system: str = "",
        max_sentences: int = 4,
        stream: bool = True,
        language: str = "",
    ) -> None:
        self.system = system or default_system(language)
        self.max_sentences = max_sentences
        self.stream = stream

    async def warmup(self) -> None:
        """Pay the model client's first-call cost before anybody is waiting.

        Measured on this stack: the first call in a process takes **4.8 s**
        because the content-safety scan loads a classifier; every call after
        takes **0.25 s**. Unwarmed, those four and a half seconds land on the
        user's first question — the single turn where somebody is deciding
        whether this thing works at all.

        Failures are swallowed on purpose. This is a pre-load; if the model is
        unreachable the real call will say so, with a better message and at a
        moment the caller asked for.
        """
        try:
            from best_engine_ai_helper.llm import chat_stream

            await asyncio.to_thread(lambda: next(iter(chat_stream("ok", system="Say ok.")), ""))
        except Exception:  # noqa: BLE001 - a warm-up may not fail a conversation
            return

    def render(self, messages: list[dict[str, str]]) -> str:
        """The conversation so far, as one prompt.

        ``chat`` takes a prompt and a system instruction, not a message list,
        so the history has to be rendered. Written as a transcript with named
        turns rather than concatenated: without the names, a model answering
        the third turn cannot tell its own earlier words from the user's, and
        starts agreeing with itself.
        """
        lines = [
            f"{'User' if m['role'] == 'user' else 'You'}: {m['content'].strip()}"
            for m in messages
            if m.get("content", "").strip()
        ]
        lines.append("You:")
        return "\n".join(lines)

    async def reply(self, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        """Yield the answer one speakable sentence at a time."""
        # `best_engine_ai_helper.llm.chat`, not `best_engine_ai_helper.chat`.
        # The suite routes every model call through that one function — no
        # script imports an Ollama or OpenAI client directly — and the
        # submodule is where it lives.
        try:
            from best_engine_ai_helper.llm import chat, chat_stream
        except ImportError as exc:  # pragma: no cover - dependency guard
            raise RuntimeError(
                "answering needs a local model. Install it with:\n"
                "    pip install 'discussion-helper[think]'"
            ) from exc

        prompt = self.render(messages)

        if not self.stream:
            # In a thread: `chat` is blocking, and this coroutine shares its
            # loop with the barge-in watcher. Calling it directly would freeze
            # the loop for the whole generation — the agent would be unable to
            # notice an interruption during precisely the stretch where one is
            # most likely.
            answer = await asyncio.to_thread(chat, prompt, system=self.system)
            if isinstance(answer, dict):  # pragma: no cover - json_schema path
                answer = str(answer.get("text", answer))
            for index, sentence in enumerate(split_sentences(str(answer))):
                if index >= self.max_sentences:
                    return
                yield sentence
            return

        # Streaming. Measured on this stack, warm: the first token arrives in
        # 0.25 s where the whole answer takes several seconds. That difference
        # is the whole budget — see KNOWLEDGE.md §2 — because the sentence can
        # be spoken while the rest is still being written.
        pending = ""
        emitted = 0
        async for piece in _in_thread(chat_stream(prompt, system=self.system)):
            pending += piece
            # Split on every arrival rather than buffering to a size: the
            # first sentence is the only one on the latency path, and a buffer
            # would hold it back for the benefit of the ones that are not.
            sentences = split_sentences(pending)
            if len(sentences) > 1:
                for sentence in sentences[:-1]:
                    yield sentence
                    emitted += 1
                    if emitted >= self.max_sentences:
                        return
                pending = sentences[-1]

        tail = pending.strip()
        if tail and emitted < self.max_sentences:
            # Models stop mid-flow, so the last sentence rarely ends in
            # punctuation. Spoken rather than dropped.
            yield tail

    async def aclose(self) -> None:
        """Nothing is held open; the client is per-call."""
        return None


class SpeakerVoice:
    """Speaks, through ``speaker-helper``, and can be stopped mid-sentence.

    Parameters
    ----------
    voice : str
        A built-in voice. Empty means "detect the language of the text and
        pick the voice that speaks it".
    language : str
        Passed through to the engine.

    Notes
    -----
    :meth:`stop` cancels the playback task and clears the queue. Draining it
    instead — playing out what was already synthesised — is the mistake that
    makes an agent feel deaf, and it is the whole reason this method exists
    rather than a flag the loop checks between sentences.
    """

    def __init__(self, *, voice: str = "", language: str = "") -> None:
        self.voice = voice
        self.language = language
        self._speaker: object | None = None
        self._playing: asyncio.Task[None] | None = None

    async def _engine(self) -> object:
        """The speaker, built once and kept.

        Rebuilding it per sentence would reload an ONNX graph between
        sentences, which would dominate the very budget this loop protects.
        """
        if self._speaker is None:
            try:
                from speaker_helper import Settings, Speaker
            except ImportError as exc:  # pragma: no cover - dependency guard
                raise RuntimeError(
                    "speaking needs speaker-helper. Install it with:\n"
                    "    pip install 'discussion-helper[speak]'"
                ) from exc
            self._speaker = Speaker(
                Settings.from_mapping(
                    {
                        "backend": "kokoro",
                        "voice": self.voice,
                        "language": self.language or "fr",
                    }
                )
            )
        return self._speaker

    async def speak(self, sentence: str) -> SpokenSentence:
        """Synthesise and play one sentence."""
        speaker = await self._engine()
        started = time.perf_counter()
        audio = await speaker.say(sentence, language=self.language or None)  # type: ignore[attr-defined]
        first_audio_s = time.perf_counter() - started

        self._playing = asyncio.ensure_future(_play(audio.wav_bytes))
        try:
            await self._playing
        except asyncio.CancelledError:
            return SpokenSentence(text=sentence, first_audio_s=first_audio_s, cut=True)
        finally:
            self._playing = None
        return SpokenSentence(
            text=sentence,
            first_audio_s=first_audio_s,
            played_s=audio.duration_s,
        )

    async def stop(self) -> None:
        """Stop the sound now and discard what was queued."""
        if self._playing is not None and not self._playing.done():
            self._playing.cancel()

    async def aclose(self) -> None:
        """Release the engine and the audio device."""
        await self.stop()
        closing = getattr(self._speaker, "aclose", None)
        if closing is not None:
            await closing()


async def _play(wav_bytes: bytes) -> None:
    """Play a WAV payload on the default output device.

    Separate from :class:`SpeakerVoice` because it is the one part a caller
    routing audio elsewhere — a phone line, a browser, a file — replaces
    wholesale. Cancelling this coroutine stops the sound; that is what makes
    barge-in possible at all.
    """
    try:
        import io

        import numpy as np
        import sounddevice as sd
        import soundfile as sf
    except ImportError as exc:  # pragma: no cover - dependency guard
        raise RuntimeError(
            "playing audio needs a sound card binding. Install it with:\n"
            "    pip install 'discussion-helper[play]'"
        ) from exc

    data, rate = sf.read(io.BytesIO(wav_bytes), dtype="float32", always_2d=False)
    sd.play(np.asarray(data), rate)
    try:
        # Polled rather than `sd.wait()`: that call blocks a whole thread and
        # cannot be cancelled, which would make the interruption arrive only
        # after the sentence finished — the exact failure this package is for.
        while sd.get_stream().active:
            await asyncio.sleep(0.01)
    except asyncio.CancelledError:
        sd.stop()
        raise


async def _in_thread(generator: object) -> AsyncIterator[str]:
    """Consume a blocking generator without freezing the event loop.

    ``chat_stream`` yields from a synchronous HTTP response. Iterating it
    directly in a coroutine blocks the loop between tokens — and the thing
    waiting on that loop is the barge-in watcher, so the agent would become
    deaf for exactly as long as it is talking.

    One ``to_thread`` per item rather than a queue and a worker: the items are
    sub-word strings arriving every few tens of milliseconds, the hop costs
    microseconds, and a queue would need its own shutdown story for the case
    this package cares about most — the consumer breaking out early because
    somebody interrupted.
    """
    iterator = iter(generator)  # type: ignore[call-overload]
    sentinel = object()
    while True:
        piece = await asyncio.to_thread(next, iterator, sentinel)
        if piece is sentinel:
            return
        yield str(piece)
