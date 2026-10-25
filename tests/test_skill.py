"""Tests for the discussion-helper Claude / OpenCode skill packaging.

The suite ships every helper with four surfaces: a library, one CLI, a FastAPI
HTTP app with MCP mounted on it, and an agent skill. These tests cover the
last one: that ``skills/discussion-helper/SKILL.md`` exists, is well-formed
against the published Agent Skills standard, and that
``scripts/check_triggers.py`` reports full trigger-bucket coverage — so a thin
or drifted description fails the gate, not production.

Author
------
Warith HARCHAOUI — https://linkedin.com/in/warith-harchaoui/
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_SKILL_DIR = _REPO / "skills" / "discussion-helper"
_SKILL = _SKILL_DIR / "SKILL.md"


def _load_checker():
    """Import scripts/check_triggers.py (not an installed module) by path."""
    spec = importlib.util.spec_from_file_location(
        "check_triggers", _REPO / "scripts" / "check_triggers.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_skill_md_exists_and_has_frontmatter() -> None:
    """SKILL.md opens with YAML frontmatter carrying the right name."""
    assert _SKILL.exists(), "skills/discussion-helper/SKILL.md is missing"
    text = _SKILL.read_text(encoding="utf-8")
    assert text.startswith("---"), "SKILL.md must open with YAML frontmatter"
    assert "\nname: discussion-helper" in text
    assert "description:" in text


def test_progressive_disclosure_references_resolve() -> None:
    """Every references/*.md the body points at actually exists."""
    import re

    body = _SKILL.read_text(encoding="utf-8").split("---", 2)[-1]
    referenced = set(re.findall(r"references/([\w.-]+\.md)", body))
    assert referenced, "SKILL.md should defer depth to references/*.md"
    for ref in sorted(referenced):
        assert (_SKILL_DIR / "references" / ref).exists(), f"missing references/{ref}"


def test_no_reference_is_shipped_unread() -> None:
    """And the other direction: a reference nothing points at is never loaded.

    Progressive disclosure only works if the body names the file; one sitting
    in references/ unmentioned is dead weight that still has to be maintained.
    """
    import re

    body = _SKILL.read_text(encoding="utf-8").split("---", 2)[-1]
    referenced = set(re.findall(r"references/([\w.-]+\.md)", body))
    on_disk = {p.name for p in (_SKILL_DIR / "references").glob("*.md")}
    assert on_disk <= referenced, f"never pointed at: {sorted(on_disk - referenced)}"


def test_triggers_catalogue_is_mirrored() -> None:
    """The catalogue exists for both audiences: repo root and skill references.

    And is byte-identical, because two catalogues that have drifted are worse
    than one: each audience believes the copy it reads.
    """
    root = _REPO / "TRIGGERS.md"
    mirror = _SKILL_DIR / "references" / "triggers.md"
    assert root.exists(), "TRIGGERS.md missing at the repo root"
    assert mirror.exists(), "skills/discussion-helper/references/triggers.md missing"
    assert root.read_text(encoding="utf-8").strip() == mirror.read_text(encoding="utf-8").strip(), (
        "the root catalogue and its mirror have drifted apart"
    )


def test_trigger_buckets_are_covered() -> None:
    """The description names every capability and carries a SKIP clause."""
    failures = _load_checker().check()
    assert not failures, "trigger coverage gaps:\n  - " + "\n  - ".join(failures)


def test_the_negative_clause_names_where_the_work_goes() -> None:
    """ "Do not use for X" with no destination leaves the host nowhere to route.

    This package sits on top of three siblings that each answer a neighbouring
    request, so an over-firing skill does not merely guess — it takes work away
    from the package that does it properly.
    """
    description = _load_checker()._extract_description(_SKILL.read_text(encoding="utf-8"))
    for sibling in ("vocal-helper", "speaker-helper", "capture-helper"):
        assert sibling in description, f"{sibling} is not named as a handoff"
