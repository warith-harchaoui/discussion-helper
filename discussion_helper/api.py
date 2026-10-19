"""
The HTTP surface: a conversation you can watch, interrupt and end.

Module summary
--------------
A spoken conversation does not fit a request. It has no single answer, it
lasts minutes, and the interesting part is what happens *during* it. So this
surface is not one endpoint that returns a reply — it is a session you create,
a stream you follow, and a button you press.

Three ways in, and they are genuinely different products rather than three
spellings of one:

* **A local session** (``POST /sessions``) opens the microphone *on this
  machine*. The caller is a dashboard, a hotkey, an agent — something that
  starts a conversation it is not itself part of, and then watches.
* **A remote session** (``POST /sessions`` with ``transport="remote"``, then
  ``WS /sessions/{id}/audio``) puts the microphone at the other end of the
  socket. The browser captures and plays; this end recognises, thinks and
  speaks. That is how every hosted voice agent works, and the audio really
  does cross the wire as PCM.
* **A single text turn** (``POST /turn``) runs one exchange through the same
  loop with no audio at all. The honest use is testing — and it is what makes
  the MCP surface meaningful, since an agent has no microphone.

What this surface refuses to pretend
------------------------------------
It does not pretend an HTTP request can hold a microphone. ``POST /sessions``
returns immediately with an id; everything live happens on the event stream or
the socket. And ``POST /sessions/{id}/interrupt`` goes through the same
:meth:`Voice.stop` the microphone's barge-in uses, because a button that
stopped the audio some other way would stop it in some *other* way.

Author
------
Warith HARCHAOUI — https://linkedin.com/in/warith-harchaoui/
"""

from __future__ import annotations

import asyncio
import base64
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

try:
    from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
    from fastapi.responses import StreamingResponse
    from pydantic import BaseModel, Field
except ImportError as exc:  # pragma: no cover - dependency guard
    raise ImportError(
        "The HTTP surface requires the [server] extra. Install with:\n"
        "    pip install 'discussion-helper[server]'"
    ) from exc

from discussion_helper.discussion import Policy
from discussion_helper.session import Session, Sessions


class StartRequest(BaseModel):
    """Body for ``POST /sessions``.

    Parameters
    ----------
    transport : str
        ``"local"`` opens the microphone on the machine running this server.
        ``"remote"`` waits for a client to connect to the session's WebSocket
        and send audio or text. ``"fake"`` uses scripted parts — the same loop
        with no hardware, which is what makes this surface testable and what
        a caller should reach for first.
    turns : list of str
        For ``"fake"`` only: what the user says.
    allow_barge_in, barge_in_grace_s, max_reply_sentences, silence_timeout_s
        The policy. See :class:`~discussion_helper.discussion.Policy`.
    voice, language
        Passed to the voice.
    """

    transport: str = Field("fake", pattern="^(local|remote|fake)$")
    turns: list[str] = Field(default_factory=list)
    allow_barge_in: bool = True
    barge_in_grace_s: float = 0.35
    max_reply_sentences: int = 0
    silence_timeout_s: float = 0.0
    voice: str = ""
    language: str = ""


class TurnRequest(BaseModel):
    """Body for ``POST /turn``: one exchange, no audio."""

    text: str = Field(..., min_length=1, description="What the user said.")
    history: list[dict[str, str]] = Field(
        default_factory=list, description="Earlier turns, as role/content pairs."
    )
    with_audio: bool = Field(
        False, description="Also synthesise the reply and return it base64-encoded."
    )
    voice: str = ""
    language: str = ""


def _policy(request: StartRequest) -> Policy:
    return Policy(
        allow_barge_in=request.allow_barge_in,
        barge_in_grace_s=request.barge_in_grace_s,
        max_reply_sentences=request.max_reply_sentences,
        silence_timeout_s=request.silence_timeout_s,
    )


