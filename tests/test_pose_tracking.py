"""Tests for the jump/duck threshold math in models/pose_tracking.py.

This is the highest-value untested logic in the codebase: pure functions
with no camera/display/mediapipe dependency that directly decide how hard
a Runner player has to move their head to trigger a jump or a duck. A
change to the sensitivity formula, the offset constants, or the frame-edge
clamps could silently make jump/duck impossible (or trivial) with nothing
to catch it before a player does - these tests are that catch.
"""
import statistics

from models.pose_tracking import (
    DUCK_LINE_RATIO,
    JUMP_LINE_RATIO,
    calibrate_baseline,
    sensitivity_scale,
    threshold_ratios,
)


def test_sensitivity_scale_leaves_the_default_offsets_unchanged_at_5():
    assert sensitivity_scale(5) == 1.0


def test_sensitivity_scale_clamps_below_the_1_to_10_range():
    assert sensitivity_scale(0) == sensitivity_scale(1)
    assert sensitivity_scale(-100) == sensitivity_scale(1)


def test_sensitivity_scale_clamps_above_the_1_to_10_range():
    assert sensitivity_scale(11) == sensitivity_scale(10)
    assert sensitivity_scale(999) == sensitivity_scale(10)


def test_sensitivity_scale_decreases_as_sensitivity_increases():
    # Higher sensitivity should require a smaller movement, i.e. a smaller
    # multiplier on the offset - never the other way around.
    values = [sensitivity_scale(s) for s in range(1, 11)]
    assert values == sorted(values, reverse=True)
    assert values[0] > values[-1]


def test_threshold_ratios_falls_back_to_fixed_lines_without_a_baseline():
    assert threshold_ratios(None) == (JUMP_LINE_RATIO, DUCK_LINE_RATIO)
    assert threshold_ratios(None, sensitivity=1) == (JUMP_LINE_RATIO, DUCK_LINE_RATIO)


def test_threshold_ratios_straddles_the_measured_baseline():
    jump_ratio, duck_ratio = threshold_ratios(0.5, sensitivity=5)
    assert jump_ratio < 0.5 < duck_ratio


def test_threshold_ratios_never_pushes_the_jump_line_off_the_top_of_frame():
    # A baseline near the very top of frame, at max sensitivity (the
    # largest offset), is exactly the case the 0.05 clamp exists for.
    jump_ratio, _ = threshold_ratios(0.02, sensitivity=1)
    assert jump_ratio >= 0.05


def test_threshold_ratios_never_pushes_the_duck_line_off_the_bottom_of_frame():
    _, duck_ratio = threshold_ratios(0.98, sensitivity=1)
    assert duck_ratio <= 0.95


def test_threshold_ratios_requires_more_movement_at_lower_sensitivity():
    jump_low, duck_low = threshold_ratios(0.5, sensitivity=1)
    jump_high, duck_high = threshold_ratios(0.5, sensitivity=10)
    assert (0.5 - jump_low) > (0.5 - jump_high)
    assert (duck_low - 0.5) > (duck_high - 0.5)


def test_threshold_ratios_duck_offset_is_smaller_than_jump_offset():
    # There is usually less headroom below the resting position than
    # above it, so ducking should need proportionally less movement.
    jump_ratio, duck_ratio = threshold_ratios(0.5, sensitivity=5)
    assert (duck_ratio - 0.5) < (0.5 - jump_ratio)


def test_calibrate_baseline_refuses_fewer_than_5_samples():
    assert calibrate_baseline([]) is None
    assert calibrate_baseline([0.1, 0.2, 0.3, 0.4]) is None


def test_calibrate_baseline_is_the_median_of_the_samples():
    samples = [0.4, 0.5, 0.6, 0.7, 0.8]
    assert calibrate_baseline(samples) == statistics.median(samples)


def test_calibrate_baseline_ignores_a_single_outlier():
    # The median, not the mean, is what makes one bad reading harmless.
    samples = [0.5, 0.5, 0.5, 0.5, 0.99]
    assert calibrate_baseline(samples) == 0.5
