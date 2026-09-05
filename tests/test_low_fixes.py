"""Tests for the Low-severity fixes (32-40 in AUDIT.md).

Same mix as test_medium_fixes.py: structural checks for the purely
mechanical cleanups (dead code removed, files deleted, config trimmed),
behavioral checks where there's real runtime behavior to lock down.
"""

import ast
import os

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _game_class(src):
    tree = ast.parse(src)
    return next(
        n for n in ast.walk(tree) if isinstance(n, ast.ClassDef) and n.name == "Game"
    )


def _method_source(game_class, src, name):
    node = next(
        n
        for n in ast.walk(game_class)
        if isinstance(n, ast.FunctionDef) and n.name == name
    )
    return ast.get_source_segment(src, node)


# --------------------------------------------------------------- fix 32
def test_draw_pose_guides_was_removed():
    from models import pose_tracking

    assert not hasattr(pose_tracking, "draw_pose_guides")


# --------------------------------------------------------------- fix 33
def test_img_with_rounded_corners_was_removed():
    from gui import utils

    assert not hasattr(utils, "img_with_rounded_corners")


# --------------------------------------------------------------- fix 34
def test_balloons_are_sorted_once_at_generation_not_every_frame():
    src = open("gui/gui.py").read()
    game_class = _game_class(src)

    init_src = _method_source(game_class, src, "init_balloons")
    assert 'balloons.sort(key=lambda x: x["time"])' in init_src

    loop_src = _method_source(game_class, src, "start_balloons_game")
    assert "balloons.sort(" not in loop_src


def test_each_generated_wave_is_actually_sorted_by_appearance_time(balloons_ready):
    game = balloons_ready
    for wave in game.waves_balloons:
        times = [b["time"] for b in wave]
        assert times == sorted(times)


# --------------------------------------------------------------- fix 35
def test_fill_rect_reuses_a_cached_surface_for_the_same_key():
    import pygame

    from gui import ui_kit as ui

    surface = pygame.Surface((200, 200))
    rect = pygame.Rect(0, 0, 40, 20)

    ui._fill_rect_cache.clear()
    ui.fill_rect(surface, rect, (10, 20, 30), 128)
    first_size = len(ui._fill_rect_cache)
    ui.fill_rect(surface, rect, (10, 20, 30), 128)
    assert len(ui._fill_rect_cache) == first_size == 1

    # A different key gets its own cache entry, not reuse of the first
    ui.fill_rect(surface, rect, (99, 98, 97), 128)
    assert len(ui._fill_rect_cache) == 2


def test_dim_screen_reuses_a_cached_surface_for_the_same_key():
    import pygame

    from gui import ui_kit as ui

    surface = pygame.Surface((300, 300))

    ui._dim_screen_cache.clear()
    ui.dim_screen(surface, alpha=100)
    ui.dim_screen(surface, alpha=100)
    assert len(ui._dim_screen_cache) == 1

    ui.dim_screen(surface, alpha=200)
    assert len(ui._dim_screen_cache) == 2


# --------------------------------------------------------------- fix 36/37
def test_orphaned_images_were_deleted():
    assert not os.path.exists(
        os.path.join(REPO_ROOT, "gui/resources/images/main_menu_bg.png")
    )
    assert not os.path.exists(
        os.path.join(REPO_ROOT, "gui/resources/images/hand_landmarks.png")
    )
    # The top-level copy the README actually links to must still be there
    assert os.path.exists(os.path.join(REPO_ROOT, "images/hand_landmarks.png"))


def test_the_shared_background_art_is_present():
    # bg.png is the one background every screen draws (menu, Balloons, Pong,
    # Runner and Credits all load it), so its absence breaks the whole app.
    # Guarded explicitly because a rename sweep once pointed the orphan
    # check above at this very file, asserting the live artwork must NOT
    # exist - which passed only while the art was genuinely missing.
    assert os.path.exists(os.path.join(REPO_ROOT, "gui/resources/images/bg.png"))


# --------------------------------------------------------------- fix 38
def test_dead_running_flags_are_gone(game):
    for name in (
        "balloons_game_running",
        "main_menu_running",
        "pong_game_running",
        "runner_game_running",
        "credits_running",
    ):
        assert not hasattr(game, name), f"{name} should have been deleted as dead state"


# --------------------------------------------------------------- fix 39
def test_pywin32_removed_from_requirements():
    requirements = open(os.path.join(REPO_ROOT, "requirements.txt")).read()
    assert "pywin32" not in requirements


# --------------------------------------------------------------- fix 40
def test_readme_documents_system_requirements():
    readme = open(os.path.join(REPO_ROOT, "README.md")).read()
    assert "System Requirements" in readme
    assert "webcam" in readme.lower()
