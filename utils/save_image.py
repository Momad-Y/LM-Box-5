import cv2
import time


def save_image_on_button_press():
    # Create a VideoCapture object
    cap = cv2.VideoCapture(0)

    # Check if the camera is opened successfully
    if not cap.isOpened():
        print("Unable to open the camera")
        return

    while True:
        # Read the frame from the camera
        _, frame = cap.read()

        # Display the frame
        cv2.imshow("Camera", frame)

        # Check if the 's' key is pressed
        if cv2.waitKey(1) & 0xFF == ord("s"):
            # Save the frame as an image
            cv2.imwrite(
                f"./finger_counting/test_imgs/test_img_{time.time()}.png", frame
            )
            print("Image saved successfully")

        # Check if the 'q' key is pressed
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    # Release the VideoCapture object and close the windows
    cap.release()
    cv2.destroyAllWindows()


# Call the function to save the image on button press
save_image_on_button_press()
