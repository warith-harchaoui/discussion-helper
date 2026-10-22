"""
Tests for the model-facing prompt catalogue.

This package's one prompt used to be a hardcoded class attribute, English
only — which for a *spoken conversation* package is a real defect, not a
cosmetic one: a French speaker got an English instruction, and a model given
an English instruction answers in English or in written-register French.

The prompts live in `locales/i18n.yaml` and are read through
`os_helper.Prompts`, the loader shared across the suite. They are authored per
language rather than translated: what makes a model answer in spoken French is
not the French words of the English sentence.

Author
------
[Warith HARCHAOUI](https://linkedin.com/in/warith-harchaoui/)
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import os_helper as osh

from discussion_helper import adapters

_ROOT = Path(__file__).resolve().parent.parent


def test_the_shared_loader_is_what_resolves_the_prompts() -> None:
    """One prompt loader in the suite, not one hardcoded string per package."""
    assert isinstance(adapters._prompts(), osh.Prompts)


def test_the_prompt_reads_in_each_language() -> None:
    """Both languages exist and differ — a catalogue that loads but serves
    one language everywhere would pass a weaker check."""
    english, french = adapters.default_system("en"), adapters.default_system("fr")
    assert english != french
    assert "speaking out loud" in english
    assert "à voix haute" in french


def test_a_regional_tag_reaches_its_base_language() -> None:
    """A Québécois caller must get the French prompt, not the English one."""
    assert adapters.default_system("fr-CA") == adapters.default_system("fr")


def test_an_unknown_language_falls_back_to_the_source() -> None:
    """A model must always be given an instruction, deterministically."""
    assert adapters.default_system("de") == adapters.default_system("en")


def test_the_responder_takes_the_language_it_is_given() -> None:
    """The wiring, end to end: constructing with a language picks the prompt."""
    assert adapters.LocalResponder(language="fr").system == adapters.default_system("fr")
    assert adapters.LocalResponder(language="en").system == adapters.default_system("en")


def test_an_explicit_system_prompt_still_wins() -> None:
    """The caller's own instruction must override the catalogue entirely."""
    assert adapters.LocalResponder(system="Only say ok.").system == "Only say ok."


def test_the_prompt_section_is_sound() -> None:
    """Every language present, nothing empty, placeholders consistent."""
    faults = adapters._prompts().problems()
    assert faults == [], "prompt faults:\n  " + "\n  ".join(faults)


def test_the_catalogue_sits_inside_the_package() -> None:
    """Outside the package directory it is not package data at all."""
    import discussion_helper

    package_dir = Path(discussion_helper.__file__).resolve().parent
    locales = package_dir / "locales" / "i18n.yaml"
    assert locales.is_file()
    assert locales.is_relative_to(package_dir)


def test_the_build_declares_the_catalogue_as_package_data() -> None:
    """Living inside the package is necessary and not sufficient.

    setuptools ships `.py` files on its own; anything else needs declaring.
    Verified absent from a built wheel before this line existed: every answer
    would have been generated under the English prompt however the caller
    asked, while a source checkout worked perfectly.

    Read with a regex rather than `tomllib`: this package supports Python
    3.10, where `tomllib` is not in the standard library.
    """
    text = (_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    section = re.search(r"^\[tool\.setuptools\.package-data\](.*?)(?=^\[|\Z)", text, re.S | re.M)
    assert section, "pyproject.toml declares no [tool.setuptools.package-data]"
    assert "locales" in section.group(1), (
        f"package-data does not ship the prompt catalogue:\n{section.group(1)}"
    )


def test_the_catalogue_is_tracked_by_git() -> None:
    """Declared and present is still not enough if git ignores it."""
    listed = subprocess.run(
        ["git", "ls-files", "discussion_helper/locales/i18n.yaml"],
        cwd=_ROOT,
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()
    assert listed, "the prompt catalogue is not tracked by git (check .gitignore)"


def test_the_declared_os_helper_floor_carries_the_prompt_loader() -> None:
    """`osh.Prompts` landed in os-helper 2.9.0; a lower floor is a lie.

    pip resolves the NEWEST os-helper, never the floor, so a wrong
    declaration stays green everywhere and breaks only for whoever pins.
    """
    text = (_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    bound = re.search(r'"os-helper>=(\d+)\.(\d+)(?:\.(\d+))?', text)
    assert bound, "pyproject.toml declares no os-helper lower bound"
    floor = tuple(int(part or 0) for part in bound.groups())
    assert floor >= (2, 9, 0), (
        f"declared floor {bound.group(0)!r} predates os_helper.Prompts (2.9.0)"
    )
