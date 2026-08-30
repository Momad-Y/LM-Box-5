"""Shared fixtures for the test suite.

Every fixture that touches gui.gui.DATA_DIR sandboxes it to a fresh temp
directory before gui.gui is ever imported. This codebase has already lost
its real user database once to a test harness that skipped this step (see
the project's own notes on the incident) - the fixtures here make that
mistake structurally impossible instead of relying on every future test
remembering to do it by hand.
"""
import os
import sys

import pytest

# Must be set before pygame/mediapipe import anything that touches a real
# display or audio device, so the suite runs headless in CI and locally.
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


@pytest.fixture(autouse=True)
def _stop_all_camera_threads():
    """Release every ThreadedCapture background thread after each test.

    A safety net on top of the `game` fixture's own teardown (which only
    covers Game() instances built through that specific fixture) - not
    every test constructs its Game()/camera that way (some patch
    cv2.VideoCapture directly, one-off style), and orphaned background
    threads accumulating across a 150+-test run were measured to make the
    whole suite's process take far longer to actually exit than pytest's
    own reported test time. Autouse, so this applies to every test without
    each one needing to ask for it.
    """
    yield
    from gui.camera_stream import stop_all

    stop_all()


@pytest.fixture
def sandboxed_data_dir(tmp_path, monkeypatch):
    """Point gui.gui.DATA_DIR at a throwaway directory for one test.

    Yields the gui.gui module itself, already patched, so a test can still
    reach anything else it needs from it.
    """
    from gui import gui as gui_mod

    monkeypatch.setattr(gui_mod, "DATA_DIR", str(tmp_path))
    return gui_mod


class FakeCap:
    """Stands in for cv2.VideoCapture - always "open", always has a frame."""

    def isOpened(self):
        return True

    def read(self):
        import numpy as np

        return True, np.zeros((480, 640, 3), dtype=np.uint8)

    def set(self, prop_id, value):
        return True

    def get(self, prop_id):
        return 0

    def release(self):
        pass


@pytest.fixture
def sandboxed_camera(monkeypatch):
    """Replace cv2.VideoCapture with a fake before any Game() is built.

    init_camera() wraps whatever cv2.VideoCapture(...) returns in
    ThreadedCapture, which spins up a background thread that polls
    .read() *continuously, forever* - a single real camera handle opened
    and left alone (the old behavior) was already not great in a test
    suite that constructs 100+ Game() instances, but an actively-polling
    thread per instance means 100+ threads hammering whatever real
    webcam happens to be attached to the machine running the tests. This
    isn't hypothetical: an earlier version of this suite did exactly
    that against real hardware and froze the machine hard enough to need
    a forced restart, on hardware already known to be fragile around
    camera stress (see docs/PERFORMANCE_AUDIT.md's incident notes). This
    must run before Game() is constructed - patching game.cap
    afterward (see balloons_ready/pong_ready below) is too late, since
    init_camera() has already opened the real device and started its
    thread by the time __init__ returns.
    """
    import cv2

    from gui import gui as gui_mod

    monkeypatch.setattr(gui_mod.cv2, "VideoCapture", lambda *a, **k: FakeCap())
    return cv2


@pytest.fixture
def game(sandboxed_data_dir, sandboxed_camera):
    """A real Game instance, built against the sandboxed data dir and a
    fake camera.

    run() is stubbed out so construction returns instead of falling into
    the main menu loop - everything before that (settings, database,
    display, sound, mediapipe) is real; only the camera is faked (see
    sandboxed_camera). Releases the camera thread and closes the real
    mediapipe Hands/Pose objects once the test is done, using references
    captured right after construction rather than read back from
    game.cap/.hand_tracking/etc. at teardown time - some tests
    (balloons_ready/pong_ready below) replace game.cap with a different
    fake via monkeypatch, which reverts its patches in its own teardown at
    an order relative to this fixture's that isn't safe to assume, and
    would otherwise risk this fixture closing whatever monkeypatch had
    already put back rather than what construction actually created.
    This isn't just tidiness: every one of this suite's 170+ tests builds
    a real Game() with real mediapipe models, each holding a GPU context
    on this machine's Mesa/Intel driver - leaving all of them open for the
    whole pytest process was measured to freeze this laptop hard enough to
    need a forced restart, the same way the original unreleased-camera bug
    did (see quit_app()'s docstring and docs/PERFORMANCE_AUDIT.md).
    """
    Game = sandboxed_data_dir.Game
    Game.run = lambda self: None
    instance = Game()
    threaded_cap = instance.cap
    hands_to_close = [
        hands
        for hands in (
            getattr(instance.hand_tracking, "hands", None),
            getattr(instance.finger_detector, "hands", None),
        )
        if hands is not None
    ]
    pose_detector = instance.pose_detector
    try:
        yield instance
    finally:
        threaded_cap.release()
        # A test can legitimately close these itself first (e.g.
        # test_shutdown_cleanup.py calling the real quit_app()) - mediapipe
        # raises ValueError on a second close() rather than tolerating it,
        # so "already closed" has to be an expected outcome here, not an
        # error.
        for hands in hands_to_close:
            try:
                hands.close()
            except ValueError:
                pass
        if pose_detector is not None:
            try:
                pose_detector.close()
            except ValueError:
                pass


@pytest.fixture
def balloons_ready(game, sandboxed_data_dir, monkeypatch):
    """A Game with Balloons fully initialized, stopped just before play.

    Stubs the camera (no real webcam in CI), the how-to screen, the player
    picker, and the get-ready timer (which would otherwise block waiting
    for a keypress) - everything else in init_balloons_game runs for real.
    """
    user_id = game.add_user_returning_id("Player")
    monkeypatch.setattr(game, "cap", FakeCap())
    monkeypatch.setattr(sandboxed_data_dir.screen_ingame, "show_instructions", lambda *a, **k: True)
    monkeypatch.setattr(game, "select_players", lambda *a, **k: [user_id])
    monkeypatch.setattr(game, "start_balloons_game_timer", lambda: None)
    game.init_balloons_game()
    return game


@pytest.fixture
def pong_ready(game, sandboxed_data_dir, monkeypatch):
    """A Game with Pong fully initialized, stopped just before play.

    Same idea as balloons_ready: stubs everything interactive so
    init_pong_game's real geometry/state setup runs unattended.
    """
    user_id_1 = game.add_user_returning_id("Player 1")
    user_id_2 = game.add_user_returning_id("Player 2")
    monkeypatch.setattr(game, "cap", FakeCap())
    monkeypatch.setattr(sandboxed_data_dir.screen_ingame, "show_instructions", lambda *a, **k: True)
    monkeypatch.setattr(game, "select_players", lambda *a, **k: [user_id_1, user_id_2])
    monkeypatch.setattr(game, "start_pong_game_timer", lambda: None)
    game.init_pong_game()
    return game
