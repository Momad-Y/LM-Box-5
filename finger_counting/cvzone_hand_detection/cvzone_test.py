# Importing the required libraries
import cv2
from cvzone.HandTrackingModule import HandDetector

# Initializing the HandDetector object and the video capture object
detector = HandDetector(maxHands=2, detectionCon=0.9)

video = cv2.VideoCapture(0)  # Capturing the video from the webcam

# The main loop to capture the video and detect the hand
while True:
    _, img = video.read()  # Reading the video frame by frame
    img = cv2.flip(img, 1)  # Flipping the video frame
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
            0,
            0,
            0,
            0,
            0,
        ]  # Initializing the list to store the centers of the fingers

        # Getting the centers of the fingers
        for i in range(5):
            if fingerup_left[i] == 1:
                fingers_centers_left[i] = tuple(left_hand["lmList"][(i + 1) * 4][0:2])
                cv2.circle(img, fingers_centers_left[i], 5, (255, 0, 0), cv2.FILLED)

        # Displaying the number of fingers up
        cv2.putText(
            img,
            f"Fingers Up Left: {sum_left}",
            (50, 50),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (255, 0, 0),
            2,
        )

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

        # Initializing the list to store the centers of the fingers
        fingers_centers_right = [0, 0, 0, 0, 0]

        # Getting the centers of the fingers
        for i in range(5):
            if fingerup_right[i] == 1:
                fingers_centers_right[i] = tuple(right_hand["lmList"][(i + 1) * 4][0:2])
                cv2.circle(img, fingers_centers_right[i], 5, (255, 0, 0), cv2.FILLED)

        # Displaying the number of fingers up
        cv2.putText(
            img,
            f"Fingers Up Right: {sum_right}",
            (350, 50),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (255, 0, 0),
            2,
        )

    # If no hands are detected
    if not is_right and not is_left:
        # Displaying the message
        cv2.putText(
            img,
            "No hands detected",
            (50, 50),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (0, 0, 255),
            2,
        )

    # Displaying the video frame
    img = cv2.resize(img, (640, 480))
    cv2.imshow("Video", img)

    # Exiting the loop if 'q' is pressed
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

# Releasing the video and destroying the windows
video.release()
cv2.destroyAllWindows()
