from __future__ import annotations

import cv2
import mediapipe as mp
import numpy as np

mp_pose = mp.solutions.pose

# Fallback threshold positions, as a fraction of frame height, used when the
# player's resting head position hasn't been calibrated.
JUMP_LINE_RATIO = 0.42
DUCK_LINE_RATIO = 0.76

# How far the player has to move their head from their own resting position
# to trigger a jump or a duck, as a fraction of frame height. Where someone's
# head sits in frame depends entirely on how the camera is angled - measured
# resting positions have been as low as 0.69 - so fixed lines end up either
# unreachable or permanently triggered. Offsetting from a measured baseline
# keeps both actions the same amount of effort for everyone. Ducking uses a
# smaller offset because there is usually less headroom below than above.
JUMP_OFFSET_RATIO = 0.15
DUCK_OFFSET_RATIO = 0.10


def initialize_pose_detector(detection_con: float = 0.5, tracking_con: float = 0.5):
    """
    Initialize the MediaPipe Pose object used for jump/duck detection.

    Parameters:
        detection_con: float
            The confidence threshold for pose detection.
        tracking_con: float
            The confidence threshold for pose tracking.

    Returns:
        pose: mediapipe.python.solutions.pose.Pose
            The Pose object.
    """

    # model_complexity=0 is the lite model: the jump/duck check only needs a
    # rough nose position, and the lite model is markedly faster per frame,
    # which matters because detection runs inline in the game loop.
    return mp_pose.Pose(
        model_complexity=0,
        min_detection_confidence=detection_con,
        min_tracking_confidence=tracking_con,
    )


def sensitivity_scale(sensitivity: int) -> float:
    """
    Convert a 1-10 gesture sensitivity into a multiplier for the thresholds.

    Parameters:
        sensitivity: int
            1 is the least sensitive (largest head movement required), 10 the
            most. 5 leaves the default offsets unchanged.

    Returns:
        scale: float
            Multiplier to apply to the jump/duck offsets.
    """

    sensitivity = max(1, min(10, int(sensitivity)))
    return 1.5 - 0.1 * sensitivity


def threshold_ratios(baseline: float | None, sensitivity: int = 5) -> tuple:
    """
    Where the jump and duck lines sit, as fractions of the frame height.

    Split out so the calibration countdown can draw the same lines the round
    will actually use, rather than placeholders that move once play starts.

    Parameters:
        baseline: float | None
            The player's measured resting head height, or None if it hasn't
            been measured yet.
        sensitivity: int
            The 1-10 gesture sensitivity setting.

    Returns:
        (jump_ratio, duck_ratio): tuple[float, float]
    """

    if baseline is None:
        return JUMP_LINE_RATIO, DUCK_LINE_RATIO

    # Keep the lines inside the frame even for an extreme baseline
    scale = sensitivity_scale(sensitivity)
    return (
        max(0.05, baseline - JUMP_OFFSET_RATIO * scale),
        min(0.95, baseline + DUCK_OFFSET_RATIO * scale),
    )


def detect_jump_duck(
    pose, img: np.ndarray, baseline: float = None, sensitivity: int = 5
) -> dict:
    """
    Detect whether the player's nose has crossed the jump/duck lines.

    Raising the head above the jump line counts as a jump and lowering it
    below the duck line counts as a duck.

    Parameters:
        pose: mediapipe.python.solutions.pose.Pose
            The Pose object.
        img: np.ndarray
            The video frame to detect the pose in.
        baseline: float
            The player's resting nose height as a fraction of frame height,
            from calibrate_baseline. The thresholds are placed either side of
            it. If None, the fixed fallback positions are used.

    Returns:
        pose_data: dict
            "jump": bool, "duck": bool, "nose_pos": (x, y) or None,
            "jump_line_y": int, "duck_line_y": int
    """

    frame_height, frame_width, _ = img.shape

    jump_ratio, duck_ratio = threshold_ratios(baseline, sensitivity)

    jump_line_y = int(frame_height * jump_ratio)
    duck_line_y = int(frame_height * duck_ratio)

    result = pose.process(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))

    pose_data = {
        "jump": False,
        "duck": False,
        "nose_pos": None,
        "jump_line_y": jump_line_y,
        "duck_line_y": duck_line_y,
    }

    if not result.pose_landmarks:
        return pose_data

    landmarks = result.pose_landmarks.landmark
    nose = landmarks[mp_pose.PoseLandmark.NOSE.value]
    nose_x = int(nose.x * frame_width)
    nose_y = int(nose.y * frame_height)
    pose_data["nose_pos"] = (nose_x, nose_y)

    if nose_y < jump_line_y:
        pose_data["jump"] = True
    elif nose_y > duck_line_y:
        pose_data["duck"] = True

    return pose_data


def calibrate_baseline(samples: list) -> float:
    """
    Turn a set of resting nose heights into a baseline for the thresholds.

    Parameters:
        samples: list
            Nose heights as fractions of frame height, collected while the
            player was standing normally.

    Returns:
        baseline: float
            The median resting height, or None if there aren't enough
            samples to trust (the caller then falls back to fixed lines).
    """

    if len(samples) < 5:
        return None

    return float(np.median(samples))


def demo() -> None:
    """
    Detect jump/duck in the webcam feed.

    Parameters:
        None

    Returns:
        None
    """
    pose = initialize_pose_detector()
    cap = cv2.VideoCapture(0)

    while True:
        _, img = cap.read()
        img = cv2.flip(img, 1)

        pose_data = detect_jump_duck(pose, img)
        if pose_data["nose_pos"]:
            cv2.circle(img, pose_data["nose_pos"], 10, (0, 0, 255), -1)

        label = "JUMP" if pose_data["jump"] else "DUCK" if pose_data["duck"] else ""
        if label:
            cv2.putText(img, label, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

        cv2.imshow("Camera", img)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break


if __name__ == "__main__":
    demo()
