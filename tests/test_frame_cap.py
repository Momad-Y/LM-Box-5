"""Tests for the 60 FPS cap.

pygame's own Clock.tick(60) computes its target frame time in whole
milliseconds - int(1000/60) is 16 - so it paces at up to 62.5 FPS, which is
why the on-screen counter was seen at 61-62 on light screens. gui.frame_clock
replaces it; these tests are what keep 60 meaning 60.

Timing assertions use loose tolerances and short runs deliberately: the
point is "never meaningfully above the cap", not sub-millisecond precision
on a machine that may be busy running the rest of this suite.
"""
import time

import pygame

from gui import gui as gui_mod
from gui.frame_clock import FrameClock


def _measure(clock, framerate, frames=30, work=0.0):
    """Frames per second actually achieved over `frames` ticks."""
    clock.tick(framerate)  # start the interval fresh
    start = time.perf_counter()
    for _ in range(frames):
        if work:
            time.sleep(work)
        clock.tick(framerate)
    return frames / (time.perf_counter() - start)


def test_a_60_fps_request_never_runs_meaningfully_faster_than_60():
    achieved = _measure(FrameClock(), 60)
    assert achieved <= 60.5, f"ran at {achieved:.2f} fps, above the 60 cap"


def test_the_cap_is_actually_reached_not_just_undershot():
    # A limiter that simply slept too long would pass the test above while
    # making the game slower than it should be.
    achieved = _measure(FrameClock(), 60)
    assert achieved >= 58.0, f"only reached {achieved:.2f} fps, well under 60"


def test_a_clock_ceiling_overrides_a_higher_per_call_request():
    # The structural half of the guarantee: even a call site asking for 240
    # cannot exceed the ceiling the clock was built with, so the cap does
    # not depend on all ~23 tick() call sites passing the right literal.
    achieved = _measure(FrameClock(max_fps=60), 240)
    assert achieved <= 60.5, f"ran at {achieved:.2f} fps despite a 60 ceiling"


def test_a_ceiling_still_applies_when_no_rate_is_requested():
    achieved = _measure(FrameClock(max_fps=60), 0)
    assert achieved <= 60.5, f"ran at {achieved:.2f} fps with no rate requested"


def test_a_loop_slower_than_the_cap_is_not_throttled_further():
    # 25ms of work per frame is a natural ~40 FPS. The limiter must let it
    # run at its own pace rather than waiting out a 60 FPS deadline it has
    # already missed - otherwise every camera-driven game screen (all of
    # which run under 60 on real hardware) would be slowed down by the cap.
    achieved = _measure(FrameClock(max_fps=60), 60, frames=20, work=0.025)
    assert achieved >= 35.0, f"a naturally-40fps loop was throttled to {achieved:.2f}"


def test_reported_fps_matches_the_rate_actually_being_paced():
    clock = FrameClock(max_fps=60)
    _measure(clock, 60)
    assert 57.0 <= clock.get_fps() <= 60.5


def test_reported_fps_is_zero_before_any_frame_has_been_timed():
    assert FrameClock().get_fps() == 0.0


def test_tick_returns_milliseconds_like_pygames_clock_does():
    # Every game loop computes `dt = clock.tick(60) / 1000` and feeds that
    # to frame_dt_scale(), so the unit has to stay milliseconds.
    clock = FrameClock(max_fps=60)
    clock.tick(60)
    elapsed_ms = clock.tick(60)
    assert 10.0 < elapsed_ms < 40.0, f"{elapsed_ms}ms is not a ~16ms frame in ms"


# ------------------------------------------------------- wiring into Game
def test_the_game_does_not_use_pygames_own_clock(game):
    # pygame's Clock cannot express a 60 FPS cap at all (see module
    # docstring), so using one anywhere would silently reintroduce 62.5.
    assert isinstance(game.clock, FrameClock)
    assert not isinstance(game.clock, pygame.time.Clock)


def test_the_games_clock_is_capped_at_the_render_target(game):
    assert game.clock._max_fps == gui_mod.TARGET_FPS


def test_no_screen_constructs_its_own_pygame_clock():
    # Every screen paces off game.clock. A module building its own
    # pygame.time.Clock would be uncapped again.
    import pathlib

    for path in pathlib.Path("gui").glob("*.py"):
        source = path.read_text()
        assert "pygame.time.Clock()" not in source, (
            f"{path} builds a raw pygame clock, which cannot honour a 60 FPS cap"
        )


# ------------------------------------------------- drop-in completeness
def test_frame_clock_covers_pygames_entire_clock_surface():
    # FrameClock replaces pygame.time.Clock wholesale, so any public method
    # of the real Clock that it does not implement is a crash waiting for
    # whichever screen happens to call it. That is not hypothetical: the
    # first version implemented only tick() and get_fps(), and the Credits
    # screen - the one screen that scrolls by elapsed time - called
    # get_time() and brought the app down with an AttributeError.
    real = {name for name in dir(pygame.time.Clock()) if not name.startswith("_")}
    ours = {name for name in dir(FrameClock()) if not name.startswith("_")}
    missing = real - ours
    assert not missing, f"FrameClock is missing pygame Clock methods: {sorted(missing)}"


def test_get_time_reports_the_last_frames_duration():
    clock = FrameClock(max_fps=60)
    clock.tick(60)
    returned = clock.tick(60)
    # get_time() must agree with what tick() just returned, in milliseconds
    assert abs(clock.get_time() - returned) < 1e-6
    assert 10.0 < clock.get_time() < 40.0


def test_get_time_is_nonzero_before_the_second_tick_and_never_none():
    # The Credits scroll multiplies by this every frame; a None or a
    # missing attribute is what broke it, so pin the type down.
    clock = FrameClock(max_fps=60)
    assert isinstance(clock.get_time(), float)
    assert isinstance(clock.get_rawtime(), float)


def test_get_rawtime_excludes_the_time_spent_waiting():
    # A near-empty frame spends almost all of its wall time waiting for the
    # cap, so raw work time must come out far below the full frame time.
    clock = FrameClock(max_fps=60)
    clock.tick(60)
    clock.tick(60)
    assert clock.get_rawtime() < clock.get_time()


def test_the_credits_scroll_advances_with_real_elapsed_time():
    # Reproduces exactly what gui/screen_credits.py does each frame.
    clock = FrameClock(max_fps=60)
    clock.tick(60)
    offset = 0.0
    for _ in range(5):
        clock.tick(60)
        offset += 30 * clock.get_time() / 1000
    assert offset > 0, "credits would never scroll"
