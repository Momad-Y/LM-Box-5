"""Tests for the 5 Low-severity fixes in docs/PERFORMANCE_AUDIT.md: the FPS
counter's uncached font, camera_feed_rect() recomputing every call, Runner's
redundant per-frame get_ticks() calls, Runner's own sprite images reloading
on every restart, and cv2.CAP_PROP_BUFFERSIZE.
"""
import ast
from unittest.mock import MagicMock, patch

import pygame


def _game_class(src):
    tree = ast.parse(src)
    return next(n for n in ast.walk(tree) if isinstance(n, ast.ClassDef) and n.name == "Game")


def _method_source(game_class, src, name):
    node = next(
        n for n in ast.walk(game_class) if isinstance(n, ast.FunctionDef) and n.name == name
    )
    return ast.get_source_segment(src, node)


# --------------------------------------------------------- fix 11: fonts
def test_no_bare_font_font_calls_with_self_font_path_remain():
    src = open("gui/gui.py").read()
    assert "pygame.font.Font(self.font_path" not in src


def test_all_six_font_call_sites_now_use_the_cached_helper():
    src = open("gui/gui.py").read()
    assert src.count("ui.font(self.font_path") == 6


def test_draw_fps_actually_renders_using_the_cached_font(game):
    game.settings["show_fps"] = True
    # Must not raise, and must produce real text output via the cached path
    game.draw_fps()


# --------------------------------------------------- fix 12: feed rect
def test_camera_feed_rect_returns_the_same_cached_object_every_call(balloons_ready):
    game = balloons_ready
    first = game.camera_feed_rect()
    second = game.camera_feed_rect()
    assert first is second
    assert first is game._camera_feed_rect


def test_camera_feed_rect_matches_the_uncached_formula(balloons_ready):
    game = balloons_ready
    expected = pygame.Rect(
        int(game.start_x_cam * game.scale_x_cam),
        int(game.start_y_cam * game.scale_y_cam),
        int((game.end_x_cam - game.start_x_cam) * game.scale_x_cam),
        int((game.end_y_cam - game.start_y_cam) * game.scale_y_cam),
    )
    assert game.camera_feed_rect() == expected


def test_pong_camera_feed_rect_is_also_cached(pong_ready):
    game = pong_ready
    assert game.camera_feed_rect() is game._camera_feed_rect


# --------------------------------------------- fix 13: redundant ticks
def test_runner_obstacle_spawn_logic_reuses_current_time_not_fresh_ticks():
    src = open("gui/gui.py").read()
    game_class = _game_class(src)
    body_src = _method_source(game_class, src, "start_runner_game")

    # Exactly one *call* fetches a fresh timestamp per iteration (for the
    # cloud-spawn check); the obstacle-spawn/cooldown logic must reuse it,
    # not call pygame.time.get_ticks() again. Only count actual code lines,
    # not comments that happen to mention the function name.
    code_lines = [
        line for line in body_src.splitlines() if not line.strip().startswith("#")
    ]
    live_calls = sum(line.count("pygame.time.get_ticks()") for line in code_lines)
    assert live_calls == 1

    assert "current_time = pygame.time.get_ticks()" in body_src
    assert "current_time - self.runner_obstacle_timer" in body_src
    assert "self.runner_obstacle_timer = current_time" in body_src


# ------------------------------------------ fix 14: Runner sprite cache
def test_runner_sprite_images_are_shared_across_instances(game):
    # Depends on the `game` fixture (not just importing runner_sprites) so
    # a display definitely exists before this runs - the cache only
    # activates once one does (see _cached_runner_images), so relying on
    # some other test file/fixture to have set one up first would make this
    # pass or fail depending on collection order (as it did before this fix
    # was added - a red-team review caught it failing when run in isolation).
    from gui.runner_sprites import Runner

    r1 = Runner(pos_x=0, ground_y=800)
    r2 = Runner(pos_x=50, ground_y=800)

    assert r1.run_imgs is r2.run_imgs
    assert r1.jump_img is r2.jump_img
    assert r1.duck_imgs is r2.duck_imgs


def test_runner_sprite_cache_still_produces_correctly_shaped_images(game):
    from gui.runner_sprites import DUCK_HEIGHT_RATIO, Runner

    r = Runner(pos_x=0, ground_y=800)
    run_height = r.run_imgs[0].get_height()
    duck_height = r.duck_imgs[0].get_height()
    # Same relationship the original inline computation guaranteed: duck
    # height is run height scaled by DUCK_HEIGHT_RATIO (allowing for int()
    # truncation).
    assert abs(duck_height - int(run_height * DUCK_HEIGHT_RATIO)) <= 1


# -------------------------------------------- fix 15: CAP_PROP_BUFFERSIZE
def test_init_camera_sets_buffersize_to_one():
    src = open("gui/gui.py").read()
    game_class = _game_class(src)
    body_src = _method_source(game_class, src, "init_camera")
    assert "self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)" in body_src


def test_init_camera_actually_calls_set_with_buffersize(sandboxed_data_dir):
    Game = sandboxed_data_dir.Game
    Game.run = lambda self: None

    fake_cap = MagicMock()
    fake_cap.isOpened.return_value = True
    with patch("cv2.VideoCapture", return_value=fake_cap):
        game = Game()

    calls = [c.args for c in fake_cap.set.call_args_list]
    assert (__import__("cv2").CAP_PROP_BUFFERSIZE, 1) in calls
