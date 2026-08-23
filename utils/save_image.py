import os
import time

import cv2

CWD = os.path.dirname(os.path.abspath(__file__))

# Captures go next to the game's other runtime data rather than into whatever
# directory the process happened to start in. The old path was relative to the
# working directory and pointed at a folder that doesn't exist, so every save
# silently failed while still reporting success.
CAPTURES_DIR = os.path.join(CWD, "..", "data", "captures")


def save_image_on_button_press():
    """Show the camera feed and save a frame each time 's' is pressed."""
    # Create a VideoCapture object
    cap = cv2.VideoCapture(0)

    # Check if the camera is opened successfully
    if not cap.isOpened():
        print("Unable to open the camera")
        return

    os.makedirs(CAPTURES_DIR, exist_ok=True)

    while True:
        # Read the frame from the camera
        read_ok, frame = cap.read()
        if not read_ok or frame is None:
            print("Unable to read a frame from the camera")
            break

        # Display the frame
        cv2.imshow("Camera", frame)

        # Check if the 's' key is pressed
        if cv2.waitKey(1) & 0xFF == ord("s"):
            # Save the frame as an image
            image_path = os.path.join(CAPTURES_DIR, f"test_img_{time.time()}.png")
            if cv2.imwrite(image_path, frame):
                print(f"Image saved to {image_path}")
            else:
                print(f"Could not save the image to {image_path}")

        # Check if the 'q' key is pressed
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    # Release the VideoCapture object and close the windows
    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    # Only run the capture loop when this file is executed directly - importing
    # it used to open the camera and block in the loop
    save_image_on_button_press()
