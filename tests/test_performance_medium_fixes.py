"""Tests for the 4 Medium-severity fixes in docs/PERFORMANCE_AUDIT.md:
sounds/backgrounds loading once per process instead of every menu
round-trip, no longer keeping raw background arrays resident forever, a
cache for the per-frame player-name DB query, and Runner's Cloud sprite
finally matching Cactus/Ptero's caching pattern.
"""
import ast

import numpy as np
import pygame
import pytest


def _game_class(src):
    tree = ast.parse(src)
    return next(n for n in ast.walk(tree) if isinstance(n, ast.ClassDef) and n.name == "Game")


def _method_source(game_class, src, name):
    node = next(
        n for n in ast.walk(game_class) if isinstance(n, ast.FunctionDef) and n.name == name
    )
    return ast.get_source_segment(src, node)


@pytest.fixture
def runner_ready(game, sandboxed_data_dir, monkeypatch):
    """A Game with Runner fully initialized, stopped just before play.

    Same idea as balloons_ready/pong_ready: stubs everything interactive
    (player picker, how-to screen, the get-ready timer) so init_runner_game's
    real asset-loading/geometry setup runs unattended.
    """
    user_id = game.add_user_returning_id("Player")
    monkeypatch.setattr(sandboxed_data_dir.screen_ingame, "show_instructions", lambda *a, **k: True)
    monkeypatch.setattr(game, "select_players", lambda *a, **k: [user_id])
    monkeypatch.setattr(game, "start_runner_game_timer", lambda: None)
    game.init_runner_game()
    return game


# --------------------------------------------------- fix 7: load once
def test_balloons_sounds_and_background_are_not_reloaded_on_re_entry(balloons_ready):
    game = balloons_ready
    sound_before = game.balloon_popping_sounds[0]
    bg_before = game.balloons_game_bg_image_pygame
    pin_before = game.pin_image

    game.init_balloons_game()

    assert game.balloon_popping_sounds[0] is sound_before
    assert game.balloons_game_bg_image_pygame is bg_before
    assert game.pin_image is pin_before


def test_balloons_volume_is_still_reapplied_on_re_entry(balloons_ready):
    game = balloons_ready
    game.sound_volume = 0.9
    game.init_balloons_game()
    assert game.balloon_popping_sounds[0].get_volume() == pytest.approx(
        game.sfx_volume(0.2), abs=0.02
    )


def test_pong_sounds_and_background_are_not_reloaded_on_re_entry(pong_ready):
    game = pong_ready
    sound_before = game.hit_sounds[0]
    bg_before = game.pong_game_bg_image_pygame

    game.init_pong_game()

    assert game.hit_sounds[0] is sound_before
    assert game.pong_game_bg_image_pygame is bg_before


def test_pong_volume_is_still_reapplied_on_re_entry(pong_ready):
    game = pong_ready
    game.sound_volume = 0.9
    game.init_pong_game()
    assert game.hit_sounds[0].get_volume() == pytest.approx(game.sfx_volume(0.2), abs=0.02)


def test_runner_sounds_and_background_are_not_reloaded_on_re_entry(runner_ready):
    game = runner_ready
    sound_before = game.runner_jump_sound
    bg_before = game.runner_game_bg_image_pygame
    ground_before = game.runner_ground_image

    game.init_runner_game()

    assert game.runner_jump_sound is sound_before
    assert game.runner_game_bg_image_pygame is bg_before
    assert game.runner_ground_image is ground_before


def test_runner_volume_is_still_reapplied_on_re_entry(runner_ready):
    game = runner_ready
    game.sound_volume = 0.9
    game.init_runner_game()
    assert game.runner_jump_sound.get_volume() == pytest.approx(game.sfx_volume(0.4), abs=0.02)


