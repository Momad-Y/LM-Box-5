import pygame
from pygame.locals import *
from pygame import mixer

import cv2

import io
import random
import sys
import time
import os
import json
import sqlite3  # Add SQLite database support
import numpy as np
import platformdirs
from gui.settings_config import DEFAULT_SETTINGS, DIFFICULTY_SETTINGS

from models.mediapipe_hand_tracking import HandTrackingDynamic
from models.cvzone_hand_detection import initialize_hand_detector, detect_hands
from models.face_capture import (
    initialize_face_capture,
    capture_face_cutout,
    cutout_coverage,
    encode_png,
    CUTOUT_SIZE,
    MIN_COVERAGE,
)
from models.pose_tracking import (
    initialize_pose_detector,
    detect_jump_duck,
    calibrate_baseline,
    threshold_ratios,
)
from screeninfo import get_monitors

from gui.utils import random_bool_by_chance, biased_random_int, resize_cover
from gui.runner_sprites import Runner, Cactus, Ptero, Cloud, ground_line_offset
from gui.camera_stream import ThreadedCapture
from gui.frame_clock import FrameClock
from gui import ui_kit as ui
from gui import (
    screen_menu,
    screen_users,
    screen_settings,
    screen_leaderboards,
    screen_credits,
    screen_ingame,
)


# Get the current working directory
CWD = os.path.dirname(os.path.abspath(__file__))


def _resolve_data_dir():
    """Where settings, the user database, and captured photos live.

    Running from source, this stays right next to the checkout - as it
    always has - so existing dev setups keep working unchanged. Once frozen
    into a standalone executable (PyInstaller etc.), __file__ resolves
    inside a temp extraction directory or a read-only install path, neither
    of which survives past this run, so a frozen build instead uses the
    OS's real per-user application-data directory.
    """
    if getattr(sys, "frozen", False):
        return platformdirs.user_data_dir("LMBox5", "LMBox5")
    return os.path.join(CWD, "..", "data")


# Local runtime data (settings, user profiles) lives here instead of loose
# in the project root, so it's easy to gitignore/back up/locate as a unit.
DATA_DIR = _resolve_data_dir()
os.makedirs(DATA_DIR, exist_ok=True)

# Camera capture resolution. Kept at a mode the webcam can actually stream at
# 30 FPS - see init_camera for why this matters to the whole game loop.
CAMERA_CAPTURE_WIDTH = 640
CAMERA_CAPTURE_HEIGHT = 480

# Width the camera frame is downscaled to before pose inference; the
# nose-position heuristic doesn't need more detail than this.
POSE_DETECT_WIDTH = 480

# How many frames per second the game loop aims to render at. This is a
# rendering target only - it deliberately does NOT appear in any movement
# maths (see MOVEMENT_REFERENCE_FPS), so it can be raised or lowered
# without changing how fast anything actually moves.
TARGET_FPS = 60

# The rate every game's per-frame movement constant (balloon speed, ball
# speed, runner speed) was originally tuned at. frame_dt_scale() converts a
# measured frame time into "how many of THESE frames' worth of movement
# should happen", which is what keeps real-world speed identical whatever
# frame rate the hardware actually sustains.
#
# Kept separate from TARGET_FPS, and this separation is the whole point:
# real-world velocity works out to (tuned constant x whatever rate dt_scale
# normalises against). When that was TARGET_FPS, raising the render target
# from 30 to 60 silently doubled the intended speed of all three games, and
# because the clamp below bounded dt_scale at 2.0 the actual speed then
# varied with frame rate too (1.33x the original tuning at 20 FPS, rising
# to a full 2x at 30 FPS and above) - so the games sped up as the machine
# got faster. Normalising against the rate the constants were authored at
# instead makes speed a property of the tuning, not of the frame rate.
MOVEMENT_REFERENCE_FPS = 30

# Upper bound on how large a single frame's dt is allowed to count as, in
# frame_dt_scale(). Without this, one bad hitch (a GC pause, an alt-tab, a
# slow disk read) would make whatever moved that frame jump so far in one
# step that a collision check between two rects could skip over each other
# entirely - capping it means a real, sustained slowdown still scales
# proportionally, but a one-off stutter can't teleport anything.
#
# Anchored to MOVEMENT_REFERENCE_FPS (always 1/2 of it), so the worst-case
# dt_scale stays 2.0x - the ceiling Pong's ball-speed displacement clamp and
# Runner's obstacle-collision margin were both verified safe against (see
# gui/runner_sprites.py's Obstacle.update).
MAX_FRAME_DT = 2 / MOVEMENT_REFERENCE_FPS

# Every in-game screen is drawn onto a canvas of this fixed size and then
# scaled onto the window, which makes the layout independent of the window -
# under Wayland it can be resized at any moment.
#
# 1080p specifically: the screens position text with hardcoded pixel offsets
# and font sizes (credit rows every 50px from y=300, columns at a quarter and
# three quarters of the width, prompts 100px off the bottom) which were all
# written against a full-HD screen. Drawing them into a smaller canvas leaves
# the text at its original size in a shrunken coordinate space, so columns
# collide and rows overrun the bottom of the screen.
GAME_CANVAS_SIZE = (1920, 1080)

# Sky colour of the Runner play field (the runner's original background)
RUNNER_FIELD_COLOR = (255, 182, 193)

# Height above the ground that a pterodactyl flies at when it's meant to be
# ducked under. It has to clear a crouching runner but block a standing one.
RUNNER_DUCK_UNDER_HEIGHT = 45

# Points between each speed-up milestone. At the default score rate (3
# points/sec at Normal difficulty) this lands the first bump at ~13s and
# the full ramp to the speed cap at ~3 minutes - meant to be a normal part
# of an average round, not a rare reward only exceptional-length runs see.
RUNNER_SPEED_MILESTONE_POINTS = 40

# How much quicker Runner scrolls than its original 30-FPS-era tuning.
# The start speed, the cap and the per-milestone step are all scaled by
# this one number so the ramp keeps its original shape - only its overall
# pace changes. Bump it to make the whole game faster, drop it to slow it
# down; nothing else needs touching.
RUNNER_SPEED_SCALE = 1.2
RUNNER_START_SPEED = 16 * RUNNER_SPEED_SCALE
RUNNER_MAX_SPEED = 26 * RUNNER_SPEED_SCALE
RUNNER_SPEED_STEP = 0.8 * RUNNER_SPEED_SCALE


