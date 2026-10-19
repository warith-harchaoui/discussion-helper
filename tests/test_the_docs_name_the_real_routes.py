"""
A route table in a README is a promise, and routes outlive the prose.

Written after the container was built and exercised: the app served eleven
routes and the README documented six. `GET /health`, `GET /sessions`,
`GET /sessions/{id}` and `POST /sessions/{id}/say` existed, worked, and were
findable only by reading the source or `/openapi.json`. The last of those is
the one that stings — pushing a user turn in as text is how a caller drives a
remote session without audio at all, and nobody could discover it.

The French twin was worse: it had no HTTP section whatsoever, so a reader in
that language could not learn the surface existed.

So the rule is simple and one-directional: **every route the app declares has
to appear in both README files.** The reverse is not checked — a table may
describe something the OpenAPI schema does not carry, and the WebSocket is
exactly that case, since OpenAPI has no notion of one.

Author
------
Warith HARCHAOUI <warithmetics@deraison.ai>
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
READMES = ("README.md", "LISEZMOI.md")

#: Routes that exist for the machinery rather than for a reader: FastAPI's own
#: documentation endpoints, and the MCP mount, which the tables name as
#: ``/mcp`` without a method.
_NOT_FOR_READERS = {
    "/openapi.json",
    "/docs",
    "/docs/oauth2-redirect",
    "/redoc",
    "/mcp",
}


def _declared_routes() -> set[str]:
    """Every path the FastAPI app serves, as the app itself reports them."""
    fastapi = pytest.importorskip(
        "fastapi", reason="the HTTP surface is behind the [server] extra"
    )
    assert fastapi  # the import is the point
    from discussion_helper.api import build

    paths = {
        getattr(route, "path", "")
        for route in build().routes
        if getattr(route, "path", "")
    }
    return {p for p in paths if p not in _NOT_FOR_READERS}


def _documented(text: str) -> set[str]:
    """Route paths a README names, normalised to the app's parameter spelling.

    The tables write ``{id}`` where FastAPI writes ``{session_id}``, because a
    table is read by a person and a path is matched by a router. Normalising
    here keeps the documents readable instead of making them spell the
    framework's variable names.
    """
    import re

    found = set()
    for path in re.findall(r"`(?:GET|POST|DELETE|PUT|PATCH|WS)\s+(/[^`]*)`", text):
        found.add(re.sub(r"\{[a-z_]+\}", "{session_id}", path.strip()))
    return found


def test_the_app_has_routes_to_check() -> None:
    """A build() that returns nothing would make the test below vacuous."""
    assert len(_declared_routes()) >= 8, sorted(_declared_routes())


@pytest.mark.parametrize("readme", READMES)
def test_every_route_is_documented(readme: str) -> None:
    """A route nobody can find is a route nobody uses."""
    text = (REPO_ROOT / readme).read_text(encoding="utf-8")
    missing = sorted(_declared_routes() - _documented(text))
    assert not missing, (
        f"{readme} does not mention {missing}. The app serves them; a reader "
        f"has only the source and /openapi.json to find them in."
    )


@pytest.mark.parametrize("readme", READMES)
def test_the_websocket_is_in_the_table(readme: str) -> None:
    """The one surface OpenAPI cannot describe, so nothing else would catch it.

    It is also the most important one here: it is where the microphone
    crosses the wire, and the two client duties that make barge-in work are
    written beside it.
    """
    text = (REPO_ROOT / readme).read_text(encoding="utf-8")
    assert "/audio" in text, f"{readme} never mentions the audio socket"
    assert '{"type":"speaking"}' in text, (
        f"{readme} does not tell a client to announce the first syllable — "
        f"without that, a barge-in cannot travel"
    )
