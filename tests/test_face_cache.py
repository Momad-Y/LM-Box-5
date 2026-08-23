"""Tests for the decoded face-surface cache (Game._face_surface_cache).

test_database.py covers the raw bytes layer (get_user_face_bytes); this
covers the layer above it that the HUD actually calls every frame
(get_user_face_surface / player_face_or_none) - the thing fix 9 stopped
re-decoding 30x/sec.
"""
import io

import pygame


def _tiny_png_bytes():
    surface = pygame.Surface((1, 1), pygame.SRCALPHA)
    buffer = io.BytesIO()
    pygame.image.save(surface, buffer, "tiny.png")
    return buffer.getvalue()


def test_face_surface_is_only_decoded_once_across_repeated_calls(game):
    user_id = game.add_user_returning_id("FaceTest")
    game.set_user_face(user_id, _tiny_png_bytes())

    call_count = 0
    real_get_bytes = game.get_user_face_bytes

    def counting_get_bytes(uid):
        nonlocal call_count
        call_count += 1
        return real_get_bytes(uid)

    game.get_user_face_bytes = counting_get_bytes
    surface_1 = game.get_user_face_surface(user_id)
    surface_2 = game.get_user_face_surface(user_id)
    surface_3 = game.player_face_or_none(user_id)
    game.get_user_face_bytes = real_get_bytes

    assert call_count == 1
    assert surface_1 is not None
    assert surface_2 is surface_1
    assert surface_3 is surface_1


def test_face_surface_is_none_for_a_user_with_no_picture(game):
    user_id = game.add_user_returning_id("NoPicture")
    assert game.get_user_face_surface(user_id) is None
    # A second call should also come back None from the cache, not raise
    assert game.get_user_face_surface(user_id) is None


def test_cache_invalidates_on_set_user_face(game):
    user_id = game.add_user_returning_id("Changer")
    game.get_user_face_surface(user_id)  # populate the None entry
    assert user_id in game._face_surface_cache

    game.set_user_face(user_id, _tiny_png_bytes())
    assert user_id not in game._face_surface_cache

    assert game.get_user_face_surface(user_id) is not None


def test_cache_invalidates_on_clear_user_face(game):
    user_id = game.add_user_returning_id("Clearer")
    game.set_user_face(user_id, _tiny_png_bytes())
    game.get_user_face_surface(user_id)  # populate the real entry
    assert user_id in game._face_surface_cache

    game.clear_user_face(user_id)
    assert user_id not in game._face_surface_cache
    assert game.get_user_face_surface(user_id) is None


def test_cache_invalidates_on_delete_user(game):
    user_id = game.add_user_returning_id("Deleted")
    game.set_user_face(user_id, _tiny_png_bytes())
    game.get_user_face_surface(user_id)
    assert user_id in game._face_surface_cache

    game.delete_user(user_id)
    assert user_id not in game._face_surface_cache