class Game:
    def __init__(self):
        self.user_screen_number = 0  # The screen number to display the game on
        self.game_name = "LM Box 5"  # The name of the game
        self.initial_screen_width = 1280  # The default screen width
        self.initial_screen_height = 720  # The default screen height
        self.user_camera_number = 0  # The camera number to use for the game
        
        # Initialize game settings
        self.load_settings()
        
        # Setup database for users
        self.setup_database()
        
        # Get the user's screen resolution
        user_screen = get_monitors()[self.user_screen_number]
        self.user_screen_width = user_screen.width
        self.user_screen_height = user_screen.height

        # Initialize the camera
        self.init_camera()

        # Initialize the finger detection
        self.init_finger_detection()

        # Initialize the hand tracking
        self.init_hand_tracking()

        # Initialize the pose detection (jump/duck detection for Runner)
        self.init_pose_detection()

        # Start Pygame
        pygame.init()

        # Initialize the mixer for sound
        mixer.init()

        # Set the icon
        icon = pygame.image.load(f"{CWD}/resources/images/5-lmbox-icon.png")
        pygame.display.set_icon(icon)

        # Create the window
        self.window = pygame.display.set_mode(
            (self.user_screen_width, self.user_screen_height),
            pygame.FULLSCREEN,
            display=self.user_screen_number,
        )

        # Under Wayland, the compositor's resize/configure handshake (e.g.
        # reserving space for bars/gaps) isn't applied until the event queue
        # is pumped, and a single pump isn't reliably enough time for that
        # round-trip to land. Poll briefly, re-reading the actual granted
        # size instead of trusting the requested monitor resolution.
        requested_size = (self.user_screen_width, self.user_screen_height)
        for _ in range(20):
            pygame.event.pump()
            granted_size = self.window.get_size()
            if granted_size != requested_size:
                break
            pygame.time.wait(20)
        self.window_width, self.window_height = self.window.get_size()

        # In-game screens draw onto a fixed-size canvas which is then scaled
        # onto the window by present(). Keeping the drawing surface a constant
        # size means the games' layout never has to be recomputed when the
        # window is resized, and it matches the size the background art and
        # the coordinate maths were built around.
        self.screen = pygame.Surface(GAME_CANVAS_SIZE)
        self.user_screen_width, self.user_screen_height = GAME_CANVAS_SIZE

        # Set the window title
        pygame.display.set_caption(self.game_name)

        # Users chosen for the current game, set by the player picker
        self.active_players = []

        # Decoded face pictures, keyed by user id. A picture can't change
        # mid-round, but the HUD asks for it every single frame, so it's
        # decoded once here and reused rather than hitting the database and
        # re-decoding the PNG 30x/sec (see get_user_face_surface).
        self._face_surface_cache = {}

        # Resolved names, keyed by user id - same idea as the face cache
        # above, for the same reason: player_label()/get_user_name() are
        # called every frame by every game's HUD, and a name can't change
        # mid-round either.
        self._user_name_cache = {}

        # Games whose how-to screen has already been shown, so the rules
        # earn their keypress once rather than every round. Persisted to
        # settings.json (see mark_instructions_seen) rather than session-only,
        # so it doesn't reset just because the app was restarted.
        self.instructions_seen = set(self.settings.get("instructions_seen", []))

        # Initialize the clock for controlling the frame rate and delta time.
        # Deliberately not pygame.time.Clock: its tick() truncates the target
        # frame time to whole milliseconds, so tick(60) actually paces at up
        # to 62.5 FPS (see gui/frame_clock.py). TARGET_FPS is handed over as
        # a ceiling the individual tick(60) call sites cannot exceed.
        self.clock = FrameClock(max_fps=TARGET_FPS)
        self.dt = 0

        # Initialize the font for the game
        self.font_path = f"{CWD}/resources/fonts/joystix monospace.otf"

        # Seed the random number generator
        random.seed(time.time())

        # Hand over to the app loop, which owns every screen from here
        self.run()

    def load_settings(self):
        """Load game settings from file or use defaults"""
        settings_path = os.path.join(DATA_DIR, "settings.json")
        if os.path.exists(settings_path):
            try:
                with open(settings_path, 'r') as f:
                    self.settings = json.load(f)
                # Fill in any missing settings with defaults
                for key, value in DEFAULT_SETTINGS.items():
                    if key not in self.settings:
                        self.settings[key] = value
            except (json.JSONDecodeError, IOError):
                # If there's an error loading, use defaults
                self.settings = DEFAULT_SETTINGS.copy()
        else:
            # If no settings file exists, use defaults
            self.settings = DEFAULT_SETTINGS.copy()
        
        # Apply settings
        self.apply_settings()
            
    def save_settings(self):
        """Save current settings to file"""
        settings_path = os.path.join(DATA_DIR, "settings.json")
        # Written via a temp file + atomic replace, not straight into the
        # live file, so a crash or power loss mid-write can't leave
        # settings.json truncated - the next launch either sees the old
        # settings or the new ones, never a half-written file.
        tmp_path = settings_path + ".tmp"
        try:
            with open(tmp_path, 'w') as f:
                json.dump(self.settings, f, indent=4)
            os.replace(tmp_path, settings_path)
        except (IOError, TypeError, ValueError):
            print("Warning: Could not save settings to file.")
            # Whatever failed, don't leave a half-written temp file behind
            # forever - the next successful save will just recreate it.
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            
    def apply_settings(self):
        """Apply the current settings to the game.

        Called on startup and again whenever a setting is changed, so the
        settings menu takes effect immediately rather than on next launch.
        """
        # Audio. Music is set live; sound effects pick the multiplier up when
        # a game loads them (see sfx_volume).
        self.music_volume = self.settings["music_volume"] / 100
        self.sound_volume = self.settings["sound_volume"] / 100
        if pygame.mixer.get_init():
            mixer.music.set_volume(self.music_volume)

        # Camera
        self.user_camera_number = self.settings["camera_number"]

        # Controls
        self.gesture_sensitivity = self.settings["gesture_sensitivity"]

        # Difficulty, and the speed/score multipliers that go with it
        self.difficulty = self.settings["difficulty"]
        self.difficulty_modifiers = DIFFICULTY_SETTINGS.get(
            self.difficulty, DIFFICULTY_SETTINGS["Normal"]
        )

    def sfx_volume(self, base_volume):
        """Scale a sound effect's designed level by the sound volume setting."""
        return max(0.0, min(1.0, base_volume * self.sound_volume))

    def frame_dt_scale(self):
        """How many nominal (1/MOVEMENT_REFERENCE_FPS) frames the last real
        frame was worth.

        Multiply any per-frame movement/speed value by this so gameplay
        stays correct in real time regardless of the actual frame rate the
        hardware sustains - 1.0 at exactly the reference rate (the tuned
        feel), higher on slower hardware, clamped so one bad hitch can't
        move something so far in a single step that a collision check skips
        over what it should have hit.

        Normalises against MOVEMENT_REFERENCE_FPS, not TARGET_FPS: the
        render target must not be able to change how fast the games play.
        """
        if not self.dt:
            return 1.0
        return min(self.dt, MAX_FRAME_DT) * MOVEMENT_REFERENCE_FPS

    def pump_events(self):
        """Fetch this frame's events, handling app quit here once.

        Every screen's event loop used to repeat the same
        QUIT-check-then-exit boilerplate; callers just iterate the
        returned list for their own key handling now and never need to
        check for pygame.QUIT themselves.
        """
        events = pygame.event.get()
        for event in events:
            if event.type == pygame.QUIT:
                self.quit_app()
        return events

    def release_resources(self):
        """Release the camera and close the mediapipe models, without
        touching pygame or the process.

        Split out from quit_app() so a test fixture that builds a real
        Game() (real mediapipe Hands/Pose objects, each backed by a GPU
        context on this machine's Mesa/Intel driver) can release the same
        resources at teardown without also tearing down pygame or the
        process - constructing 100+ of these across a full test run and
        never releasing any of them was itself enough to freeze this
        laptop hard, the same way the original unreleased-camera bug did.
        See quit_app()'s docstring and docs/PERFORMANCE_AUDIT.md's
        incident note.
        """
        if getattr(self, "cap", None) is not None:
            self.cap.release()

        for detector in (
            getattr(self, "hand_tracking", None),
            getattr(self, "finger_detector", None),
        ):
            hands = getattr(detector, "hands", None)
            if hands is not None:
                hands.close()

        if getattr(self, "pose_detector", None) is not None:
            self.pose_detector.close()

    def quit_app(self):
        """Release the camera/mediapipe models, then end the process.

        The one and only way this app should ever terminate. Every quit
        path - the main menu's own quit action, pump_events' QUIT-event
        handling, and every screen that still polls for QUIT itself
        (show_instructions, show_privacy_notice, show_no_camera in
        screen_ingame.py) - calls this instead of pygame.quit()+exit()
        directly, so releasing resources can never be skipped by a future
        exit path that forgets to duplicate it. There were 5 separate
        pygame.quit()+exit() call sites before this, and none of them
        released anything.

        This isn't cosmetic: the camera used to just get left open,
        actively streaming, for the process's entire life, then abruptly
        cut off when it died instead of being stopped gracefully first -
        on this app's actual hardware, that was enough to hang the whole
        machine, not just the app, requiring a hard reboot. See
        docs/PERFORMANCE_AUDIT.md's note on this incident.
        """
        self.release_resources()
        pygame.quit()
        exit()

    def draw_fps(self):
        """Draw the frame rate in the corner when the setting is enabled."""
        if not self.settings.get("show_fps"):
            return

        font = ui.font(self.font_path, 20)
        text = font.render(
            f"FPS:{int(self.clock.get_fps())}", True, (255, 255, 255), (0, 0, 0)
        )
        self.screen.blit(text, (20, self.screen.get_height() - text.get_height() - 20))

    def setup_database(self):
        """Set up SQLite database for user management"""
        # Create a database in the same directory as the script
        db_path = os.path.join(DATA_DIR, "lmbox_users.db")
        try:
            self.conn = sqlite3.connect(db_path)
            self.cursor = self.conn.cursor()

            # Create users table if it doesn't exist
            self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''')
            self.conn.commit()

            # Add the face picture column to databases created before it
            # existed, so an existing users file keeps working after an update
            columns = [
                row[1] for row in self.cursor.execute("PRAGMA table_info(users)").fetchall()
            ]
            if "face_image" not in columns:
                self.cursor.execute("ALTER TABLE users ADD COLUMN face_image BLOB")
                self.conn.commit()

            # Scores are kept per user and per game, so a personal best can be
            # shown when a round ends
            self.cursor.execute(
                """
            CREATE TABLE IF NOT EXISTS scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                game TEXT NOT NULL,
                score INTEGER NOT NULL,
                played_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
            )
            self.conn.commit()

            # Check if there are any users, add a default one if empty
            self.cursor.execute("SELECT COUNT(*) FROM users")
            if self.cursor.fetchone()[0] == 0:
                self.cursor.execute("INSERT INTO users (name) VALUES (?)", ("Player 1",))
                self.conn.commit()
        except sqlite3.Error as exc:
            sys.exit(
                f"Could not open or set up the database at {db_path}: {exc}\n"
                "It may be corrupted, or locked by another program. Close any "
                "other copy of LM Box 5 and try again."
            )

    def _db_execute(self, query, params=(), *, commit=False):
        """Run one SQL statement, returning the cursor or None on failure.

        Every read/write below goes through here so a locked or corrupted
        database degrades whichever screen asked for it instead of crashing
        the whole app - most importantly, a failure here can no longer lose
        the score from the round that was just played.
        """
        try:
            result = self.cursor.execute(query, params)
            if commit:
                self.conn.commit()
            return result
        except sqlite3.Error as exc:
            print(f"Warning: database operation failed: {exc}")
            return None

    def _valid_user_name(self, name):
        """Clean and validate a name before it's written to the database.

        Mirrors the constraints prompt_text already enforces while typing
        (a 30-character cap, printable characters only) - this is the
        actual persistence boundary, so it enforces them again rather than
        trusting every caller to have gone through that screen. Returns the
        stripped name, or None if it isn't usable.
        """
        if not isinstance(name, str):
            return None
        name = name.strip()
        if not name or len(name) > 30 or not name.isprintable():
            return None
        return name

    def get_users(self):
        """Get all users from the database"""
        result = self._db_execute("SELECT id, name FROM users")
        return result.fetchall() if result is not None else []

    def delete_user(self, user_id):
        """Delete a user, along with their scores"""
        # SQLite doesn't enforce foreign keys unless asked to, so the scores
        # are removed here rather than left orphaned behind a deleted user.
        # Each delete commits on its own rather than leaving the first one
        # pending: without a commit here, a failure on the second delete
        # would leave the scores delete sitting in an open transaction on
        # this long-lived connection, to be flushed later by whatever
        # unrelated write happens to commit next.
        if (
            self._db_execute(
                "DELETE FROM scores WHERE user_id = ?", (user_id,), commit=True
            )
            is None
        ):
            return
        if (
            self._db_execute(
                "DELETE FROM users WHERE id = ?", (user_id,), commit=True
            )
            is None
        ):
            return

        # Forget the player if they were one of the remembered picks
        for key in ("player_1_id", "player_2_id"):
            if self.settings.get(key) == user_id:
                self.change_setting(key, 0)

        self._invalidate_face_cache(user_id)
        self._invalidate_user_name_cache(user_id)

    def record_score(self, user_id, game, score):
        """Store the result of a round for a user."""
        if not user_id:
            return
        self._db_execute(
            "INSERT INTO scores (user_id, game, score) VALUES (?, ?, ?)",
            (user_id, game, int(score)),
            commit=True,
        )

    def get_best_score(self, user_id, game):
        """Return a user's best score for a game, or None if they've none."""
        if not user_id:
            return None
        result = self._db_execute(
            "SELECT MAX(score) FROM scores WHERE user_id = ? AND game = ?",
            (user_id, game),
        )
        if result is None:
            return None
        row = result.fetchone()
        return row[0] if row and row[0] is not None else None

    def get_leaderboard(self, game, limit=8):
        """Return the best score per user for a game, highest first.

        Joined against users so only people who still exist are listed.
        """
        result = self._db_execute(
            """
            SELECT users.id, users.name, MAX(scores.score) AS best
            FROM scores
            JOIN users ON users.id = scores.user_id
            WHERE scores.game = ?
            GROUP BY users.id
            ORDER BY best DESC, users.name ASC
            LIMIT ?
            """,
            (game, limit),
        )
        return result.fetchall() if result is not None else []

    def get_user_name(self, user_id):
        """Return a user's name, or None if they no longer exist.

        Cached per user id (see _user_name_cache) - a round's active
        players don't change mid-round, but every game's HUD asks for
        their name every single frame via player_label().
        """
        if not user_id:
            return None
        if user_id not in self._user_name_cache:
            result = self._db_execute("SELECT name FROM users WHERE id = ?", (user_id,))
            row = result.fetchone() if result is not None else None
            self._user_name_cache[user_id] = row[0] if row else None
        return self._user_name_cache[user_id]

    def rename_user(self, user_id, name):
        """Change a user's name, keeping their id and picture."""
        name = self._valid_user_name(name)
        if name is None:
            return
        self._db_execute(
            "UPDATE users SET name = ? WHERE id = ?", (name, user_id), commit=True
        )
        self._invalidate_user_name_cache(user_id)

    def add_user_returning_id(self, name):
        """Add a user and return the new row's id, or None if the name was
        invalid or the write failed."""
        name = self._valid_user_name(name)
        if name is None:
            return None
        result = self._db_execute(
            "INSERT INTO users (name) VALUES (?)", (name,), commit=True
        )
        return self.cursor.lastrowid if result is not None else None

    def set_user_face(self, user_id, png_bytes):
        """Store a user's face picture (PNG bytes, with transparency)."""
        self._db_execute(
            "UPDATE users SET face_image = ? WHERE id = ?",
            (sqlite3.Binary(png_bytes), user_id),
            commit=True,
        )
        self._invalidate_face_cache(user_id)

    def clear_user_face(self, user_id):
        """Remove a user's face picture, keeping the user."""
        self._db_execute(
            "UPDATE users SET face_image = NULL WHERE id = ?", (user_id,), commit=True
        )
        self._invalidate_face_cache(user_id)

    def get_user_face_bytes(self, user_id):
        """Return a user's stored PNG bytes, or None if they have no picture."""
        result = self._db_execute(
            "SELECT face_image FROM users WHERE id = ?", (user_id,)
        )
        if result is None:
            return None
        row = result.fetchone()
        return bytes(row[0]) if row and row[0] is not None else None

    def get_user_face_surface(self, user_id):
        """Return a user's face as a pygame surface with transparency.

        This is what the games can draw with once they know who is playing.
        Cached per user id so the HUD - which calls this every frame - only
        hits the database and decodes the PNG once per round, not 30x/sec.
        """
        if user_id not in self._face_surface_cache:
            data = self.get_user_face_bytes(user_id)
            self._face_surface_cache[user_id] = (
                pygame.image.load(io.BytesIO(data), "face.png").convert_alpha()
                if data
                else None
            )
        return self._face_surface_cache[user_id]

    def _invalidate_face_cache(self, user_id):
        """Forget any decoded face surface cached for a user.

        Called whenever their stored picture changes, so the next frame
        that asks for it re-decodes instead of showing a stale image.
        """
        self._face_surface_cache.pop(user_id, None)

    def _invalidate_user_name_cache(self, user_id):
        """Forget any name cached for a user.

        Called whenever their name changes (or they're deleted), so the
        next frame that asks for it re-queries instead of showing a stale
        name.
        """
        self._user_name_cache.pop(user_id, None)


    def init_users_database(self):
        """Show the users screen: add, rename, photograph or delete players."""
        self.sync_screen_size()
        return screen_users.run(self)

    def init_face_capture_models(self):
        """Load the segmentation and face detection models once, on first use.

        They take a moment to load, so this is deliberately not done at
        startup - most sessions never open the picture screen.
        """
        if not hasattr(self, "face_capture_models"):
            self.face_capture_models = initialize_face_capture()
        return self.face_capture_models

    def get_prompt_background(self):
        """Background used by the prompt and picture screens."""
        if not hasattr(self, "prompt_bg_image"):
            self.prompt_bg_image = pygame.image.load(
                f"{CWD}/resources/images/credits_bg.png"
            ).convert()
        return self.prompt_bg_image

    def draw_prompt_screen(self, title, lines):
        """Draw a centred prompt on the game canvas."""
        self.blit_background(self.get_prompt_background())

        font = ui.font(self.font_path, 40)
        text = font.render(title, True, (255, 255, 255), (0, 0, 0))
        self.screen.blit(
            text,
            (
                self.screen.get_width() // 2 - text.get_width() // 2,
                self.screen.get_height() // 2 - 140,
            ),
        )

        font = ui.font(self.font_path, 24)
        for line_number, line in enumerate(lines):
            hint = font.render(line, True, (255, 255, 255), (0, 0, 0))
            self.screen.blit(
                hint,
                (
                    self.screen.get_width() // 2 - hint.get_width() // 2,
                    self.screen.get_height() // 2 - 50 + line_number * 45,
                ),
            )

    def init_leaderboards(self):
        """Show the best score each user has recorded, one game at a time."""
        self.sync_screen_size()
        return screen_leaderboards.run(self)

    def current_player_id(self, slot=0):
        """The user id playing in a slot, or None if there isn't one."""
        players = getattr(self, "active_players", [])
        return players[slot] if slot < len(players) else None

    def player_label(self, slot=0):
        """The name to show for a slot.

        Falls back to a generic label if the user was deleted mid-session, so
        a scoreboard never ends up blank.
        """
        return self.get_user_name(self.current_player_id(slot)) or f"Player {slot + 1}"

    def player_face_or_none(self, user_id):
        """A user's face surface, or None if they have no picture."""
        try:
            return self.get_user_face_surface(user_id)
        except (pygame.error, ValueError):
            return None

    def select_players(self, game_title, slot_labels):
        """Let the player(s) choose who is playing before a game starts.

        Defaults to whoever played last, so an unchanged line-up is a single
        ENTER. Returns a list of user ids, or None if cancelled.
        """
        users = self.get_users()
        if not users:
            return None

        user_ids = [user_id for user_id, _ in users]
        slot_count = len(slot_labels)

        # Start from the remembered picks, falling back to the first users
        chosen = []
        for slot in range(slot_count):
            remembered = self.settings.get(f"player_{slot + 1}_id", 0)
            if remembered in user_ids and remembered not in chosen:
                chosen.append(remembered)
            else:
                chosen.append(None)

        # Fill any empty slot with a user not already picked
        for slot in range(slot_count):
            if chosen[slot] is None:
                spare = next((uid for uid in user_ids if uid not in chosen), user_ids[0])
                chosen[slot] = spare

        active_slot = 0

        def step(slot, direction):
            """Move a slot to the next user, skipping anyone already picked."""
            index = user_ids.index(chosen[slot])
            for _ in range(len(user_ids)):
                index = (index + direction) % len(user_ids)
                candidate = user_ids[index]
                if candidate not in chosen or candidate == chosen[slot]:
                    chosen[slot] = candidate
                    return

        while True:
            for event in self.pump_events():
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        return None

                    if event.key == pygame.K_RETURN:
                        for slot in range(slot_count):
                            self.change_setting(f"player_{slot + 1}_id", chosen[slot])
                        return chosen

                    if event.key == pygame.K_DOWN:
                        active_slot = (active_slot + 1) % slot_count
                    elif event.key == pygame.K_UP:
                        active_slot = (active_slot - 1) % slot_count
                    elif event.key == pygame.K_RIGHT:
                        step(active_slot, 1)
                    elif event.key == pygame.K_LEFT:
                        step(active_slot, -1)

            self._draw_player_picker(game_title, slot_labels, chosen, active_slot)
            self.clock.tick(60)

    def draw_game_over(self, background, headline, entries, hint, headline_color=None):
        """Draw the end-of-round panel shared by all three games.

        `entries` is one dict per player - {"user_id", "name", "score",
        "note"} - so the one-player games and Pong's two sides use the same
        panel rather than each laying its own text out by hand.
        """
        surface = self.screen
        width, height = surface.get_size()

        self.blit_background(background)
        ui.dim_screen(surface, 178)

        pad = ui.cqw(2.4, width)
        headline_size = ui.cqw(3.2, width)
        face_size = ui.cqw(9.0, width)
        name_size = ui.cqw(1.6, width)
        score_size = ui.cqw(3.6, width)
        note_size = ui.cqw(1.4, width)
        gap = ui.cqw(1.0, width)

        panel_width = int(width * (0.46 if len(entries) == 1 else 0.66))
        panel_height = (
            pad * 2 + headline_size + gap + face_size + gap + name_size + gap
            + score_size + gap + note_size
        )
        panel = pygame.Rect(0, 0, panel_width, panel_height)
        panel.center = (width // 2, height // 2)
        ui.draw_panel(surface, panel, border_color=(210, 205, 225), fill_alpha=224)

        ui.draw_text(
            surface,
            headline,
            self.font_path,
            headline_size,
            color=headline_color or ui.PINK,
            midtop=(panel.centerx, panel.top + pad),
            letter_spacing=ui.cqw(0.12, width),
        )

        column = panel_width // len(entries)
        for index, entry in enumerate(entries):
            centre_x = panel.left + column * index + column // 2
            top = panel.top + pad + headline_size + gap

            face_rect = pygame.Rect(0, 0, face_size, face_size)
            face_rect.midtop = (centre_x, top)
            ui.draw_face(surface, self.player_face_or_none(entry["user_id"]), face_rect)

            ui.draw_text(
                surface,
                ui.truncate(entry["name"].upper(), 16),
                self.font_path,
                name_size,
                color=ui.INK,
                midtop=(centre_x, face_rect.bottom + gap),
                letter_spacing=ui.cqw(0.06, width),
            )
            ui.draw_text(
                surface,
                str(entry["score"]),
                self.font_path,
                score_size,
                color=entry.get("score_color", ui.INK),
                midtop=(centre_x, face_rect.bottom + gap * 2 + name_size),
            )
            if entry.get("note"):
                ui.draw_text(
                    surface,
                    entry["note"],
                    self.font_path,
                    note_size,
                    color=ui.SUN,
                    midtop=(centre_x, face_rect.bottom + gap * 3 + name_size + score_size),
                    letter_spacing=ui.cqw(0.06, width),
                )

        ui.draw_hint(surface, hint, self.font_path)
        self.draw_fps()
        self.present()

    def personal_best_note(self, score, previous_best):
        """The line under a score: whether it beat the player's own record."""
        if previous_best is None:
            return "FIRST SCORE!"
        if score > previous_best:
            return "NEW PERSONAL BEST!"
        return f"BEST {previous_best}"

    def _draw_player_picker(self, game_title, slot_labels, chosen, active_slot):
        """Draw the picker: one boxed slot per player, side by side.

        The slots are equal width whatever the names are, so a long name
        can't make one side of a two-player game bigger than the other.
        """
        surface = self.screen
        width, height = surface.get_size()

        self.blit_background(self.get_prompt_background())
        ui.dim_screen(surface)
        ui.draw_title(surface, game_title.upper(), self.font_path)

        slot_count = len(slot_labels)
        band = int(width * (0.66 if slot_count > 1 else 0.34))
        gap = ui.cqw(4.0, width)
        slot_width = (band - gap * (slot_count - 1)) // slot_count
        left = (width - band) // 2

        pad = ui.cqw(1.6, width)
        side_size = ui.cqw(1.25, width)
        face_size = ui.cqw(11.0, width)
        name_size = ui.cqw(1.8, width)
        inner_gap = ui.cqw(0.8, width)
        slot_height = pad * 2 + side_size + face_size + name_size + inner_gap * 2
        top = int(height * 0.52) - slot_height // 2

        for slot, label in enumerate(slot_labels):
            selected = slot == active_slot
            color = ui.SUN if selected else ui.INK
            rect = pygame.Rect(left + slot * (slot_width + gap), top, slot_width, slot_height)

            if selected:
                ui.draw_glow(surface, rect)
            ui.draw_panel(surface, rect, selected=selected)

            ui.draw_text(
                surface,
                ui.truncate(label.upper(), 26),
                self.font_path,
                side_size,
                color=(190, 182, 205),
                midtop=(rect.centerx, rect.top + pad),
                letter_spacing=ui.cqw(0.08, width),
            )

            face_rect = pygame.Rect(0, 0, face_size, face_size)
            face_rect.midtop = (rect.centerx, rect.top + pad + side_size + inner_gap)
            ui.draw_face(surface, self.player_face_or_none(chosen[slot]), face_rect)

            name = self.get_user_name(chosen[slot]) or "-"
            name_y = face_rect.bottom + inner_gap
            ui.draw_text(
                surface,
                ui.truncate(name.upper(), 13),
                self.font_path,
                name_size,
                color=color,
                midtop=(rect.centerx, name_y),
            )
            arrow_color = color if selected else (120, 115, 132)
            ui.draw_text(
                surface, "<", self.font_path, name_size, color=arrow_color,
                topleft=(rect.left + pad, name_y),
            )
            ui.draw_text(
                surface, ">", self.font_path, name_size, color=arrow_color,
                midright=(rect.right - pad, name_y + name_size // 2),
            )

        hints = ["LEFT / RIGHT TO CHOOSE"]
        if slot_count > 1:
            hints.append("UP / DOWN TO SWITCH")
        hints.append("ENTER TO START")
        hints.append("ESC TO GO BACK")
        ui.draw_hint(surface, "  ·  ".join(hints), self.font_path)

        self.present()

    def prompt_text(self, title, initial="", lines=(), max_length=30):
        """Ask for a line of text on the canvas.

        Returns the trimmed text, or None if the player cancelled. Typing is
        handled here rather than with a menu widget so the prompt can be
        opened from inside a running menu without nesting a second menu loop.
        """
        text = initial

        while True:
            for event in self.pump_events():
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        return None

                    if event.key == pygame.K_RETURN:
                        return text.strip()

                    if event.key == pygame.K_BACKSPACE:
                        text = text[:-1]
                    elif (
                        event.unicode
                        and event.unicode.isprintable()
                        and len(text) < max_length
                    ):
                        text += event.unicode

            self.draw_prompt_screen(title, list(lines))

            # The typed name, with a blinking caret
            caret = "_" if (pygame.time.get_ticks() // 400) % 2 == 0 else " "
            font = ui.font(self.font_path, 32)
            typed = font.render(text + caret, True, (255, 255, 255), (0, 0, 0))
            self.screen.blit(
                typed,
                (
                    self.screen.get_width() // 2 - typed.get_width() // 2,
                    self.screen.get_height() // 2 + 90,
                ),
            )

            self.present()
            self.clock.tick(60)

    def ask_yes_no(self, question, lines=()):
        """Ask a yes/no question on the canvas. Returns True for yes."""
        while True:
            for event in self.pump_events():
                if event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_y, pygame.K_RETURN):
                        return True
                    if event.key in (pygame.K_n, pygame.K_ESCAPE):
                        return False

            self.draw_prompt_screen(
                question, list(lines) + ["", "Y or ENTER for yes, N or ESC for no"]
            )
            self.present()
            self.clock.tick(60)

    def capture_user_face(self, user_id, user_name):
        """Show a live cutout preview and store it when the player confirms.

        Returns True if a picture was saved.
        """
        if not self.cap.isOpened():
            self.ask_yes_no(
                "No camera available",
                ("A picture can't be taken without a working camera",),
            )
            return False

        segmentor, face_cascade = self.init_face_capture_models()

        # Checkerboard so the transparent areas are obvious in the preview
        preview_size = CUTOUT_SIZE * 2
        board = pygame.Surface((preview_size, preview_size))
        tile = 24
        for row in range(0, preview_size, tile):
            for col in range(0, preview_size, tile):
                shade = 90 if (row // tile + col // tile) % 2 == 0 else 130
                board.fill((shade, shade, shade), (col, row, tile, tile))

        # Nothing to save until the first frame has been through the cutout
        cutout = None
        no_subject = False

        while True:
            for event in self.pump_events():
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        return False

                    if event.key in (pygame.K_SPACE, pygame.K_RETURN):
                        if cutout is None or cutout_coverage(cutout) < MIN_COVERAGE:
                            # Saving now would store a fully transparent
                            # picture that shows up as nothing later on
                            no_subject = True
                            continue
                        png_bytes = encode_png(cutout)
                        if png_bytes:
                            self.set_user_face(user_id, png_bytes)
                            return True
                        return False

            read_ok, frame = self.cap.read()
            if not read_ok or frame is None:
                self.clock.tick(60)
                continue

            frame = cv2.flip(frame, 1)
            cutout = capture_face_cutout(frame, segmentor, face_cascade)

            # BGRA from OpenCV, so swap to RGBA for pygame
            rgba = cv2.cvtColor(cutout, cv2.COLOR_BGRA2RGBA)
            face_surface = pygame.image.frombuffer(
                rgba.tobytes(), (cutout.shape[1], cutout.shape[0]), "RGBA"
            )
            face_surface = pygame.transform.scale(
                face_surface, (preview_size, preview_size)
            )

            self.blit_background(self.get_prompt_background())

            font = ui.font(self.font_path, 40)
            text = font.render(
                f"Photo for {user_name}", True, (255, 255, 255), (0, 0, 0)
            )
            self.screen.blit(
                text, (self.screen.get_width() // 2 - text.get_width() // 2, 90)
            )

            preview_x = self.screen.get_width() // 2 - preview_size // 2
            preview_y = self.screen.get_height() // 2 - preview_size // 2
            self.screen.blit(board, (preview_x, preview_y))
            self.screen.blit(face_surface, (preview_x, preview_y))
            pygame.draw.rect(
                self.screen,
                (255, 255, 255),
                (preview_x, preview_y, preview_size, preview_size),
                3,
            )

            font = ui.font(self.font_path, 24)
            enough_subject = cutout_coverage(cutout) >= MIN_COVERAGE
            if no_subject and not enough_subject:
                status = "Nobody detected - step into view"
            elif enough_subject:
                status = "SPACE or ENTER to save, ESC to cancel"
            else:
                status = "Step into view to take a photo"

            for line_number, line in enumerate(
                ("The chequered area is transparent", status)
            ):
                hint = font.render(line, True, (255, 255, 255), (0, 0, 0))
                self.screen.blit(
                    hint,
                    (
                        self.screen.get_width() // 2 - hint.get_width() // 2,
                        preview_y + preview_size + 40 + line_number * 45,
                    ),
                )

            self.present()
            self.clock.tick(60)

    def init_camera(self):
        # Initialize the camera
        stream = cv2.VideoCapture(self.user_camera_number)

        # Check if the camera is opened
        if not stream.isOpened():
            print("Trying alternate camera index 1")
            stream = cv2.VideoCapture(1)
            if not stream.isOpened():
                print("Trying alternate camera index 2")
                stream = cv2.VideoCapture(2)
            if not stream.isOpened():
                print("WARNING: Could not open any camera. Some features may not work properly.")

        # MJPG lets the camera compress each frame on-device before
        # sending it, instead of streaming raw YUYV - this webcam is
        # already known to be bandwidth-limited (see the resolution
        # comment below: it can't sustain more than ~10 FPS at 720p in
        # its default format), and MJPG needs far less USB bandwidth per
        # frame at the same resolution/rate. Must be set before
        # resolution/FPS below - some backends silently ignore it if set
        # after. Verified via a readback rather than trusting the set()
        # call's own return value (the lesson the buffer-size regression
        # taught this session, see docs/PERFORMANCE_AUDIT.md) - but a
        # readback only proves the driver *accepted* the request, not
        # that it actually improved real delivered framerate. This needs
        # the same real-hardware confirmation that earlier regression did
        # before being trusted.
        mjpg = cv2.VideoWriter_fourcc(*"MJPG")
        stream.set(cv2.CAP_PROP_FOURCC, mjpg)
        if int(stream.get(cv2.CAP_PROP_FOURCC)) != mjpg:
            print("NOTE: camera did not accept MJPG capture format, staying on its default")

        # Set the camera resolution. Requesting the full screen resolution
        # made the webcam negotiate 1280x720, which it can only deliver at
        # ~10 FPS in its default (YUYV) format - that capped every game's
        # loop before ThreadedCapture existed, since each frame used to
        # block on cap.read() directly. 640x480 was measured to hold ~30 FPS
        # in that same default format, and is still more detail than the
        # tracking (which downscales anyway) needs. Whether this specific
        # camera can actually sustain 60 FPS at 640x480 - with MJPG, without
        # it, or at all - hasn't been measured on real hardware; asking for
        # TARGET_FPS below is a request, not a guarantee, which is exactly
        # why ThreadedCapture exists: the game loop no longer depends on the
        # camera actually delivering whatever rate is requested here.
        stream.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_CAPTURE_WIDTH)
        stream.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_CAPTURE_HEIGHT)

        # Set the camera frame rate
        stream.set(cv2.CAP_PROP_FPS, TARGET_FPS)

        # Wrap in a background-thread reader so every game loop's
        # self.cap.read() never blocks on the camera's own capture
        # cadence (see gui/camera_stream.py) - every existing call site
        # (capture_scaled_frame, Runner's own direct read, quit_app's
        # release, test fixtures that substitute self.cap wholesale)
        # keeps working unchanged, since this matches cv2.VideoCapture's
        # own interface exactly.
        self.cap = ThreadedCapture(stream)

        # Initialize the camera image
        self.camera_image = None

    def blit_background(self, surface):
        """Draw a background image so it exactly fills the window.

        Backgrounds used to be scaled against the window size measured once
        at startup and then centred on the screen. Any later resize left the
        stale surface offset (and cropped) - which happens routinely under
        Wayland, where the compositor resizes the window when the tiling
        layout changes or fullscreen is toggled. Scaling to the surface's
        current size keeps the background aligned whatever the window does.
        """
        if surface.get_size() != self.screen.get_size():
            surface = pygame.transform.scale(surface, self.screen.get_size())
        self.screen.blit(surface, (0, 0))

    def load_rgba_background(self, path):
        """Load a background PNG as an RGBA numpy array.

        Shared by Balloons and Pong, whose backgrounds are both drawn under
        a camera feed that needs the alpha channel (Runner's background has
        no such overlay, so it loads its own without one).
        """
        image = cv2.imread(path)
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        return cv2.cvtColor(image, cv2.COLOR_RGB2RGBA)

    def array_to_scaled_surface(self, image_array, mode="RGBA"):
        """Turn a raw (height, width, channels) array into a canvas-sized surface.

        Each game's background is built once from its own numpy array (this
        way) and then just blitted every frame after - nothing about it
        changes during a round, so redoing the conversion every frame would
        be pure repeated work for the same pixels.

        convert() is what makes that per-frame blit cheap, and it is not
        optional here: frombuffer produces a surface in the buffer's own
        format (with a per-pixel alpha channel, for the RGBA default), so
        blitting it onto the canvas meant translating every one of 1920x1080
        pixels into the canvas format AND alpha-blending them, every frame.
        Profiling the real Balloons loop on the target hardware measured
        that single background blit at 35ms of a 56ms frame - about 60% of
        the entire frame budget, and the reason the games ran at ~18 FPS
        while Credits (whose background was already convert()ed, see
        get_prompt_background) sat at 60. Converted against self.screen
        rather than the display, since the canvas - not the window - is
        what these get blitted onto. The background is fully opaque
        (RGB2RGBA sets alpha to 255 everywhere), so dropping the alpha
        channel loses nothing; the camera feed drawn on top of it keeps its
        own alpha regardless.
        """
        surface = pygame.image.frombuffer(
            image_array.tobytes(),
            (image_array.shape[1], image_array.shape[0]),
            mode,
        )
        return pygame.transform.scale(surface, self.screen.get_size()).convert(self.screen)

    def capture_scaled_frame(self, ratio, flip=True):
        """Grab and process one camera frame, sized to 1/ratio of the canvas.

        Shared by Balloons and Pong, both at round start and in their game
        loop, so the capture pipeline (colour swap, flip, resize_cover) only
        has one copy to get right - a fix used to have to land in up to 4
        near-identical places, and once already didn't (round start was
        missing the flip the loop applied).

        Returns None on a failed read - a transient camera hiccup - rather
        than raising, so callers can fall back to a blank placeholder (round
        start) or simply keep whatever frame they already have (every frame
        after).
        """
        read_ok, frame = self.cap.read()
        if not read_ok or frame is None:
            return None

        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        if flip:
            frame = cv2.flip(frame, 1)

        return resize_cover(
            frame,
            int(self.user_screen_width // ratio),
            int(self.user_screen_height // ratio),
        )

    def present(self):
        """Scale the game canvas onto the window and show the frame.

        Called instead of pygame.display.flip() by every in-game screen. The
        canvas keeps its fixed size while this fits it to whatever the window
        currently is, so a resize mid-round is picked up on the very next
        frame without any layout being recomputed. The aspect ratio is
        preserved (letterboxed rather than stretched) so the ball stays round
        and the sprites keep their proportions.
        """
        window_width, window_height = self.window.get_size()
        canvas_width, canvas_height = self.screen.get_size()

        scale = min(window_width / canvas_width, window_height / canvas_height)
        target = (max(1, int(canvas_width * scale)), max(1, int(canvas_height * scale)))
        offset = ((window_width - target[0]) // 2, (window_height - target[1]) // 2)

        # A window that already matches the canvas 1:1 (the common case - a
        # fullscreen window on a 1080p display, since GAME_CANVAS_SIZE is
        # 1920x1080) needs no resampling at all. transform.scale() always
        # allocates and resamples a brand-new ~8MB surface even for a same-
        # size copy, so skipping it here saves that cost every single frame.
        if target == (canvas_width, canvas_height):
            frame = self.screen
        else:
            # Nearest-neighbour keeps the pixel art crisp
            frame = pygame.transform.scale(self.screen, target)

        # Only clear to black when the scaled frame doesn't fill the window
        # exactly - otherwise the blit below overwrites every pixel anyway,
        # and there's no letterbox bar left showing from a previous frame.
        if target != (window_width, window_height):
            self.window.fill((0, 0, 0))
        self.window.blit(frame, offset)
        pygame.display.flip()

    def camera_surface(self, size=None):
        """One camera frame as a pygame surface, mirrored, or None.

        Mirrored because every screen showing it is showing the player
        themselves, and an unmirrored feed makes reaching left move right.
        """
        if not getattr(self, "cap", None) or not self.cap.isOpened():
            return None

        read_ok, frame = self.cap.read()
        if not read_ok or frame is None:
            return None

        frame = cv2.cvtColor(cv2.flip(frame, 1), cv2.COLOR_BGR2RGB)
        if size is not None:
            frame = cv2.resize(frame, size)
        return pygame.image.frombuffer(
            frame.tobytes(), (frame.shape[1], frame.shape[0]), "RGB"
        )

    def camera_feed_rect(self):
        """Where the camera feed belongs on the canvas.

        The games position it in their background image's 1280x720 space, so
        it has to be scaled up to the canvas the same way the background is.
        Computed once at round start (init_balloons_game/init_pong_game) and
        cached as self._camera_feed_rect, since none of its inputs
        (start_x_cam, scale_x_cam, etc.) change mid-round - this used to
        redo the same arithmetic and Rect allocation on every call instead.
        """
        return self._camera_feed_rect

    def camera_feed_surface(self):
        """`self.camera_image` as a pygame surface, whatever its channels."""
        image = self.camera_image
        if image is None:
            return None
        mode = "RGBA" if image.shape[2] == 4 else "RGB"
        return pygame.image.frombuffer(
            image.tobytes(), (image.shape[1], image.shape[0]), mode
        )

    def draw_camera_feed(self, tag=None):
        """Draw the feed straight onto the canvas, in the shared frame.

        It used to be pasted into the background array after having its
        corners rounded. The rounding produces a transparent RGBA cutout and
        the paste was a plain assignment, so the corners landed as opaque
        black - and the whole feed was then upscaled 1.5x with the
        background, which softened it. Drawing it here does neither.
        """
        return screen_ingame.draw_viewport(
            self, self.camera_feed_rect(), self.camera_feed_surface(), tag
        )

    def canvas_placement(self):
        """Where the canvas lands in the window: (left, top, scale)."""
        window_width, window_height = self.window.get_size()
        canvas_width, canvas_height = self.screen.get_size()

        scale = min(window_width / canvas_width, window_height / canvas_height)
        left = (window_width - canvas_width * scale) / 2
        top = (window_height - canvas_height * scale) / 2
        return left, top, scale

    def window_to_canvas(self, position):
        """Map a window coordinate (a mouse position) back onto the canvas.

        Returns None for a point in the letterbox bars, where there is
        nothing to click.
        """
        left, top, scale = self.canvas_placement()
        x = (position[0] - left) / scale
        y = (position[1] - top) / scale

        if not (0 <= x < self.screen.get_width() and 0 <= y < self.screen.get_height()):
            return None
        return int(x), int(y)

    def sync_screen_size(self):
        """Pick up a window resize before showing a screen.

        Screens draw to the fixed-size canvas and `present` fits it to the
        window every frame, so nothing has to be re-laid out here - this only
        keeps the recorded window size current for anything that reads it.
        """
        width, height = self.window.get_size()
        if (width, height) == (self.window_width, self.window_height):
            return False

        self.window_width, self.window_height = width, height
        return True

    def show_camera_required(self, game_name):
        """Explain that a camera is needed and return to the main menu."""
        return screen_ingame.show_no_camera(self, game_name)

    def init_finger_detection(self):
        # Initialize the HandDetector object
        self.finger_detector = initialize_hand_detector()

    def init_hand_tracking(self):
        # Initialize the HandDetector object
        self.hand_tracking = HandTrackingDynamic()

    def init_pose_detection(self):
        # Initialize the PoseDetector object (jump/duck detection for Runner)
        self.pose_detector = initialize_pose_detector()

    def run(self):
        """The app loop: show the menu, run whatever it returns, repeat.

        Every screen returns here when it is done rather than calling back
        into the menu. The menu used to invoke a game directly and the game
        re-entered the menu on the way out, so each round trip left two stack
        frames behind and a long session eventually overflowed.
        """
        actions = {
            "balloons": self.init_balloons_game,
            "pong": self.init_pong_game,
            "runner": self.init_runner_game,
            "users": self.init_users_database,
            "scores": self.init_leaderboards,
            "settings": self.init_settings,
            "credits": self.init_credits,
        }

        if not self.settings.get("privacy_notice_seen"):
            screen_ingame.show_privacy_notice(self)
            self.settings["privacy_notice_seen"] = True
            self.save_settings()

        while True:
            action = self.start_main_menu()
            if action == "quit":
                break
            handler = actions.get(action)
            if handler is not None:
                handler()

        self.quit_app()

    def start_main_menu(self):
        """Show the main menu and return the action the player chose."""
        self.sync_screen_size()

        mixer.music.load(f"{CWD}/resources/sounds/main_menu_bg_music.ogg")
        mixer.music.set_volume(self.music_volume)
        mixer.music.play(-1)

        return screen_menu.run(self)

    def init_credits(self):
        """Show the credits."""
        self.sync_screen_size()
        return screen_credits.run(self)

    def init_balloons_game(self):
        self.sync_screen_size()

        # Balloons is played entirely with hand tracking
        if not self.cap.isOpened():
            return self.show_camera_required("Balloons")

        players = self.select_players("BALLOONS", ("Player",))
        if players is None:
            return
        self.active_players = players

        if not screen_ingame.show_instructions(
            self, "balloons", waves=self.settings["balloons_waves"]
        ):
            return

        # Set the background music for the main menu
        mixer.music.load(f"{CWD}/resources/sounds/balloon_game_bg_music.ogg")
        mixer.music.set_volume(self.music_volume)

        # Play the background music
        mixer.music.play(-1)

        # Sounds, background and pin image are fixed for the whole process -
        # loaded from disk once, ever, rather than on every trip back to the
        # main menu and into Balloons again (previously every re-entry paid
        # a real disk-read + decode hit right as the player expected the
        # game to start). Only per-round randomized state (the wave tables,
        # built further down) needs to happen on every entry.
        if not hasattr(self, "balloon_popping_sounds"):
            self.balloon_popping_sounds = [
                mixer.Sound(f"{CWD}/resources/sounds/balloon-pop-1.ogg"),
                mixer.Sound(f"{CWD}/resources/sounds/balloon-pop-2.ogg"),
                mixer.Sound(f"{CWD}/resources/sounds/balloon-pop-3.ogg"),
                mixer.Sound(f"{CWD}/resources/sounds/balloon-pop-4.ogg"),
                mixer.Sound(f"{CWD}/resources/sounds/balloon-pop-5.ogg"),
                mixer.Sound(f"{CWD}/resources/sounds/balloon-pop-6.ogg"),
                mixer.Sound(f"{CWD}/resources/sounds/balloon-pop-7.ogg"),
                mixer.Sound(f"{CWD}/resources/sounds/balloon-pop-8.ogg"),
                mixer.Sound(f"{CWD}/resources/sounds/balloon-pop-9.ogg"),
                mixer.Sound(f"{CWD}/resources/sounds/balloon-pop-10.ogg"),
            ]
            self.balloon_game_over_sound = mixer.Sound(
                f"{CWD}/resources/sounds/game-over.ogg"
            )
            self.balloon_popping_fill_sounds = mixer.Sound(
                f"{CWD}/resources/sounds/balloon-inflation.ogg"
            )

            # Initialize the background image for the Balloons game. Built
            # once ever into the surface actually drawn every frame -
            # nothing about it changes between rounds, so redoing this
            # conversion on every menu round-trip would just repeat the
            # same work for identical output. The raw decoded array is a
            # local variable, not kept on self - only its (small, cheap to
            # keep) native size is, since array_to_scaled_surface's output
            # is scaled to the canvas and no longer has the original
            # dimensions the camera-box geometry below is computed against.
            balloons_game_bg_image = self.load_rgba_background(
                f"{CWD}/resources/images/balloons_game_bg.png"
            )
            self.balloons_game_bg_native_size = (
                balloons_game_bg_image.shape[1],
                balloons_game_bg_image.shape[0],
            )
            self.balloons_game_bg_image_pygame = self.array_to_scaled_surface(
                balloons_game_bg_image
            )

            # Initialize the pin image. convert_alpha() matches the pixel
            # format SDL actually renders in, so every blit is a fast
            # same-format copy instead of a slow per-pixel format
            # translation.
            self.pin_image = pygame.image.load(
                f"{CWD}/resources/images/pin.png"
            ).convert_alpha()

            # Make the pin image smaller
            self.pin_image = pygame.transform.scale(self.pin_image, (70, 70))

        # Volume always reflects the current setting, even though the Sound
        # objects above are only loaded from disk once - sfx_volume() is
        # re-applied here every entry, same as before this change.
        for sound in self.balloon_popping_sounds:
            sound.set_volume(self.sfx_volume(0.2))
        self.balloon_game_over_sound.set_volume(self.sfx_volume(0.5))
        self.balloon_popping_fill_sounds.set_volume(self.sfx_volume(0.2))

        # Initialize the balloons list
        self.balloons = []

        # Initialize the Balloons game screen ratio. The box this ends up in
        # (camera_feed_rect) is sized from these exact dimensions, so
        # changing the ratio changes the box.
        #
        # 3.0 specifically: it makes the resulting frame (1920//3.0,
        # 1080//3.0) = (640, 360) fit entirely within the native
        # CAMERA_CAPTURE_WIDTH/HEIGHT (640x480) capture - resize_cover then
        # needs a pure centre-crop with no upscaling at all, instead of the
        # old ratio (2.5 -> 768x432) which was wider than the native
        # capture and forced an upscale-then-crop before every hand-tracking
        # call. Shrinks the on-screen camera box by ~17%.
        self.balloon_screen_ratio = 3.0

        # Take an initial camera image. A blank placeholder stands in until
        # the real feed arrives on the first loop iteration below -
        # including when the read fails outright (camera still warming up,
        # or genuinely unavailable) - so this always has a real array of the
        # right shape to work with instead of crashing on None.
        frame = self.capture_scaled_frame(self.balloon_screen_ratio)
        self.camera_image = (
            frame
            if frame is not None
            else np.zeros(
                (
                    int(self.user_screen_height // self.balloon_screen_ratio),
                    int(self.user_screen_width // self.balloon_screen_ratio),
                    3,
                ),
                dtype=np.uint8,
            )
        )

        # A blank placeholder until the first frame arrives
        self.camera_image[:, :] = 0

        # Get the camera image dimensions and the background image dimensions.
        # bg_width/bg_height come from the cached native size, not the
        # (no-longer-kept) raw array or the cached pygame surface - that
        # surface is scaled to the canvas, not the background art's own
        # 1280x720 space this geometry is computed in.
        bg_width, bg_height = self.balloons_game_bg_native_size
        image_height, image_width, _ = self.camera_image.shape

        # Calculate the top-left coordinates for the camera image
        top_left_x = (bg_width - image_width) // 2
        top_left_y = (bg_height - image_height) // 2

        # Calculate the start and end coordinates for the camera image
        self.start_x_cam = top_left_x
        self.start_y_cam = top_left_y + 50
        self.end_x_cam = top_left_x + image_width
        self.end_y_cam = top_left_y + image_height + 50

        # Initialize the scale value for x and y
        self.scale_x_cam = self.user_screen_width / bg_width
        self.scale_y_cam = self.user_screen_height / bg_height

        # Initialize the translate value for x and y
        self.translation_x_cam = int(self.start_x_cam * self.scale_x_cam)
        self.translation_y_cam = int(self.start_y_cam * self.scale_y_cam)

        # Where the camera feed belongs on the canvas - computed once here
        # since none of its inputs change mid-round, instead of every call
        # to camera_feed_rect() (up to twice/frame in this game's HUD/feed
        # draw calls).
        self._camera_feed_rect = pygame.Rect(
            int(self.start_x_cam * self.scale_x_cam),
            int(self.start_y_cam * self.scale_y_cam),
            int((self.end_x_cam - self.start_x_cam) * self.scale_x_cam),
            int((self.end_y_cam - self.start_y_cam) * self.scale_y_cam),
        )

        # Initialize the score
        self.balloons_score = 0

        # A personal best can't change mid-round (only recorded at the end
        # of one), so it's fetched once here instead of on every HUD frame.
        self.balloons_best_score = self.get_best_score(self.current_player_id(0), "balloons")

        # Initialize the wave
        self.balloons_wave = 1

        # Initialize the max number of waves
        self.max_balloons_waves = self.settings["balloons_waves"]

        # Initialize the max wave time
        self.max_wave_time = 20

        # Initialize the wave wait time
        self.balloon_wave_wait_time = 3
        # The rules used to share this screen, so wave one waited long enough
        # to read them. They have their own screen now.
        self.balloon_first_wave_wait_time = 4

        # Initialize the balloons
        self.init_balloons()

        # Start the Balloons game timer
        self.start_balloons_game_timer()

    def init_balloons(self):
        # Initialize the normal balloon image paths
        normal_balloon_image_paths = [
            f"{CWD}/resources/images/balloon-red.png",
            f"{CWD}/resources/images/balloon-green.png",
            f"{CWD}/resources/images/balloon-blue.png",
            f"{CWD}/resources/images/balloon-yellow.png",
            f"{CWD}/resources/images/balloon-purple.png",
            f"{CWD}/resources/images/balloon-orange.png",
            f"{CWD}/resources/images/balloon-gray.png",
        ]

        # Initialize the combo balloon image paths
        combo_balloon_image_paths = [
            f"{CWD}/resources/images/balloon-combo-1.png",
            f"{CWD}/resources/images/balloon-combo-2.png",
            f"{CWD}/resources/images/balloon-combo-3.png",
        ]

        # Initialize the balloons waves configurations
        ballons_number_per_wave = [
            [5, 15],
            [15, 25],
            [25, 35],
            [35, 45],
            [45, 55],
        ]

        ballons_combo_probability_per_wave = [0.2, 0.15, 0.1, 0.05, 0.03]

        normal_ballons_speed_per_wave = [[2, 10], [4, 12], [6, 14], [8, 16], [10, 18]]

        combo_ballons_speed_per_wave = [
            [11, 15],
            [13, 17],
            [15, 19],
            [17, 21],
            [19, 23],
        ]

        # How strongly a wave's balloons cluster into its first half
        # (biased_random_int's bias_strength - higher means more clustered).
        # Early waves are small enough that a front-loaded "arrival flurry"
        # never gets dense; later waves have 3-4x as many balloons, so the
        # same strong bias piles them into a burst instead - tapering it down
        # spreads the higher-count waves closer to evenly across the wave's
        # full duration while keeping the flurry feel where it doesn't hurt.
        apperance_time_bias_per_wave = [10, 8, 6, 4, 3]

        self.waves_balloons = []

        # Every balloon instance across every wave picks from the same 10
        # source files - loaded and scaled once each here, rather than
        # freshly from disk for every single instance (up to ~275 of them
        # at the hardest difficulty). Safe to share one Surface across many
        # balloons: it's only ever blitted, never mutated per-instance.
        balloon_images = {}

        def scaled_balloon_image(path):
            if path not in balloon_images:
                # convert_alpha() matches SDL's actual rendering pixel format,
                # so the many per-frame blits of this cached, reused surface
                # are a fast same-format copy instead of a slow per-pixel
                # format translation - paid once here, not once per blit.
                balloon_images[path] = pygame.transform.scale(
                    pygame.image.load(path).convert_alpha(), (250, 250)
                )
            return balloon_images[path]

        for wave_number in range(self.max_balloons_waves):
            # The per-wave tables only describe the first few waves, so any
            # wave past the end of them reuses the hardest entry rather than
            # running off the end of the list
            wave_config = min(wave_number, len(ballons_number_per_wave) - 1)
            balloons = []
            for _ in range(
                random.randint(
                    ballons_number_per_wave[wave_config][0],
                    ballons_number_per_wave[wave_config][1],
                )
            ):
                is_combo = random_bool_by_chance(
                    ballons_combo_probability_per_wave[wave_config]
                )

                balloon_img_path = (
                    random.choice(combo_balloon_image_paths)
                    if is_combo
                    else random.choice(normal_balloon_image_paths)
                )
                balloon_img = scaled_balloon_image(balloon_img_path)
                balloon_rect = balloon_img.get_rect()

                # Randomize the balloon rect position. A finger position can
                # only ever land within the camera box's own footprint on
                # canvas (translation_x_cam to end_x_cam * scale_x_cam - the
                # same transform finger centers go through), so confining
                # the spawn range to exactly that footprint is what makes
                # every balloon poppable, instead of drawing from the
                # background art's raw, unscaled pixel space and ending up
                # partly outside where a finger can ever be detected.
                spawn_x = random.randint(
                    self.translation_x_cam, int(self.end_x_cam * self.scale_x_cam)
                )
                spawn_y = int(self.end_y_cam * self.scale_y_cam) + 100
                balloon_rect.update(
                    (
                        spawn_x,
                        spawn_y,
                        100,
                        100,
                    )
                )

                speed = max(1, round(self.difficulty_modifiers["balloon_speed"] * (
                    random.randint(
                        combo_ballons_speed_per_wave[wave_config][0],
                        combo_ballons_speed_per_wave[wave_config][1],
                    )
                    if is_combo
                    else random.randint(
                        normal_ballons_speed_per_wave[wave_config][0],
                        normal_ballons_speed_per_wave[wave_config][1],
                    )
                )))
                apperance_time = biased_random_int(
                    0,
                    self.max_wave_time,
                    (0, self.max_wave_time // 2),
                    apperance_time_bias_per_wave[wave_config],
                )
                balloon_type = (
                    0 if not is_combo else int(balloon_img_path.split(".")[-2][-1])
                )

                balloons.append(
                    {
                        "rect": balloon_rect,
                        "image": balloon_img,
                        "speed": speed,
                        "time": apperance_time,
                        "is_combo": is_combo,
                        "type": balloon_type,
                        "is_popped": False,
                    }
                )
            # Sorted once here rather than every frame of play: each
            # balloon's appearance time is fixed for the rest of the wave
            # the moment it's generated, so re-sorting during play would
            # only ever repeat the same result.
            balloons.sort(key=lambda x: x["time"])
            self.waves_balloons.append(balloons)

    def start_balloons_game_timer(self):
        """The get-ready beat before a wave.

        Wave one is a countdown on the artwork; later waves are a banner over
        the paused field carrying the score so far, so you know where you are
        without leaving the game.
        """
        if self.balloons_wave > self.max_balloons_waves:
            self.end_balloons_game()
            return

        start_time = time.time()
        self.balloon_popping_fill_sounds.play()

        first_wave = self.balloons_wave == 1
        total = (
            self.balloon_first_wave_wait_time if first_wave else self.balloon_wave_wait_time
        )

        while True:
            for event in self.pump_events():
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        return

            time_remaining = total - int(time.time() - start_time)

            if first_wave:
                screen_ingame.draw_countdown(
                    self,
                    "BALLOONS",
                    f"WAVE {self.balloons_wave}",
                    time_remaining,
                    total,
                    "HANDS UP, INSIDE THE FRAME",
                    viewport=screen_ingame.corner_viewport(self),
                )
            else:
                self.draw_balloons_field(camera_alpha=128)
                screen_ingame.draw_banner(
                    self,
                    f"WAVE {self.balloons_wave}",
                    f"{int(self.balloons_score)} POINTS SO FAR  -  STARTS IN {max(0, time_remaining)}",
                )
                self.draw_balloons_hud(time_left=None)
                self.present()

            self.clock.tick(60)

            if time_remaining <= 0:
                break

        time.sleep(1)

        # Start the Balloons game
        self.start_balloons_game()

    def draw_balloons_field(self, camera_alpha=255):
        """The backdrop and the camera feed the balloons are played over."""
        self.blit_background(self.balloons_game_bg_image_pygame)
        self.draw_camera_feed("YOU")
        if camera_alpha < 255:
            veil = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
            veil.fill((12, 5, 26, 255 - camera_alpha))
            self.screen.blit(veil, (0, 0))

    def draw_balloons_hud(self, time_left):
        """Title, plus score/best/wave/time flanking the camera feed.

        Four chips on top of a title all crowded the same strip along the
        top edge, so they sit either side of the feed instead - two per
        side, which is also why a fourth stat (personal best) joined score,
        wave and time: an odd one out would leave one column lopsided.
        """
        screen_ingame.draw_game_title(self, "balloons")

        feed = self.camera_feed_rect()
        gap = ui.cqw(1.2, self.screen.get_width())
        # Fetched once at round start (init_balloons_game) - a personal
        # best can't change mid-round, so this HUD doesn't re-query it.
        best = self.balloons_best_score

        screen_ingame.draw_stat_column(
            self,
            (
                ("SCORE", int(self.balloons_score), ui.SUN),
                ("BEST", "--" if best is None else best, ui.INK),
            ),
            x=feed.left - gap,
            align="right",
            center_y=feed.centery,
        )
        screen_ingame.draw_stat_column(
            self,
            (
                ("WAVE", f"{self.balloons_wave}/{self.max_balloons_waves}", ui.INK),
                ("LEFT", "--" if time_left is None else f"{max(0, time_left)}s", ui.WIRE),
            ),
            x=feed.right + gap,
            align="left",
            center_y=feed.centery,
        )

        # Top-left: the camera feed reaches the bottom-left corner here
        screen_ingame.draw_whoami(self, 0, best=best, corner="top-left")
        screen_ingame.draw_escape(self)
        self.draw_fps()

    def start_balloons_game(self):

        start_time = time.time()

        while True:
            for event in self.pump_events():
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        return

            # How far balloons should rise this frame, in real time rather
            # than a fixed amount per loop iteration.
            dt_scale = self.frame_dt_scale()

            # Take a camera image. A transient read failure (USB hiccup, the
            # camera briefly grabbed by another process) just keeps last
            # frame's picture on screen instead of crashing the round.
            frame = self.capture_scaled_frame(self.balloon_screen_ratio)
            if frame is not None:
                self.camera_image = frame

            # Get the right and left hand centers. self.camera_image is RGB
            # (capture_scaled_frame already converted it for display), but
            # cvzone's findHands (called inside detect_hands) converts
            # BGR->RGB internally, per its own "Finds hands in a BGR image"
            # contract - feeding it RGB directly converts it a second time and
            # hands mediapipe channel-swapped data, silently breaking
            # detection. Convert back to BGR first so it lands on true RGB
            # internally; detect_hands doesn't draw onto or return this image,
            # so there's nothing to convert back for display.
            bgr_for_tracking = cv2.cvtColor(self.camera_image, cv2.COLOR_RGB2BGR)
            hands_data = detect_hands(self.finger_detector, bgr_for_tracking)
            try:
                fingers_centers_right = hands_data["right_hand"]["fingers_centers"]
            except (KeyError, TypeError):
                fingers_centers_right = [(-1, -1) for _ in range(5)]

            try:
                fingers_centers_left = hands_data["left_hand"]["fingers_centers"]
            except (KeyError, TypeError):
                fingers_centers_left = [(-1, -1) for _ in range(5)]

            # Initialize the fingers centers rects
            fingers_centers_rects = []

            # Apply the transformations to the fingers centers and add them to the fingers centers rects
            for finger_center in fingers_centers_right:
                if finger_center == (-1, -1):
                    continue

                finger_center = (
                    int(finger_center[0] * self.scale_x_cam) + self.translation_x_cam,
                    int(finger_center[1] * self.scale_y_cam) + self.translation_y_cam,
                )

                fingers_centers_rects.append(
                    pygame.Rect(finger_center[0], finger_center[1], 20, 20)
                )

            for finger_center in fingers_centers_left:
                if finger_center == (-1, -1):
                    continue

                finger_center = (
                    int(finger_center[0] * self.scale_x_cam) + self.translation_x_cam,
                    int(finger_center[1] * self.scale_y_cam) + self.translation_y_cam,
                )

                fingers_centers_rects.append(
                    pygame.Rect(finger_center[0], finger_center[1], 20, 20)
                )

            # The feed is drawn over the background rather than into it, so
            # the balloons' coordinate space stays the plain background.
            # balloons_game_bg_image_pygame was already built once at init -
            # nothing about the background changes during a round.
            self.draw_balloons_field()

            # Draw the pins on the fingers centers
            for finger_rect in fingers_centers_rects:
                self.screen.blit(
                    self.pin_image,
                    (finger_rect.left - 40, finger_rect.top - 30),
                )

            elapsed_time = int(time.time() - start_time)

            # Get the current wave balloons. Already sorted by appearance
            # time once, when the wave was generated (init_balloons).
            balloons = self.waves_balloons[self.balloons_wave - 1]

            # Draw random balloons that move up the screen
            for balloon in balloons:
                # Skip the balloon if its appearance time has not come yet
                if elapsed_time < balloon["time"]:
                    continue

                if balloon["is_popped"]:
                    continue

                # Remove the balloon if it goes off the screen. rect.top is
                # in canvas space (see init_balloons), so the threshold has
                # to be translation_y_cam - the canvas-space version of
                # start_y_cam - not the raw bg-space value itself.
                if balloon["rect"].top <= self.translation_y_cam + balloon["rect"].height:

                    # Remove a point if the balloon is not a combo balloon
                    if not balloon["is_combo"]:
                        self.balloons_score = max(0, self.balloons_score - 1)

                    balloon["is_popped"] = True
                    random.choice(self.balloon_popping_sounds).play()
                    break

                # Move the balloon up the screen and draw it
                balloon["rect"].move_ip(0, -balloon["speed"] * dt_scale)
                self.screen.blit(
                    balloon["image"],
                    (balloon["rect"].left - 70, balloon["rect"].top - 40),
                )

                # Check if the balloon is popped by the fingers
                for finger_rect in fingers_centers_rects:
                    if balloon["rect"].colliderect(finger_rect):
                        # Not rounded per pop - base_points is 1 for the vast
                        # majority of balloons (plain, non-combo), and
                        # round(1 * 0.8/1.0/1.2) is 1 either way, making the
                        # multiplier a no-op for almost every pop. Kept as
                        # the exact float and only truncated for display/
                        # recording (see draw_balloons_hud, end_balloons_game)
                        # - the same way Runner's own score already works -
                        # so the difficulty difference actually accumulates
                        # over a wave instead of rounding itself away.
                        base_points = {1: 2, 2: 3, 3: 5}.get(balloon["type"], 1)
                        points = base_points * self.difficulty_modifiers["score_multiplier"]
                        self.balloons_score = max(0, self.balloons_score + points)

                        balloon["is_popped"] = True
                        random.choice(self.balloon_popping_sounds).play()
                        break

            # Check if the balloons are all popped or the wave time is over.
            # Balloons are never removed from the list - popping or
            # escaping only flips is_popped - so this has to check that
            # flag on every entry rather than the list's own length.
            if all(b["is_popped"] for b in balloons) or elapsed_time > self.max_wave_time:
                self.balloons_wave += 1
                self.start_balloons_game_timer()
                break

            # Drawn last, so a balloon cannot float over the score
            self.draw_balloons_hud(time_left=self.max_wave_time - elapsed_time)
            self.present()

            # Update the clock and delta time
            self.dt = self.clock.tick(60) / 1000

    def end_balloons_game(self):
        self.balloon_game_over_sound.play()

        # Finalized to a clean int here - same idiom as Runner's own score
        # (end_runner_game) - the running total stays an exact float during
        # play so difficulty differences actually accumulate instead of
        # rounding away pop by pop.
        self.balloons_score = max(0, int(self.balloons_score))

        player_id = self.current_player_id(0)
        previous_best = self.get_best_score(player_id, "balloons")
        self.record_score(player_id, "balloons", self.balloons_score)

        # Already built once at init - nothing about the background changes
        # between the last frame of play and this screen.
        background = self.balloons_game_bg_image_pygame

        entries = [
            {
                "user_id": player_id,
                "name": self.player_label(0),
                "score": self.balloons_score,
                "note": self.personal_best_note(self.balloons_score, previous_best),
            }
        ]

        while True:
            self.draw_game_over(
                background, "GAME OVER", entries, "ESC FOR THE MAIN MENU"
            )

            for event in self.pump_events():
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        return

            self.clock.tick(60)

    def init_pong_game(self):
        self.sync_screen_size()

        # Pong is played entirely with hand tracking
        if not self.cap.isOpened():
            return self.show_camera_required("Pong")

        # Pong is two-player, so it needs two users to attribute the sides to
        if len(self.get_users()) < 2:
            if self.ask_yes_no(
                "Pong needs two players",
                ("Only one user exists so far", "Add another one now?"),
            ):
                return self.init_users_database()
            return

        players = self.select_players(
            "PONG", ("Player 1 (left hand)", "Player 2 (right hand)")
        )
        if players is None:
            return
        self.active_players = players

        if not screen_ingame.show_instructions(
            self, "pong", points=self.settings["pong_points_to_win"]
        ):
            return

        # Set the background music for the main menu
        mixer.music.load(f"{CWD}/resources/sounds/pong_game_bg_music.ogg")
        mixer.music.set_volume(self.music_volume)

        # Play the background music
        mixer.music.play(-1)

        # Sounds and background are fixed for the whole process - loaded
        # from disk once, ever, rather than on every trip back to the main
        # menu and into Pong again. One flag gates both blocks below (rather
        # than each checking hasattr on its own first attribute) so they
        # can't drift out of sync with each other.
        first_pong_entry = not hasattr(self, "pong_game_bg_image_pygame")

        if first_pong_entry:
            # Built once into the surface actually drawn every frame -
            # nothing about it changes between rounds, so redoing this on
            # every menu round-trip would repeat the same work for
            # identical output. The raw decoded array is a local variable,
            # not kept on self - only its (small, cheap to keep) native
            # size is, since array_to_scaled_surface's output is scaled to
            # the canvas.
            pong_game_bg_image = self.load_rgba_background(
                f"{CWD}/resources/images/pong_game_bg.png"
            )
            self.pong_game_bg_native_size = (
                pong_game_bg_image.shape[1],
                pong_game_bg_image.shape[0],
            )
            self.pong_game_bg_image_pygame = self.array_to_scaled_surface(
                pong_game_bg_image
            )

        # Initialize the ball radius
        self.ball_raduis = 10

        # Initialize the ball speed, scaled by the difficulty setting
        base_ball_speed = max(
            1, round(7 * self.difficulty_modifiers["pong_speed"])
        )
        self.ball_speed_x = random.choice([-base_ball_speed, base_ball_speed])
        self.ball_speed_y = random.choice([-base_ball_speed, base_ball_speed])
        self.base_ball_speed = base_ball_speed

        # Initialize the paddle dimensions
        self.paddle_width = 10
        self.paddle_height = 80

        # Initialize the speed
        self.speed_increment_interval = 7
        self.speed_increment = 3

        # A rally that keeps escalating forever eventually gets fast enough
        # to tunnel straight through a paddle between frames (collision is
        # only checked once per frame) - capped just under the paddle's own
        # width plus the ball's radius, the point past which a single
        # frame's movement could skip the paddle entirely.
        #
        # This bounds the stored speed value itself (so escalation still has
        # real range to climb through, unlike capping it low enough to
        # account for dt_scale here too - that would leave almost no room
        # to escalate at higher difficulties, where the starting speed is
        # already close to this cap). The actual per-frame *displacement*
        # (speed * dt_scale) is what actually has to stay under this
        # threshold on a slow frame - that's clamped separately, at the
        # point the ball is moved, in start_pong_game.
        self.max_ball_speed = self.paddle_width + self.ball_raduis - 2

        # Initialize the scores
        self.player1_score = 0
        self.player2_score = 0

        # Initialize the screen ratio. The box this ends up in
        # (camera_feed_rect) and the play field are both sized from these
        # exact dimensions, so changing the ratio changes the table too.
        self.pong_screen_ratio = 3.5

        # Take an initial camera image. A blank placeholder stands in until
        # the real feed arrives on the first loop iteration below -
        # including when the read fails outright (camera still warming up,
        # or genuinely unavailable) - so this always has a real array of the
        # right shape to work with instead of crashing on None.
        frame = self.capture_scaled_frame(self.pong_screen_ratio)
        self.camera_image = (
            frame
            if frame is not None
            else np.zeros(
                (
                    int(self.user_screen_height // self.pong_screen_ratio),
                    int(self.user_screen_width // self.pong_screen_ratio),
                    3,
                ),
                dtype=np.uint8,
            )
        )

        # No rounding: the feed is drawn in the shared frame, not pasted

        # Set the entire camera image to be black
        self.camera_image[:, :] = 0

        # Get the camera image dimensions and the background image
        # dimensions. bg_width/bg_height come from the cached native size,
        # not the (no-longer-kept) raw array or the cached pygame surface -
        # that surface is scaled to the canvas, not the background art's own
        # 1280x720 space this geometry is computed in.
        bg_width, bg_height = self.pong_game_bg_native_size
        image_height, image_width, _ = self.camera_image.shape

        # Calculate the top-left coordinates for the camera image
        top_left_x = (bg_width - image_width) // 2
        top_left_y = (bg_height - image_height) // 2

        # Calculate the start and end coordinates for the camera image.
        # The old +100 vertical bias left room for a title the loop drew
        # separately; the title now comes from draw_game_title and reserves
        # its own space above, so +100 just left a wide dead gap below it.
        # A small +30 keeps a bit of breathing room under the title without
        # reopening that gap.
        pong_vertical_bias = 30
        self.start_x_cam = top_left_x + 300
        self.start_y_cam = top_left_y + pong_vertical_bias
        self.end_x_cam = top_left_x + image_width + 300
        self.end_y_cam = top_left_y + image_height + pong_vertical_bias

        # Initialize the scale value for x and y
        self.scale_x_cam = self.user_screen_width / bg_width
        self.scale_y_cam = self.user_screen_height / bg_height

        # Initialize the translate value for x and y
        self.translation_x_cam = int(self.start_x_cam * self.scale_x_cam)
        self.translation_y_cam = int(self.start_y_cam * self.scale_y_cam)

        # Where the camera feed belongs on the canvas - computed once here
        # since none of its inputs change mid-round, instead of every call
        # to camera_feed_rect() in this game's per-frame feed draw call.
        self._camera_feed_rect = pygame.Rect(
            int(self.start_x_cam * self.scale_x_cam),
            int(self.start_y_cam * self.scale_y_cam),
            int((self.end_x_cam - self.start_x_cam) * self.scale_x_cam),
            int((self.end_y_cam - self.start_y_cam) * self.scale_y_cam),
        )

        # Calculate the play field height and width
        play_field_height, play_field_width = (
            image_height * self.scale_y_cam,
            image_width * self.scale_x_cam,
        )

        self.start_x_play_field = (
            self.translation_x_cam
            - play_field_width
            - ((self.translation_x_cam - (self.user_screen_width // 2)) * 2)
        )
        self.start_y_play_field = self.translation_y_cam

        # Initialize a rect for the play field
        self.play_field_rect = pygame.Rect(
            self.start_x_play_field,
            self.start_y_play_field,
            play_field_width,
            play_field_height,
        )

        # Initialize the scale value for x and y
        self.scale_x_play_field = (
            self.play_field_rect.width / self.camera_image.shape[1]
        )
        self.scale_y_play_field = (
            self.play_field_rect.height / self.camera_image.shape[0]
        )

        # Initialize the translate value for x and y
        self.translation_x_play_field = int(self.start_x_play_field)
        self.translation_y_play_field = int(self.start_y_play_field)

        # Initialize the ball position
        self.ball_x = self.play_field_rect.centerx
        self.ball_y = self.play_field_rect.centery

        # Initialize the paddle positions
        self.paddle1_x = self.play_field_rect.left + 10
        self.paddle1_y = self.play_field_rect.centery - self.paddle_height // 2

        # Initialize the paddle positions
        self.paddle2_x = self.play_field_rect.right - self.paddle_width - 10
        self.paddle2_y = self.play_field_rect.centery - self.paddle_height // 2

        # Initialize the wave wait time
        # The rules have their own screen now, so this is a get-ready beat
        self.pong_first_wave_wait_time = 5

        if first_pong_entry:
            # Load hit sounds
            self.hit_sounds = [
                mixer.Sound(f"{CWD}/resources/sounds/ball-hit-1.ogg"),
                mixer.Sound(f"{CWD}/resources/sounds/ball-hit-2.ogg"),
                mixer.Sound(f"{CWD}/resources/sounds/ball-hit-3.ogg"),
                mixer.Sound(f"{CWD}/resources/sounds/ball-hit-4.ogg"),
                mixer.Sound(f"{CWD}/resources/sounds/ball-hit-5.ogg"),
                mixer.Sound(f"{CWD}/resources/sounds/ball-hit-6.ogg"),
            ]

            # Load whistle sound
            self.point_whistle_sound = mixer.Sound(
                f"{CWD}/resources/sounds/referee-whistle-1.ogg"
            )
            self.pong_game_over_sound = mixer.Sound(
                f"{CWD}/resources/sounds/referee-whistle-2.ogg"
            )

            # Load game over sound
            self.ball_drop_sound = mixer.Sound(
                f"{CWD}/resources/sounds/ball-dropping.ogg"
            )

        # Volume always reflects the current setting, even though the Sound
        # objects above are only loaded from disk once - sfx_volume() is
        # re-applied here every entry, same as before this change.
        for sound in self.hit_sounds:
            sound.set_volume(self.sfx_volume(0.2))
        self.point_whistle_sound.set_volume(self.sfx_volume(0.2))
        self.pong_game_over_sound.set_volume(self.sfx_volume(0.5))
        self.ball_drop_sound.set_volume(self.sfx_volume(0.2))

        # Initialize the max score
        self.max_score = self.settings["pong_points_to_win"]

        # Start the Pong game timer
        self.start_pong_game_timer()

    def start_pong_game_timer(self):
        """The get-ready beat, with the camera up so both sides can frame."""
        start_time = time.time()
        self.ball_drop_sound.play()
        total = self.pong_first_wave_wait_time

        while True:
            for event in self.pump_events():
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        return

            time_remaining = total - int(time.time() - start_time)
            screen_ingame.draw_countdown(
                self,
                "PONG",
                "GET READY",
                time_remaining,
                total,
                "BOTH PLAYERS INSIDE THE FRAME",
                viewport=screen_ingame.corner_viewport(self),
            )
            self.clock.tick(60)

            if time_remaining <= 0:
                break

        time.sleep(1)

        # Start the Pong game
        self.start_pong_game()

    def start_pong_game(self):

        # Tracks time since the last speed bump, not time since the last
        # point - it must NOT reset when either player scores, or the ramp
        # only ever accumulates within one uninterrupted rally instead of
        # across the whole match (a match made of short exchanges would
        # never speed up at all).
        last_speed_increment_time = time.time()

        while True:
            for event in self.pump_events():
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        return

            # Increase the ball speed every interval
            current_time = time.time()
            if current_time - last_speed_increment_time > self.speed_increment_interval:
                self.ball_speed_x += (
                    self.speed_increment
                    if self.ball_speed_x > 0
                    else -self.speed_increment
                )
                self.ball_speed_y += (
                    self.speed_increment
                    if self.ball_speed_y > 0
                    else -self.speed_increment
                )
                self.ball_speed_x = max(
                    -self.max_ball_speed, min(self.max_ball_speed, self.ball_speed_x)
                )
                self.ball_speed_y = max(
                    -self.max_ball_speed, min(self.max_ball_speed, self.ball_speed_y)
                )
                last_speed_increment_time = current_time

            # Take a camera image. A transient read failure (USB hiccup, the
            # camera briefly grabbed by another process) just keeps last
            # frame's picture on screen instead of crashing the round.
            frame = self.capture_scaled_frame(self.pong_screen_ratio)
            if frame is not None:
                self.camera_image = frame

            is_left_hand = False
            is_right_hand = False

            # Get the hands data. self.camera_image is RGB (capture_scaled_frame
            # already converted it, since that's also what gets displayed) but
            # findFingers converts BGR->RGB internally to match its own
            # standalone-script contract - feeding it RGB directly would
            # convert it a second time and hand mediapipe channel-swapped data,
            # silently breaking detection. Round-trip through BGR so findFingers
            # gets what it expects and lands on true RGB again, and convert its
            # (landmark-annotated) result back to RGB for display.
            bgr_for_tracking = cv2.cvtColor(self.camera_image, cv2.COLOR_RGB2BGR)
            bgr_for_tracking = self.hand_tracking.findFingers(bgr_for_tracking)
            self.camera_image = cv2.cvtColor(bgr_for_tracking, cv2.COLOR_BGR2RGB)
            hands_data = self.hand_tracking.findPosition(
                self.camera_image, self.camera_image.shape[1]
            )

            lmsList1, _, center1, side1 = hands_data[0]
            lmsList2, _, center2, side2 = hands_data[1]

            # Move the paddles based on the hands data
            if side1 == "left" and len(lmsList1) != 0:
                is_left_hand = True
                _, center1_y = center1
                center1_y = (
                    int(center1_y * self.scale_y_play_field)
                    + self.translation_y_play_field
                )

                self.paddle1_y = center1_y - self.paddle_height // 2

                if self.paddle1_y < self.play_field_rect.top:
                    self.paddle1_y = self.play_field_rect.top + 10
                elif self.paddle1_y > self.play_field_rect.bottom - 75:
                    self.paddle1_y = (
                        self.play_field_rect.bottom - self.paddle_height - 10 - 10
                    )

            if side2 == "right" and len(lmsList2) != 0:
                is_right_hand = True
                _, center2_y = center2
                center2_y = (
                    int(center2_y * self.scale_y_play_field)
                    + self.translation_y_play_field
                )
                self.paddle2_y = center2_y - self.paddle_height // 2

                if self.paddle2_y < self.play_field_rect.top:
                    self.paddle2_y = self.play_field_rect.top + 10
                elif self.paddle2_y > self.play_field_rect.bottom - 75:
                    self.paddle2_y = (
                        self.play_field_rect.bottom - self.paddle_height - 10 - 10
                    )

            # Move the ball, scaled to real time rather than loop iterations
            # so its speed doesn't depend on how fast this frame ran. The
            # actual displacement is clamped to max_ball_speed too (not just
            # the stored speed value) - dt_scale can be up to 2x on a slow
            # frame, and speed * dt_scale is what could tunnel through a
            # paddle, not speed alone.
            dt_scale = self.frame_dt_scale()
            self.ball_x += max(
                -self.max_ball_speed, min(self.max_ball_speed, self.ball_speed_x * dt_scale)
            )
            self.ball_y += max(
                -self.max_ball_speed, min(self.max_ball_speed, self.ball_speed_y * dt_scale)
            )

            # Check if the ball hits the top or bottom of the screen
            if self.ball_y <= self.play_field_rect.top + self.ball_raduis:
                self.hit_sounds[random.randint(0, len(self.hit_sounds) - 1)].play()
                self.ball_speed_y = -self.ball_speed_y
            elif self.ball_y >= self.play_field_rect.bottom - self.ball_raduis:
                self.ball_speed_y = -self.ball_speed_y
                self.hit_sounds[random.randint(0, len(self.hit_sounds) - 1)].play()

            # Convert the ball poistion to a pygame rect
            ball_rect = pygame.Rect(
                self.ball_x, self.ball_y, self.ball_raduis, self.ball_raduis
            )

            # Convert the paddle poistion to a pygame rect
            paddle_rect1 = pygame.Rect(
                self.paddle1_x, self.paddle1_y, self.paddle_width, self.paddle_height
            )
            paddle_rect2 = pygame.Rect(
                self.paddle2_x, self.paddle2_y, self.paddle_width, self.paddle_height
            )

            # Check if the ball hits the paddle
            if paddle_rect1.colliderect(ball_rect):
                self.hit_sounds[random.randint(0, len(self.hit_sounds) - 1)].play()
                self.ball_speed_x = -self.ball_speed_x
                self.ball_x = self.paddle1_x + self.paddle_width + self.ball_raduis
            elif paddle_rect2.colliderect(ball_rect):
                self.hit_sounds[random.randint(0, len(self.hit_sounds) - 1)].play()
                self.ball_speed_x = -self.ball_speed_x
                self.ball_x = self.paddle2_x - self.ball_raduis

            # Check if the ball hits the left or right of the screen.
            # Deliberately not scaled by difficulty_modifiers["score_multiplier"]
            # (unlike Balloons/Runner's reward points): this is a race-to-N
            # win condition, not an accumulating score, so a fractional or
            # difficulty-dependent point value would make "first to
            # pong_points_to_win" mean a different number of actual rallies
            # depending on difficulty - confusing rather than harder.
            if self.ball_x <= self.play_field_rect.left + self.ball_raduis:
                self.point_whistle_sound.play()
                self.player2_score += 1
                self.ball_x = self.play_field_rect.centerx
                self.ball_y = self.play_field_rect.centery
                self.ball_speed_x = random.choice(
                    [-self.base_ball_speed, self.base_ball_speed]
                )
                self.ball_speed_y = random.choice(
                    [-self.base_ball_speed, self.base_ball_speed]
                )

            elif self.ball_x >= self.play_field_rect.right - self.ball_raduis:
                self.point_whistle_sound.play()
                self.player1_score += 1
                self.ball_x = self.play_field_rect.centerx
                self.ball_y = self.play_field_rect.centery
                self.ball_speed_x = random.choice(
                    [-self.base_ball_speed, self.base_ball_speed]
                )
                self.ball_speed_y = random.choice(
                    [-self.base_ball_speed, self.base_ball_speed]
                )

            # The feed is drawn over the background rather than into it.
            # pong_game_bg_image_pygame was already built once at init -
            # nothing about the background changes during a round.
            self.blit_background(self.pong_game_bg_image_pygame)
            self.draw_camera_feed("BOTH PLAYERS")

            # Draw the play field
            [
                pygame.draw.rect(
                    self.screen, color, self.play_field_rect, width, border_radius=30
                )
                for color, width in [((2, 48, 32), 0), ((255, 255, 255), 5)]
            ]

            # Draw the ball
            pygame.draw.circle(
                self.screen,
                (255, 255, 255),
                (self.ball_x, self.ball_y),
                self.ball_raduis,
            )

            # Draw the paddles
            pygame.draw.rect(
                self.screen,
                (255, 255, 255),
                (self.paddle1_x, self.paddle1_y, self.paddle_width, self.paddle_height),
            )
            pygame.draw.rect(
                self.screen,
                (255, 255, 255),
                (self.paddle2_x, self.paddle2_y, self.paddle_width, self.paddle_height),
            )

            # Draw the net
            for i in range(
                self.start_y_play_field,
                self.start_y_play_field + self.play_field_rect.height,
                20,
            ):
                pygame.draw.rect(
                    self.screen,
                    (255, 255, 255),
                    (
                        self.play_field_rect.width // 2 + self.start_x_play_field,
                        i,
                        4,
                        8,
                    ),
                )

            if (
                self.player1_score == self.max_score
                or self.player2_score == self.max_score
            ):
                self.end_pong_game()
                break

            # A scoreboard at each player's own end, so which side is
            # yours is never in question. Drawn last, so the ball cannot
            # pass over the score.
            self.draw_pong_hud(is_left_hand, is_right_hand)
            self.present()

            # Update the clock and delta time
            self.dt = self.clock.tick(60) / 1000

    def draw_pong_hud(self, left_hand_seen, right_hand_seen):
        """The title, both scoreboards, and the target score.

        Each scoreboard sits at the end of the field its player controls;
        the status line says whose hand is currently being tracked. The two
        hands are tracked independently by the game loop - it used to only
        pass this function the right hand's state and infer the left as
        "not right", so both boxes read wrong whenever both hands were (or
        weren't) in frame at once, which is the common case.
        """
        screen_ingame.draw_game_title(self, "pong")

        tracked = {0: left_hand_seen, 1: right_hand_seen}
        for slot, score in ((0, self.player1_score), (1, self.player2_score)):
            screen_ingame.draw_side_score(
                self,
                slot,
                score,
                self.play_field_rect,
                right=slot == 1,
                tracked=tracked[slot],
            )

        screen_ingame.draw_stat_bar(
            self, (("FIRST TO", self.max_score, ui.INK),), top_percent=81.0
        )
        screen_ingame.draw_escape(self)
        self.draw_fps()

    def end_pong_game(self):
        self.pong_game_over_sound.play()

        # Both sides get their own points recorded
        scores = (self.player1_score, self.player2_score)
        for slot, score in enumerate(scores):
            self.record_score(self.current_player_id(slot), "pong", score)

        winner = 0 if self.player1_score >= self.player2_score else 1

        # Already built once at init - nothing about the background changes
        # between the last frame of play and this screen.
        background = self.pong_game_bg_image_pygame

        entries = [
            {
                "user_id": self.current_player_id(slot),
                "name": self.player_label(slot),
                "score": scores[slot],
                "note": "WINNER" if slot == winner else "",
                "score_color": ui.SUN if slot == winner else ui.INK,
            }
            for slot in range(2)
        ]

        while True:
            self.draw_game_over(
                background,
                f"{ui.truncate(self.player_label(winner).upper(), 14)} WINS",
                entries,
                "ESC FOR THE MAIN MENU",
                headline_color=ui.SUN,
            )

            for event in self.pump_events():
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        return

            self.clock.tick(60)

    def init_runner_game(self):
        self.sync_screen_size()

        # Runner is played entirely with body pose tracking, same as
        # Balloons/Pong are with hand tracking - it used to also accept
        # Up/Space/Down as a keyboard fallback when no camera was found,
        # but no game in this app should have a manual-control path.
        if not self.cap.isOpened():
            return self.show_camera_required("Runner")

        players = self.select_players("RUNNER", ("Player",))
        if players is None:
            return
        self.active_players = players

        if not screen_ingame.show_instructions(self, "runner"):
            return

        # Set the background music for the Runner game
        mixer.music.load(f"{CWD}/resources/sounds/main_menu_bg_music.ogg")
        mixer.music.set_volume(self.music_volume)

        # Play the background music
        mixer.music.play(-1)

        # Sounds, background and ground tile are fixed for the whole
        # process - loaded from disk once, ever, rather than on every trip
        # back to the main menu and into Runner again. The countdown cue
        # uses the Runner game's own chime rather than Pong's 5-second
        # ball-drop, which belonged to a different game and outlasted the
        # countdown.
        if not hasattr(self, "runner_start_sound"):
            self.runner_start_sound = mixer.Sound(
                f"{CWD}/resources/sounds/runner-point.ogg"
            )
            self.runner_jump_sound = mixer.Sound(
                f"{CWD}/resources/sounds/runner-jump.ogg"
            )
            self.runner_lose_sound = mixer.Sound(
                f"{CWD}/resources/sounds/runner-lose.ogg"
            )
            self.runner_point_sound = mixer.Sound(
                f"{CWD}/resources/sounds/runner-point.ogg"
            )

            # Initialize the background image for the Runner game. The raw
            # decoded array is a local variable, not kept on self - nothing
            # reads it again after this method returns.
            runner_game_bg_image = cv2.imread(
                f"{CWD}/resources/images/runner_game_bg.png"
            )
            self.runner_game_bg_image_pygame = pygame.image.frombuffer(
                cv2.cvtColor(runner_game_bg_image, cv2.COLOR_BGR2RGB).tobytes(),
                (runner_game_bg_image.shape[1], runner_game_bg_image.shape[0]),
                "RGB",
            )
            # convert() for the same reason array_to_scaled_surface does it
            # (see that method) - an unconverted background costs a
            # full-canvas pixel-format translation on every single frame.
            self.runner_game_bg_image_pygame = pygame.transform.scale(
                self.runner_game_bg_image_pygame,
                self.screen.get_size(),
            ).convert(self.screen)

            # Load the ground image (tiled and scrolled across the bottom),
            # scaled 1.5x to match the sprites so the ground line reads clearly
            ground_image = pygame.image.load(
                f"{CWD}/resources/images/ground.png"
            ).convert_alpha()
            self.runner_ground_image = pygame.transform.scale(
                ground_image,
                (
                    int(ground_image.get_width() * 1.5),
                    int(ground_image.get_height() * 1.5),
                ),
            )
            # The solid line sits partway down the tile, so shift the blit
            # up by that much to put the drawn ground exactly under the
            # sprites' feet
            self.runner_ground_offset = ground_line_offset(self.runner_ground_image)

        # Volume always reflects the current setting, even though the Sound
        # objects above are only loaded from disk once - sfx_volume() is
        # re-applied here every entry, same as before this change.
        self.runner_start_sound.set_volume(self.sfx_volume(0.4))
        self.runner_jump_sound.set_volume(self.sfx_volume(0.4))
        self.runner_lose_sound.set_volume(self.sfx_volume(0.5))
        self.runner_point_sound.set_volume(self.sfx_volume(0.3))

        # The camera overlay's box comes from screen_ingame.corner_viewport,
        # so every game's feed sits in the same place and at the same size

        # Initialize the play field, so the run happens inside a clearly
        # bounded area (like Pong's field) rather than being lost against
        # the busy background art.
        field_width = int(self.user_screen_width * 0.82)
        field_height = int(self.user_screen_height * 0.34)
        self.runner_field_rect = pygame.Rect(
            (self.user_screen_width - field_width) // 2,
            int(self.user_screen_height * 0.42),
            field_width,
            field_height,
        )

        # The ground line sits inside the play field, near its bottom
        self.runner_ground_y = self.runner_field_rect.bottom - int(field_height * 0.14)

        # Initialize the wave wait time
        self.runner_start_wait_time = 5

        # Measured during the countdown; None means use the fallback lines
        self.runner_pose_baseline = None

        # Run rounds in a loop rather than recursive calls, so "Press R to
        # restart" doesn't grow the call stack a level deeper every time
        # (start_runner_game_timer/start_runner_game/end_runner_game all return a
        # plain value now instead of calling back into each other).
        self.reset_runner_round()
        while True:
            action = self.start_runner_game_timer()
            if action != "restart":
                return
            self.reset_runner_round()

    def reset_runner_round(self):
        """Reset per-round Runner state (sprites, score, timers) for a fresh
        round, without reloading sounds/images every replay."""
        # The Runner sprite bottom-aligns itself to the ground line, so run,
        # jump and duck frames (which all have different heights) stay
        # planted instead of sinking through the ground.
        runner_x = self.runner_field_rect.left + int(self.runner_field_rect.width * 0.08)
        self.runner_sprite = Runner(runner_x, self.runner_ground_y)

        self.runner_group = pygame.sprite.GroupSingle(self.runner_sprite)
        self.runner_obstacle_group = pygame.sprite.Group()
        self.runner_cloud_group = pygame.sprite.Group()

        self.runner_score = 0
        # A personal best can't change mid-round (only recorded at the end
        # of one), so it's fetched once here instead of on every HUD frame.
        self.runner_best_score = self.get_best_score(self.current_player_id(0), "runner")
        # Pixels per frame at 30 FPS (~480 px/s scroll speed), scaled by the
        # difficulty setting
        self.runner_game_speed = (
            RUNNER_START_SPEED * self.difficulty_modifiers["runner_speed"]
        )
        self.runner_ground_x = 0
        self.runner_obstacle_timer = pygame.time.get_ticks()
        self.runner_obstacle_spawn = True
        self.runner_obstacle_cooldown = 1500
        self.runner_cloud_timer = pygame.time.get_ticks()
        self.runner_cloud_spawn_time = 3000
        self.runner_speed_milestone = 0
        self.runner_guide_ratios = (0.30, 0.70, None)

    def start_runner_game_timer(self):
        """The countdown, which is also the calibration.

        The jump and duck lines are placed around wherever the player's head
        rests, so this beat has to sample it. That is why Runner always runs
        the countdown even when the rules screen has been skipped.
        """
        start_time = time.time()
        self.runner_start_sound.play()
        total = self.runner_start_wait_time

        baseline_samples = []
        nose_ratio = None

        while True:
            for event in self.pump_events():
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        return

            read_ok, calib_frame = self.cap.read()
            if read_ok and calib_frame is not None:
                calib_frame = cv2.flip(calib_frame, 1)
                calib_height = int(
                    POSE_DETECT_WIDTH * calib_frame.shape[0] / calib_frame.shape[1]
                )
                calib_frame = cv2.resize(calib_frame, (POSE_DETECT_WIDTH, calib_height))
                calib_data = detect_jump_duck(self.pose_detector, calib_frame)
                if calib_data["nose_pos"]:
                    nose_ratio = calib_data["nose_pos"][1] / calib_height
                    baseline_samples.append(nose_ratio)

            time_remaining = total - int(time.time() - start_time)
            found = nose_ratio is not None

            # Show the lines this run will actually use, refined as samples
            # arrive, rather than placeholders that jump once play starts
            jump_ratio, duck_ratio = threshold_ratios(
                calibrate_baseline(baseline_samples), self.gesture_sensitivity
            )
            screen_ingame.draw_countdown(
                self,
                "RUNNER",
                "MEASURING YOU",
                time_remaining,
                total,
                "SIT NORMALLY AND HOLD STILL" if found else "STEP INTO THE FRAME",
                viewport=screen_ingame.corner_viewport(self),
                overlays=(
                    screen_ingame.threshold_overlay(
                        self, jump_ratio, duck_ratio, nose_ratio
                    ),
                ),
            )
            self.clock.tick(60)

            if time_remaining <= 0:
                break

        # Place the thresholds either side of the player's resting position
        self.runner_pose_baseline = calibrate_baseline(baseline_samples)

        # Say so rather than silently falling back to lines at fixed heights
        if self.runner_pose_baseline is None:
            self.show_calibration_failed()

        time.sleep(1)

        # Start the Runner game
        return self.start_runner_game()

    def show_calibration_failed(self):
        """Warn that nobody was measured, so the lines are at fixed heights."""
        shown_until = time.time() + 2.5
        while time.time() < shown_until:
            for event in self.pump_events():
                if event.type == pygame.KEYDOWN:
                    return

            self.blit_background(self.runner_game_bg_image_pygame)
            ui.dim_screen(self.screen)
            screen_ingame.draw_banner(
                self,
                "NOT MEASURED",
                "THE LINES ARE AT THEIR DEFAULT HEIGHTS",
            )
            self.present()
            self.clock.tick(60)

    def start_runner_game(self):
        while True:
            for event in self.pump_events():
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        return

            # How much real time this frame is worth, in nominal
            # (1/TARGET_FPS) frames - scrolling, obstacle speed, scoring and
            # the runner's own jump physics all move by this rather than a
            # fixed amount per loop iteration, so the game runs at the same
            # real-world speed regardless of the frame rate the hardware
            # actually sustains.
            dt_scale = self.frame_dt_scale()

            # Take a camera image and detect jump/duck from the player's pose.
            # The capture is at screen resolution, which is far more than the
            # nose-position heuristic needs; downscaling first is what keeps
            # the per-frame pose inference cheap enough to hold the framerate.
            # With no working camera the game stays playable on the keyboard.
            read_ok, frame = self.cap.read()
            if not read_ok or frame is None:
                frame = None
                pose_data = {"jump": False, "duck": False}
            else:
                frame = cv2.flip(frame, 1)
                detect_height = int(POSE_DETECT_WIDTH * frame.shape[0] / frame.shape[1])
                frame = cv2.resize(frame, (POSE_DETECT_WIDTH, detect_height))
                pose_data = detect_jump_duck(
                    self.pose_detector,
                    frame,
                    baseline=self.runner_pose_baseline,
                    sensitivity=self.gesture_sensitivity,
                )

                # The guides are drawn on the canvas by draw_runner_camera,
                # so they match the how-to and countdown screens exactly
                # rather than being OpenCV lines baked into a 480px frame
                # and then upscaled.
                self.runner_guide_ratios = (
                    pose_data["jump_line_y"] / detect_height,
                    pose_data["duck_line_y"] / detect_height,
                    pose_data["nose_pos"][1] / detect_height
                    if pose_data["nose_pos"]
                    else None,
                )

            # Update the runner
            self.runner_group.update(
                pose_data["jump"],
                pose_data["duck"],
                jump_sound=self.runner_jump_sound,
                dt_scale=dt_scale,
            )

            # Check collision with an obstacle
            if pygame.sprite.spritecollide(self.runner_sprite, self.runner_obstacle_group, False):
                return self.end_runner_game()

            # Draw the Runner game background image to the center of the screen
            self.blit_background(self.runner_game_bg_image_pygame)

            # Fill the play field with the runner's own sky colour, so the
            # ground and sprites read clearly instead of getting lost in the
            # background art
            pygame.draw.rect(
                self.screen, RUNNER_FIELD_COLOR, self.runner_field_rect, border_radius=30
            )

            # Spawn clouds
            current_time = pygame.time.get_ticks()
            if current_time - self.runner_cloud_timer > self.runner_cloud_spawn_time:
                self.runner_cloud_group.add(
                    Cloud(
                        spawn_x=self.runner_field_rect.right,
                        y_min=self.runner_field_rect.top + 20,
                        y_max=self.runner_ground_y - 140,
                    )
                )
                self.runner_cloud_timer = current_time
                self.runner_cloud_spawn_time = random.randint(1500, 3000)

            # Spawn obstacles at the right edge of the play field. Reuses
            # current_time (already fetched above for the cloud-spawn check)
            # instead of calling pygame.time.get_ticks() again at each of
            # these three points - the same instant, several times over.
            if self.runner_obstacle_spawn:
                if current_time - self.runner_obstacle_timer > 1500:
                    if random.randint(1, 10) <= 7:
                        obstacle = Cactus(self.runner_field_rect.right, 0)
                        obstacle.rect.bottom = self.runner_ground_y
                    else:
                        obstacle = Ptero(screen_width=self.runner_field_rect.right)
                        # Only two flight heights, far enough apart to read at
                        # a glance: skimming the ground (jump it) or clearly
                        # overhead (duck under it). An in-between height just
                        # looked like the low one while still needing a jump.
                        obstacle.rect.bottom = self.runner_ground_y - random.choice(
                            [0, RUNNER_DUCK_UNDER_HEIGHT]
                        )
                    self.runner_obstacle_group.add(obstacle)

                    self.runner_obstacle_timer = current_time
                    self.runner_obstacle_spawn = False
                    self.runner_obstacle_cooldown = random.randint(1500, 3000)
            elif current_time - self.runner_obstacle_timer > self.runner_obstacle_cooldown:
                self.runner_obstacle_spawn = True

            # Everything below is confined to the play field, so sprites and
            # the scrolling ground can't bleed out over the rest of the screen
            self.screen.set_clip(self.runner_field_rect)

            # Scroll and draw the ground across the field
            self.runner_ground_x -= self.runner_game_speed * dt_scale
            ground_width = self.runner_ground_image.get_width()
            for i in range(
                -ground_width,
                self.runner_field_rect.width + ground_width * 2,
                ground_width,
            ):
                self.screen.blit(
                    self.runner_ground_image,
                    (
                        self.runner_field_rect.left + self.runner_ground_x + i,
                        self.runner_ground_y - self.runner_ground_offset,
                    ),
                )
            if self.runner_ground_x <= -ground_width:
                self.runner_ground_x = 0

            # Update and draw the clouds, runner and obstacles
            self.runner_cloud_group.update(self.runner_field_rect.left - 150)
            self.runner_cloud_group.draw(self.screen)
            self.runner_group.draw(self.screen)
            self.runner_obstacle_group.update(
                self.runner_game_speed * dt_scale,
                self.runner_field_rect.left - 150,
                dt_scale=dt_scale,
            )
            self.runner_obstacle_group.draw(self.screen)

            self.screen.set_clip(None)

            # Outline the play field, matching Pong's bordered field
            pygame.draw.rect(
                self.screen, (255, 255, 255), self.runner_field_rect, 5, border_radius=30
            )

            self.draw_runner_camera(frame)

            self.runner_score += (
                0.1 * dt_scale * self.difficulty_modifiers["score_multiplier"]
            )

            # Speed up the game once per RUNNER_SPEED_MILESTONE_POINTS-point
            # milestone (runner_score crosses each multiple of it over
            # several frames, so this is guarded by runner_speed_milestone
            # rather than firing every frame int(runner_score) happens to be
            # a multiple of it).
            milestone = int(self.runner_score) // RUNNER_SPEED_MILESTONE_POINTS
            if milestone > self.runner_speed_milestone:
                self.runner_speed_milestone = milestone
                if self.runner_game_speed < RUNNER_MAX_SPEED:
                    self.runner_game_speed += RUNNER_SPEED_STEP
                    self.runner_point_sound.play()

            # Title, score/best/speed and the player badge - draw_runner_hud
            # already calls draw_fps, so nothing else needs to before present
            self.draw_runner_hud()
            self.present()

            # Update the clock and delta time. Matches Balloons/Pong -
            # self.cap.read() no longer blocks (see ThreadedCapture in
            # gui/camera_stream.py), so this loop isn't tied to the
            # camera's own capture rate anymore.
            self.dt = self.clock.tick(60) / 1000

    def draw_runner_camera(self, frame):
        """The feed in the top-right, or a keyboard hint when there is none."""
        rect = screen_ingame.corner_viewport(self)

        if frame is None:
            screen_ingame.draw_viewport(self, rect, None, "NO CAMERA")
            for line_number, line in enumerate(("USE UP / DOWN", "ARROW KEYS")):
                ui.draw_text(
                    self.screen,
                    line,
                    self.font_path,
                    ui.cqw(1.0),
                    color=(200, 195, 212),
                    center=(rect.centerx, rect.centery + line_number * ui.cqw(1.4)),
                    letter_spacing=ui.cqw(0.08),
                )
            return rect

        image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        surface = pygame.image.frombuffer(
            image.tobytes(), (image.shape[1], image.shape[0]), "RGB"
        )

        jump, duck, nose = getattr(self, "runner_guide_ratios", (0.30, 0.70, None))
        return screen_ingame.draw_viewport(
            self,
            rect,
            surface,
            "YOU",
            overlays=(screen_ingame.threshold_overlay(self, jump, duck, nose),),
        )

    def draw_runner_hud(self):
        """Title, score/best/speed, plus who is playing."""
        # Fetched once per round (reset_runner_round) - a personal best
        # can't change mid-round, so this HUD doesn't re-query it.
        best = self.runner_best_score
        multiplier = self.runner_game_speed / (
            16 * self.difficulty_modifiers["runner_speed"]
        )

        title_rect = screen_ingame.draw_game_title(self, "runner")
        screen_ingame.draw_stat_bar(
            self,
            (
                ("SCORE", int(self.runner_score), ui.SUN),
                ("BEST", "--" if best is None else best, ui.INK),
                ("SPEED", f"x{multiplier:.1f}", ui.WIRE),
            ),
            top=title_rect.bottom + ui.cqw(2.6, self.screen.get_width()),
        )
        screen_ingame.draw_whoami(self, 0, best=best)
        screen_ingame.draw_escape(self)
        self.draw_fps()

    def end_runner_game(self):
        self.runner_lose_sound.play()

        self.runner_score = max(0, int(self.runner_score))

        player_id = self.current_player_id(0)
        previous_best = self.get_best_score(player_id, "runner")
        self.record_score(player_id, "runner", self.runner_score)

        entries = [
            {
                "user_id": player_id,
                "name": self.player_label(0),
                "score": self.runner_score,
                "note": self.personal_best_note(self.runner_score, previous_best),
            }
        ]

        while True:
            self.draw_game_over(
                self.runner_game_bg_image_pygame,
                "GAME OVER",
                entries,
                "R TO PLAY AGAIN  ·  ESC FOR THE MAIN MENU",
            )

            for event in self.pump_events():
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        return "menu"

                    if event.key == pygame.K_r:
                        # Signal the round-loop in init_runner_game to reset
                        # and go again, instead of recursing back into
                        # init_runner_game (which would nest a new set of
                        # timer/game/end-game stack frames on every replay).
                        return "restart"

            self.clock.tick(60)

    def change_setting(self, key, value):
        """Store a setting, apply it immediately and persist it to disk."""
        self.settings[key] = value
        self.apply_settings()
        self.save_settings()

    def mark_instructions_seen(self, key):
        """Remember that a game's how-to screen has been shown, for good.

        Like player_1_id/player_2_id, this lives in settings.json but isn't
        exposed in the Settings screen - it's set by playing (pressing
        ENTER through the rules once), not by editing.
        """
        if key in self.instructions_seen:
            return
        self.instructions_seen.add(key)
        self.settings["instructions_seen"] = sorted(self.instructions_seen)
        self.save_settings()

    def init_settings(self):
        """Show the settings screen.

        Every change writes through change_setting, so it is applied and
        saved to data/settings.json as soon as it is made.
        """
        self.sync_screen_size()
        return screen_settings.run(self)
