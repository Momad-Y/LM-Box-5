"""
Face capture for user profile pictures.

Produces a head-and-shoulders cutout with a transparent background, so the
result can be drawn straight over a game's artwork. The background is removed
with MediaPipe's selfie segmentation mask written into the alpha channel -
compositing onto a flat green screen instead would bake the colour in and
leave a halo wherever it is drawn.
"""

import cv2
import mediapipe as mp
import numpy as np

mp_selfie_segmentation = mp.solutions.selfie_segmentation

# Size of the square cutout that gets stored per user
CUTOUT_SIZE = 256

# Segmentation confidence below which a pixel is treated as background
MASK_THRESHOLD = 0.5

# Width the frame is downscaled to before segmentation, for speed
SEGMENTATION_WIDTH = 480

# White border drawn around the cutout so it reads clearly against any
# background it is later drawn over
OUTLINE_THICKNESS = 6
OUTLINE_COLOR = (255, 255, 255)

# A cutout with less of the frame than this is treated as "nobody there"
MIN_COVERAGE = 0.04


def initialize_face_capture(model_selection: int = 1) -> tuple:
    """
    Initialize the segmentation model and the face detector.

    Parameters:
        model_selection: int
            MediaPipe selfie segmentation model. 1 is the landscape model,
            which is the faster of the two.

    Returns:
        segmentor: SelfieSegmentation
            The segmentation model.
        face_cascade: cv2.CascadeClassifier
            The face detector used to frame the cutout.
    """

    segmentor = mp_selfie_segmentation.SelfieSegmentation(
        model_selection=model_selection
    )
    face_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )
    return segmentor, face_cascade


def detect_face_box(image: np.ndarray, face_cascade, padding: int = 60) -> tuple:
    """
    Find the region to crop around the largest detected face.

    Parameters:
        image: np.ndarray
            The BGR frame to search.
        face_cascade: cv2.CascadeClassifier
            The face detector.
        padding: int
            Extra pixels kept around the face so it isn't cropped tight.

    Returns:
        box: tuple
            (x, y, w, h) clamped to the frame, or None if no face was found.
    """

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, 1.1, 4)

    if len(faces) == 0:
        return None

    # The largest detection is the one closest to the camera
    x, y, w, h = max(faces, key=lambda face: face[2] * face[3])

    frame_height, frame_width = image.shape[:2]
    x = max(0, x - padding)
    y = max(0, y - padding)
    w = min(frame_width - x, w + padding * 2)
    h = min(frame_height - y, h + padding * 2)

    return x, y, w, h


def segment_alpha(image: np.ndarray, segmentor) -> np.ndarray:
    """
    Build an alpha channel that keeps the person and drops the background.

    Parameters:
        image: np.ndarray
            The BGR frame.
        segmentor: SelfieSegmentation
            The segmentation model.

    Returns:
        alpha: np.ndarray
            uint8 mask the same size as the frame, 255 where the person is.
    """

    frame_height, frame_width = image.shape[:2]

    # Segment at a reduced width; the mask is upscaled back afterwards
    scale_height = max(1, int(SEGMENTATION_WIDTH * frame_height / frame_width))
    small = cv2.resize(image, (SEGMENTATION_WIDTH, scale_height))

    result = segmentor.process(cv2.cvtColor(small, cv2.COLOR_BGR2RGB))
    mask = result.segmentation_mask

    if mask is None:
        return np.full((frame_height, frame_width), 255, np.uint8)

    mask = cv2.resize(mask, (frame_width, frame_height))
    alpha = np.where(mask > MASK_THRESHOLD, 255, 0).astype(np.uint8)

    # Soften the edge so the cutout doesn't look cut with scissors
    return cv2.GaussianBlur(alpha, (7, 7), 0)


