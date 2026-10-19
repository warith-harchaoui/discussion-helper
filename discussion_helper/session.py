"""
A conversation that outlives the call that started it.

Module summary
--------------
:class:`~discussion_helper.discussion.Discussion` is a coroutine: you await it
and it hands back a finished conversation. That is the right shape for a
command line and the wrong one for everything else. A web page, an agent or a
"stop talking" button all need the same three things while the conversation is
still happening — to *see* it, to *interrupt* it, and to *end* it — and none
of them can hold the await.

So a :class:`Session` is a running discussion plus the handle on it: a
background task, a floor you can read, an event stream you can follow, and an
interrupt that goes through **the same barge-in path the microphone uses**.
That last point is what keeps this from being a second implementation of the
loop. A button that stopped the audio some other way would stop it in some
other way — draining instead of discarding, or leaving the floor with the
agent — and the difference would only show in a room.

Why there is a registry
-----------------------
One process, several conversations: a server with two callers, a test that
runs three at once, an agent that starts one and comes back later. The
registry is what makes "come back later" possible, and it is deliberately
in-memory — sessions do not survive a restart, because neither does the
microphone they were listening to.

Author
------
Warith HARCHAOUI — https://linkedin.com/in/warith-harchaoui
"""

from __future__ import annotations

import asyncio
import contextlib
import secrets
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from discussion_helper.discussion import Discussion, Policy
from discussion_helper.parts import Listener, Responder, Voice
from discussion_helper.types import Conversation, Floor, Utterance


@dataclass
class Event:
    """Something worth telling a watcher about, as it happens.

    Deliberately coarse. A watcher wants to know that a turn landed, that the
    floor moved, that the agent was cut off — not every frame of audio. The
    audio has its own channel; this one is for what a transcript would show.

    Parameters
    ----------
    kind : str
        ``"floor"``, ``"utterance"``, ``"timing"`` or ``"ended"``.
    at_s : float
        Seconds since the session started.
    data : dict
        The payload, already JSON-shaped: a watcher is usually a socket.
    """

    kind: str
    at_s: float
    data: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        """The event as it goes on the wire."""
        return {"kind": self.kind, "at_s": round(self.at_s, 3), **self.data}


