"""Tests for the Minimum/Recommended system requirements documentation:
the README section and the matching in-game CREDITS entries.
"""
import os

import pygame

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _readme():
    return open(os.path.join(REPO_ROOT, "README.md")).read()


def test_readme_has_minimum_and_recommended_sections():
    readme = _readme()
    assert "### Minimum" in readme
    assert "### Recommended" in readme
    # Minimum comes before Recommended, not the other way round
    assert readme.index("### Minimum") < readme.index("### Recommended")


def test_readme_specs_cover_cpu_ram_and_webcam_for_both_tiers():
    readme = _readme()
    minimum = readme[readme.index("### Minimum") : readme.index("### Recommended")]
    recommended = readme[readme.index("### Recommended") :]

    for section in (minimum, recommended):
        assert "CPU" in section
        assert "RAM" in section
    assert "Webcam" in minimum
    assert "keyboard" in minimum.lower()


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
