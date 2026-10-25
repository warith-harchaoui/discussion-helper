"""
The command line — ``discussion-helper``.

Module summary
--------------
Two commands, and the second one is why this file is worth reading.

``talk`` opens the microphone and holds a conversation. ``rehearse`` holds the
same conversation with the microphone, the model and the sound card replaced
by fakes — the same loop, the same floor handling, the same interruption
logic, running in a second with nothing installed. It is how you check that
*this package* works before deciding whether the room does.

That distinction matters more than it looks. When a voice agent misbehaves,
the first question is always "is it the loop or is it the hardware", and
without something like ``rehearse`` the only way to ask it is to change one
thing and listen again.

One command line, one parser. Until 0.4.0 these two commands were declared
twice — two parsers over one shared handler table, the second reachable under
a name that advertised the parsing library — and keeping the pair in step cost
more than the second door was worth.

Author
------
Warith HARCHAOUI — https://linkedin.com/in/warith-harchaoui
"""

from __future__ import annotations

import asyncio
import json
import sys
from collections.abc import Callable
from typing import TypeVar

import click

from discussion_helper import __version__
from discussion_helper.discussion import Discussion, Policy
from discussion_helper.types import Conversation

_Command = TypeVar("_Command", bound=Callable[..., None])


def _common(function: _Command) -> _Command:
    """The flags both commands share, applied once rather than twice."""
    function = click.option(
        "--no-barge-in",
        is_flag=True,
        default=False,
        help="Strict half-duplex: the user may not interrupt. Correct on a "
        "speakerphone, where every reply would otherwise interrupt itself.",
    )(function)
    function = click.option(
        "--grace",
        type=float,
        default=0.35,
        show_default=True,
        metavar="SECONDS",
        help="How long after the agent starts speaking before an interruption "
        "is believed. Absorbs the agent's own voice when there is no echo "
        "cancellation.",
    )(function)
    function = click.option(
        "--max-sentences",
        type=int,
        default=0,
        show_default=True,
        help="Cap on reply length. 0 means no cap.",
    )(function)
    function = click.option(
        "--json",
        "as_json",
        is_flag=True,
        default=False,
        help="Write the transcript and the latency breakdown as JSON.",
    )(function)
    return function


@click.group(
    context_settings={"help_option_names": ["-h", "--help"]},
    help=(
        "Hold a spoken conversation: listen, answer, speak — and stop the moment the user cuts in."
    ),
    epilog=(
        # The `\b` keeps click from reflowing the block under it into one
        # paragraph, which is what turns an examples list into prose.
        "\b\n"
        "Examples:\n"
        "  discussion-helper rehearse 'bonjour' 'ça va ?'   # no hardware\n"
        "  discussion-helper talk --voice ff_siwis\n"
        "  discussion-helper talk --no-barge-in             # strict half-duplex\n"
        "\n"
        "KNOWLEDGE.md explains the latency budget, turn detection and why echo\n"
        "decides your defaults."
    ),
)
# Read from the package, not from the installed distribution's metadata.
# `package_name=` alone sends click to importlib.metadata, which reports
# whatever was last pip-installed -- a step behind the code in every editable
# checkout. Measured while there were still two doors: click said 0.1.0 and
# the module said 0.2.0, in the same tree.
# ``-V`` as well as ``--version``, because the short form is the one people
# actually type, and ``-v`` is spoken for by verbosity elsewhere in the suite.
@click.version_option(__version__, "-V", "--version", package_name="discussion-helper")
def cli() -> None:  # pragma: no cover - click dispatches
    """Front door over the two commands."""


def _policy(
    *,
    no_barge_in: bool,
    grace: float,
    max_sentences: int,
    silence_timeout: float = 0.0,
) -> Policy:
    """The policy the shared flags describe."""
    return Policy(
        allow_barge_in=not no_barge_in,
        barge_in_grace_s=grace,
        max_reply_sentences=max_sentences,
        silence_timeout_s=silence_timeout,
    )


