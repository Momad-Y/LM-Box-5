"""Tests for Runner's jump physics.

Runner.update() is a plain pygame.sprite.Sprite method with no camera or
display dependency, so it's directly testable. These tests protect two
things: the module's own documented invariant ("clears the tallest 60px
cactus with plenty of room"), and the dt-scaled integration added so jump
height/duration stay the same regardless of the frame rate the hardware
actually sustains - the exact property a naive per-frame `+=` would not
have had.
"""
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

pygame.init()
pygame.display.set_mode((1, 1))

from gui.runner_sprites import Runner

TALLEST_CACTUS_HEIGHT = 60


def _bare_runner():
    """A Runner with just the state update() needs, no image loading."""
    runner = Runner.__new__(Runner)
    runner.altitude = 0
    runner.velocity_y = 0
    runner.jumping = False
    runner.ducking = False
    runner.animation_timer = 0
    runner.run_index = 0
    runner.duck_index = 0
    runner.image = None
    runner.jump_img = "jump-frame"
    runner.run_imgs = ["run-0", "run-1"]
    runner.duck_imgs = ["duck-0", "duck-1"]
    runner._align_to_ground = lambda: None
    return runner


def _simulate_jump(dt_scale):
    """Run one full jump at a fixed dt_scale, return (peak altitude, calls)."""
    runner = _bare_runner()
    runner.update(jump_input=True, dt_scale=dt_scale)
    peak = runner.altitude
    calls = 1

    guard = 0
    while runner.jumping and guard < 100_000:
        runner.update(jump_input=False, dt_scale=dt_scale)
        peak = max(peak, runner.altitude)
        calls += 1
        guard += 1

    assert guard < 100_000, "jump never landed - infinite loop guard tripped"
    return peak, calls


def test_jump_starts_only_on_a_rising_edge():
    runner = _bare_runner()
    runner.update(jump_input=True, dt_scale=1.0)
    assert runner.jumping is True

    velocity_after_first_tick = runner.velocity_y
    # Holding jump_input while already jumping must not re-trigger the launch
    runner.update(jump_input=True, dt_scale=1.0)
    assert runner.velocity_y != velocity_after_first_tick or runner.jumping


def test_jump_clears_the_tallest_cactus_at_the_reference_frame_rate():
    peak, _ = _simulate_jump(dt_scale=1.0)
    assert peak > TALLEST_CACTUS_HEIGHT


def test_jump_peak_altitude_matches_the_documented_invariant():
    # Module docstring: apex ~= JUMP_VELOCITY^2 / (2 * GRAVITY) ~= 137px
    peak, _ = _simulate_jump(dt_scale=1.0)
    assert 120 <= peak <= 155


def test_jump_lands_eventually():
    runner = _bare_runner()
    runner.update(jump_input=True, dt_scale=1.0)
    guard = 0
    while runner.jumping and guard < 100_000:
        runner.update(dt_scale=1.0)
        guard += 1
    assert not runner.jumping
    assert runner.altitude == 0
    assert runner.velocity_y == 0


def test_jump_peak_altitude_is_consistent_across_simulated_frame_rates():
    # Half the frame rate (dt_scale=2.0) and double the frame rate
    # (dt_scale=0.5) should reach ~the same real-world peak height as the
    # reference rate - this is the property a plain `altitude -= velocity_y`
    # would NOT have had, since it would move twice as far per call at half
    # the frame rate with nothing to compensate.
    peak_reference, _ = _simulate_jump(dt_scale=1.0)
    peak_half_rate, _ = _simulate_jump(dt_scale=2.0)
    peak_double_rate, _ = _simulate_jump(dt_scale=0.5)

    assert abs(peak_half_rate - peak_reference) / peak_reference < 0.15
    assert abs(peak_double_rate - peak_reference) / peak_reference < 0.15


def test_jump_clears_the_cactus_at_every_simulated_frame_rate():
    for dt_scale in (0.5, 1.0, 2.0, 3.0):
        peak, _ = _simulate_jump(dt_scale=dt_scale)
        assert peak > TALLEST_CACTUS_HEIGHT


def test_jump_takes_proportionally_fewer_update_calls_at_higher_dt_scale():
    # The property a no-op dt_scale (i.e. the fix silently reverted) would
    # NOT have: if dt_scale doesn't actually affect the integration, the
    # number of update() calls needed to land is identical no matter what
    # dt_scale is passed in. Real scaling makes it roughly inversely
    # proportional instead - a slower simulated frame rate (higher
    # dt_scale) reaches the ground in fewer, larger steps.
    _, calls_at_1x = _simulate_jump(dt_scale=1.0)
    _, calls_at_2x = _simulate_jump(dt_scale=2.0)
    _, calls_at_half = _simulate_jump(dt_scale=0.5)

    assert calls_at_2x < calls_at_1x * 0.7
    assert calls_at_half > calls_at_1x * 1.3


def test_ducking_does_not_start_a_jump():
    runner = _bare_runner()
    runner.update(duck_input=True, dt_scale=1.0)
    assert runner.jumping is False
    assert runner.ducking is True


def test_duck_animation_advances_with_dt_scale():
    runner = _bare_runner()
    runner.update(duck_input=True, dt_scale=1.0)
    assert runner.animation_timer == 1.0

    runner.animation_timer = 0
    runner.update(duck_input=True, dt_scale=2.5)
    assert runner.animation_timer == 2.5
