"""
Settings configuration module for LM Box 5.

Defines the settings persisted to data/settings.json, the values they are
allowed to take, and the per-difficulty multipliers the games apply. Every
key in DEFAULT_SETTINGS is read somewhere in the game - a setting that stops
having an effect belongs here no longer.
"""

# Default game settings
DEFAULT_SETTINGS = {
    # Audio. music_volume is the absolute playback level; sound_volume scales
    # each sound effect's designed level, so 100 means "as the game mixed it".
    "music_volume": 20,
    "sound_volume": 80,
    # Controls
    "camera_number": 0,
    # 1-10; higher means less head movement is needed to trigger jump/duck
    "gesture_sensitivity": 5,
    # Last players chosen, so the picker can default to them next time.
    # 0 means nobody has been chosen yet. Not shown in the settings menu -
    # they are set by playing, not by editing.
    "player_1_id": 0,
    "player_2_id": 0,
    # Gameplay
    "difficulty": "Normal",  # Easy, Normal, Hard
    "pong_points_to_win": 7,
    "balloons_waves": 5,
    "show_fps": False,
    # Which games' how-to screen has already been shown. Like player_1_id
    # above, this isn't shown in the settings menu - it's set by playing,
    # here specifically by pressing ENTER through a game's rules once.
    "instructions_seen": [],
    # Whether the one-time "everything stays on this device" notice has
    # been shown. Not shown in the settings menu either - see PRIVACY in
    # the credits screen for a permanent copy of the same message.
    "privacy_notice_seen": False,
}

# Difficulty options, in the order the settings menu offers them
DIFFICULTIES = ["Easy", "Normal", "Hard"]

# Multipliers each game applies to its speeds and scoring
DIFFICULTY_SETTINGS = {
    "Easy": {
        "balloon_speed": 0.7,
        "pong_speed": 0.7,
        "runner_speed": 0.8,
        "score_multiplier": 0.8,
    },
    "Normal": {
        "balloon_speed": 1.0,
        "pong_speed": 1.0,
        "runner_speed": 1.0,
        "score_multiplier": 1.0,
    },
    "Hard": {
        "balloon_speed": 1.3,
        "pong_speed": 1.3,
        "runner_speed": 1.2,
        "score_multiplier": 1.2,
    },
}

# Ranges the settings menu offers, as (minimum, maximum)
VOLUME_RANGE = (0, 100)
GESTURE_SENSITIVITY_RANGE = (1, 10)
PONG_POINTS_RANGE = (1, 15)
BALLOONS_WAVES_RANGE = (1, 10)

# Camera indices offered in the settings menu
CAMERA_NUMBERS = [0, 1, 2]
