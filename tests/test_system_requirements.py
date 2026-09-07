"""Tests for the Minimum/Recommended system requirements documentation:
the README section and the matching in-game CREDITS entries.
"""
import os

import pygame

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _readme():
    return open(os.path.join(REPO_ROOT, "README.md")).read()


def _requirements_block(readme):
    """The Requirements section, however it happens to be laid out.

    It used to be two "### Minimum"/"### Recommended" subsections and is now
    a two-column table. These tests are about whether the specs are
    documented, not about which of those shapes is used, so they slice the
    section by its heading rather than by the old subheadings.
    """
    start = readme.index("## Requirements")
    end = readme.index("\n## ", start + 1)
    return readme[start:end]


def test_readme_documents_both_a_minimum_and_a_recommended_tier():
    block = _requirements_block(_readme())
    assert "Minimum" in block
    assert "Recommended" in block
    assert block.index("Minimum") < block.index("Recommended")


def test_readme_specs_cover_cpu_ram_and_webcam():
    block = _requirements_block(_readme())
    for spec in ("CPU", "RAM", "Webcam"):
        assert spec in block, f"the requirements section never mentions {spec}"


def test_credits_lists_minimum_and_recommended_spec():
    from gui.screen_credits import CREDITS

    labels = dict(CREDITS)
    assert "MINIMUM SPEC" in labels
    assert "RECOMMENDED SPEC" in labels
    # Minimum comes before Recommended in the scroll order too
    label_order = [label for label, _ in CREDITS]
    assert label_order.index("MINIMUM SPEC") < label_order.index("RECOMMENDED SPEC")


def test_credits_spec_rows_fit_within_the_panel_without_overlapping_the_label(game):
    # Regression guard: a future wording change to these two rows (or any
    # row) must not overflow the panel or collide with its own label - the
    # scrolling list has no wrapping, so an oversized row would silently
    # render off the edge or on top of the label with nothing catching it.
    from gui import ui_kit as ui
    from gui.screen_credits import CREDITS, panel_rect

    panel = panel_rect(game.screen)
    width = game.screen.get_width()
    size = ui.cqw(1.3, width)
    pad = ui.cqw(2.0, width)
    inner_width = panel.width - pad * 2

    for label, value in CREDITS:
        label_width = ui.text_width(label, game.font_path, size)
        value_width = ui.text_width(value, game.font_path, size)
        assert value_width <= inner_width, f"{label!r} row's value overflows the panel"
        assert label_width + value_width <= inner_width, (
            f"{label!r} row's label and value would overlap"
        )
