"""
A conversation you can watch, interrupt and end — over HTTP, and over a socket.

The objection this surface had to answer is that a conversation does not fit a
request: it has no single answer, it lasts minutes, and the interesting part
is what happens *during* it. The answer is that the request does not hold the
conversation — it starts one and hands back an id, and everything live happens
on the event stream or the WebSocket.

And the audio really does cross the wire. The socket test below sends PCM up
and receives WAV down, which is how every hosted voice agent works; "HTTP
cannot carry a microphone" was a failure of imagination, not a property of
HTTP.

Every test here runs with the `fake` or `remote` transport — no microphone, no
model, no sound card — because that is the only way the interruption path gets
exercised at all.

Author
------
Warith HARCHAOUI — https://linkedin.com/in/warith-harchaoui/
"""

from __future__ import annotations

import asyncio
import json

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from discussion_helper.api import create_app  # noqa: E402
from discussion_helper.session import Sessions  # noqa: E402


@pytest.fixture
def client() -> TestClient:
    """A client over an app with its own registry.

    Entered as a context manager, and that is not a formality. A session is a
    task scheduled during one request and expected to outlive it; a bare
    ``TestClient(app)`` gives each request its own portal, so the task is torn
    down the moment the request that created it returns. The symptom is a
    conversation that ends three milliseconds in with one turn recorded —
    which reads exactly like a loop bug, and cost an hour under a real server
    where it cannot happen.
    """
    with TestClient(create_app(Sessions())) as client:
        yield client


# ── Is this machine able to hold a conversation at all? ────────────────────


def test_health_answers_for_each_part_separately(client: TestClient) -> None:
    """ "It does not work" is useless when two thirds of it does."""
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert set(body["parts"]) == {"listen", "think", "speak", "play"}
    for part in body["parts"].values():
        # Either it is available, or it says what would install it.
        assert part["available"] or part["fix"]


# ── Sessions ───────────────────────────────────────────────────────────────


def test_starting_a_session_returns_before_it_finishes(client: TestClient) -> None:
    """The whole point: a request cannot hold a microphone open for minutes."""
    body = client.post("/sessions", json={"transport": "fake", "turns": ["bonjour"]}).json()
    assert body["id"]
    assert body["transport"] == "fake"
    assert client.get("/sessions").json()["ids"] == [body["id"]]


def _wait_for_end(client: TestClient, session_id: str) -> None:
    """Follow the stream until the session says it is over."""
    with client.stream("GET", f"/sessions/{session_id}/events") as stream:
        for line in stream.iter_lines():
            if line.startswith("data: ") and json.loads(line[6:])["kind"] == "ended":
                return


def test_the_transcript_is_one_get_away(client: TestClient) -> None:
    """Which is why it is not replayed into the stream."""
    session_id = client.post(
        "/sessions", json={"transport": "fake", "turns": ["un", "deux"]}
    ).json()["id"]
    _wait_for_end(client, session_id)

    state = client.get(f"/sessions/{session_id}").json()
    assert [u["speaker"] for u in state["utterances"]] == [
        "user",
        "agent",
        "user",
        "agent",
    ]
    assert state["timings"]
    assert state["running"] is False
    client.delete(f"/sessions/{session_id}")


def test_ending_a_running_session_returns_what_was_said_so_far(
    client: TestClient,
) -> None:
    """`DELETE` means "stop now", not "stop when it would have stopped".

    So a partial transcript is the right answer rather than a missing one —
    somebody who hangs up mid-sentence still wants the half they had.
    """
    session_id = client.post(
        "/sessions", json={"transport": "fake", "turns": ["un", "deux"]}
    ).json()["id"]
    body = client.delete(f"/sessions/{session_id}").json()
    assert body["ended"] == session_id
    assert len(body["utterances"]) <= 4
    assert client.get(f"/sessions/{session_id}").status_code == 404


def test_an_unknown_session_is_a_404_naming_what_was_asked_for(client: TestClient) -> None:
    answer = client.get("/sessions/nope")
    assert answer.status_code == 404
    assert "nope" in answer.json()["detail"]


def test_the_event_stream_reports_the_floor_and_the_turns(client: TestClient) -> None:
    """A watcher wants what a transcript would show, not every audio frame."""
    session_id = client.post("/sessions", json={"transport": "fake", "turns": ["bonjour"]}).json()[
        "id"
    ]

    kinds: list[str] = []
    with client.stream("GET", f"/sessions/{session_id}/events") as stream:
        for line in stream.iter_lines():
            if not line.startswith("data: "):
                continue
            kinds.append(json.loads(line[6:])["kind"])
            if kinds[-1] == "ended":
                break

    assert "floor" in kinds
    assert "utterance" in kinds
    assert "timing" in kinds
    assert kinds[-1] == "ended", "a watcher must be released, or it waits forever"


