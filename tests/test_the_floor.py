"""
Who holds the floor, and what happens when two parties want it.

Every test here runs with no microphone, no model and no sound card — which
is the point. The behaviour that is hardest to get right in a voice agent is
also the hardest to observe in a room: whether the audio really stopped,
whether what was queued was thrown away or quietly played, whether the floor
came back. A test with a real voice can hear none of that.

Author
------
Warith HARCHAOUI — https://linkedin.com/in/warith-harchaoui
"""

from __future__ import annotations

import asyncio

import pytest

from discussion_helper.discussion import Discussion, Policy
from discussion_helper.testing import EchoResponder, ScriptedListener, SilentVoice
from discussion_helper.types import Floor

# ── The ordinary exchange ──────────────────────────────────────────────────


async def test_a_turn_is_heard_answered_and_recorded() -> None:
    """The loop, at its simplest: in, out, and both in the history."""
    talk = Discussion(ScriptedListener(["bonjour"]), EchoResponder(), SilentVoice())
    conversation = await talk.run()
    assert [(u.speaker, u.text) for u in conversation.utterances] == [
        ("user", "bonjour"),
        ("agent", "bonjour"),
    ]


async def test_the_floor_comes_back_to_the_user() -> None:
    """An agent still holding the floor at the end is an agent nobody can answer."""
    talk = Discussion(ScriptedListener(["un", "deux"]), EchoResponder(), SilentVoice())
    conversation = await talk.run()
    assert conversation.floor is Floor.IDLE
    assert len([u for u in conversation.utterances if u.speaker == "agent"]) == 2


async def test_the_model_is_shown_the_history_not_just_the_last_line() -> None:
    """A conversation the model cannot see is a sequence of unrelated answers."""
    responder = EchoResponder()
    await Discussion(ScriptedListener(["un", "deux"]), responder, SilentVoice()).run()
    second_call = responder.seen[1]
    assert [m["role"] for m in second_call] == ["user", "assistant", "user"]


async def test_a_turn_that_recognised_to_nothing_is_not_answered() -> None:
    """Answering silence is how an agent starts talking to an empty room."""
    voice = SilentVoice()
    conversation = await Discussion(
        ScriptedListener(["", "   ", "bonjour"]), EchoResponder(), voice
    ).run()
    assert voice.spoken == ["bonjour"]
    assert len(conversation.utterances) == 2


# ── The interruption ───────────────────────────────────────────────────────


async def test_the_user_can_cut_the_agent_off() -> None:
    """The behaviour the whole package exists for."""
    voice = SilentVoice(seconds_per_sentence=1.0)
    listener = ScriptedListener(["bonjour"], interrupt_after_s=0.05)
    conversation = await Discussion(
        listener,
        EchoResponder(sentences=5),
        voice,
        Policy(barge_in_grace_s=0.0),
    ).run()

    agent = [u for u in conversation.utterances if u.speaker == "agent"][0]
    assert agent.interrupted is True
    assert voice.stops == 1


async def test_what_was_queued_and_not_heard_is_discarded() -> None:
    """Drain-instead-of-discard is what makes an agent feel deaf.

    A reply is synthesised ahead of playback, so an interruption always finds
    audio made and not yet heard. Playing it out — because it exists, because
    it was paid for — is the mistake. The sentence that was cut must not be
    counted as said, and the ones after it must never start.
    """
    voice = SilentVoice(seconds_per_sentence=1.0)
    await Discussion(
        ScriptedListener(["bonjour"], interrupt_after_s=0.05),
        EchoResponder(sentences=5),
        voice,
        Policy(barge_in_grace_s=0.0),
    ).run()

    assert len(voice.spoken) == 1, "sentences after the interruption must not start"
    assert voice.completed == [], "the cut sentence must not count as said"


async def test_the_interruption_is_fast() -> None:
    """Under 150 ms from the first syllable to silence is the published bar.

    Past it the agent is audibly talking over somebody, which is the rudest
    thing a voice interface does. Measured against a one-second sentence, so
    a loop that waited for the sentence to end would fail by a wide margin
    rather than by a flaky one.
    """
    voice = SilentVoice(seconds_per_sentence=1.0)
    started = asyncio.get_running_loop().time()
    await Discussion(
        ScriptedListener(["bonjour"], interrupt_after_s=0.02),
        EchoResponder(sentences=5),
        voice,
        Policy(barge_in_grace_s=0.0),
    ).run()
    elapsed = asyncio.get_running_loop().time() - started
    assert elapsed < 0.15, f"took {elapsed * 1000:.0f} ms to stop"


