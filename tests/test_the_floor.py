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
    conversation = await Discussion(
        ScriptedListener(["bonjour"]), EchoResponder(), voice
    ).run()
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
    assert split_sentences("Une phrase, avec une virgule.") == [
        "Une phrase, avec une virgule."
    ]


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

    import tomllib

    root = Path(__file__).resolve().parent.parent
    manifest = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    for command, target in manifest["project"]["scripts"].items():
        module_name, _, attribute = target.partition(":")
        module = importlib.import_module(module_name)
        assert hasattr(module, attribute), f"{command} points at {target}"
