"""Tests for capture_scaled_frame and the once-per-round background cache.

Covers fixes 10, 12 and 13: the camera capture pipeline shared between
Balloons and Pong (instead of 4 near-duplicate copies), and each game's
background surface being built once at round start instead of rebuilt
every frame of the loop.
"""
import ast

import numpy as np


class _FailingCap:
    def read(self):
        return False, None


class _WorkingCap:
    def read(self):
        return True, np.zeros((480, 640, 3), dtype=np.uint8)


def test_capture_scaled_frame_returns_none_on_a_failed_read(game):
    game.cap = _FailingCap()
    assert game.capture_scaled_frame(ratio=2.5) is None


def test_capture_scaled_frame_returns_correctly_shaped_frame_on_success(game):
    game.cap = _WorkingCap()
    game.user_screen_width, game.user_screen_height = 1920, 1080
    frame = game.capture_scaled_frame(ratio=2.5)
    assert frame is not None
    assert frame.shape == (int(1080 // 2.5), int(1920 // 2.5), 3)


def test_balloons_background_surface_is_built_once_at_init(balloons_ready):
    game = balloons_ready
    assert hasattr(game, "balloons_game_bg_image_pygame")
    assert game.balloons_game_bg_image_pygame.get_size() == game.screen.get_size()


def test_pong_background_surface_is_built_once_at_init(pong_ready):
    game = pong_ready
    assert hasattr(game, "pong_game_bg_image_pygame")
    assert game.pong_game_bg_image_pygame.get_size() == game.screen.get_size()


def test_game_loops_no_longer_rebuild_the_background_every_frame():
    # Structural check: the only place a background surface should be
    # built from a raw numpy buffer is array_to_scaled_surface itself (used
    # once at init) - not inside either game's per-frame loop.
    src = open("gui/gui.py").read()
    tree = ast.parse(src)
    game_class = next(
        n for n in ast.walk(tree) if isinstance(n, ast.ClassDef) and n.name == "Game"
    )
    for loop_name in ("start_balloons_game", "start_pong_game"):
        node = next(
            n
            for n in ast.walk(game_class)
            if isinstance(n, ast.FunctionDef) and n.name == loop_name
        )
        body_src = ast.get_source_segment(src, node)
        assert "pygame.image.frombuffer" not in body_src, (
            f"{loop_name} still rebuilds a surface from a raw buffer every frame"
        )
        assert "dt_scale" in body_src, f"{loop_name} should use dt_scale for movement"
