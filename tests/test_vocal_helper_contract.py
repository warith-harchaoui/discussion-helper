"""
The options the listener sends, read by the real vocal-helper.

The listener's own test fakes vocal-helper with a `PipelineConfig` that takes
any keyword, which is what lets it run with no model — and also what would let
a renamed or removed keyword through. These tests hand the same options to the
real class instead. They need the `[listen]` extra, so they skip where it is
absent (CI) and run in the pre-push gate, where it is installed.

Author
------
Warith HARCHAOUI — https://linkedin.com/in/warith-harchaoui
"""

from __future__ import annotations

import pytest

from discussion_helper.adapters import pipeline_options

voh = pytest.importorskip("vocal_helper")


@pytest.mark.parametrize("language", ["", "fr"])
def test_the_real_pipeline_config_accepts_the_listener_options(language: str) -> None:
    """Every keyword exists in the installed vocal-helper, with the value sent."""
    config = voh.PipelineConfig(**pipeline_options(language))
    assert config.asr == {"language": language or "auto"}
    assert config.llm is None
    assert config.eot is None


def test_the_whole_buffer_rediarization_stays_off() -> None:
    """A loop that labels every turn "user" must not pay for revised labels.

    vocal-helper 4 defaults `growing` to "auto", a re-diarization of the whole
    buffer at 2.6 to 3.3 times the audio. Losing the explicit None would bring
    that cost back silently, since nothing here reads speaker labels.
    """
    assert voh.PipelineConfig(**pipeline_options()).growing is None
