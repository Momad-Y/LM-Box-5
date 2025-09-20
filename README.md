# LM Box 5

## Classic Games Powered by Computer Vision

### Overview

LM Box 5 is a retro gaming project that replaces traditional controllers with computer vision. Players can compete in three classic games:

-   **Balloons**: Use finger movements to pop balloons before they vanish.
-   **Pong**: Control paddles via hand tracking to bounce a ball back and forth.
-   **Dinosaur Runner**: Jump and duck using body movements to avoid obstacles.

The project leverages real-time hand and body tracking using computer vision modules for an intuitive gaming experience.

## Features

-   **Hand Tracking**: Utilizes the Mediapipe Hands module for accurate finger detection and gesture recognition.
-   **Body Pose Detection**: Uses Mediapipe Pose to track body movements for jumping and ducking.
-   **Interactive UI**: A sleek interface for game selection and settings.
-   **Real-Time Performance**: Ensures responsive gameplay with minimal lag.
-   **Customizable Settings**: Adjustable difficulty, sound levels, and display options.

## Games Included

1. **Balloons**: Pop colorful balloons using finger movements before they float away.
2. **Pong**: Classic two-player paddle game controlled by hand tracking.
3. **Dinosaur Runner**: A T-Rex runner clone controlled by body movements.

## Installation

### Prerequisites

Ensure you have Python 3.8 or later installed.

### Setup

1. Clone the repository (GitHub):
    ```sh
    git clone https://github.com/Samspei01/LM_BOX_5.git
    cd LM_BOX_5
    ```
2. Or Clone the repository (GitLab):
    ```sh
    git clone https://gitlab.com/Momad-Y/lm-box-5.git
    cd lm-box-5
    ```
3. Install dependencies:
    ```sh
    pip install -r requirements.txt
    ```
4. Run the application:
    ```sh
    python main.py
    ```

## Dependencies

Key libraries used in this project:

```
- OpenCV (opencv-python)
- NumPy
- PyGame
- PyGame_menu
- cvzone
- Mediapipe
- SQLite3
```

For the full list, see [requirements.txt](requirements.txt).

## Methodology

LM Box 5 uses the following computer vision technologies:

1. **Mediapipe Hands** module: A high-fidelity hand and finger tracking solution that employs machine learning to infer 21 3D landmarks of a hand from just a single frame. This powers the Balloons and Pong games.

2. **Mediapipe Pose** module: Used in the Dinosaur game to track body position and movements, enabling jump and duck controls.

### How It Works

1. **Mediapipe Hands**:

    - **Hand Detection**: Identifies hands in real-time video streams.
    - **Landmark Inference**: Infers 21 3D landmarks per hand, including finger tips, joints, and palm points.
    - **Gesture Mapping**: Translates finger positions and gestures into game controls.

![labeled hand landmarks image](./images/hand_landmarks.png)

2. **Mediapipe Pose**:

    - **Pose Estimation**: Tracks full-body movements from RGB video in real time.
    - **Landmark Inference**: Extracts 33 high-fidelity 3D body landmarks and a background segmentation mask.
    - **ML Pipeline**: Uses a two-step detector–tracker approach:

        - **Detector** finds the person/pose ROI.
        - **Tracker** predicts landmarks and segmentation from cropped frames. Detection re-runs only if tracking fails.

![labeled pose landmarks image](./images/pose_landmarks.png)

### Application in LM Box 5:

-   In **Balloons**, finger movements are tracked to pop on-screen balloons.
-   In **Pong**, hand gestures control players' paddle movement.
-   In **Dinosaur Runner**, body pose detection enables jumping and ducking movements.

## Screenshots

Here are some screenshots showcasing the different games and features of LM Box 5:

-   _Main menu interface with game selection options_
    ![Main Menu](./images/main_menu.png)

-   _Balloons game with colorful balloons to pop using hand gestures_
    ![Balloons Game](./images/balloons_game.png)

-   _Classic Pong game controlled via hand tracking_
    ![Pong Game](./images/pong_game.png)

-   _Dinosaur runner game with pose detection controls_
    ![Dinosaur Game](./images/dino_game.png)

## References

-   [PyGame Documentation](https://www.pygame.org/docs/)
-   [Mediapipe Hands Documentation](https://mediapipe.readthedocs.io/en/latest/solutions/hands.html)
-   [Mediapipe Pose Documentation](https://mediapipe.readthedocs.io/en/latest/solutions/pose.html)
-   [cvzone Repository](https://github.com/cvzone/cvzone)

## Contact

For questions or support, you can reach out to the project maintainers:

| Name            | Abdelrhman Saeed                                                                    | Mohamed Abdelnasser                                                       |
| --------------- | ----------------------------------------------------------------------------------- | ------------------------------------------------------------------------- |
| Email           | [abdosaaed749@gmail.com](mailto:abdosaaed749@gmail.com)                             | [Mohamed.y.abdelnasser@gmail.com](mailto:Mohamed.y.abdelnasser@gmail.com) |
| Code Repository | [GitHub Profile](https://github.com/Samspei01)                                      | [GitLab Profile](https://gitlab.com/Momad-Y)                              |
| LinkedIn        | [LinkedIn Profile](https://www.linkedin.com/in/abdelrhman-saeed-elsayed-9b17b9238/) | [LinkedIn Profile](https://www.linkedin.com/in/mohamed-y-abdelnasser)     |

## Credits

-   Built with Pygame and Mediapipe
-   Font: Press Start 2P, Joystix Monospace
-   Sound effects: Creative Commons licensed

## License

This project is licensed under the MIT License.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
