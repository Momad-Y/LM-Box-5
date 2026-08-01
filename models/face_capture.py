# TODO: dead code, not wired into any game yet. Ported from the abandoned
# origin/models branch (face capture / background replacement prototype) so
# the feature isn't lost; needs integration into gui/ or removal.

import cv2
from cvzone.SelfiSegmentationModule import SelfiSegmentation
import numpy as np


def init_face_capture() -> tuple:
    """
    Initialize the SelfiSegmentation object, the background color, and the face cascade classifier.

    Returns:
        segmentor: SelfiSegmentation
            The SelfiSegmentation object.
        bg_color: tuple
            The background color. Default is (0, 255, 0), Green color.
        face_cascade: cv2.CascadeClassifier
            The face cascade classifier
    """

    segmentor = SelfiSegmentation()
    bg_color = (0, 255, 0)
    face_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )
    return segmentor, bg_color, face_cascade


def detect_face(
    image: np.ndarray, face_cascade: cv2.CascadeClassifier, padding: int = 60
) -> np.ndarray:
    """
    Detect faces in the image.

    Args:
        image: np.ndarray
            The image to detect faces in.
        face_cascade: cv2.CascadeClassifier
            The face cascade classifier.
        padding: int
            The padding to add to the detected face. Default is 60.

    Returns:
        face: np.ndarray
            The cropped face, resized to 256x256.
            If no face is detected, the original image is returned, resized to 256x256.
    """

    # Convert the image to the grayscale color space
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Detect faces in the image
    faces = face_cascade.detectMultiScale(gray, 1.1, 4)

    if len(faces) == 0:
        return cv2.resize(image, (256, 256))

    # Get the first face
    x, y, w, h = faces[0]

    # Add padding
    x -= padding
    y -= padding
    w += padding * 2
    h += padding * 2

    # Crop
    face = image[y : y + h, x : x + w]

    # Resize the face to 256x256
    try:
        face = cv2.resize(face, (256, 256))
    except:
        return cv2.resize(image, (256, 256))

    return face


def draw_face_boundary(image: np.ndarray, border_size: int = 2) -> np.ndarray:
    """
    Draw the boundary of the detected face.

    Args:
        image: np.ndarray
            The image to draw the boundary on.
        border_size: int
            The size of the border. Default is 2.

    Returns:
        image: np.ndarray
            The image with the boundary drawn.
    """

    # Convert the image to the grayscale color space
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Detect faces in the image
    edges = cv2.Canny(gray, 100, 200)

    # Find contours
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_TC89_KCOS)

    cv2.drawContours(image, contours, -1, (50, 50, 50, 255), border_size)

    return image


def remove_background(
    image: np.ndarray, segmentor: SelfiSegmentation, bg_color: tuple
) -> np.ndarray:
    """
    Remove the background from the image.

    Args:
        image: np.ndarray
            The image to remove the background from.
        segmentor: SelfiSegmentation
            The SelfiSegmentation object.
        bg_color: tuple
            The background color.

    Returns:
        image: np.ndarray
            The image with the background removed.
    """

    # Remove the background
    image = segmentor.removeBG(image, bg_color)

    return image


def pipline(
    image: np.ndarray,
    segmentor: SelfiSegmentation,
    bg_color: tuple,
    face_cascade: cv2.CascadeClassifier,
) -> np.ndarray:
    """
    The pipeline to process the image.

    Args:
        image: np.ndarray
            The image to process.
        segmentor: SelfiSegmentation
            The SelfiSegmentation object.
        bg_color: tuple
            The background color.
        face_cascade: cv2.CascadeClassifier
            The face cascade classifier.

    Returns:
        image: np.ndarray
            The processed image.
    """

    # Remove the background
    image = remove_background(image, segmentor, bg_color)

    # Detect the face
    face = detect_face(image, face_cascade)

    # Draw the boundary of the face
    face = draw_face_boundary(face)

    return face


def demo() -> None:
    """
    Run the face capture demo.
    """
    segmentor, bg_color, face_cascade = init_face_capture()

    cap = cv2.VideoCapture(0)

    while True:
        success, img = cap.read()

        img = pipline(img, segmentor, bg_color, face_cascade)

        cv2.imshow("Image", img)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    demo()
