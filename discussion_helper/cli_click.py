"""
The click command line — ``discussion-helper``.

The twin of :mod:`discussion_helper.cli`: same two commands, same handlers,
the other parser. Both build the same ``argparse.Namespace`` and hand it to
the same functions, so a handler cannot tell which front door called it — and
a command cannot exist on one and not the other.

Author
------
Warith HARCHAOUI — https://linkedin.com/in/warith-harchaoui
"""

from __future__ import annotations

import argparse

import click

from discussion_helper import cli as _argcli

#: Every command, and the handler it shares with the argparse front door. A
#: command missing from here is a command that parses and does nothing, which
#: is why a test reads this table rather than trusting the two to agree.
_HANDLERS = {
    "talk": _argcli._cmd_talk,
    "rehearse": _argcli._cmd_rehearse,
}


def _run(command: str, **fields: object) -> None:
    """Build the shared namespace and dispatch; propagate the exit code."""
    raise SystemExit(_HANDLERS[command](argparse.Namespace(command=command, **fields)))


def _common(function):  # type: ignore[no-untyped-def]
    """The flags both commands share, applied once rather than twice."""
    function = click.option(
        "--no-barge-in",
        is_flag=True,
        default=False,
        help="Strict half-duplex: the user may not interrupt.",
    )(function)
    function = click.option(
        "--grace",
        type=float,
        default=0.35,
        metavar="SECONDS",
        help="Delay before an interruption is believed (absorbs the agent's own voice).",
    )(function)
    function = click.option(
        "--max-sentences", type=int, default=0, help="Cap on reply length; 0 is none."
    )(function)
    function = click.option("--json", "json_", is_flag=True, default=False, help="Emit JSON.")(
        function
    )
    return function


@click.group(
    context_settings={"help_option_names": ["-h", "--help"]},
    help=(
        "Hold a spoken conversation: listen, answer, speak — and stop the "
        "moment the user cuts in. KNOWLEDGE.md explains the latency budget, "
        "turn detection, and why echo decides your defaults."
    ),
)
@click.version_option(package_name="discussion-helper")
def cli() -> None:  # pragma: no cover - click dispatches
    """Front door over the two commands."""


@cli.command()
@_common
@click.option("--voice", default="", help="Voice to read with.")
@click.option("--language", default="", help="Language hint.")
@click.option("--device", default=None, help="Microphone name substring.")
@click.option(
    "--silence-timeout",
    type=float,
    default=30.0,
    metavar="SECONDS",
    help="Give up after this much silence.",
)
def talk(
    no_barge_in: bool,
    grace: float,
    max_sentences: int,
    json_: bool,
    voice: str,
    language: str,
    device: str | None,
    silence_timeout: float,
) -> None:
    """Hold a conversation at the microphone."""
    _run(
        "talk",
        no_barge_in=no_barge_in,
        grace=grace,
        max_sentences=max_sentences,
        json=json_,
        voice=voice,
        language=language,
        device=device,
        silence_timeout=silence_timeout,
    )


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
@click.option("--sentences", type=int, default=3, help="How long the fake reply runs.")
def rehearse(
    no_barge_in: bool,
    grace: float,
    max_sentences: int,
    json_: bool,
    turns: tuple[str, ...],
    interrupt_after: float | None,
    sentences: int,
) -> None:
    """Run the same loop with fake parts — no microphone, model or speaker.

    The question a voice agent always raises first is "is it the loop or is it
    the room". This answers it in a second, with nothing installed.
    """
    _run(
        "rehearse",
        no_barge_in=no_barge_in,
        grace=grace,
        max_sentences=max_sentences,
        json=json_,
        turns=list(turns) or ["bonjour"],
        interrupt_after=interrupt_after,
        sentences=sentences,
    )


def main() -> None:
    """Console-script entry point."""
    import os_helper as osh

    osh.init_logging()
    cli()


if __name__ == "__main__":  # pragma: no cover
    # `cli()` raises SystemExit with its own code; wrapping `main()` in
    # sys.exit would only ever pass None, which means 0 whatever happened.
    main()
