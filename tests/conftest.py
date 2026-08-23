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


@pytest.fixture
def sandboxed_data_dir(tmp_path, monkeypatch):
    """Point gui.gui.DATA_DIR at a throwaway directory for one test.

    Yields the gui.gui module itself, already patched, so a test can still
    reach anything else it needs from it.
    """
    from gui import gui as gui_mod

    monkeypatch.setattr(gui_mod, "DATA_DIR", str(tmp_path))
    return gui_mod


@pytest.fixture
def game(sandboxed_data_dir):
    """A real Game instance, built against the sandboxed data dir.

    run() is stubbed out so construction returns instead of falling into
    the main menu loop - everything before that (settings, database,
    display, camera, sound) is real.
    """
    Game = sandboxed_data_dir.Game
    Game.run = lambda self: None
    return Game()


class FakeCap:
    """Stands in for cv2.VideoCapture - always "open", always has a frame."""

    def isOpened(self):
        return True

    def read(self):
        import numpy as np

        return True, np.zeros((480, 640, 3), dtype=np.uint8)

    def release(self):
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
