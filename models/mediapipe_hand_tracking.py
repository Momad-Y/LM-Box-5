import mediapipe as mp
import cv2 as cv
import math
import numpy as np


class HandTrackingDynamic:
    def __init__(
        self,
        mode: bool = False,
        maxHands: int = 2,
        detectionCon: float = 0.5,
        trackCon: float = 0.5,
    ):
        """
        Initializes the HandTrackingDynamic class.

        Args:
            mode (bool): Whether to run in static mode or not. Default is False.
            maxHands (int): Maximum number of hands to detect. Default is 2.
            detectionCon (float): Minimum confidence value for hand detection. Default is 0.5.
            trackCon (float): Minimum confidence value for hand tracking. Default is 0.5.
        """
        self.__mode__ = mode
        self.__maxHands__ = maxHands
        self.__detectionCon__ = detectionCon
        self.__trackCon__ = trackCon
        self.handsMp = mp.solutions.hands
        self.hands = self.handsMp.Hands(max_num_hands=maxHands)
        self.mpDraw = mp.solutions.drawing_utils
        self.tipIds = [4, 8, 12, 16, 20]

    def findFingers(self, frame: np.ndarray, draw: bool = True):
        """
        Finds and detects fingers in the given frame.

        Args:
            frame (numpy.ndarray): The input frame to process.
            draw (bool): Whether to draw the landmarks on the frame. Default is True.

        Returns:
            numpy.ndarray: The frame with the landmarks drawn.
        """
        imgRGB = cv.cvtColor(frame, cv.COLOR_BGR2RGB)
        self.results = self.hands.process(imgRGB)
        if self.results.multi_hand_landmarks:
            for handLms in self.results.multi_hand_landmarks:
                if draw:
                    self.mpDraw.draw_landmarks(
                        frame, handLms, self.handsMp.HAND_CONNECTIONS
                    )
        return frame

    def findPosition(self, frame: np.ndarray, size_frame: int, draw: bool = True):
        """
        Finds the position of the hands in the given frame.

        Args:
            frame (numpy.ndarray): The input frame to process.
            size_frame (int): The size of the frame.
            draw (bool): Whether to draw the bounding boxes on the frame. Default is True.

        Returns:
            list: A list containing the hand data for each hand found in the frame.
                  Each hand data is represented as a tuple containing the landmarks, bounding box,
                  center coordinates, and hand side.
        """
        hands_data = [(-1, -1, (-1, -1), "nth"), (-1, -1, (-1, -1), "nth")]
        if self.results.multi_hand_landmarks:
            for handNo, myHand in enumerate(self.results.multi_hand_landmarks):
                if handNo >= self.__maxHands__:
                    break
                xList = []
                yList = []
                lmsList = []
                for id, lm in enumerate(myHand.landmark):
                    h, w, c = frame.shape
                    cx, cy = int(lm.x * w), int(lm.y * h)
                    xList.append(cx)
                    yList.append(cy)
                    lmsList.append([id, cx, cy])
                xmin, xmax = min(xList), max(xList)
                ymin, ymax = min(yList), max(yList)
                bbox = xmin, ymin, xmax, ymax
                center_x = (xmin + xmax) // 2
                center_y = (ymin + ymax) // 2
                side = size_frame // 2

                if center_x < side:
                    hands_data[0] = (lmsList, bbox, (center_x, center_y), "left")
                elif center_x > side:
                    hands_data[1] = (lmsList, bbox, (center_x, center_y), "right")

                if draw:
                    cv.rectangle(
                        frame,
                        (xmin - 20, ymin - 20),
                        (xmax + 20, ymax + 20),
                        (0, 255, 0),
                        2,
                    )
                    cv.circle(frame, (center_x, center_y), 5, (0, 255, 0), cv.FILLED)
        return hands_data

    def findDistance(
        self,
        p1: int,
        p2: int,
        frame: np.ndarray,
        draw: bool = True,
        r: int = 15,
        t: int = 3,
    ):
        """
        Finds the distance between two landmarks in the given frame.

        Args:
            p1 (int): Index of the first landmark.
            p2 (int): Index of the second landmark.
            frame (numpy.ndarray): The input frame to process.
            draw (bool): Whether to draw the distance line and circles on the frame. Default is True.
            r (int): Radius of the circles to draw. Default is 15.
            t (int): Thickness of the distance line. Default is 3.

        Returns:
            tuple: A tuple containing the distance between the landmarks, the frame with the distance line and circles drawn,
                   and the coordinates of the landmarks and their midpoint.
        """
        x1, y1 = self.lmsList[p1][1:]
        x2, y2 = self.lmsList[p2][1:]
        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
        if draw:
            cv.line(frame, (x1, y1), (x2, y2), (255, 0, 255), t)
            cv.circle(frame, (x1, y1), r, (255, 0, 255), cv.FILLED)
            cv.circle(frame, (x2, y2), r, (255, 0, 0), cv.FILLED)
            cv.circle(frame, (cx, cy), r, (0, 255, 0), cv.FILLED)
        length = math.hypot(x2 - x1, y2 - y1)
        return length, frame, [x1, y1, x2, y2, cx, cy]


if __name__ == "__main__":
    cap = cv.VideoCapture(0)
    detector = HandTrackingDynamic()

    while True:
        success, img = cap.read()
        img = detector.findFingers(img)
        cv.imshow("Image", img)
        cv.waitKey(1)

        if cv.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv.destroyAllWindows()