async def test_barge_in_can_be_switched_off() -> None:
    """Strict half-duplex: rude, and right on a speakerphone with no AEC.

    Every reply would otherwise interrupt itself, because the agent's own
    voice reaching its own microphone looks exactly like the user speaking.
    """
    voice = SilentVoice(seconds_per_sentence=0.02)
    conversation = await Discussion(
        ScriptedListener(["bonjour"], interrupt_after_s=0.0),
        EchoResponder(sentences=3),
        voice,
        Policy(allow_barge_in=False),
    ).run()
    agent = [u for u in conversation.utterances if u.speaker == "agent"][0]
    assert agent.interrupted is False
    assert len(voice.completed) == 3


async def test_the_grace_period_absorbs_the_agents_own_first_syllable() -> None:
    """Without echo cancellation, that syllable is the loudest thing heard.

    An interruption arriving inside the grace window is treated as the
    agent's own voice, and — crucially — the watcher keeps watching rather
    than returning, or one echo would disable barge-in for the whole turn.
    """
    voice = SilentVoice(seconds_per_sentence=0.05)
    conversation = await Discussion(
        ScriptedListener(["bonjour"], interrupt_after_s=0.0),
        EchoResponder(sentences=3),
        voice,
        Policy(barge_in_grace_s=0.5),
    ).run()
    agent = [u for u in conversation.utterances if u.speaker == "agent"][0]
    assert agent.interrupted is False, "an echo must not read as an interruption"


# ── Length, silence, and tidying up ────────────────────────────────────────


async def test_a_reply_can_be_capped() -> None:
    """An agent that talks for ninety seconds is one the user has to interrupt."""
    voice = SilentVoice()
    await Discussion(
        ScriptedListener(["bonjour"]),
        EchoResponder(sentences=10),
        voice,
        Policy(max_reply_sentences=2),
    ).run()
    assert len(voice.spoken) == 2


async def test_silence_ends_the_session_rather_than_raising() -> None:
    """An open microphone in an empty room is an ordinary ending."""
    listener = ScriptedListener(["bonjour"], pace_s=5.0)
    conversation = await Discussion(
        listener, EchoResponder(), SilentVoice(), Policy(silence_timeout_s=0.05)
    ).run()
    assert conversation.utterances == []


async def test_closing_releases_all_three_parts() -> None:
    """A microphone left open outlives the program that opened it."""
    listener, responder, voice = ScriptedListener([]), EchoResponder(), SilentVoice()
    async with Discussion(listener, responder, voice):
        pass
    assert (listener.closed, responder.closed, voice.closed) == (True, True, True)


# ── What the timings say ───────────────────────────────────────────────────


async def test_each_exchange_reports_where_its_latency_went() -> None:
    """A single total says a conversation feels slow and nothing about why."""
    conversation = await Discussion(
        ScriptedListener(["bonjour"]), EchoResponder(delay_s=0.05), SilentVoice()
    ).run()
    timing = conversation.timings[0]
    assert timing.think_s >= 0.05
    assert timing.to_first_audio_s >= timing.think_s
    assert timing.slowest_stage == "think"


async def test_the_budget_counts_time_to_first_audio_not_playback() -> None:
    """The measurement mistake this split exists to prevent.

    A fast engine playing a long sentence must not look slower than a slow
    engine playing a short one. The number that belongs in the budget is the
    silence before the sound, and only the voice knows it.
    """
    voice = SilentVoice(seconds_per_sentence=0.40, first_audio_s=0.02)
    conversation = await Discussion(ScriptedListener(["bonjour"]), EchoResponder(), voice).run()
    timing = conversation.timings[0]
    assert timing.speak_s == pytest.approx(0.02, abs=0.01)
    assert timing.speak_s < 0.40, "playback time must not land in the budget"


def test_the_interruption_rate_is_a_diagnostic() -> None:
    """A high rate usually means answers that run too long.

    Which a transcript will not show: the text of an interrupted answer looks
    complete.
    """
    from discussion_helper.types import Conversation, Utterance

    conversation = Conversation()
    conversation.add(Utterance(speaker="agent", text="a", interrupted=True))
    conversation.add(Utterance(speaker="agent", text="b"))
    assert conversation.interruption_rate == pytest.approx(0.5)


# ── The adapters, without their siblings ───────────────────────────────────


def test_sentences_split_at_sentence_ends_not_at_clauses() -> None:
    """A chunk cut at a comma comes out flat: the model never sees where the
    sentence was going. See KNOWLEDGE.md §5."""
    from discussion_helper.adapters import split_sentences

    assert split_sentences("Un. Deux ! Trois ?") == ["Un.", "Deux !", "Trois ?"]
    assert split_sentences("Une phrase, avec une virgule.") == ["Une phrase, avec une virgule."]


