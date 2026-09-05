"""Actually run every screen's real loop for a few frames.

The rest of the suite checks screens structurally - that a method exists,
that a source line says what it should. None of it ever *executed* a screen
loop, which is how `screen_credits.run` shipped calling `clock.get_time()`
on a FrameClock that had no such method: every test passed, and the app
died with an AttributeError the moment a player opened Credits.

Anything a screen only touches at runtime - a method on a substituted
object, an attribute set by a different code path, a name typo in a branch
nothing else takes - is invisible to a structural test and obvious to this
one. Each test here drives the genuine loop (real drawing, real event
handling, real clock, real ThreadedCapture) for a handful of frames and
fails on any exception.

Loops are bounded by swapping in a clock whose tick() raises after N
frames. Every loop in the app calls clock.tick() once per iteration, so
this terminates all of them without needing to know how each one decides
to exit - and it passes 0 to the real tick, so the frames run flat out
instead of sleeping out a 60 FPS cap in a test suite.
"""
import pytest

from gui import (
    gui as gui_mod,
    screen_credits,
    screen_ingame,
    screen_leaderboards,
    screen_menu,
    screen_settings,
    screen_users,
)

FRAMES = 4


class _StopLoop(Exception):
    """Raised from the patched clock to end a screen loop under test."""


def run_frames(game, call, frames=FRAMES):
    """Run `call()` for `frames` rendered frames, then stop it.

    Returns the number of frames actually drawn, so a test can tell "the
    loop ran and was cut off" apart from "the loop returned immediately
    without drawing anything", which would make the check vacuous.
    """
    real_tick = game.clock.tick
    drawn = {"count": 0}

    def bounded_tick(framerate=0):
        drawn["count"] += 1
        if drawn["count"] > frames:
            raise _StopLoop
        return real_tick(0)  # 0 = measure, don't pace: keeps the suite fast

    game.clock.tick = bounded_tick
    try:
        call()
    except _StopLoop:
        pass
    finally:
        game.clock.tick = real_tick
    return drawn["count"] - 1


def assert_screen_runs(game, call, frames=FRAMES):
    rendered = run_frames(game, call, frames)
    assert rendered >= 1, "screen returned without drawing a frame - nothing was tested"


# --------------------------------------------------------------- menus
def test_main_menu_loop_runs(game):
    assert_screen_runs(game, game.start_main_menu)


def test_menu_module_loop_runs(game):
    assert_screen_runs(game, lambda: screen_menu.run(game))


def test_users_screen_loop_runs(game):
    assert_screen_runs(game, lambda: screen_users.run(game))


def test_leaderboards_screen_loop_runs(game):
    assert_screen_runs(game, lambda: screen_leaderboards.run(game))


def test_settings_screen_loop_runs(game):
    assert_screen_runs(game, lambda: screen_settings.run(game))


def test_credits_screen_loop_runs(game):
    # The exact screen that crashed: it is the only one that advances by
    # clock.get_time(), so it is the only one a missing Clock method broke.
    assert_screen_runs(game, lambda: screen_credits.run(game))


def test_credits_scrolls_rather_than_sitting_still(game):
    # Guards the reason get_time() is called at all - a get_time() that
    # always returned 0 would satisfy every other test here while leaving
    # the credits frozen on screen.
    seen = []
    real_draw = screen_credits.draw
    screen_credits.draw = lambda g, offset: seen.append(offset)
    try:
        run_frames(game, lambda: screen_credits.run(game), frames=8)
    finally:
        screen_credits.draw = real_draw

    assert len(set(seen)) > 1, f"credits never scrolled: offsets stayed {set(seen)}"


# ------------------------------------------------------- in-game screens
def test_instructions_screen_loop_runs(game):
    game.instructions_seen = set()  # otherwise it returns before drawing
    assert_screen_runs(
        game, lambda: screen_ingame.show_instructions(game, "balloons", waves=5)
    )


def test_privacy_notice_loop_runs(game):
    assert_screen_runs(game, lambda: screen_ingame.show_privacy_notice(game))


def test_no_camera_screen_loop_runs(game):
    assert_screen_runs(game, lambda: screen_ingame.show_no_camera(game, "Runner"))


# ---------------------------------------------------------- prompt loops
def test_ask_yes_no_loop_runs(game):
    assert_screen_runs(game, lambda: game.ask_yes_no("Delete?", ("A line",)))


def test_prompt_text_loop_runs(game):
    assert_screen_runs(game, lambda: game.prompt_text("New user", lines=("Type",)))


def test_player_picker_loop_runs(game):
    game.add_user_returning_id("Smoke")
    assert_screen_runs(game, lambda: game.select_players("BALLOONS", ("Player",)))


def test_face_capture_loop_runs(game):
    # Exercises the camera path end to end: capture_scaled_frame ->
    # ThreadedCapture.read -> cutout models -> preview draw.
    user_id = game.add_user_returning_id("Face")
    assert_screen_runs(game, lambda: game.capture_user_face(user_id, "Face"))


# ------------------------------------------------------------ game loops
def test_balloons_round_loop_runs(balloons_ready):
    assert_screen_runs(balloons_ready, balloons_ready.start_balloons_game)


def test_balloons_countdown_loop_runs(balloons_ready):
    # Called off the class, not the instance: the *_ready fixtures stub the
    # countdown on the instance so init_* can return, and calling the stub
    # would test nothing.
    assert_screen_runs(
        balloons_ready,
        lambda: type(balloons_ready).start_balloons_game_timer(balloons_ready),
    )


def test_balloons_game_over_screen_runs(balloons_ready):
    assert_screen_runs(balloons_ready, balloons_ready.end_balloons_game)


def test_pong_round_loop_runs(pong_ready):
    assert_screen_runs(pong_ready, pong_ready.start_pong_game)


def test_pong_countdown_loop_runs(pong_ready):
    assert_screen_runs(
        pong_ready, lambda: type(pong_ready).start_pong_game_timer(pong_ready)
    )


def test_pong_game_over_screen_runs(pong_ready):
    assert_screen_runs(pong_ready, pong_ready.end_pong_game)


@pytest.fixture
def runner_ready(game, sandboxed_data_dir, monkeypatch):
    """Runner initialised up to the point its round loop can be called."""
    user_id = game.add_user_returning_id("Runner")
    monkeypatch.setattr(
        sandboxed_data_dir.screen_ingame, "show_instructions", lambda *a, **k: True
    )
    monkeypatch.setattr(game, "select_players", lambda *a, **k: [user_id])
    monkeypatch.setattr(game, "start_runner_game_timer", lambda: None)
    game.init_runner_game()
    return game


def test_runner_round_loop_runs(runner_ready):
    assert_screen_runs(runner_ready, runner_ready.start_runner_game)


def test_runner_countdown_loop_runs(runner_ready):
    assert_screen_runs(
        runner_ready, lambda: type(runner_ready).start_runner_game_timer(runner_ready)
    )


def test_runner_game_over_screen_runs(runner_ready):
    assert_screen_runs(runner_ready, runner_ready.end_runner_game)
