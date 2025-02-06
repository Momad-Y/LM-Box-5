# LM Box 5

## Classic Games Powered by Computer Vision

### Overview

LM Box 5 is a retro gaming project that replaces traditional controllers with computer vision. Two players can compete in two classic games:

-   **Balloons**: Use finger movements to pop balloons before they vanish.
-   **Pong**: Control paddles via hand tracking to bounce a ball back and forth.

The project leverages real-time hand tracking using the Mediapipe Hands module for an intuitive gaming experience.

---

## Features

-   **Hand Tracking**: Utilizes the Mediapipe Hands module for accurate finger detection and gesture recognition.
-   **Interactive UI**: A simple interface for game selection and settings.
-   **Real-Time Performance**: Ensures responsive gameplay with minimal lag.

---

## Installation

### Prerequisites

Ensure you have Python 3.8 or later installed.

### Setup

1. Clone the repository:
    ```sh
    git clone https://gitlab.com/Momad-Y/lm-box-5.git
    cd lm-box-5
    ```
2. Install dependencies:
    ```sh
    pip install -r requirements.txt
    ```
3. Run the application:
    ```sh
    python -m main.py
    ```

---

## Dependencies

Key libraries used in this project:

```
- OpenCV (opencv-python)
- NumPy
- PyGame
- cvzone
- Mediapipe
```

For the full list, see [requirements.txt](requirements.txt).

---

## Methodology

LM Box 5 uses the **Mediapipe Hands** module, a high-fidelity hand and finger tracking solution. It employs machine learning (ML) to infer **21 3D landmarks** of a hand from just a single frame. It doesn't require powerful hardware and can run on most devices.

### How It Works:

-   **Hand Detection**: Identifies hands in real-time video streams.
-   **Landmark Inference**: Infers 21 3D landmarks per hand, including finger tips, joints, and palm points.
-   **Gesture Mapping**: Translates finger positions and gestures into game controls.

![labeled hand landmarks image](./images/hand_landmarks.png)

### Application in LM Box 5:

-   In **Balloons**, finger movements are tracked to pop on-screen balloons.
-   In **Pong**, hand gestures control players' paddle movement.

---

## File Structure

```
lm-box-5/
├─ .gitignore
├─ gui/
│   ├─ design/
│   │   └─ ...
│   ├─ resources/
│   │   ├─ fonts/
│   │   │   └─ ...
│   │   ├─ images/
│   │   │   └─ ...
│   │   └─ sounds/
│   │       └─ ...
│   ├─ __init__.py
│   ├─ gui.py
│   ├─ utils.py
├─ models/
│   ├─ __init__.py
│   ├─ cvzone_hand_detection.py
│   ├─ mediapipe_hand_tracking.py
│   └─ requirements.txt
├─ utils/
│   └─ save_image.py
├─ requirements.txt
├─ README.md
└─ main.py
```

---

## References

-   [PyGame Documentation](https://www.pygame.org/docs/)
-   [Mediapipe Hands Documentation](https://mediapipe.readthedocs.io/en/latest/solutions/hands.html)
-   [cvzone Repository](https://github.com/cvzone/cvzone)

---

## License

This project is licensed under the MIT License.
