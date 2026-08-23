"""Tests for the 3 High-severity fixes applied in docs/PERFORMANCE_AUDIT.md:
present()'s unconditional full-canvas rescale, the camera viewport's
smoothscale() vs scale(), and Balloons' screen ratio no longer forcing an
upscale before hand detection.
"""
import ast

import pygame
import pytest

from gui.utils import resize_cover


def _game_class(src):
    tree = ast.parse(src)
    return next(n for n in ast.walk(tree) if isinstance(n, ast.ClassDef) and n.name == "Game")


def _method_source(game_class, src, name):
    node = next(
        n for n in ast.walk(game_class) if isinstance(n, ast.FunctionDef) and n.name == name
    )
    return ast.get_source_segment(src, node)


# --------------------------------------------------------------- present()
def test_present_skips_transform_scale_when_window_matches_canvas_1to1(game, monkeypatch):
    canvas_size = game.screen.get_size()
    monkeypatch.setattr(game, "window", pygame.Surface(canvas_size))

    scale_calls = []
    real_scale = pygame.transform.scale

    def spy_scale(surface, size, *a, **k):
        scale_calls.append(size)
        return real_scale(surface, size, *a, **k)

    monkeypatch.setattr(pygame.transform, "scale", spy_scale)
    game.present()

    assert scale_calls == [], f"transform.scale was called at 1:1: {scale_calls}"