# ------------------------------------------- fix 8: no dead raw arrays
def test_balloons_geometry_matches_the_real_background_art_scale(balloons_ready):
    # Regression guard for the "read bg size from a cached tuple, not the
    # (no-longer-kept) raw array or the canvas-scaled pygame surface" fix -
    # scale_x_cam/scale_y_cam must still come out as the real canvas/art
    # ratio (1920/1280 = 1080/720 = 1.5), not something derived from the
    # wrong-sized surface.
    game = balloons_ready
    assert game.scale_x_cam == pytest.approx(1.5)
    assert game.scale_y_cam == pytest.approx(1.5)


def test_pong_geometry_matches_the_real_background_art_scale(pong_ready):
    game = pong_ready
    assert game.scale_x_cam == pytest.approx(1.5)
    assert game.scale_y_cam == pytest.approx(1.5)


def test_raw_background_arrays_are_not_kept_as_instance_attributes(balloons_ready, pong_ready):
    for game in (balloons_ready, pong_ready):
        assert not hasattr(game, "balloons_game_bg_image")
        assert not hasattr(game, "pong_game_bg_image")


def test_runner_raw_background_array_is_not_kept_as_an_instance_attribute(runner_ready):
    assert not hasattr(runner_ready, "runner_game_bg_image")


# ------------------------------------------ fix 9: cached user name
def test_get_user_name_is_cached_after_the_first_lookup(game, monkeypatch):
    user_id = game.add_user_returning_id("Alice")
    assert game.get_user_name(user_id) == "Alice"

    # Change the name directly in the DB, bypassing rename_user (which
    # invalidates the cache) - if get_user_name is genuinely cached, it must
    # still report the old name.
    game._db_execute(
        "UPDATE users SET name = ? WHERE id = ?", ("Bob", user_id), commit=True
    )
    assert game.get_user_name(user_id) == "Alice"


def test_rename_user_invalidates_the_name_cache(game):
    user_id = game.add_user_returning_id("Alice")
    assert game.get_user_name(user_id) == "Alice"

    game.rename_user(user_id, "Alicia")
    assert game.get_user_name(user_id) == "Alicia"


def test_delete_user_invalidates_the_name_cache(game):
    user_id = game.add_user_returning_id("Alice")
    assert game.get_user_name(user_id) == "Alice"

    game.delete_user(user_id)
    assert game.get_user_name(user_id) is None


def test_player_label_uses_the_cached_name(game):
    user_id = game.add_user_returning_id("Alice")
    game.active_players = [user_id]
    assert game.player_label(0) == "Alice"
    assert user_id in game._user_name_cache


# --------------------------------------- fix 10: Cloud sprite caching
def test_cloud_image_is_shared_across_spawns():
    from gui.runner_sprites import Cloud

    cloud1 = Cloud()
    cloud2 = Cloud()
    assert cloud1.image is cloud2.image


def test_cloud_keeps_its_untrimmed_size_not_the_load_trimmed_crop():
    # Cloud deliberately does NOT use _load_trimmed (unlike Cactus/Ptero) -
    # this fix only had to add caching + convert_alpha(), not change what
    # gets loaded. Pin the real, untrimmed size so a future "make Cloud
    # consistent with its siblings" edit can't silently shrink every
    # cloud's rendered size without a test catching it - the other Cloud
    # tests (identity, pixel format) would all still pass even if this
    # regressed.
    from gui.runner_sprites import IMAGES_DIR, Cloud

    raw = pygame.image.load(f"{IMAGES_DIR}/cloud.png")
    trimmed_size = raw.subsurface(raw.get_bounding_rect()).get_size()

    cloud = Cloud()

    assert cloud.image.get_size() == raw.get_size()
    assert cloud.image.get_size() != trimmed_size


def test_cloud_image_is_converted_for_fast_blitting():
    from gui import runner_sprites as rs

    rs._cloud_image_cache = None  # force a fresh load for this check
    image = rs._cached_cloud_image()
    # A converted surface's R/G/B channel order matches the real display's
    # pixel format - the raw loaded PNG (still RGBA but in file byte order)
    # would not. Alpha mask is excluded: the opaque display surface has none
    # (0), while convert_alpha() deliberately adds one - that's the point.
    display = pygame.display.get_surface()
    assert image.get_masks()[:3] == display.get_masks()[:3]
