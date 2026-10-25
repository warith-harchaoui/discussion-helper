"""
The MCP surface: the same routes, republished as agent tools.

Module summary
--------------
There is no second implementation here. :mod:`discussion_helper.api` already
describes every operation — its parameters, its types, its ``operation_id`` —
and ``fastapi-mcp`` turns that description into a tool catalogue. An agent
starting a session and a shell calling ``POST /sessions`` reach the same
function, so the two surfaces cannot drift into disagreeing.

The parsing is `click <https://click.palletsprojects.com>`_, like
:mod:`discussion_helper.cli`. It used to be ``argparse`` — the last one left
after 0.4.0 put the command line on click — which meant two parsing libraries
in one wheel and two answers to ``-h``, one of them refusing the flag.

What an agent can actually do with a conversation
-------------------------------------------------
Not hold one: it has no microphone and no ears. What it has is the other three
verbs, and they are the useful ones for an assistant sitting beside a person:

* **start** a session on the user's machine, and **end** it;
* **watch** it — the transcript as it grows, the floor, and where each
  exchange's latency went;
* **interrupt** it, which is the one that matters. "Stop talking" is a thing
  people say to an agent, and routing it through the same ``Voice.stop`` the
  microphone's barge-in uses means it stops the same way: discarding what was
  synthesised rather than letting it drain.
* **take one turn as text**, which is the only way an agent can ask the
  conversation's model something directly.

Author
------
Warith HARCHAOUI — https://linkedin.com/in/warith-harchaoui/
"""

from __future__ import annotations

import sys

import click

#: The command name the console script installs. Passed to click explicitly as
#: ``prog_name``: left to itself click reads ``sys.argv[0]``, which prints
#: ``mcp.py`` under ``python -m`` and the test runner's name under pytest.
_PROG = "discussion-helper-mcp"


@click.command(
    context_settings={"help_option_names": ["-h", "--help"]},
    epilog=(
        # `\b` stops click reflowing the block under it into one paragraph.
        # The second half is the reason the host default is what it is, not a
        # continuation of the sentence about environment variables.
        "\b\n"
        "Defaults come from DISCUSSION_HELPER_MCP_HOST and\n"
        "DISCUSSION_HELPER_MCP_PORT when those are set.\n"
        "The host defaults to 127.0.0.1, and should stay there: this server\n"
        "can open the machine's microphone."
    ),
)
# `envvar=` rather than a default computed from `os.environ`: an option's
# default is evaluated when this module is imported, so reading the environment
# there would freeze whatever the shell held at import time. click consults the
# variable per invocation, and an explicit flag still wins over it.
@click.option(
    "--host",
    default="127.0.0.1",
    envvar="DISCUSSION_HELPER_MCP_HOST",
    show_default=True,
    help="Interface to bind.",
)
@click.option(
    "--port",
    type=int,
    default=8090,
    envvar="DISCUSSION_HELPER_MCP_PORT",
    show_default=True,
    help="Port to bind.",
)
def cli(host: str, port: int) -> int:
    """Serve discussion-helper's MCP tools over HTTP.

    Every tool is a route on the same FastAPI app, with the MCP endpoint
    mounted beside them at /mcp.

    \f

    Everything above the form feed is what ``--help`` prints: click renders
    the whole docstring, so the numpydoc sections below would otherwise land
    in a user's terminal, double backticks and all.

    Parameters
    ----------
    host : str
        Interface to bind; ``DISCUSSION_HELPER_MCP_HOST`` when unset.
    port : int
        Port to bind; ``DISCUSSION_HELPER_MCP_PORT`` when unset.

    Returns
    -------
    int
        A process exit code, handed back by :func:`main` rather than raised:
        ``standalone_mode=False`` is what lets this value travel.
    """
    try:
        import uvicorn
    except ImportError:
        click.echo(
            "The MCP surface needs a web server. Install it with:\n"
            "    pip install 'discussion-helper[mcp]'",
            err=True,
        )
        return 2

    from discussion_helper.api import create_app

    # One worker, and here it is not an optimisation. Sessions live in this
    # process's memory and hold this machine's microphone; a second worker
    # would answer half the requests about conversations it cannot see.
    uvicorn.run(create_app(), host=host, port=port, workers=1)
    return 0


def main(argv: list[str] | None = None) -> int:
    """Serve the API with its MCP endpoint mounted.

    Parameters
    ----------
    argv : list of str or None
        Argument vector without ``argv[0]``; reads ``sys.argv`` when ``None``.

    Returns
    -------
    int
        A process exit code. Non-zero when the extra is missing, with the
        install line rather than a traceback about a module the reader has
        never imported.
    """
    # `standalone_mode=False` is the whole point: it stops click calling
    # `sys.exit` itself, so the exit code comes back here and this function
    # keeps returning an `int`. A console script that raises instead of
    # returning its code is a regression, and `[project.scripts]` points
    # straight at this name.
    try:
        code = cli.main(
            args=argv if argv is not None else sys.argv[1:],
            prog_name=_PROG,
            standalone_mode=False,
        )
    except click.ClickException as exc:
        # A bad flag lands here as a UsageError: show the usage line and give
        # back its exit code (2), which is what argparse did before.
        exc.show()
        return exc.exit_code
    except click.exceptions.Exit as exc:  # -h / --help
        return int(exc.exit_code)
    except SystemExit as exc:  # pragma: no cover - defensive
        return int(exc.code or 0)
    return int(code or 0)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