class Session:
    """A discussion running in the background, with a handle on it.

    Parameters
    ----------
    listener, responder, voice
        The three parts, as :class:`Discussion` takes them.
    policy : Policy
        What to do about interruptions and length.

    Notes
    -----
    Subscribers get their **own** queue rather than sharing one. Two watchers
    reading from one queue each take half the events and neither knows it —
    the kind of bug that looks like a flaky network.
    """

    def __init__(
        self,
        listener: Listener,
        responder: Responder,
        voice: Voice,
        policy: Policy | None = None,
    ) -> None:
        self.id = secrets.token_urlsafe(9)
        self.started_at = time.perf_counter()
        self.discussion = Discussion(listener, responder, voice, policy)
        self._task: asyncio.Task[Conversation] | None = None
        self._subscribers: list[asyncio.Queue[Event | None]] = []
        self._seen_utterances = 0
        self._seen_timings = 0
        self._last_floor: Floor | None = None
        self._watch: asyncio.Task[None] | None = None
        self._ended = False

    # -- lifecycle ---------------------------------------------------------

    @property
    def started(self) -> bool:
        """Whether the conversation has begun."""
        return self._task is not None

    def start(self) -> Session:
        """Begin the conversation in the background and return immediately.

        Must be called from the loop the conversation will run on — the tasks
        are scheduled here. Calling it from another thread binds them to a
        loop nobody is running, and the conversation simply never happens:
        no error, no turns, a session that reports `running` and does nothing.
        """
        if self._task is not None:
            raise RuntimeError(f"session {self.id} has already started")
        self._task = asyncio.ensure_future(self._run())
        self._watch = asyncio.ensure_future(self._publish_changes())
        return self

    async def _run(self) -> Conversation:
        """The discussion itself, plus the final event whatever happens."""
        try:
            return await self.discussion.run()
        finally:
            # Emitted in `finally` so a watcher is released even when the loop
            # raised. A socket left waiting for an "ended" that never comes is
            # indistinguishable, from the far end, from a conversation where
            # nobody is talking.
            self._drain_state()
            self._ended = True
            self._emit(Event(kind="ended", at_s=self._elapsed()))
            for queue in self._subscribers:
                queue.put_nowait(None)

    async def _publish_changes(self) -> None:
        """Turn the conversation's growing state into events.

        Polled rather than pushed, and that is a deliberate trade. The
        alternative is callbacks threaded through the loop, which would make
        the loop know about watchers — and the loop is the one piece in this
        package that is worth keeping free of them. The cost is a 20 ms
        granularity on an event stream whose smallest unit is a spoken
        sentence.
        """
        try:
            while True:
                self._drain_state()
                await asyncio.sleep(0.02)
        except asyncio.CancelledError:
            self._drain_state()
            raise

    def _drain_state(self) -> None:
        """Emit an event for anything that changed since the last look."""
        conversation = self.discussion.conversation
        if conversation.floor is not self._last_floor:
            self._last_floor = conversation.floor
            self._emit(
                Event(
                    kind="floor",
                    at_s=self._elapsed(),
                    data={"floor": conversation.floor.value},
                )
            )
        while self._seen_utterances < len(conversation.utterances):
            utterance = conversation.utterances[self._seen_utterances]
            self._seen_utterances += 1
            self._emit(
                Event(
                    kind="utterance",
                    at_s=self._elapsed(),
                    data={
                        "speaker": utterance.speaker,
                        "text": utterance.text,
                        "interrupted": utterance.interrupted,
                    },
                )
            )
        while self._seen_timings < len(conversation.timings):
            timing = conversation.timings[self._seen_timings]
            self._seen_timings += 1
            self._emit(
                Event(
                    kind="timing",
                    at_s=self._elapsed(),
                    data={**timing.as_dict(), "slowest_stage": timing.slowest_stage},
                )
            )

    def _emit(self, event: Event) -> None:
        """Hand an event to every watcher."""
        for queue in self._subscribers:
            queue.put_nowait(event)

    def _elapsed(self) -> float:
        return time.perf_counter() - self.started_at

    # -- being watched -----------------------------------------------------

    async def events(self) -> AsyncIterator[Event]:
        """Follow the conversation as it happens.

        Yields until the session ends. A subscriber that arrives late sees
        what happens next, not what it missed — the transcript is in
        :attr:`state`, and duplicating it into the stream would make a
        reconnecting client replay the whole conversation.
        """
        if self._ended:
            # Subscribing to a conversation that is already over. It has to
            # end at once, and the first version of this did not: the `None`
            # sentinel goes to the subscribers that exist *at that moment*, so
            # a watcher arriving one tick late waited forever. Which is the
            # exact failure this class's docstring warns about, built into the
            # class that warns about it — and the shape is the worst kind: the
            # far end cannot tell a finished conversation from a silent one.
            yield Event(kind="ended", at_s=self._elapsed())
            return

        queue: asyncio.Queue[Event | None] = asyncio.Queue()
        self._subscribers.append(queue)
        try:
            while True:
                event = await queue.get()
                if event is None:
                    return
                yield event
        finally:
            self._subscribers.remove(queue)

    @property
    def state(self) -> dict[str, Any]:
        """Everything a watcher needs to catch up, in one object."""
        conversation = self.discussion.conversation
        return {
            "id": self.id,
            "floor": conversation.floor.value,
            "running": self._task is not None and not self._task.done(),
            "elapsed_s": round(self._elapsed(), 3),
            "utterances": [
                {
                    "speaker": u.speaker,
                    "text": u.text,
                    "interrupted": u.interrupted,
                }
                for u in conversation.utterances
            ],
            "timings": [t.as_dict() for t in conversation.timings],
            "interruption_rate": round(conversation.interruption_rate, 3),
        }

    # -- being interrupted -------------------------------------------------

    async def interrupt(self) -> bool:
        """Stop the agent now, as a person talking over it would.

        Goes through :meth:`Voice.stop` — the same path the microphone's
        barge-in takes — rather than cancelling the task. A button that
        stopped the audio some other way would stop it in some *other* way:
        draining instead of discarding, or leaving the floor with the agent.
        The difference would only ever show in a room.

        Returns
        -------
        bool
            Whether there was anything to interrupt. ``False`` is not a
            failure: it means the agent was not speaking, which is the common
            case for a button somebody pressed a moment too late.
        """
        if self.discussion.conversation.floor is not Floor.SPEAKING:
            return False
        await self.discussion.voice.stop()
        return True

    async def stop(self) -> Conversation:
        """End the conversation and release everything it holds."""
        if self._watch is not None:
            self._watch.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._watch
        if self._task is not None and not self._task.done():
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self._task
        await self.discussion.aclose()
        return self.discussion.conversation

    async def wait(self) -> Conversation:
        """Wait for the conversation to end on its own."""
        if self._task is None:
            raise RuntimeError(f"session {self.id} was never started")
        return await self._task


class Sessions:
    """Every conversation this process is holding.

    In-memory on purpose: a session is a microphone and an audio device as
    much as it is a transcript, and neither survives a restart. Persisting the
    text alone would hand a caller a session id that resolves to something
    that cannot speak.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}

    def add(self, session: Session) -> Session:
        """Register a session and return it."""
        self._sessions[session.id] = session
        return session

    def get(self, session_id: str) -> Session | None:
        """The session with that id, or ``None``."""
        return self._sessions.get(session_id)

    def ids(self) -> list[str]:
        """Every live session id."""
        return list(self._sessions)

    def __len__(self) -> int:
        return len(self._sessions)

    async def remove(self, session_id: str) -> Conversation | None:
        """Stop a session and forget it."""
        session = self._sessions.pop(session_id, None)
        if session is None:
            return None
        return await session.stop()

    async def aclose(self) -> None:
        """Stop every session. Called when the server shuts down.

        A microphone left open outlives the process that opened it on some
        platforms, which is the kind of thing a user discovers from a
        recording indicator that will not go away.
        """
        for session_id in list(self._sessions):
            await self.remove(session_id)


def utterance_of(speaker: str, text: str, at_s: float = 0.0) -> Utterance:
    """Build an utterance from the wire, for callers that push text in."""
    return Utterance(speaker=speaker, text=text, started_s=at_s, ended_s=at_s)
