"""Tests for Game.frame_dt_scale(), the shared delta-time normalizer.

Every game's movement multiplies by this instead of a bare per-iteration
constant, so its own correctness (including the clamp) is worth testing
independently of any one game's use of it.
"""
from gui import gui as gui_mod


def test_scale_is_1_at_exactly_the_target_frame_rate(game):
    game.dt = 1 / gui_mod.TARGET_FPS
    assert abs(game.frame_dt_scale() - 1.0) < 1e-9


def test_scale_is_1_before_the_first_frame_has_ever_ticked(game):
    game.dt = 0
    assert game.frame_dt_scale() == 1.0


def test_scale_grows_for_a_slower_than_target_frame(game):
    game.dt = 1 / (gui_mod.TARGET_FPS / 2)  # half the target rate
    assert abs(game.frame_dt_scale() - 2.0) < 1e-9


def test_scale_shrinks_for_a_faster_than_target_frame(game):
    game.dt = 1 / (gui_mod.TARGET_FPS * 2)  # double the target rate
    assert abs(game.frame_dt_scale() - 0.5) < 1e-9


def test_scale_is_clamped_against_a_single_bad_hitch(game):
    game.dt = 5.0  # a multi-second stall
    assert game.frame_dt_scale() == gui_mod.MAX_FRAME_DT * gui_mod.TARGET_FPS


def test_scale_can_never_exceed_the_clamp(game):
    for dt in (0.1, 0.5, 1.0, 10.0, 100.0):
        game.dt = dt
        assert game.frame_dt_scale() <= gui_mod.MAX_FRAME_DT * gui_mod.TARGET_FPS
