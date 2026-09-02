"""Tests for Game.frame_dt_scale(), the shared delta-time normalizer.

Every game's movement multiplies by this instead of a bare per-iteration
constant, so its own correctness (including the clamp) is worth testing
independently of any one game's use of it.
"""
from gui import gui as gui_mod


def test_scale_is_1_at_exactly_the_target_frame_rate(game):
    game.dt = 1 / gui_mod.MOVEMENT_REFERENCE_FPS
    assert abs(game.frame_dt_scale() - 1.0) < 1e-9


def test_scale_is_1_before_the_first_frame_has_ever_ticked(game):
    game.dt = 0
    assert game.frame_dt_scale() == 1.0


def test_scale_grows_for_a_slower_than_target_frame(game):
    game.dt = 1 / (gui_mod.MOVEMENT_REFERENCE_FPS / 2)  # half the target rate
    assert abs(game.frame_dt_scale() - 2.0) < 1e-9


def test_scale_shrinks_for_a_faster_than_target_frame(game):
    game.dt = 1 / (gui_mod.MOVEMENT_REFERENCE_FPS * 2)  # double the target rate
    assert abs(game.frame_dt_scale() - 0.5) < 1e-9


def test_scale_is_clamped_against_a_single_bad_hitch(game):
    game.dt = 5.0  # a multi-second stall
    assert game.frame_dt_scale() == gui_mod.MAX_FRAME_DT * gui_mod.MOVEMENT_REFERENCE_FPS


def test_scale_can_never_exceed_the_clamp(game):
    for dt in (0.1, 0.5, 1.0, 10.0, 100.0):
        game.dt = dt
        assert game.frame_dt_scale() <= gui_mod.MAX_FRAME_DT * gui_mod.MOVEMENT_REFERENCE_FPS


def test_render_target_cannot_change_movement_speed(game, monkeypatch):
    # The regression this guards against: dt_scale used to normalise
    # against TARGET_FPS, so raising the render target from 30 to 60
    # silently doubled the intended real-world speed of all three games.
    # A rendering target must never be an input to movement maths.
    game.dt = 1 / 30
    before = game.frame_dt_scale()
    monkeypatch.setattr(gui_mod, "TARGET_FPS", 144)
    assert game.frame_dt_scale() == before


def test_real_time_speed_is_identical_at_every_sustainable_frame_rate(game):
    # A constant tuned as "N pixels per frame" has to cover the same
    # distance per second at any frame rate down to the clamp floor -
    # otherwise the game speeds up on faster hardware, which is exactly
    # what the TARGET_FPS-normalised version did between 20 and 30 FPS.
    speed = 10
    expected = speed * gui_mod.MOVEMENT_REFERENCE_FPS
    for fps in (15, 20, 30, 45, 60, 120):
        game.dt = 1 / fps
        travelled_per_second = fps * speed * game.frame_dt_scale()
        assert abs(travelled_per_second - expected) < 1e-6, f"differs at {fps} FPS"