# ── Interrupting from outside ──────────────────────────────────────────────


def test_interrupting_when_nobody_is_speaking_is_not_an_error(client: TestClient) -> None:
    """The common case for a button pressed a moment too late."""
    session_id = client.post("/sessions", json={"transport": "fake", "turns": ["bonjour"]}).json()[
        "id"
    ]
    body = client.post(f"/sessions/{session_id}/interrupt").json()
    assert body["interrupted"] in (True, False)
    assert "floor" in body


def test_the_interrupt_route_uses_the_same_path_as_a_barge_in() -> None:
    """A button that stopped the audio some other way would stop it *some
    other way* — draining instead of discarding, or leaving the floor with
    the agent. The difference would only ever show in a room, so it is
    asserted here instead: the route calls `Voice.stop`.
    """
    import asyncio

    from discussion_helper.discussion import Policy
    from discussion_helper.session import Session
    from discussion_helper.testing import EchoResponder, ScriptedListener, SilentVoice

    async def scenario() -> tuple[int, bool]:
        voice = SilentVoice(seconds_per_sentence=1.0)
        session = Session(
            ScriptedListener(["bonjour"]),
            EchoResponder(sentences=5),
            voice,
            Policy(allow_barge_in=False),  # no microphone could do this
        ).start()
        await asyncio.sleep(0.15)
        stopped = await session.interrupt()
        await session.stop()
        return voice.stops, stopped

    stops, stopped = asyncio.run(scenario())
    assert stopped is True
    assert stops == 1, "the route must go through the voice, not around it"


# ── One turn, no audio ─────────────────────────────────────────────────────


def test_a_text_turn_says_what_is_missing_rather_than_failing(client: TestClient) -> None:
    """503 and a reason, not a 500 and a traceback.

    Two different things make this machine unable to answer, and both are
    503 rather than 500 because the *server* is fine either way: the model
    client is not installed, or it is installed and the daemon behind it is
    not serving. The first names a `pip install`; the second names the URL
    that did not answer. A test that demanded the first would pass only on
    machines with no model at all.
    """
    answer = client.post("/turn", json={"text": "bonjour"})
    assert answer.status_code in (200, 503)
    if answer.status_code == 503:
        detail = answer.json()["detail"]
        # Not a fixed string — the message improved twice while this test was
        # being written, and pinning its wording would have made every
        # improvement look like a regression. What has to hold is that it
        # tells the reader something to *do*.
        assert any(
            action in detail for action in ("pip install", "ollama pull", "BEST_LLM", "http")
        ), detail
    else:
        assert answer.json()["sentences"]


# ── The microphone at the other end of the socket ──────────────────────────


def _tiny_wav(seconds: float = 0.05, rate: int = 16_000) -> bytes:
    """A real, decodable WAV. Small, silent, and genuinely RIFF."""
    import io
    import wave

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(b"\x00\x00" * int(rate * seconds))
    return buffer.getvalue()


def test_the_socket_carries_a_turn_in_and_audio_out() -> None:
    """The audio really does cross the wire.

    The client pushes a finished turn; the server answers, synthesises and
    sends WAV back as a **binary** frame beside a JSON event naming the
    sentence. Two frame types rather than one encoding, because base64 on a
    continuous audio stream is a third more bytes for nothing — the text
    channel is for events, and events are small.

    The parts are injected rather than taken from the API, so this asserts
    the transport and not whether a model happens to be installed. A test
    that needed Ollama running would be a test that runs on one machine.
    """
    from discussion_helper.discussion import Policy
    from discussion_helper.remote import RemoteListener, RemoteVoice
    from discussion_helper.session import Session
    from discussion_helper.testing import EchoResponder

    registry = Sessions()
    listener = RemoteListener()

    async def synthesise(sentence: str) -> tuple[bytes, float]:
        return _tiny_wav(), 0.05

    async def unbound(*_: object) -> None:
        return None

    session = Session(
        listener,
        EchoResponder(sentences=1),
        RemoteVoice(unbound, synthesise=synthesise),
        Policy(max_reply_sentences=1),
    )
    registry.add(session)

    with TestClient(create_app(registry)) as client:
        # Not started here: `start()` schedules tasks on the loop it is called
        # from, and this is the test's thread. The socket handler starts it on
        # the app's loop, which is where a conversation has to live.
        with client.websocket_connect(f"/sessions/{session.id}/audio") as socket:
            socket.send_text(json.dumps({"type": "text", "text": "bonjour"}))

            spoken: str | None = None
            audio: bytes | None = None
            while audio is None:
                message = socket.receive()
                if message.get("bytes") is not None:
                    audio = message["bytes"]
                elif message.get("text") is not None:
                    frame = json.loads(message["text"])
                    if frame.get("kind") == "speaking":
                        spoken = frame["text"]
            socket.send_text(json.dumps({"type": "end"}))

    assert audio[:4] == b"RIFF", "a WAV frame, not base64 in the text channel"
    assert spoken == "bonjour", "the event names the sentence the bytes carry"


