"""
Settings configuration module for LM Box 5.
This file stores default settings and configurations.
"""

# Default game settings
DEFAULT_SETTINGS = {
    "sound_volume": 10,  # Volume from 0-10
    "music_volume": 10,  # Volume from 0-10
    "fullscreen": True,
    "screen_width": 1280,
    "screen_height": 720,
    "camera_number": 0,
    "difficulty": "Normal",  # Easy, Normal, Hard
    "show_fps": False,
    "gesture_sensitivity": 5,  # Scale 1-10
}

# Available screen resolutions
SCREEN_RESOLUTIONS = [
    "800x600", 
    "1024x768",
    "1280x720", 
    "1366x768", 
    "1600x900", 
    "1920x1080", 
    "2560x1440",
    "Native"
]

# Difficulty settings with their modifiers
DIFFICULTY_SETTINGS = {
    "Easy": {
        "balloon_speed": 0.7,
        "pong_speed": 0.7,
        "dino_speed": 0.8,
        "score_multiplier": 0.8
    },
    "Normal": {
        "balloon_speed": 1.0,
        "pong_speed": 1.0,
        "dino_speed": 1.0,
        "score_multiplier": 1.0
    },
    "Hard": {
        "balloon_speed": 1.3,
        "pong_speed": 1.3,
        "dino_speed": 1.2,
        "score_multiplier": 1.2
    }
}
