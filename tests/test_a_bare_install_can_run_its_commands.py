"""
Every command `pip install discussion-helper` puts on the PATH has to start.

Found the night before the first publication, in a clean virtualenv and
nowhere else: `discussion-helper` — the headline command, the one the README
tells you to run — imported `click` at module level, and `click` was declared
nowhere. Not a dependency, not an extra. A plain `pip install` put a command
on the PATH that answered a traceback about a package the reader had never
heard of.

A checkout cannot see this. Click is always already there, because something
else in the environment brought it.

So the rule is static and cheap: **a module a console script names may import,
at module level, only the standard library and this package's declared base
dependencies.** Anything heavier belongs behind an extra, and then behind a
`try: ... except ImportError:` that says which extra — the shape `mcp.py`
already uses and the one the CLI lacked.

What this deliberately does not do is build a wheel and install it. That is
the thorough version, it needs the network and a minute, and it belongs behind
a marker rather than in the run somebody does before every commit.

Author
------
Warith HARCHAOUI <warithmetics@deraison.ai>
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

_SCRIPTS_RE = re.compile(r"^\[project\.scripts\]\s*$(.*?)(?=^\[|\Z)", re.M | re.S)
_ENTRY_RE = re.compile(r'^\s*([A-Za-z0-9._-]+)\s*=\s*["\']([^"\']+)["\']', re.M)
_BASE_DEPS_RE = re.compile(r"^dependencies\s*=\s*\[(.*?)^\]", re.M | re.S)
_DIST_RE = re.compile(r'^\s*"([A-Za-z0-9][A-Za-z0-9._-]*)', re.M)


def _pyproject() -> str:
    return (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")


def _console_scripts() -> dict[str, str]:
    """``command -> dotted.module`` for every entry point."""
    section = _SCRIPTS_RE.search(_pyproject())
    assert section, "no [project.scripts] section"
    return {name: target.split(":")[0] for name, target in _ENTRY_RE.findall(section.group(1))}


def _base_distributions() -> set[str]:
    """Distribution names a plain ``pip install`` brings in.

    The declared ones only — not their transitive closure, which would make
    this check pass on whatever a dependency happened to pull today.
    """
    block = _BASE_DEPS_RE.search(_pyproject())
    assert block, "no base dependencies block"
    return {d.lower().replace("-", "_") for d in _DIST_RE.findall(block.group(1))}


def _unguarded_imports(module_path: Path) -> set[str]:
    """Top-level third-party imports, skipping anything inside a try block.

    A `try: import x / except ImportError:` is the documented way to need
    something optional, so those are not the subject here. Imports nested in
    functions are not either: they happen when the function is called, which
    is after the command has started and printed its help.
    """
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            names.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module.split(".")[0])
    return names


def _is_stdlib(name: str) -> bool:
    return name in sys.stdlib_module_names


def test_there_are_console_scripts_to_check() -> None:
    """A regex that stops matching would make the test below vacuous."""
    assert len(_console_scripts()) >= 3, _console_scripts()


@pytest.mark.parametrize("command", sorted(_console_scripts()), ids=lambda c: c)
def test_the_command_imports_on_a_bare_install(command: str) -> None:
    """Its module needs only stdlib and the declared base dependencies."""
    module = _console_scripts()[command]
    path = REPO_ROOT / Path(*module.split(".")).with_suffix(".py")
    assert path.is_file(), f"{command} points at {module}, which is not on disk"

    base = _base_distributions() | {"discussion_helper"}
    offenders = sorted(
        name
        for name in _unguarded_imports(path)
        if not _is_stdlib(name) and name.lower().replace("-", "_") not in base
    )
    assert not offenders, (
        f"`{command}` imports {offenders} at module level, and "
        f"pyproject.toml does not list them as base dependencies. On a clean "
        f"`pip install discussion-helper` this command answers a traceback. "
        f"Declare them, or guard the import with try/except ImportError and "
        f"name the extra that installs them."
    )


def test_the_optional_surfaces_guard_their_imports() -> None:
    """`mcp.py` is the shape the CLI should have had, so hold it to it."""
    source = (REPO_ROOT / "discussion_helper" / "mcp.py").read_text(encoding="utf-8")
    assert "ImportError" in source, (
        "mcp.py needs fastapi and uvicorn, which are behind [mcp]; without a "
        "guard the command dies on an import rather than naming the extra"
    )
    assert "discussion-helper[mcp]" in source, "the guard has to name the extra that fixes it"