def add_outline(
    cutout: np.ndarray,
    thickness: int = OUTLINE_THICKNESS,
    color: tuple = OUTLINE_COLOR,
) -> np.ndarray:
    """
    Draw a solid border around the visible part of a cutout.

    Parameters:
        cutout: np.ndarray
            The BGRA image to outline.
        thickness: int
            Border width in pixels.
        color: tuple
            Border colour as BGR.

    Returns:
        outlined: np.ndarray
            A copy of the cutout with the border drawn into it.
    """

    alpha = cutout[:, :, 3]
    solid = (alpha > 127).astype(np.uint8)

    if solid.max() == 0:
        return cutout.copy()

    kernel = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE, (thickness * 2 + 1, thickness * 2 + 1)
    )
    grown = cv2.dilate(solid, kernel)

    # The ring is everything the dilation added around the subject
    ring = (grown > 0) & (solid == 0)

    outlined = cutout.copy()
    outlined[ring] = (color[0], color[1], color[2], 255)
    return outlined


def cutout_coverage(cutout: np.ndarray) -> float:
    """
    Fraction of the cutout that is visible rather than transparent.

    Parameters:
        cutout: np.ndarray
            The BGRA image.

    Returns:
        coverage: float
            0.0 when nothing was segmented, 1.0 when the whole frame is.
    """

    return float((cutout[:, :, 3] > 127).mean())


def center_square(image: np.ndarray) -> np.ndarray:
    """
    Crop the largest centred square from a frame.

    Used when no face is detected, so the fallback keeps the aspect ratio
    instead of squashing the whole frame into a square.

    Parameters:
        image: np.ndarray
            The image to crop.

    Returns:
        cropped: np.ndarray
            The centred square crop.
    """

    height, width = image.shape[:2]
    side = min(height, width)
    top = (height - side) // 2
    left = (width - side) // 2
    return image[top : top + side, left : left + side]


def capture_face_cutout(
    image: np.ndarray, segmentor, face_cascade, size: int = CUTOUT_SIZE
) -> np.ndarray:
    """
    Turn a camera frame into a square BGRA cutout of the person.

    Parameters:
        image: np.ndarray
            The BGR frame.
        segmentor: SelfieSegmentation
            The segmentation model.
        face_cascade: cv2.CascadeClassifier
            The face detector.
        size: int
            Side length of the returned square image.

    Returns:
        cutout: np.ndarray
            size x size BGRA image; the background is fully transparent.
    """

    alpha = segment_alpha(image, segmentor)

    box = detect_face_box(image, face_cascade)
    if box is not None:
        x, y, w, h = box
        image = image[y : y + h, x : x + w]
        alpha = alpha[y : y + h, x : x + w]
    else:
        # No face found, so keep a centred square rather than squashing the
        # whole frame into one
        image = center_square(image)
        alpha = center_square(alpha)

    if image.size == 0:
        return np.zeros((size, size, 4), np.uint8)

    image = cv2.resize(image, (size, size))
    alpha = cv2.resize(alpha, (size, size))

    cutout = cv2.cvtColor(image, cv2.COLOR_BGR2BGRA)
    cutout[:, :, 3] = alpha
    return add_outline(cutout)


def encode_png(cutout: np.ndarray) -> bytes:
    """
    Encode a BGRA cutout as PNG bytes, keeping the transparency.

    Parameters:
        cutout: np.ndarray
            The BGRA image.

    Returns:
        data: bytes
            PNG encoded image, or empty bytes if encoding failed.
    """

    encoded, buffer = cv2.imencode(".png", cutout)
    return buffer.tobytes() if encoded else b""


def demo() -> None:
    """
    Show the live cutout with a checkerboard behind it.

    Parameters:
        None

    Returns:
        None
    """
    segmentor, face_cascade = initialize_face_capture()
    cap = cv2.VideoCapture(0)

    while True:
        read_ok, frame = cap.read()
        if not read_ok:
            break

        cutout = capture_face_cutout(cv2.flip(frame, 1), segmentor, face_cascade)

        # Composite over a checkerboard so the transparency is visible
        board = np.zeros((CUTOUT_SIZE, CUTOUT_SIZE, 3), np.uint8)
        tile = 16
        board[:, :] = (60, 60, 60)
        for row in range(0, CUTOUT_SIZE, tile):
            for col in range(0, CUTOUT_SIZE, tile):
                if (row // tile + col // tile) % 2 == 0:
                    board[row : row + tile, col : col + tile] = (100, 100, 100)

        alpha = cutout[:, :, 3:4] / 255.0
        preview = (cutout[:, :, :3] * alpha + board * (1 - alpha)).astype(np.uint8)

        cv2.imshow("Face cutout", preview)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    demo()