def test_importing_an_adapter_does_not_import_its_sibling() -> None:
    """A base install carries the loop and nothing else.

    Every sibling import is inside a function, which is what lets the floor
    and interruption logic be exercised in CI with no recogniser, no model
    and no sound card anywhere.
    """
    import subprocess
    import sys
    import textwrap

    done = subprocess.run(
        [
            sys.executable,
            "-c",
            textwrap.dedent(
                """
                import sys
                import discussion_helper.adapters  # noqa: F401
                leaked = sorted(
                    m for m in sys.modules
                    if m.split(".")[0] in (
                        "vocal_helper", "speaker_helper", "sounddevice",
                        "best_engine_ai_helper", "torch", "onnxruntime",
                    )
                )
                assert not leaked, leaked
                print("OK")
                """
            ),
        ],
        capture_output=True,
        text=True,
    )
    assert done.returncode == 0, done.stderr[-1500:]
    assert "OK" in done.stdout


def test_every_adapter_satisfies_the_protocol_it_claims() -> None:
    """Structural conformance, so a renamed method fails here and not in a room."""
    from discussion_helper.adapters import LocalResponder, SpeakerVoice, VocalListener
    from discussion_helper.parts import Listener, Responder, Voice

    assert isinstance(VocalListener(), Listener)
    assert isinstance(LocalResponder(), Responder)
    assert isinstance(SpeakerVoice(), Voice)


def test_the_fakes_satisfy_the_protocols_too() -> None:
    """Otherwise the tests exercise a shape nothing ships."""
    from discussion_helper.parts import Listener, Responder, Voice

    assert isinstance(ScriptedListener([]), Listener)
    assert isinstance(EchoResponder(), Responder)
    assert isinstance(SilentVoice(), Voice)


def test_the_spoken_reply_asks_for_speech_not_prose() -> None:
    """Lists, markdown and headings cannot be heard.

    And brevity here is a latency decision, not a style one: an agent that
    talks for ninety seconds is one the user has to interrupt.
    """
    from discussion_helper.adapters import LocalResponder

    system = LocalResponder().system.lower()
    assert "out loud" in system
    assert "markdown" in system


# ── The two front doors ────────────────────────────────────────────────────


def test_the_two_front_doors_offer_the_same_commands() -> None:
    """A command on one and not the other is the failure a twin invites."""
    import click

    from discussion_helper.cli import build_parser
    from discussion_helper.cli_click import cli

    argparse_commands: set[str] = set()
    for action in build_parser()._actions:
        if getattr(action, "choices", None) and isinstance(action.choices, dict):
            argparse_commands |= set(action.choices)
    with click.Context(cli) as ctx:
        click_commands = set(cli.list_commands(ctx))

    assert argparse_commands and argparse_commands == click_commands


def test_every_command_has_a_handler() -> None:
    """A sub-command the dispatcher does not know parses and then does nothing."""
    from discussion_helper.cli import build_parser
    from discussion_helper.cli_click import _HANDLERS

    declared: set[str] = set()
    for action in build_parser()._actions:
        if getattr(action, "choices", None) and isinstance(action.choices, dict):
            declared |= set(action.choices)
    assert declared <= set(_HANDLERS)


def test_every_declared_command_points_at_something_importable() -> None:
    """A console script naming a module nobody wrote installs and then fails.

    This package shipped a `discussion-helper-mcp` line for exactly as long
    as it took to notice there was no `mcp.py` behind it.
    """
    import importlib
    from pathlib import Path

    try:
        import tomllib  # stdlib from 3.11 (PEP 680)
    except ModuleNotFoundError:  # pragma: no cover - only on 3.10
        # This package declares `requires-python = ">=3.10"`, and on 3.10 a bare
        # `import tomllib` makes this test error out. Skipping it there would be
        # the easy fix and the wrong one: this is the guard that caught the
        # `discussion-helper-mcp` script pointing at a module nobody had written,
        # so it has to run on the oldest Python we claim to support, not just the
        # convenient ones. `tomli` is the same parser under its pre-stdlib name.
        import tomli as tomllib

    root = Path(__file__).resolve().parent.parent
    manifest = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    for command, target in manifest["project"]["scripts"].items():
        module_name, _, attribute = target.partition(":")
        module = importlib.import_module(module_name)
        assert hasattr(module, attribute), f"{command} points at {target}"


# ── The microphone path, without a microphone ──────────────────────────────


