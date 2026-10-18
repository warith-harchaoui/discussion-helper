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
import re
import time
from collections.abc import AsyncIterator

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
    ) -> None:
        self.language = language
        self.device_name = device_name
        self.device_index = device_index
        self._speech = asyncio.Event()
        self._pipeline: object | None = None

    async def utterances(self) -> AsyncIterator[Utterance]:
        """Yield each completed user turn, as the pipeline closes it."""
        try:
            import vocal_helper as voh
        except ImportError as exc:  # pragma: no cover - dependency guard
            raise RuntimeError(
                "hearing needs vocal-helper and a microphone. Install them with:\n"
                "    pip install 'discussion-helper[listen]'"
            ) from exc

        started = time.perf_counter()
        async for event in voh.sources.from_microphone(
            device_name=self.device_name, device_index=self.device_index
        ):
            # The VAD half, published as it happens: a barge-in cannot wait
            # for the transcript that this same stream will produce later.
            if getattr(event, "is_speech", False):
                self._speech.set()
            text = getattr(event, "text", "") or ""
            if not text:
                continue
            self._speech.clear()
            now = time.perf_counter() - started
            yield Utterance(
                speaker="user",
                text=text,
                started_s=getattr(event, "t0", now),
                ended_s=getattr(event, "t1", now),
            )

    async def speech_started(self) -> None:
        """Return as soon as the VAD says somebody is talking."""
        self._speech.clear()
        await self._speech.wait()

    async def aclose(self) -> None:
        """Release the microphone."""
        closing = getattr(self._pipeline, "aclose", None)
        if closing is not None:  # pragma: no cover - depends on the sibling
            await closing()


class LocalResponder:
    """Answers, with whatever model fits this machine.

    Parameters
    ----------
    system : str
        The instruction the model is given. The default asks for brevity, and
        that is a latency decision rather than a style one: an agent that
        talks for ninety seconds is one the user has to interrupt, and
        interruption is the expensive path.
    max_sentences : int
        Stop after this many sentences even if the model keeps going.

    Notes
    -----
    Sentences are emitted as soon as they are complete rather than when the
    answer is. Waiting for the whole reply adds its entire generation time to
    the silence the user sits through; yielding the first sentence removes all
    but its own share.
    """

    DEFAULT_SYSTEM = (
        "You are speaking out loud, not writing. Answer in one or two short "
        "sentences. No lists, no markdown, no headings — none of it can be "
        "heard. If the question needs a long answer, give the short one and "
        "offer to go further."
    )

    def __init__(self, *, system: str = "", max_sentences: int = 4) -> None:
        self.system = system or self.DEFAULT_SYSTEM
        self.max_sentences = max_sentences

    async def reply(self, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        """Yield the answer one sentence at a time."""
        try:
            import best_engine_ai_helper as beh
        except ImportError as exc:  # pragma: no cover - dependency guard
            raise RuntimeError(
                "answering needs a local model. Install it with:\n"
                "    pip install 'discussion-helper[think]'"
            ) from exc

        full = [{"role": "system", "content": self.system}, *messages]
        pending = ""
        emitted = 0

        async for piece in _as_async(beh.chat(full, stream=True)):
            pending += piece
            # Split on every arrival rather than buffering to a size: the
            # first sentence is the only one on the latency path, and a
            # buffer would hold it back for the benefit of the ones that are
            # not.
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
            # The last sentence rarely ends in punctuation — models stop
            # mid-flow — so the tail is spoken rather than dropped.
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
            return SpokenSentence(
                text=sentence, first_audio_s=first_audio_s, cut=True
            )
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


async def _as_async(stream: object) -> AsyncIterator[str]:
    """Iterate a stream that may be sync or async.

    Chat clients differ on this and the difference is not interesting here.
    """
    if hasattr(stream, "__aiter__"):
        async for piece in stream:  # type: ignore[union-attr]
            yield str(piece)
        return
    for piece in stream:  # type: ignore[union-attr]
        yield str(piece)
        # Yield to the loop between pieces, or a synchronous generator would
        # starve the barge-in watcher for the whole reply.
        await asyncio.sleep(0)
