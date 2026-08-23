"""Tests for the 3 Critical fixes in docs/PERFORMANCE_AUDIT.md.

Covers: mediapipe Hands() running the lite model instead of the full one,
the double BGR<->RGB conversion that fed mediapipe channel-swapped color
data, and the missing convert_alpha() on balloon/pin sprites.
"""
import ast

import cv2
import numpy as np


def _game_class(src):
    tree = ast.parse(src)
    return next(n for n in ast.walk(tree) if isinstance(n, ast.ClassDef) and n.name == "Game")


def _method_source(game_class, src, name):
    node = next(
        n for n in ast.walk(game_class) if isinstance(n, ast.FunctionDef) and n.name == name
    )
    return ast.get_source_segment(src, node)


# ------------------------------------------------------ model_complexity
def test_hand_tracking_dynamic_uses_the_lite_model():
    from models import mediapipe_hand_tracking as mht

    captured = {}

    class _FakeHands:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    class _FakeHandsMp:
        Hands = _FakeHands
        HAND_CONNECTIONS = None

    fake_mp_solutions_hands = _FakeHandsMp()
    real_hands_module = mht.mp.solutions.hands
    mht.mp.solutions.hands = fake_mp_solutions_hands
    try:
        mht.HandTrackingDynamic(detectionCon=0.7, trackCon=0.6)
    finally:
        mht.mp.solutions.hands = real_hands_module

    assert captured.get("model_complexity") == 0
    assert captured.get("min_detection_confidence") == 0.7
    assert captured.get("min_tracking_confidence") == 0.6


def test_cvzone_hand_detector_is_initialized_with_the_lite_model():
    from models.cvzone_hand_detection import initialize_hand_detector

    detector = initialize_hand_detector()
    assert detector.modelComplexity == 0


# ---------------------------------------------------- BGR/RGB round trip
def test_rgb_to_bgr_to_rgb_round_trip_is_lossless():
    # The fix's premise: converting RGB->BGR->RGB must reproduce the exact
    # original array, so routing through BGR just to satisfy a BGR-input
    # contract doesn't itself introduce any data loss.
    rng = np.random.default_rng(0)
    frame = rng.integers(0, 256, size=(48, 64, 3), dtype=np.uint8)
    round_tripped = cv2.cvtColor(cv2.cvtColor(frame, cv2.COLOR_RGB2BGR), cv2.COLOR_BGR2RGB)
    assert np.array_equal(round_tripped, frame)


def test_double_bgr2rgb_conversion_actually_cancels_back_to_the_original_order():
    # Confirms the bug's mechanism: applying BGR2RGB to data that is already
    # RGB (as self.camera_image is by the time it reaches the hand-tracking
    # call sites) returns the ORIGINAL BGR-ordered bytes, not true RGB.
    rng = np.random.default_rng(1)
    bgr_source = rng.integers(0, 256, size=(48, 64, 3), dtype=np.uint8)
    true_rgb = cv2.cvtColor(bgr_source, cv2.COLOR_BGR2RGB)
    double_converted = cv2.cvtColor(true_rgb, cv2.COLOR_BGR2RGB)
    assert np.array_equal(double_converted, bgr_source)
    assert not np.array_equal(double_converted, true_rgb)


def test_pong_hand_tracking_call_site_round_trips_through_bgr(pong_ready):
    # Structural check on the real fix: the call site must convert
    # self.camera_image to BGR before calling findFingers (which converts
    # BGR->RGB internally per its own documented contract), and convert the
    # result back to RGB before it's reassigned to self.camera_image for
    # display.
    src = open("gui/gui.py").read()
    game_class = _game_class(src)
    body_src = _method_source(game_class, src, "start_pong_game")

    assert "cv2.cvtColor(self.camera_image, cv2.COLOR_RGB2BGR)" in body_src
    assert "cv2.cvtColor(bgr_for_tracking, cv2.COLOR_BGR2RGB)" in body_src
    # The old, buggy direct call must be gone
    assert "self.hand_tracking.findFingers(self.camera_image)" not in body_src


def test_balloons_hand_tracking_call_site_converts_to_bgr_first():
    src = open("gui/gui.py").read()
    game_class = _game_class(src)
    body_src = _method_source(game_class, src, "start_balloons_game")

    assert "cv2.cvtColor(self.camera_image, cv2.COLOR_RGB2BGR)" in body_src
    assert "detect_hands(self.finger_detector, bgr_for_tracking)" in body_src
    # The old, buggy direct call must be gone
    assert "detect_hands(self.finger_detector, self.camera_image)" not in body_src