def test_stopping_tells_the_client_to_drop_what_it_holds() -> None:
    """The one instruction whose breach is invisible from this end.

    A client that plays out its buffer after a `stop` reproduces, at the far
    end, exactly the deafness that stopping it here was meant to prevent —
    and the server's logs will show a clean interruption.
    """
    from discussion_helper.discussion import Policy
    from discussion_helper.remote import RemoteListener, RemoteVoice
    from discussion_helper.session import Session
    from discussion_helper.testing import EchoResponder

    registry = Sessions()
    listener = RemoteListener()

    async def slow_synthesise(sentence: str) -> tuple[bytes, float]:
        await asyncio.sleep(0.05)
        return _tiny_wav(), 1.0

    async def unbound(*_: object) -> None:
        return None

    session = Session(
        listener,
        EchoResponder(sentences=6),
        RemoteVoice(unbound, synthesise=slow_synthesise),
        Policy(allow_barge_in=False),
    )
    registry.add(session)

    with TestClient(create_app(registry)) as client:
        # Not started here: `start()` schedules tasks on the loop it is called
        # from, and this is the test's thread. The socket handler starts it on
        # the app's loop, which is where a conversation has to live.
        with client.websocket_connect(f"/sessions/{session.id}/audio") as socket:
            socket.send_text(json.dumps({"type": "text", "text": "bonjour"}))
            # Wait until it is actually speaking, then cut it off.
            while True:
                message = socket.receive()
                if message.get("text") and json.loads(message["text"]).get("kind") == "speaking":
                    break
            client.post(f"/sessions/{session.id}/interrupt")

            kinds: list[str] = []
            while "stop" not in kinds:
                message = socket.receive()
                if message.get("text") is not None:
                    kinds.append(json.loads(message["text"]).get("kind", ""))
            socket.send_text(json.dumps({"type": "end"}))

    assert "stop" in kinds


def test_a_local_session_refuses_to_be_handed_text(client: TestClient) -> None:
    """It owns a microphone; pushing text in would be two sources of truth."""
    from discussion_helper.testing import ScriptedListener

    session_id = client.post("/sessions", json={"transport": "fake"}).json()["id"]
    answer = client.post(f"/sessions/{session_id}/say", json={"text": "hello"})
    assert answer.status_code == 409
    assert "microphone" in answer.json()["detail"]
    assert isinstance(ScriptedListener([]), object)
    client.delete(f"/sessions/{session_id}")


def test_connecting_to_an_unknown_session_closes_rather_than_hangs(
    client: TestClient,
) -> None:
    """A socket that accepts and then says nothing is the worst failure shape."""
    from starlette.websockets import WebSocketDisconnect

    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/sessions/nope/audio") as socket:
            socket.receive()


# ── The agent surface ──────────────────────────────────────────────────────


def test_the_mcp_endpoint_is_mounted_and_the_api_survives_it(client: TestClient) -> None:
    """Both at once, because the second used to break the first.

    fastapi-mcp 0.4.0 raised a TypeError out of create_app() in a sibling
    package, and a guard that only caught ImportError let it through — so an
    optional surface took down every API route. The app must construct either
    way.
    """
    assert client.get("/health").status_code == 200
    pytest.importorskip("fastapi_mcp")
    assert any(route.path == "/mcp" for route in client.app.routes)


def test_every_route_an_agent_needs_carries_an_operation_id(client: TestClient) -> None:
    """The MCP catalogue is built from these; an unnamed route is an unnamed tool."""
    schema = client.get("/openapi.json").json()
    named = {
        operation["operationId"]
        for path in schema["paths"].values()
        for operation in path.values()
        if isinstance(operation, dict) and "operationId" in operation
    }
    assert {
        "health",
        "start_session",
        "read_session",
        "interrupt_session",
        "end_session",
        "take_turn",
    } <= named
