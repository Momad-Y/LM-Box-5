"""Tests for the game-balance fixes in docs/BALANCE.md.

Covers: the Runner jump-vs-duck fix (already exercised in depth by
test_runner_physics.py's duck-vs-jump section), the Balloons wave-5
front-loading tweak, the Pong per-rally-to-per-match speed ramp, and the
Runner speed-milestone pacing change.
"""
import ast

from gui.gui import RUNNER_SPEED_MILESTONE_POINTS
from gui.utils import biased_random_int


def _game_class(src):
    tree = ast.parse(src)
    return next(n for n in ast.walk(tree) if isinstance(n, ast.ClassDef) and n.name == "Game")


def _method_source(game_class, src, name):
    node = next(
        n for n in ast.walk(game_class) if isinstance(n, ast.FunctionDef) and n.name == name
    )
    return ast.get_source_segment(src, node)


# --------------------------------------------------------- balloons pacing
def test_wave_appearance_bias_tapers_down_for_denser_waves():
    src = open("gui/gui.py").read()
    game_class = _game_class(src)
    body_src = _method_source(game_class, src, "init_balloons")

    assert "apperance_time_bias_per_wave" in body_src
    # The bias must vary per wave (not a single constant reused everywhere) -
    # that's what makes later, denser waves spread out instead of bursting.
    assert "apperance_time_bias_per_wave[wave_config]" in body_src


def test_lower_bias_strength_meaningfully_reduces_front_loading():
    # Direct statistical check on the real function: wave 5's configured
    # bias (3) must front-load its balloons noticeably less than the old
    # blanket bias (10) did, not just nominally less.
    max_wave_time = 20
    bias_range = (0, max_wave_time // 2)

    def frac_in_first_half(bias_strength, samples=4000):
        hits = sum(
            1
            for _ in range(samples)
            if biased_random_int(0, max_wave_time, bias_range, bias_strength) <= max_wave_time // 2
        )
        return hits / samples

    frac_old = frac_in_first_half(10)
    frac_new = frac_in_first_half(3)

    assert frac_old > 0.85, f"sanity check on the old behavior failed: {frac_old}"
    assert frac_new < frac_old - 0.10, (
        f"tapered bias (3) didn't meaningfully reduce front-loading vs the old "
        f"blanket bias (10): {frac_new} vs {frac_old}"
    )


def test_every_generated_wave_still_has_balloons(balloons_ready):
    # Regression guard: tapering the bias must not accidentally break wave
    # generation (e.g. an out-of-range bias_strength for a wave index).
    game = balloons_ready
    for wave in game.waves_balloons:
        assert wave, "a wave was generated with zero balloons"


# ------------------------------------------------------------ pong ramp
def test_pong_speed_ramp_timer_is_not_reset_by_scoring():
    # The old bug: round_start_time reset on every scored point, so the
    # +3-every-7s ramp only ever accumulated within one uninterrupted rally,
    # never across the whole match. The ramp timer must survive a point
    # being scored - only the periodic increment itself should reset it.
    src = open("gui/gui.py").read()
    game_class = _game_class(src)
    start_src = _method_source(game_class, src, "start_pong_game")

    # The ramp timer must be initialized once and updated only by the
    # periodic increment check - never re-initialized by scoring.
    assert start_src.count("last_speed_increment_time = time.time()") == 1
    assert start_src.count("last_speed_increment_time = current_time") == 1

    # Confirm both scoring blocks reset ball_speed_x/y but not the timer.
    for marker in ("self.player1_score += 1", "self.player2_score += 1"):
        idx = start_src.index(marker)
        # The next ~10 lines after a score are the reset block; the timer
        # variable must not appear anywhere in it.
        block = start_src[idx : idx + 400]
        assert "last_speed_increment_time" not in block
        assert "round_start_time" not in start_src


# ---------------------------------------------------- runner ramp pacing
def test_runner_speed_milestone_is_frequent_enough_for_an_average_round():
    # Decision: the ramp should be a normal mid-round event, not a rare
    # reward only exceptional-length runs reach. At the default score rate
    # (3 points/sec at Normal), the first bump must land well under a
    # minute in, not the old ~33s-per-100-points pacing.
    score_rate = 3.0  # points/sec at Normal difficulty (0.1 * 30fps)
    time_to_first_milestone = RUNNER_SPEED_MILESTONE_POINTS / score_rate
    assert time_to_first_milestone < 20, (
        f"first speed bump takes {time_to_first_milestone:.1f}s - "
        "too slow to read as a normal round event"
    )


def test_runner_milestone_uses_the_named_constant_not_a_hardcoded_100():
    src = open("gui/gui.py").read()
    game_class = _game_class(src)
    body_src = _method_source(game_class, src, "start_runner_game")
    assert "RUNNER_SPEED_MILESTONE_POINTS" in body_src
    assert "// 100" not in body_src
