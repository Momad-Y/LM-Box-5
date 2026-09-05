"""Tests for quit_app() - the centralized shutdown path that releases the
camera and mediapipe models before the process exits.

Root cause this guards against: the game used to leave the camera open and
actively streaming for its entire life, then let the process die with it
still streaming instead of stopping it gracefully first. On real hardware
this was severe enough to hang the whole machine, not just the app,
requiring a hard reboot - not merely a resource leak. See
docs/PERFORMANCE_AUDIT.md's note on this incident.
"""
import ast
import sys
from unittest.mock import MagicMock

import pygame


def _game_class(src):
    tree = ast.parse(src)
    return next(n for n in ast.walk(tree) if isinstance(n, ast.ClassDef) and n.name == "Game")


def _method_source(game_class, src, name):
    node = next(
        n for n in ast.walk(game_class) if isinstance(n, ast.FunctionDef) and n.name == name
    )
    return ast.get_source_segment(src, node)


def _stub_exit(game, monkeypatch):
    """Prevent quit_app() from actually tearing down pygame or the process."""
    monkeypatch.setattr(pygame, "quit", MagicMock())
    monkeypatch.setattr(sys, "exit", MagicMock())


def test_quit_app_releases_the_camera(game, monkeypatch):
    _stub_exit(game, monkeypatch)
    fake_cap = MagicMock()
    monkeypatch.setattr(game, "cap", fake_cap)

    game.quit_app()

    fake_cap.release.assert_called_once()


def test_quit_app_closes_the_hand_tracking_model(game, monkeypatch):
    _stub_exit(game, monkeypatch)
    monkeypatch.setattr(game, "cap", MagicMock())
    fake_hands = MagicMock()
    monkeypatch.setattr(game.hand_tracking, "hands", fake_hands)

    game.quit_app()

    fake_hands.close.assert_called_once()


def test_quit_app_closes_the_finger_detector_model(game, monkeypatch):
    _stub_exit(game, monkeypatch)
    monkeypatch.setattr(game, "cap", MagicMock())
    fake_hands = MagicMock()
    monkeypatch.setattr(game.finger_detector, "hands", fake_hands)

    game.quit_app()

    fake_hands.close.assert_called_once()


def test_quit_app_closes_the_pose_detector_model(game, monkeypatch):
    _stub_exit(game, monkeypatch)
    monkeypatch.setattr(game, "cap", MagicMock())
    fake_pose = MagicMock()
    monkeypatch.setattr(game, "pose_detector", fake_pose)

    game.quit_app()

    fake_pose.close.assert_called_once()


def test_quit_app_still_calls_pygame_quit_and_exit(game, monkeypatch):
    monkeypatch.setattr(game, "cap", MagicMock())
    quit_mock = MagicMock()
    exit_mock = MagicMock()
    monkeypatch.setattr(pygame, "quit", quit_mock)
    monkeypatch.setattr(sys, "exit", exit_mock)

    game.quit_app()

    quit_mock.assert_called_once()
    exit_mock.assert_called_once()


def test_quit_app_works_end_to_end_against_the_real_objects(game, monkeypatch):
    # Not mocks: the actual cv2.VideoCapture and mediapipe Hands/Pose
    # objects a real run constructs. This is the check that would have
    # caught a wrong attribute name or method name (e.g. .hands vs
    # .finger_detector directly) that the mocked tests above can't, since
    # a mock happily accepts a call to a misspelled method.
    monkeypatch.setattr(pygame, "quit", MagicMock())
    monkeypatch.setattr(sys, "exit", MagicMock())

    game.quit_app()  # must not raise against the real cap/hands/pose objects


def test_quit_app_tolerates_a_partially_constructed_game(monkeypatch):
    # Called before init_camera()/init_hand_tracking()/etc. have run (e.g.
    # QUIT arrives during startup) must not crash just because cap/
    # hand_tracking/finger_detector/pose_detector don't exist yet.
    from gui.gui import Game

    bare = Game.__new__(Game)  # skips __init__ entirely - no attributes set
    monkeypatch.setattr(pygame, "quit", MagicMock())
    monkeypatch.setattr(sys, "exit", MagicMock())

    bare.quit_app()  # must not raise


# --------------------------------------------------- every exit path
def test_pump_events_quit_handling_calls_quit_app_not_raw_pygame_quit():
    src = open("gui/gui.py").read()
    game_class = _game_class(src)
    body_src = _method_source(game_class, src, "pump_events")
    assert "self.quit_app()" in body_src
    assert "pygame.quit()" not in body_src


def test_run_loop_end_calls_quit_app_not_raw_pygame_quit():
    src = open("gui/gui.py").read()
    game_class = _game_class(src)
    body_src = _method_source(game_class, src, "run")
    assert "self.quit_app()" in body_src
    assert "pygame.quit()" not in body_src


def test_no_raw_pygame_quit_or_exit_calls_remain_outside_quit_app():
    # quit_app() itself is the only place allowed to call pygame.quit()
    # directly - every other QUIT handler (in gui.py and screen_ingame.py)
    # must route through it instead of duplicating pygame.quit()+exit()
    # inline, which is exactly how the camera-release step got skipped in
    # the first place: 5 separate copies of the same shutdown boilerplate,
    # and none of them released anything.
    src = open("gui/gui.py").read()
    game_class = _game_class(src)
    quit_app_src = _method_source(game_class, src, "quit_app")
    src_without_quit_app = src.replace(quit_app_src, "")
    assert "pygame.quit()" not in src_without_quit_app, "gui/gui.py has a raw pygame.quit() outside quit_app()"

    screen_ingame_src = open("gui/screen_ingame.py").read()
    assert "pygame.quit()" not in screen_ingame_src, "screen_ingame.py has a raw pygame.quit() call"