def create_app(sessions: Sessions | None = None) -> FastAPI:
    """Build the application.

    Parameters
    ----------
    sessions : Sessions or None
        Injectable so a test can hold the registry it asserts against, and so
        two apps in one process do not share conversations.
    """
    registry = sessions or Sessions()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        """Stop every conversation on the way down.

        A microphone left open outlives the process that opened it on some
        platforms — which a user discovers from a recording indicator that
        will not go away.
        """
        yield
        await registry.aclose()

    app = FastAPI(
        title="discussion-helper",
        version=_version(),
        lifespan=lifespan,
        description=(
            "A spoken conversation you can watch, interrupt and end. Sessions "
            "rather than requests, because a conversation does not fit one."
        ),
    )

    # -- is this machine able to hold a conversation at all? ---------------

    @app.get("/health", operation_id="health")
    async def health() -> dict:
        """Whether each of the three parts could run here, and what is missing.

        Asked of the three separately, because they fail separately and the
        answer "it does not work" is useless when two thirds of it does.
        """
        return {
            "status": "ok",
            "version": _version(),
            "sessions": len(registry),
            "parts": {
                "listen": _probe("vocal_helper", "discussion-helper[listen]"),
                "think": _probe("best_engine_ai_helper", "discussion-helper[think]"),
                "speak": _probe("speaker_helper", "discussion-helper[speak]"),
                "play": _probe("sounddevice", "discussion-helper[play]"),
            },
        }

    # -- sessions ----------------------------------------------------------

    @app.post("/sessions", operation_id="start_session")
    async def start_session(request: StartRequest) -> dict:
        """Start a conversation and return its id immediately.

        It returns before the conversation does anything, and that is the
        design rather than a limitation: a request cannot hold a microphone
        open for five minutes. Follow ``/sessions/{id}/events``.
        """
        try:
            session = Session(*_parts_for(request), _policy(request))
        except RuntimeError as exc:
            # A missing extra, named. A 503 rather than a 500: the server is
            # fine, this machine simply cannot do that half.
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        registry.add(session)
        if request.transport != "remote":
            session.start()
        # A remote session waits for its socket. There is nothing for it to do
        # before one connects — the microphone is at the other end — and
        # starting it here would run the silence timeout against a client that
        # has not finished loading its page.
        return {"id": session.id, "transport": request.transport, **session.state}

    @app.get("/sessions", operation_id="list_sessions")
    async def list_sessions() -> dict:
        """Every conversation this process is holding."""
        return {"ids": registry.ids()}

    @app.get("/sessions/{session_id}", operation_id="read_session")
    async def read_session(session_id: str) -> dict:
        """The transcript, the floor and the timings, as they stand."""
        return _require(registry, session_id).state

    @app.get("/sessions/{session_id}/events", operation_id="follow_session")
    async def follow_session(session_id: str) -> StreamingResponse:
        """Follow the conversation as Server-Sent Events.

        A late subscriber sees what happens next, not what it missed —
        replaying the transcript into the stream would make a reconnecting
        client hear the whole conversation again. The transcript is one `GET`
        away.
        """
        session = _require(registry, session_id)

        async def stream() -> AsyncIterator[bytes]:
            async for event in session.events():
                yield f"data: {json.dumps(event.as_dict(), ensure_ascii=False)}\n\n".encode()

        return StreamingResponse(stream(), media_type="text/event-stream")

    @app.post("/sessions/{session_id}/interrupt", operation_id="interrupt_session")
    async def interrupt_session(session_id: str) -> dict:
        """Stop the agent now, as a person talking over it would.

        ``interrupted: false`` is not a failure — it means the agent was not
        speaking, which is the common case for a button pressed a moment too
        late.
        """
        session = _require(registry, session_id)
        return {"interrupted": await session.interrupt(), **session.state}

    @app.post("/sessions/{session_id}/say", operation_id="say_to_session")
    async def say_to_session(session_id: str, body: dict) -> dict:
        """Push a user turn in as text, for a remote session.

        The client already has a transcript — a browser using the Web Speech
        API, a phone system with its own recogniser — so this end does not
        listen, it only answers and speaks.
        """
        session = _require(registry, session_id)
        listener = session.discussion.listener
        push = getattr(listener, "push_text", None)
        if push is None:
            raise HTTPException(
                status_code=409,
                detail=(
                    "this session listens to its own microphone; it cannot be "
                    "handed text. Start one with transport=remote to push turns in."
                ),
            )
        push(str(body.get("text", "")))
        return session.state

    @app.delete("/sessions/{session_id}", operation_id="end_session")
    async def end_session(session_id: str) -> dict:
        """End the conversation and release what it held."""
        _require(registry, session_id)
        conversation = await registry.remove(session_id)
        assert conversation is not None  # _require would have raised
        return {
            "ended": session_id,
            "utterances": [
                {"speaker": u.speaker, "text": u.text, "interrupted": u.interrupted}
                for u in conversation.utterances
            ],
            "timings": [t.as_dict() for t in conversation.timings],
        }

    # -- the microphone at the other end -----------------------------------

    @app.websocket("/sessions/{session_id}/audio")
    async def audio(websocket: WebSocket, session_id: str) -> None:
        """Carry the conversation's audio, both ways.

        The client sends JSON control frames and binary PCM; the server sends
        JSON events and binary WAV. Two frame types rather than one encoding,
        because base64 on a continuous audio stream is a third more bytes for
        nothing — the text channel is for *events*, and events are small.

        The client's duties, and they are not optional:

        * ``{"type": "speaking"}`` on the **first syllable**, from its own
          voice activity detection. This is what releases a barge-in, and the
          server cannot derive it — it never hears the room.
        * ``{"type": "text", "text": ...}`` or binary PCM for a **completed**
          turn. Where a turn ends is turn detection, and this package does
          none (KNOWLEDGE.md §3).
        * Drop buffered audio on ``{"kind": "stop"}``. Playing it out
          reproduces, at the far end, exactly the deafness that stopping it
          here was meant to prevent.
        """
        session = registry.get(session_id)
        if session is None:
            await websocket.close(code=4404, reason="no such session")
            return
        listener = session.discussion.listener
        if not hasattr(listener, "push_text"):
            await websocket.close(code=4409, reason="this session owns its microphone")
            return

        await websocket.accept()
        _bind_socket(session, websocket)
        if not session.started:
            # Started here, on the loop that will run it, and not when the
            # session was created: a conversation whose microphone is at the
            # far end begins when the far end arrives.
            session.start()

        events = asyncio.ensure_future(_pump_events(session, websocket))
        try:
            while True:
                message = await websocket.receive()
                if message.get("type") == "websocket.disconnect":
                    break
                if (payload := message.get("bytes")) is not None:
                    await listener.push_audio(payload)  # type: ignore[attr-defined]
                    continue
                if (text := message.get("text")) is not None:
                    await _handle_control(listener, json.loads(text))
        except (WebSocketDisconnect, RuntimeError):
            pass
        finally:
            events.cancel()
            listener.end()  # type: ignore[attr-defined]

    # -- one turn, no audio ------------------------------------------------

    @app.post("/turn", operation_id="take_turn")
    async def take_turn(request: TurnRequest) -> dict:
        """Run one exchange through the loop, with no session and no audio.

        This is the shape an agent can actually use — it has no microphone —
        and the shape a test wants. The reply comes back as sentences because
        that is the unit the loop speaks in, and joining them here would hide
        where it would have stopped had somebody interrupted.
        """
        from discussion_helper.adapters import LocalResponder

        messages = [*request.history, {"role": "user", "content": request.text}]
        sentences: list[str] = []
        try:
            async for sentence in LocalResponder().reply(messages):
                sentences.append(sentence)
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

        answer: dict[str, Any] = {"sentences": sentences, "text": " ".join(sentences)}
        if request.with_audio and sentences:
            answer["audio_wav_base64"] = await _synthesise_base64(
                " ".join(sentences), request.voice, request.language
            )
        return answer

    _mount_mcp(app)
    return app


