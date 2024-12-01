import cv2
import mediapipe as mp

mp_hands = mp.solutions.hands
hands = mp_hands.Hands(
    static_image_mode=False,
    max_num_hands=2,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5,
)
mp_draw = mp.solutions.drawing_utils

finger_tips = [4, 8, 12, 16, 20]


def find_hands(img, draw=True):
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    results = hands.process(img_rgb)
    if results.multi_hand_landmarks:
        for hand_landmarks in results.multi_hand_landmarks:
            if draw:
                mp_draw.draw_landmarks(img, hand_landmarks, mp_hands.HAND_CONNECTIONS)
    return img, results


def find_position(img, results, hand_no=0, draw=True):
    lm_list = []
    if results.multi_hand_landmarks:
        my_hand = results.multi_hand_landmarks[hand_no]
        for id, lm in enumerate(my_hand.landmark):
            h, w, c = img.shape
            cx, cy = int(lm.x * w), int(lm.y * h)
            lm_list.append([id, cx, cy])
            if draw:
                cv2.circle(img, (cx, cy), 15, (255, 0, 255), cv2.FILLED)
    return lm_list


video_capture = cv2.VideoCapture(0)

# Main loop to capture video frames and detect fingers
while True:
    success, frame = video_capture.read()

    # Detect hands in the frame and get landmark positions
    frame, results = find_hands(frame)
    landmarks = find_position(frame, results, draw=False)

    if len(landmarks) != 0:
        fingers_status = []

        # Detect thumb: compare x-coordinates for open/closed status
        if landmarks[finger_tips[0]][1] > landmarks[finger_tips[0] - 1][1]:
            fingers_status.append(1)
        else:
            fingers_status.append(0)

        # Detect the rest of the fingers: compare y-coordinates for open/closed status
        for finger in range(1, 5):
            if (
                landmarks[finger_tips[finger]][2]
                < landmarks[finger_tips[finger] - 2][2]
            ):
                fingers_status.append(1)
            else:
                fingers_status.append(0)

        # Count the number of fingers that are up
        total_fingers_up = fingers_status.count(1)

        # Display the result on the video frame
        cv2.rectangle(frame, (10, 10), (100, 70), (0, 0, 255), cv2.FILLED)
        cv2.putText(
            frame,
            str(total_fingers_up),
            (34, 60),
            cv2.FONT_HERSHEY_SIMPLEX,
            2,
            (255, 255, 255),
            4,
        )

    else:
        # Display the message if no hands are detected
        cv2.putText(
            frame,
            "No hands detected",
            (50, 50),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (0, 0, 255),
            2,
        )

    # Display the video frame
    cv2.imshow("Finger Counting", frame)

    # Break the loop if 'q' is pressed
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

# Release the VideoCapture object and close the windows
video_capture.release()
cv2.destroyAllWindows()