def _report(conversation: Conversation, as_json: bool) -> None:
    """Print the transcript, and where the latency went.

    The breakdown is printed even in the human-readable form, because a total
    says a conversation felt slow and nothing about which stage to fix.
    """
    if as_json:
        sys.stdout.write(
            json.dumps(
                {
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
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n"
        )
        return

    for utterance in conversation.utterances:
        mark = " (cut off)" if utterance.interrupted else ""
        who = "you" if utterance.speaker == "user" else "it"
        sys.stdout.write(f"{who:>4}: {utterance.text}{mark}\n")

    if conversation.timings:
        sys.stdout.write("\n")
        for index, timing in enumerate(conversation.timings, start=1):
            sys.stdout.write(
                f"turn {index}: {timing.to_first_audio_s * 1000:.0f} ms to first "
                f"audio, slowest stage {timing.slowest_stage}\n"
            )


@cli.command()
@_common
@click.option("--voice", default="", help="Voice to read with.")
@click.option("--language", default="", help="Language hint.")
@click.option("--device", default=None, help="Microphone name substring.")
@click.option(
    "--silence-timeout",
    type=float,
    default=30.0,
    show_default=True,
    metavar="SECONDS",
    help="Give up after this much silence. An open microphone in an empty "
    "room is an ordinary ending.",
)
def talk(
    no_barge_in: bool,
    grace: float,
    max_sentences: int,
    as_json: bool,
    voice: str,
    language: str,
    device: str | None,
    silence_timeout: float,
) -> None:
    """Hold a conversation at the microphone."""
    from discussion_helper.adapters import LocalResponder, SpeakerVoice, VocalListener

    policy = _policy(
        no_barge_in=no_barge_in,
        grace=grace,
        max_sentences=max_sentences,
        silence_timeout=silence_timeout,
    )

    async def run() -> Conversation:
        async with Discussion(
            VocalListener(language=language, device_name=device),
            LocalResponder(),
            SpeakerVoice(voice=voice, language=language),
            policy,
        ) as discussion:
            return await discussion.run()

    try:
        conversation = asyncio.run(run())
    except RuntimeError as exc:
        # The adapters raise this with the install line for the half that is
        # missing, which is more use than a traceback about a module the
        # reader has never imported.
        sys.stderr.write(f"{exc}\n")
        raise SystemExit(1) from None
    except KeyboardInterrupt:
        sys.stderr.write("\n")
        raise SystemExit(0) from None
    _report(conversation, as_json)


@cli.command()
@_common
@click.argument("turns", nargs=-1)
@click.option(
    "--interrupt-after",
    type=float,
    default=None,
    metavar="SECONDS",
    help="Stage a barge-in this long into the agent's reply.",
)
@click.option(
    "--sentences", type=int, default=3, show_default=True, help="How long the fake reply runs."
)
def rehearse(
    no_barge_in: bool,
    grace: float,
    max_sentences: int,
    as_json: bool,
    turns: tuple[str, ...],
    interrupt_after: float | None,
    sentences: int,
) -> None:
    """Run the same loop with fake parts — no microphone, model or speaker.

    The question a voice agent always raises first is "is it the loop or is it
    the room". This answers it in a second, with nothing installed.
    """
    from discussion_helper.testing import EchoResponder, ScriptedListener, SilentVoice

    discussion = Discussion(
        ScriptedListener(list(turns) or ["bonjour"], interrupt_after_s=interrupt_after),
        EchoResponder(sentences=sentences),
        SilentVoice(seconds_per_sentence=0.2),
        _policy(no_barge_in=no_barge_in, grace=grace, max_sentences=max_sentences),
    )
    _report(asyncio.run(discussion.run()), as_json)


def main() -> None:
    """Console-script entry point."""
    import os_helper as osh

    osh.init_logging()
    cli()


if __name__ == "__main__":  # pragma: no cover
    # `cli()` raises SystemExit with its own code; wrapping `main()` in
    # sys.exit would only ever pass None, which means 0 whatever happened.
    main()