# ── helpers ────────────────────────────────────────────────────────────────


def _require(registry: Sessions, session_id: str) -> Session:
    """The session, or a 404 naming the id that was asked for."""
    session = registry.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"no session {session_id!r}")
    return session


def _parts_for(request: StartRequest) -> tuple[Any, Any, Any]:
    """The three parts a transport implies."""
    if request.transport == "fake":
        from discussion_helper.testing import (
            EchoResponder,
            ScriptedListener,
            SilentVoice,
        )

        return (
            ScriptedListener(request.turns or ["bonjour"]),
            EchoResponder(sentences=2),
            SilentVoice(seconds_per_sentence=0.2),
        )

    from discussion_helper.adapters import LocalResponder

    if request.transport == "local":
        from discussion_helper.adapters import SpeakerVoice, VocalListener

        return (
            VocalListener(language=request.language),
            LocalResponder(),
            SpeakerVoice(voice=request.voice, language=request.language),
        )

    from discussion_helper.remote import RemoteListener, RemoteVoice

    listener = RemoteListener()

    async def _unbound(*_: object) -> None:
        """Until a socket connects there is nowhere to send audio.

        Dropped rather than buffered: a reply synthesised before anybody is
        listening is a reply nobody asked for, and holding it would play it
        at whoever connects next.
        """
        return None

    return (
        listener,
        LocalResponder(),
        RemoteVoice(_unbound, voice=request.voice, language=request.language),
    )