def _fake_vocal_helper():
    """A stand-in for ``vocal_helper`` shaped like the real one.

    Shaped like it in the one way that matters here: every event is a
    ``TypedDict``, so at runtime it is a plain ``dict`` with no attributes.
    That is what let the real listener read ``.text`` off a PCM frame for as
    long as it did — ``getattr(frame, "text", "")`` cannot raise on a dict, it
    just answers ``""``.
    """
    import types

    import numpy as np

    sources = types.SimpleNamespace()

    async def from_microphone(*, device_name=None, device_index=None):
        # One quiet frame, then a loud one: enough to tell an onset tap that
        # fires on level from one that fires on anything.
        yield {"t0": 0.00, "sample_rate": 16_000, "pcm": np.zeros(320, np.float32)}
        yield {"t0": 0.02, "sample_rate": 16_000, "pcm": np.full(320, 0.5, np.float32)}

    sources.from_microphone = from_microphone

    class PipelineConfig:
        def __init__(self, **kw):
            self.kw = kw

    class Pipeline:
        """Drains the source — so the onset tap really runs — then speaks."""

        def __init__(self, *, source, config):
            self.source, self.config = source, config

        async def run(self):
            async for _frame in self.source():
                pass
            yield {"t0": 0.02, "t1": 0.40, "speaker": "S1", "text": "bonjour"}

    module = types.ModuleType("vocal_helper")
    module.sources = sources
    module.Pipeline = Pipeline
    module.PipelineConfig = PipelineConfig
    return module


async def test_the_listener_yields_what_the_pipeline_recognised(monkeypatch) -> None:
    """The regression that no microphone test could ever have caught.

    Before this, ``utterances()`` consumed ``sources.from_microphone``
    directly — the raw PCM source, not the pipeline — and looked for a
    transcript on frames that carry none. It therefore yielded nothing, ever,
    and raised nothing either: the agent simply never heard anybody. The one
    assertion that matters is that a turn comes out at all.
    """
    import sys

    monkeypatch.setitem(sys.modules, "vocal_helper", _fake_vocal_helper())
    from discussion_helper.adapters import VocalListener

    heard = [u async for u in VocalListener().utterances()]
    assert [(u.speaker, u.text) for u in heard] == [("user", "bonjour")]
    # Timestamps come from the event, not from a wall clock, or the transcript
    # cannot be lined up against the audio afterwards.
    assert (heard[0].started_s, heard[0].ended_s) == (0.02, 0.40)


async def test_a_loud_frame_releases_the_barge_in_wait(monkeypatch) -> None:
    """``speech_started`` has to answer from the frames, not from the output.

    The pipeline's earliest event arrives after Silero's trailing-silence
    window; waiting for it would blow the 150 ms bar pinned above by a wide
    margin.
    """
    import asyncio
    import sys

    monkeypatch.setitem(sys.modules, "vocal_helper", _fake_vocal_helper())
    from discussion_helper.adapters import VocalListener

    listener = VocalListener()
    waiting = asyncio.ensure_future(listener.speech_started())
    await asyncio.sleep(0)
    _ = [u async for u in listener.utterances()]
    await asyncio.wait_for(waiting, timeout=1.0)


async def test_a_quiet_room_does_not_look_like_speech(monkeypatch) -> None:
    """Otherwise the agent interrupts itself on the first frame of silence."""
    import sys

    module = _fake_vocal_helper()

    async def only_silence(*, device_name=None, device_index=None):
        import numpy as np

        for i in range(5):
            yield {
                "t0": i * 0.02,
                "sample_rate": 16_000,
                "pcm": np.zeros(320, np.float32),
            }

    module.sources.from_microphone = only_silence
    monkeypatch.setitem(sys.modules, "vocal_helper", module)
    from discussion_helper.adapters import VocalListener

    listener = VocalListener()
    _ = [u async for u in listener.utterances()]
    assert not listener._speech.is_set()


def test_the_two_declared_versions_agree() -> None:
    """`pyproject.toml` and `__version__` are both hand-written.

    Which is one copy too many: the wheel takes its version from the manifest
    and every `--version` flag takes it from the module, so a bump applied to
    one and not the other ships a package that misreports itself. Cheap to
    check, and nothing else would notice.
    """
    from pathlib import Path

    try:
        import tomllib
    except ModuleNotFoundError:  # pragma: no cover - only on 3.10
        import tomli as tomllib

    import discussion_helper

    root = Path(__file__).resolve().parent.parent
    manifest = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    assert manifest["project"]["version"] == discussion_helper.__version__


def test_every_door_reports_the_same_latency_breakdown() -> None:
    """The stage to fix must not depend on which door you came through.

    `slowest_stage` is the one field in the breakdown that says what to *do*
    about a slow conversation, and it used to be bolted on per caller: named
    by the text CLI, merged in by hand by the HTTP event stream, and missing
    from the CLI's own `--json` — the door a script reads.
    """
    from discussion_helper.types import TurnTiming

    # to_first_audio_s is derived, not stored — the four stages are the input.
    timing = TurnTiming(endpoint_s=0.1, recognise_s=0.2, think_s=0.9, speak_s=0.1)
    payload = timing.as_dict()
    assert payload["slowest_stage"] == timing.slowest_stage == "think"
    assert set(payload) == {
        "endpoint_s",
        "recognise_s",
        "think_s",
        "speak_s",
        "to_first_audio_s",
        "slowest_stage",
    }