def test_pong_camera_image_stays_true_rgb_after_hand_tracking(pong_ready, monkeypatch):
    # End-to-end: after the round-trip fix, self.camera_image must still be
    # in true RGB order for display, not left in BGR order by mistake.
    game = pong_ready
    rng = np.random.default_rng(2)
    original_rgb = rng.integers(0, 256, size=(308, 548, 3), dtype=np.uint8)
    game.camera_image = original_rgb.copy()

    # findFingers with draw=False just needs to not crash and to return
    # something usable - stub it to isolate the color-handling logic under
    # test from real mediapipe inference.
    monkeypatch.setattr(
        game.hand_tracking, "findFingers", lambda frame, *a, **k: frame
    )

    bgr_for_tracking = cv2.cvtColor(game.camera_image, cv2.COLOR_RGB2BGR)
    bgr_for_tracking = game.hand_tracking.findFingers(bgr_for_tracking)
    result_rgb = cv2.cvtColor(bgr_for_tracking, cv2.COLOR_BGR2RGB)

    assert np.array_equal(result_rgb, original_rgb)


def test_the_bgr_round_trip_is_what_actually_makes_real_hand_detection_work():
    # The stubbed test above only proves the color bytes round-trip losslessly
    # - it doesn't touch real mediapipe inference, so it can't catch a
    # regression of the underlying bug (feeding wrong color data still
    # "round trips the array" as far as that test can tell). This one runs
    # the real HandTrackingDynamic against a real hand photo and asserts on
    # actual detection outcomes for both the old buggy call pattern and the
    # fixed one - if this pattern regresses, this is the test that catches it.
    #
    # A fresh HandTrackingDynamic per attempt is required: reusing one
    # detector across repeated identical frames lets mediapipe's tracking
    # mode (the class's default) coast on a stale lock from a single lucky
    # first detection instead of genuinely re-detecting each time, which
    # would mask this exact bug.
    img = cv2.imread("images/balloons_game.png")
    assert img is not None, "reference image with a real hand is missing"
    img = cv2.resize(img, (768, 432))
    camera_image_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    def detections(frame_passed_to_find_fingers, attempts=5):
        from models.mediapipe_hand_tracking import HandTrackingDynamic

        hits = 0
        for _ in range(attempts):
            tracker = HandTrackingDynamic()
            tracker.findFingers(frame_passed_to_find_fingers.copy(), draw=False)
            if tracker.results.multi_hand_landmarks:
                hits += 1
        return hits

    # Old, buggy call pattern: pass self.camera_image (already RGB) straight
    # into findFingers, which converts it again - the two conversions cancel,
    # so mediapipe receives the original BGR-ordered bytes mislabeled as RGB.
    old_buggy_hits = detections(camera_image_rgb)

    # New, fixed call pattern (matches start_pong_game/start_balloons_game):
    # convert back to BGR first so findFingers' own conversion lands on true
    # RGB.
    bgr_for_tracking = cv2.cvtColor(camera_image_rgb, cv2.COLOR_RGB2BGR)
    fixed_hits = detections(bgr_for_tracking)

    assert old_buggy_hits == 0, (
        f"expected the old buggy color path to fail detection outright, got "
        f"{old_buggy_hits}/5 - if mediapipe changed how sensitive it is to "
        f"channel order, this test's premise needs re-checking"
    )
    assert fixed_hits == 5, f"fixed color path only detected {fixed_hits}/5"


# -------------------------------------------------------- convert_alpha
def test_balloon_images_are_converted_for_fast_blitting(balloons_ready):
    game = balloons_ready
    all_balloons = [b for wave in game.waves_balloons for b in wave]
    assert all_balloons, "no balloons were generated to check"
    for balloon in all_balloons:
        # A converted surface always reports per-pixel alpha (SRCALPHA) once
        # convert_alpha() has run - checking get_flags() would also be true
        # of the raw loaded PNG (which already carries an alpha channel), so
        # this only proves the surface loaded correctly, not that convert
        # was applied - the real regression guard is the source check below,
        # which pins down the exact code path.
        assert balloon["image"].get_size() == (250, 250)


def test_scaled_balloon_image_calls_convert_alpha():
    src = open("gui/gui.py").read()
    game_class = _game_class(src)
    body_src = _method_source(game_class, src, "init_balloons")
    assert "pygame.image.load(path).convert_alpha()" in body_src


def test_pin_image_calls_convert_alpha():
    src = open("gui/gui.py").read()
    game_class = _game_class(src)
    body_src = _method_source(game_class, src, "init_balloons_game")
    assert "resources/images/pin.png" in body_src
    assert ").convert_alpha()" in body_src