def _bind_socket(session: Session, websocket: WebSocket) -> None:
    """Point the session's voice at this socket."""
    voice = session.discussion.voice

    async def send(wav_bytes: bytes, sentence: str) -> None:
        await websocket.send_text(
            json.dumps({"kind": "speaking", "text": sentence}, ensure_ascii=False)
        )
        await websocket.send_bytes(wav_bytes)

    async def on_stop() -> None:
        # The client must honour this by *discarding*. Said in the protocol
        # docs and repeated here because it is the one instruction whose
        # breach is invisible from this end.
        await websocket.send_text(json.dumps({"kind": "stop"}))

    voice.send = send  # type: ignore[attr-defined]
    voice.on_stop = on_stop  # type: ignore[attr-defined]


async def _handle_control(listener: Any, frame: dict) -> None:
    """One JSON control frame from the client."""
    kind = frame.get("type")
    if kind == "speaking":
        listener.mark_speaking()
    elif kind == "text":
        listener.push_text(str(frame.get("text", "")))
    elif kind == "end":
        listener.end()


async def _pump_events(session: Session, websocket: WebSocket) -> None:
    """Forward the session's events to the client."""
    try:
        async for event in session.events():
            await websocket.send_text(json.dumps(event.as_dict(), ensure_ascii=False))
    except (WebSocketDisconnect, RuntimeError, asyncio.CancelledError):
        return


async def _synthesise_base64(text: str, voice: str, language: str) -> str:
    """One sentence of audio, encoded for a JSON body."""
    try:
        from speaker_helper import Settings, Speaker
    except ImportError as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "audio needs speaker-helper. Install it with:\n"
                "    pip install 'discussion-helper[speak]'"
            ),
        ) from exc
    async with Speaker(
        Settings.from_mapping(
            {"backend": "kokoro", "voice": voice, "language": language or "fr"}
        )
    ) as speaker:
        audio = await speaker.say(text, language=language or None)
    return base64.b64encode(audio.wav_bytes).decode("ascii")


def _probe(module: str, extra: str) -> dict:
    """Whether one half is installed, and the line that installs it."""
    import importlib.util

    try:
        found = importlib.util.find_spec(module) is not None
    except (ImportError, ModuleNotFoundError, ValueError):
        found = False
    return {"available": found} if found else {"available": False, "fix": f"pip install '{extra}'"}


def _version() -> str:
    from discussion_helper import __version__

    return __version__


def _mount_mcp(app: FastAPI) -> None:
    """Republish the routes as agent tools, if the extra is installed.

    Guarded against ``Exception`` and not only ``ImportError``, and that width
    is borrowed from a scar in a sibling package: ``fastapi-mcp`` 0.4.0 called
    the ``mcp`` SDK with an argument count it no longer accepted, the
    resulting ``TypeError`` escaped ``create_app()``, and an optional surface
    took down the entire HTTP API. An agent tool nobody can reach is a missing
    feature; an API that will not construct is an outage.
    """
    try:
        from fastapi_mcp import FastApiMCP
    except ImportError:
        return

    try:
        server = FastApiMCP(
            app,
            name="discussion-helper",
            description=(
                "Hold and watch a spoken conversation: start a session, follow "
                "its transcript and latency, interrupt the agent, take a single "
                "turn as text."
            ),
        )
        if hasattr(server, "mount_http"):
            server.mount_http()
        else:  # pragma: no cover - legacy fastapi-mcp
            server.mount()
    except Exception as exc:  # pragma: no cover - version-pairing guard
        import os_helper as osh

        osh.warn(
            f"MCP surface not mounted ({type(exc).__name__}: {exc}). The HTTP "
            f"API is unaffected; `pip install 'discussion-helper[mcp]'` "
            f"installs a pairing known to work."
        )


app = None  # built by `create_app`; uvicorn targets `discussion_helper.api:build`


def build() -> FastAPI:
    """ASGI factory, for ``uvicorn discussion_helper.api:build --factory``."""
    return create_app()
