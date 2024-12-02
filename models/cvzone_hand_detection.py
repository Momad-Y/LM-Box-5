import cv2
from cvzone.HandTrackingModule import HandDetector
import numpy as np
import pprint


def initialize_hand_detector(detection_con: float = 0.9) -> HandDetector:
    """
    Initialize the HandDetector object and the video capture object.

    Parameters:
        detection_con: float
            The confidence threshold for hand detection.

    Returns:
        detector: HandDetector
            The HandDetector object.
    """

    # Initializing the HandDetector object and the video capture object
    detector = HandDetector(maxHands=2, detectionCon=detection_con)

    return detector


def detect_hands(detector: HandDetector, img: np.ndarray) -> dict:
    """
    Detect the hands in the video frame.

    Parameters:
        detector: HandDetector
            The HandDetector object.
        img: np.ndarray
            The video frame in which the hands are to be detected.

    Returns:
        hand_data: dict
            The data of the detected hands.
    """

    hand_data = detector.findHands(img, draw=False)  # Detecting the hand

    hands = hand_data[0]  # Getting the hand data

    # Initializing the variables to store if one or two hands are detected
    is_one = False
    is_both = False

    # Checking if one or two hands are detected
    try:
        first_hand = hands[0]
    except:
        is_one = False
    else:
        is_one = True

        try:
            second_hand = hands[1]
        except:
            is_both = False
        else:
            is_both = True

    # Initializing the variables to store the left and right hand data
    is_left = False
    is_right = False

    # Checking if the left or right hand is detected
    hand_data = {
        "left_hand": None,
        "right_hand": None,
    }

    # Checking if the left or right hand is detected
    if is_one and not is_both:
        if first_hand["type"] == "Left":
            right_hand = first_hand
            is_right = True
        else:
            left_hand = first_hand
            is_left = True
    elif is_one and is_both:
        if first_hand["type"] == "Left":
            left_hand = first_hand
            right_hand = second_hand
        else:
            left_hand = second_hand
            right_hand = first_hand

        is_left = True
        is_right = True

    if is_left:
        fingerup_left = detector.fingersUp(
            left_hand
        )  # Getting the number of fingers up

        # Calculating the sum of the fingers up
        sum_left = (
            fingerup_left[0]
            + fingerup_left[1]
            + fingerup_left[2]
            + fingerup_left[3]
            + fingerup_left[4]
        )

        fingers_centers_left = [
            (-1, -1) for _ in range(5)
        ]  # Initializing the list to store the centers of the fingers

        # Getting the centers of the fingers
        for i in range(5):
            if fingerup_left[i] == 1:
                fingers_centers_left[i] = tuple(left_hand["lmList"][(i + 1) * 4][0:2])
                # cv2.circle(img, fingers_centers_left[i], 5, (255, 0, 0), cv2.FILLED)

        # Storing the left hand data
        hand_data["left_hand"] = {
            "fingers_up": fingerup_left,
            "total_fingers_up": sum_left,
            "fingers_centers": fingers_centers_left,
        }

    if is_right:
        fingerup_right = detector.fingersUp(
            right_hand
        )  # Getting the number of fingers up

        # Calculating the sum of the fingers up
        sum_right = (
            fingerup_right[0]
            + fingerup_right[1]
            + fingerup_right[2]
            + fingerup_right[3]
            + fingerup_right[4]
        )

        fingers_centers_right = [
            (-1, -1) for _ in range(5)
        ]  # Initializing the list to store the centers of the fingers

        # Getting the centers of the fingers
        for i in range(5):
            if fingerup_right[i] == 1:
                fingers_centers_right[i] = tuple(right_hand["lmList"][(i + 1) * 4][0:2])
                # cv2.circle(img, fingers_centers_right[i], 5, (255, 0, 0), cv2.FILLED)

        # Storing the right hand data
        hand_data["right_hand"] = {
            "fingers_up": fingerup_right,
            "total_fingers_up": sum_right,
            "fingers_centers": fingers_centers_right,
        }

    return hand_data


def demo() -> None:
    """
    Detect the hands in the image.

    Parameters:
        None

    Returns:
        None
    """
    # Initialize the HandDetector object
    detector = initialize_hand_detector()

    # Open the camera and read the frame
    cap = cv2.VideoCapture(0)

    while True:
        _, img = cap.read()

        img = cv2.flip(img, 1)

        img = cv2.resize(
            img,
            (
                768,
                432,
            ),
        )

        # Detect the hands
        hand_data = detect_hands(detector, img)

        # Display the frame
        cv2.imshow("Camera", img)

        # Break the loop if the 'q' key is pressed
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

        pprint.pprint(hand_data)


if __name__ == "__main__":
    # Run the demo
    demo()
