"""
The MCP surface: the same routes, republished as agent tools.

Module summary
--------------
There is no second implementation here. :mod:`discussion_helper.api` already
describes every operation — its parameters, its types, its ``operation_id`` —
and ``fastapi-mcp`` turns that description into a tool catalogue. An agent
starting a session and a shell calling ``POST /sessions`` reach the same
function, so the two surfaces cannot drift into disagreeing.

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

import argparse
import os
import sys


def main(argv: list[str] | None = None) -> int:
    """Serve the API with its MCP endpoint mounted.

    Returns
    -------
    int
        A process exit code. Non-zero when the extra is missing, with the
        install line rather than a traceback about a module the reader has
        never imported.
    """
    parser = argparse.ArgumentParser(
        prog="discussion-helper-mcp",
        description=(
            "Serve discussion-helper's MCP tools over HTTP. Every tool is a "
            "route on the same FastAPI app, with the MCP endpoint mounted "
            "beside them at /mcp."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Defaults come from DISCUSSION_HELPER_MCP_HOST and "
            "DISCUSSION_HELPER_MCP_PORT when those are set.\n"
            "The host defaults to 127.0.0.1, and should stay there: this "
            "server can open the machine's microphone."
        ),
    )
    parser.add_argument(
        "--host",
        default=os.environ.get("DISCUSSION_HELPER_MCP_HOST", "127.0.0.1"),
        help="Interface to bind (default: %(default)s).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("DISCUSSION_HELPER_MCP_PORT", "8090")),
        help="Port to bind (default: %(default)s).",
    )
    args = parser.parse_args(argv)

    try:
        import uvicorn
    except ImportError:
        sys.stderr.write(
            "The MCP surface needs a web server. Install it with:\n"
            "    pip install 'discussion-helper[mcp]'\n"
        )
        return 2

    from discussion_helper.api import create_app

    # One worker, and here it is not an optimisation. Sessions live in this
    # process's memory and hold this machine's microphone; a second worker
    # would answer half the requests about conversations it cannot see.
    uvicorn.run(create_app(), host=args.host, port=args.port, workers=1)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
