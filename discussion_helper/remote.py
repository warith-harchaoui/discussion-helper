"""
The microphone at the other end of a socket.

Module summary
--------------
A browser has a microphone and a speaker; a server has the model. That is the
ordinary shape of a voice agent, and it is a real product rather than a
compromise — every hosted voice agent works this way. The audio crosses the
wire as PCM, which is what WebRTC and WebSocket transports carry underneath
their own framing.

So the two device-bound parts get a second implementation each. The
:class:`RemoteListener` reads frames a client pushes in instead of opening a
microphone; the :class:`RemoteVoice` hands synthesised audio back to the
client instead of a sound card. The loop does not know the difference — which
is the point of it being written against protocols.

What crossing a network changes, and what it does not
-----------------------------------------------------
It does not change the floor, the interruption, or the budget's shape. It
changes two things, and both are honest to state:

**The budget grows a network leg**, 30–80 ms each way on a good link and a
tail that is much worse than its median. On a local-first deployment — the
browser and the server on one machine — it is nothing. Across the internet it
is the line that decides whether 800 ms is reachable at all.

**Echo moves to the client.** The server never sees the room, so it cannot
tell the agent's voice from the user's. The browser can: `getUserMedia` has
had `echoCancellation` for years, and it is better than anything this package
could do at this end. A client that turns it off gets the self-interruption
described in KNOWLEDGE.md §4, and no server-side grace period fully rescues
it.

Author
------
Warith HARCHAOUI — https://linkedin.com/in/warith-harchaoui/
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator

from discussion_helper.types import SpokenSentence, Utterance


class RemoteListener:
    """Hears whatever a client pushes in.

    Two ways to push, because two kinds of client exist and pretending
    otherwise would force one of them to lie:

    * :meth:`push_text` — the client already has a transcript. A browser using
      the Web Speech API, a phone system with its own recogniser, a test.
    * :meth:`push_audio` — the client has PCM and wants this end to listen.
      Frames are handed to a recogniser the caller supplies; without one, this
      raises rather than silently dropping the audio.

    :meth:`speech_started` is driven by :meth:`mark_speaking`, which the
    transport calls when its own voice activity detection fires. It is kept
    separate from the audio path on purpose: a barge-in has to travel on the
    first syllable, and waiting for a transcript would make it a sentence late
    — on a network, a sentence plus a round trip.

    Parameters
    ----------
    recogniser : callable or None
        ``(pcm, sample_rate) -> str``, awaited. Required only for
        :meth:`push_audio`.
    sample_rate : int
        What the client is sending. 16 kHz is what every recogniser in this
        suite wants and what `capture-helper` produces.
    """

    def __init__(
        self,
        *,
        recogniser: object | None = None,
        sample_rate: int = 16_000,
    ) -> None:
        self.recogniser = recogniser
        self.sample_rate = sample_rate
        self.closed = False
        self._turns: asyncio.Queue[Utterance | None] = asyncio.Queue()
        self._speech = asyncio.Event()
        self._started = time.perf_counter()

    # -- what the transport calls -----------------------------------------

    def push_text(self, text: str) -> None:
        """Hand in a finished turn the client already transcribed."""
        if not text.strip():
            return
        now = time.perf_counter() - self._started
        self._speech.clear()
        self._turns.put_nowait(
            Utterance(speaker="user", text=text, started_s=now, ended_s=now)
        )

    async def push_audio(self, pcm: bytes) -> None:
        """Hand in one completed utterance's worth of PCM.

        A *completed* utterance, not a frame: deciding where a turn ends is
        turn detection, and this package does none of it (KNOWLEDGE.md §3).
        A transport that has raw frames should run them through
        ``vocal-helper``'s VAD and end-of-turn stages and call this with what
        comes out.
        """
        if self.recogniser is None:
            raise RuntimeError(
                "this listener was given audio and no recogniser. Either pass "
                "`recogniser=` when building it, or have the client send text "
                "with push_text()."
            )
        text = await self.recogniser(pcm, self.sample_rate)  # type: ignore[operator]
        self.push_text(str(text))

    def mark_speaking(self) -> None:
        """The client's VAD says somebody started talking.

        Called on the first syllable, not on the first word: this is what
        releases a barge-in, and a barge-in that waited for a word would be
        late by a word plus a network leg.
        """
        self._speech.set()

    def end(self) -> None:
        """No more turns are coming; the conversation may finish."""
        self._turns.put_nowait(None)

    # -- the Listener protocol --------------------------------------------

    async def utterances(self) -> AsyncIterator[Utterance]:
        """Yield each turn the client pushed, in order."""
        while True:
            turn = await self._turns.get()
            if turn is None:
                return
            yield turn

    async def speech_started(self) -> None:
        """Return when the client's VAD reports speech."""
        self._speech.clear()
        await self._speech.wait()

    async def aclose(self) -> None:
        self.closed = True
        self.end()


class RemoteVoice:
    """Sends the audio back instead of playing it.

    The sentence is synthesised here — the model is on this end — and the
    samples go out over whatever the transport hands in. What makes this a
    voice rather than a function call is :meth:`stop`: it fires a cancellation
    the transport is expected to honour by **discarding** whatever it has
    buffered, not by letting it drain. A client that plays out its buffer
    reproduces, at the far end, exactly the deafness KNOWLEDGE.md §4 is about
    — and from the server's logs the interruption will look like it worked.

    Parameters
    ----------
    send : callable
        ``(wav_bytes, sentence) -> None``, awaited, called once per sentence.
    on_stop : callable or None
        Awaited when an interruption lands, so the transport can tell its
        client to drop what it is holding.
    synthesise : callable or None
        ``(sentence) -> (wav_bytes, duration_s)``, awaited. Defaults to
        ``speaker-helper``.
    """

    def __init__(
        self,
        send: object,
        *,
        on_stop: object | None = None,
        synthesise: object | None = None,
        voice: str = "",
        language: str = "",
    ) -> None:
        self.send = send
        self.on_stop = on_stop
        self._synthesise = synthesise
        self.voice = voice
        self.language = language
        self._speaker: object | None = None
        self._sending: asyncio.Task[None] | None = None

    async def _render(self, sentence: str) -> tuple[bytes, float]:
        """Synthesise one sentence, through the injected hook or the engine."""
        if self._synthesise is not None:
            return await self._synthesise(sentence)  # type: ignore[operator]

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
        audio = await self._speaker.say(  # type: ignore[attr-defined]
            sentence, language=self.language or None
        )
        return audio.wav_bytes, audio.duration_s

    async def speak(self, sentence: str) -> SpokenSentence:
        """Synthesise one sentence and push it to the client."""
        started = time.perf_counter()
        wav_bytes, duration_s = await self._render(sentence)
        first_audio_s = time.perf_counter() - started

        self._sending = asyncio.ensure_future(self.send(wav_bytes, sentence))  # type: ignore[operator]
        try:
            await self._sending
        except asyncio.CancelledError:
            return SpokenSentence(text=sentence, first_audio_s=first_audio_s, cut=True)
        finally:
            self._sending = None
        return SpokenSentence(
            text=sentence, first_audio_s=first_audio_s, played_s=duration_s
        )

    async def stop(self) -> None:
        """Stop sending, and tell the client to drop what it holds."""
        if self._sending is not None and not self._sending.done():
            self._sending.cancel()
        if self.on_stop is not None:
            await self.on_stop()  # type: ignore[operator]

    async def aclose(self) -> None:
        """Release the engine."""
        await self.stop()
        closing = getattr(self._speaker, "aclose", None)
        if closing is not None:
            await closing()