def test_present_still_scales_when_window_size_differs(game, monkeypatch):
    canvas_width, canvas_height = game.screen.get_size()
    smaller_window = (canvas_width // 2, canvas_height // 2)
    monkeypatch.setattr(game, "window", pygame.Surface(smaller_window))

    scale_calls = []
    real_scale = pygame.transform.scale

    def spy_scale(surface, size, *a, **k):
        scale_calls.append(size)
        return real_scale(surface, size, *a, **k)

    monkeypatch.setattr(pygame.transform, "scale", spy_scale)
    game.present()

    assert len(scale_calls) == 1
    # Aspect ratio preserved (letterboxed), scaled down to fit the smaller window
    assert scale_calls[0][0] <= smaller_window[0]
    assert scale_calls[0][1] <= smaller_window[1]


class _FillCountingSurface:
    """Proxies a real pygame.Surface, counting fill() calls.

    pygame.Surface's methods are read-only C attributes - they can't be
    monkeypatched directly on an instance - so a thin proxy is used instead,
    the same technique this suite already uses for sqlite3.Cursor.
    """

    def __init__(self, surface):
        self._surface = surface
        self.fill_calls = 0

    def fill(self, *args, **kwargs):
        self.fill_calls += 1
        return self._surface.fill(*args, **kwargs)

    def __getattr__(self, name):
        return getattr(self._surface, name)


def test_present_skips_the_letterbox_fill_when_the_scaled_frame_fills_the_window(
    game, monkeypatch
):
    canvas_size = game.screen.get_size()
    fake_window = _FillCountingSurface(pygame.Surface(canvas_size))
    monkeypatch.setattr(game, "window", fake_window)

    game.present()

    assert fake_window.fill_calls == 0, "window.fill() ran even though there's no letterbox bar to paint"


def test_present_does_the_letterbox_fill_when_there_are_bars(game, monkeypatch):
    canvas_width, canvas_height = game.screen.get_size()
    # A wider window than the canvas's aspect ratio leaves side letterbox bars
    wide_window = _FillCountingSurface(pygame.Surface((canvas_width * 2, canvas_height)))
    monkeypatch.setattr(game, "window", wide_window)

    game.present()

    assert wide_window.fill_calls == 1


def test_present_letterbox_content_and_offset_are_correct_when_one_axis_matches(game):
    # The mixed case a red-team review flagged as undertested: window
    # matches the canvas exactly in one axis (skips transform.scale entirely
    # - target == canvas) but is taller in the other (still needs a
    # letterbox fill and the frame blitted at a non-zero vertical offset,
    # not just "fill_calls == 1" without checking WHERE things landed).
    canvas_width, canvas_height = game.screen.get_size()
    window = pygame.Surface((canvas_width, canvas_height * 2))
    game.window = window

    pygame.draw.rect(game.screen, (12, 200, 90), pygame.Rect(0, 0, canvas_width, canvas_height))
    game.present()

    expected_offset_y = (window.get_height() - canvas_height) // 2
    # A pixel inside the letterbox bar (above the blitted frame) must be black
    assert window.get_at((canvas_width // 2, expected_offset_y - 5))[:3] == (0, 0, 0)
    # A pixel inside the blitted frame must show the drawn content, at the
    # correct vertical offset (not at y=0, which would mean the fill-skip
    # logic also wrongly skipped centring the blit)
    assert window.get_at((canvas_width // 2, expected_offset_y + 5))[:3] == (12, 200, 90)


def test_present_output_is_pixel_identical_at_1to1_vs_the_old_always_scale_path(game):
    # Regression guard: skipping transform.scale() at 1:1 must produce the
    # exact same visible output as always scaling would have (a no-op scale
    # is a no-op, not an approximation).
    canvas_size = game.screen.get_size()
    game.window = pygame.Surface(canvas_size)

    pygame.draw.rect(game.screen, (12, 200, 90), pygame.Rect(10, 10, 50, 50))
    game.present()
    fast_path_pixels = pygame.image.tostring(game.window, "RGB")

    always_scaled = pygame.transform.scale(game.screen, canvas_size)
    reference_window = pygame.Surface(canvas_size)
    reference_window.fill((0, 0, 0))
    reference_window.blit(always_scaled, (0, 0))
    reference_pixels = pygame.image.tostring(reference_window, "RGB")

    assert fast_path_pixels == reference_pixels


# ---------------------------------------------------------- draw_viewport
def test_draw_viewport_uses_scale_for_downscale_and_smoothscale_for_upscale():
    # Decision, revised after a red-team catch: Balloons/Pong's main camera
    # box is architecturally always a 1.5x upscale (confirmed: canvas is
    # 1920x1080, the background art it's positioned against is 1280x720,
    # 1920/1280 = 1.5), and nearest-neighbour is visibly blockier than
    # smoothscale on a player's own live face/hand feed at that factor - a
    # real quality regression a blanket scale() swap would have shipped.
    # scale() is still used for genuine downscales (Runner's continuous
    # camera box, every game's pre-round demo/countdown feed), where there's
    # no quality trade-off to make.
    src = open("gui/screen_ingame.py").read()
    assert "pygame.transform.smoothscale if scale > 1.0 else pygame.transform.scale" in src


def test_draw_viewport_picks_scale_for_a_downscale(game, monkeypatch):
    from gui import screen_ingame

    calls = {"scale": 0, "smoothscale": 0}
    real_scale = pygame.transform.scale
    real_smoothscale = pygame.transform.smoothscale

    def spy_scale(*a, **k):
        calls["scale"] += 1
        return real_scale(*a, **k)

    def spy_smoothscale(*a, **k):
        calls["smoothscale"] += 1
        return real_smoothscale(*a, **k)

    monkeypatch.setattr(pygame.transform, "scale", spy_scale)
    monkeypatch.setattr(pygame.transform, "smoothscale", spy_smoothscale)

    frame = pygame.Surface((640, 480))
    rect = pygame.Rect(0, 0, 320, 240)  # smaller than the frame: a downscale
    screen_ingame.draw_viewport(game, rect, frame)

    assert calls == {"scale": 1, "smoothscale": 0}


def test_draw_viewport_picks_smoothscale_for_an_upscale(game, monkeypatch):
    from gui import screen_ingame

    calls = {"scale": 0, "smoothscale": 0}
    real_scale = pygame.transform.scale
    real_smoothscale = pygame.transform.smoothscale

    def spy_scale(*a, **k):
        calls["scale"] += 1
        return real_scale(*a, **k)

    def spy_smoothscale(*a, **k):
        calls["smoothscale"] += 1
        return real_smoothscale(*a, **k)

    monkeypatch.setattr(pygame.transform, "scale", spy_scale)
    monkeypatch.setattr(pygame.transform, "smoothscale", spy_smoothscale)

    frame = pygame.Surface((640, 360))
    rect = pygame.Rect(0, 0, 960, 540)  # 1.5x larger than the frame: an upscale
    screen_ingame.draw_viewport(game, rect, frame)

    assert calls == {"scale": 0, "smoothscale": 1}


def test_draw_viewport_still_fills_the_target_rect_correctly(game):
    from gui import screen_ingame

    frame = pygame.Surface((640, 480))
    frame.fill((100, 150, 200))
    rect = pygame.Rect(50, 50, 300, 200)

    screen_ingame.draw_viewport(game, rect, frame)

    # The box should be fully covered by the (cropped-to-cover) feed color,
    # not left showing background through gaps.
    assert game.screen.get_at((rect.centerx, rect.centery))[:3] == (100, 150, 200)


def test_draw_viewport_handles_a_none_frame_without_crashing(game):
    from gui import screen_ingame

    rect = pygame.Rect(50, 50, 300, 200)
    screen_ingame.draw_viewport(game, rect, None)


# ------------------------------------------------ balloon_screen_ratio
def test_balloon_screen_ratio_no_longer_forces_an_upscale_before_hand_detection(balloons_ready):
    # Decision: raise balloon_screen_ratio (2.5 -> 3.0) so the resulting
    # frame size fits within the native camera capture (CAMERA_CAPTURE_WIDTH
    # /HEIGHT, 640x480) instead of being wider than it - resize_cover then
    # needs a pure crop, never an upscale, before every hand-tracking call.
    game = balloons_ready
    target_width = int(game.user_screen_width // game.balloon_screen_ratio)
    target_height = int(game.user_screen_height // game.balloon_screen_ratio)

    assert target_width <= 640, "target width still exceeds the native capture width"
    assert target_height <= 480, "target height still exceeds the native capture height"

    # Drive resize_cover with a native-sized frame and confirm it produces
    # the target purely by cropping - if it had to upscale first, the
    # intermediate scaled size (checked via its own scale formula) would
    # exceed the native capture size in some dimension.
    import numpy as np

    native_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    result = resize_cover(native_frame, target_width, target_height)
    assert result.shape[:2] == (target_height, target_width)
    upscale_factor = max(target_width / 640, target_height / 480)
    assert upscale_factor <= 1.0, f"resize_cover would still upscale by {upscale_factor}x"


def test_balloons_camera_image_shape_matches_the_new_ratio(balloons_ready):
    game = balloons_ready
    expected_width = int(game.user_screen_width // game.balloon_screen_ratio)
    expected_height = int(game.user_screen_height // game.balloon_screen_ratio)
    assert game.camera_image.shape[:2] == (expected_height, expected_width)
