import pygame
import pygame_menu
from pygame_menu.themes import Theme
from pygame.locals import *
from pygame import mixer

import cv2

import random
import time
import os
import json
import sqlite3  # Add SQLite database support
from gui.settings_config import DEFAULT_SETTINGS, SCREEN_RESOLUTIONS, DIFFICULTY_SETTINGS

from models.mediapipe_hand_tracking import HandTrackingDynamic
from models.cvzone_hand_detection import initialize_hand_detector, detect_hands
from screeninfo import get_monitors

from gui.utils import img_with_rounded_corners, random_bool_by_chance, biased_random_int


# Get the current working directory
CWD = os.path.dirname(os.path.abspath(__file__))


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

        # Start Pygame
        pygame.init()

        # Initialize the mixer for sound
        mixer.init()

        # Set the icon
        icon = pygame.image.load(f"{CWD}/resources/images/5-lmbox-icon.png")
        pygame.display.set_icon(icon)

        # Create a screen
        self.screen = pygame.display.set_mode(
            (self.user_screen_width, self.user_screen_height),
            pygame.FULLSCREEN,
            display=self.user_screen_number,
        )
        # Set the window title
        pygame.display.set_caption(self.game_name)

        # Initialize the clock for controlling the frame rate and delta time
        self.clock = pygame.time.Clock()
        self.dt = 0

        # Initialize a boolean for what screen the game is currently on
        self.balloons_game_running = False
        self.main_menu_running = False
        self.pong_game_running = False
        self.credits_running = False

        # Initialize a boolean for whether the background music is muted
        self.bg_music_muted = False  #! Set to True for testing

        # Initialize the font for the game
        self.font_path = f"{CWD}/resources/fonts/joystix monospace.otf"

        # Seed the random number generator
        random.seed(time.time())

        # Initialize the themes and main menu
        self.init_theme()
        self.init_main_menu()

        # Start the main menu
        self.start_main_menu()

    def load_settings(self):
        """Load game settings from file or use defaults"""
        settings_path = os.path.join(CWD, "..", "settings.json")
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
        settings_path = os.path.join(CWD, "..", "settings.json")
        try:
            with open(settings_path, 'w') as f:
                json.dump(self.settings, f, indent=4)
        except IOError:
            print("Warning: Could not save settings to file.")
            
    def apply_settings(self):
        """Apply the current settings to the game"""
        # Apply volume settings - safely check if mixer is initialized
        if pygame.mixer.get_init():
            mixer.music.set_volume(self.settings["music_volume"] / 100)
        
        # Apply screen settings
        if self.settings["screen_width"] != self.initial_screen_width or \
           self.settings["screen_height"] != self.initial_screen_height:
            self.initial_screen_width = self.settings["screen_width"]
            self.initial_screen_height = self.settings["screen_height"]
            
        # Apply camera settings
        self.user_camera_number = self.settings["camera_number"]
        
        # Apply difficulty settings
        self.difficulty = self.settings["difficulty"]

    def setup_database(self):
        """Set up SQLite database for user management"""
        # Create a database in the same directory as the script
        db_path = os.path.join(CWD, "..", "lmbox_users.db")
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
        
        # Check if there are any users, add a default one if empty
        self.cursor.execute("SELECT COUNT(*) FROM users")
        if self.cursor.fetchone()[0] == 0:
            self.cursor.execute("INSERT INTO users (name) VALUES (?)", ("Player 1",))
            self.conn.commit()
            
    def add_user(self, name):
        """Add a new user to the database"""
        self.cursor.execute("INSERT INTO users (name) VALUES (?)", (name,))
        self.conn.commit()
        
    def get_users(self):
        """Get all users from the database"""
        self.cursor.execute("SELECT id, name FROM users")
        return self.cursor.fetchall()
    
    def delete_user(self, user_id):
        """Delete a user from the database"""
        self.cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
        self.conn.commit()
        
    def init_users_database(self):
        """Initialize the users database screen"""
        # Set game state
        self.main_menu_running = False
        self.balloons_game_running = False
        self.pong_game_running = False
        self.dino_game_running = False
        self.credits_running = False
        self.users_screen_running = True
        
        # Create a submenu for the users database
        self.users_menu = pygame_menu.Menu(
            "Users",
            self.user_screen_width,
            self.user_screen_height,
            theme=self.theme,
            columns=1,
            rows=8,
        )
        
        # Get all users
        users = self.get_users()
        
        # Add title
        title_label = self.users_menu.add.label(
            "Users",
            align=pygame_menu.locals.ALIGN_CENTER,
            font_size=50,
            margin=(0, 50),
        )
        title_label.set_max_height(70)
        
        # Add all users to the menu
        users_label = self.users_menu.add.label(
            "Current Users:",
            align=pygame_menu.locals.ALIGN_CENTER,
            font_size=30,
            margin=(0, 20),
        )
        users_label.set_max_height(50)
        
        # Display each user with a delete button
        for user_id, name in users:
            row_frame = self.users_menu.add.frame_h(width=700, height=80, margin=(0, 10))
            # Enable relaxed mode to avoid size exceptions
            row_frame._relax = True
            
            user_label = self.users_menu.add.label(
                f"{name}",
                align=pygame_menu.locals.ALIGN_LEFT,
                font_size=25
            )
            user_label.set_max_height(70)
            row_frame.pack(
                user_label, 
                align=pygame_menu.locals.ALIGN_LEFT
            )
            
            delete_button = self.users_menu.add.button(
                "Delete",
                lambda uid=user_id: self.delete_user_and_refresh(uid),
                align=pygame_menu.locals.ALIGN_RIGHT,
                font_size=20,
                background_color=(200, 50, 50),
                cursor=pygame.SYSTEM_CURSOR_HAND,
            )
            delete_button.set_max_height(70)
            row_frame.pack(
                delete_button,
                align=pygame_menu.locals.ALIGN_RIGHT
            )
        
        # Add a separator
        self.users_menu.add.vertical_margin(30)
        
        # Add new user input
        self.user_name_input = self.users_menu.add.text_input(
            "New User Name: ",
            default="",
            align=pygame_menu.locals.ALIGN_CENTER,
            font_size=25,
            textinput_id="user_name",
            input_underline_len=20,  # Make underline longer
            maxchar=30,  # Increase max characters
            maxwidth=500,  # Increase max width
        )
        
        # Add button to add a new user
        add_user_button = self.users_menu.add.button(
            "Add User",
            self.add_user_and_refresh,
            align=pygame_menu.locals.ALIGN_CENTER,
            margin=(0, 20),
            font_size=30,
            background_color=(50, 200, 50),
            cursor=pygame.SYSTEM_CURSOR_HAND,
        )
        
        # Set max height for the button
        add_user_button.set_max_height(50)
        
        # Add vertical space
        self.users_menu.add.vertical_margin(50)
        
        # Add a back button to return to the main menu
        back_button = self.users_menu.add.button(
            "Back to Main Menu",
            self.start_main_menu,
            align=pygame_menu.locals.ALIGN_CENTER,
            font_size=30,
            background_color=(0, 0, 0),
            cursor=pygame.SYSTEM_CURSOR_HAND,
        )
        
        # Set max height for the button
        back_button.set_max_height(50)
        
        # Start the users menu
        self.users_menu.mainloop(self.screen, fps_limit=60)
        
    def delete_user_and_refresh(self, user_id):
        """Delete a user and refresh the users menu"""
        self.delete_user(user_id)
        self.init_users_database()
        
    def add_user_and_refresh(self):
        """Add a new user and refresh the users menu"""
        user_name = self.user_name_input.get_value()
        if user_name and len(user_name) > 0:
            self.add_user(user_name)
            self.init_users_database()

    def init_camera(self):
        # Initialize the camera
        self.cap = cv2.VideoCapture(self.user_camera_number)

        # Check if the camera is opened
        if not self.cap.isOpened():
            print("Trying alternate camera index 1")
            self.cap = cv2.VideoCapture(1)
            if not self.cap.isOpened():
                print("Trying alternate camera index 2")
                self.cap = cv2.VideoCapture(2)
            if not self.cap.isOpened():
                print("WARNING: Could not open any camera. Some features may not work properly.")

        # Set the camera resolution
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.user_screen_width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.user_screen_height)

        # Set the camera frame rate
        self.cap.set(cv2.CAP_PROP_FPS, 30)

        # Initialize the camera image
        self.camera_image = None

    def init_finger_detection(self):
        # Initialize the HandDetector object
        self.finger_detector = initialize_hand_detector()

    def init_hand_tracking(self):
        # Initialize the HandDetector object
        self.hand_tracking = HandTrackingDynamic()

    def init_theme(self):
        # Set the background image
        self.menu_bg_image = pygame_menu.baseimage.BaseImage(
            image_path=f"{CWD}/resources/images/main_menu_bg.png",
            drawing_mode=pygame_menu.baseimage.IMAGE_MODE_FILL,
        )

        # Create a theme
        font = pygame.font.Font(self.font_path, 50)
        self.theme = Theme(
            background_color=self.menu_bg_image,
            title_bar_style=pygame_menu.widgets.MENUBAR_STYLE_NONE,
            widget_font_color=(251, 251, 251),
            widget_font_size=50,
            widget_font=font,
        )

    def init_main_menu(self):
        # Create the main menu
        self.main_menu = pygame_menu.Menu(
            "",
            self.user_screen_width,
            self.user_screen_height,
            theme=self.theme,
            columns=2,
            rows=8,
        )

        # Add vertical space
        self.main_menu.add.vertical_margin(250)

        # Add the "Play Balloons" button to the main menu
        self.main_menu.add.button(
            "Play Balloons",
            self.init_balloons_game,
            align=pygame_menu.locals.ALIGN_LEFT,
            margin=(100, 0),
            padding=(0, 0),
            background_color=(0, 0, 0),
            selection_effect=pygame_menu.widgets.LeftArrowSelection(
                arrow_right_margin=15,
                arrow_vertical_offset=0,
            ),
            cursor=pygame.SYSTEM_CURSOR_HAND,
        )

        # Add vertical space
        self.main_menu.add.vertical_margin(50)

        # Add the "Play Pong" button to the main menu
        self.main_menu.add.button(
            "Play Pong",
            self.init_pong_game,
            align=pygame_menu.locals.ALIGN_LEFT,
            margin=(100, 0),
            padding=(0, 0),
            background_color=(0, 0, 0),
            selection_effect=pygame_menu.widgets.LeftArrowSelection(
                arrow_right_margin=15,
                arrow_vertical_offset=0,
            ),
            cursor=pygame.SYSTEM_CURSOR_HAND,
        )

        # Add vertical space
        self.main_menu.add.vertical_margin(50)

        # Add the "Dino" button to the main menu
        self.main_menu.add.button(
            "Dino",
            self.init_dino_game,
            align=pygame_menu.locals.ALIGN_LEFT,
            margin=(100, 0),
            padding=(0, 0),
            background_color=(0, 0, 0),
            selection_effect=pygame_menu.widgets.LeftArrowSelection(
                arrow_right_margin=15,
                arrow_vertical_offset=0,
            ),
            cursor=pygame.SYSTEM_CURSOR_HAND,
        )

        

        # Add vertical space
        self.main_menu.add.vertical_margin(50)

        # Add the "Quit" button to the main menu
        self.main_menu.add.button(
            "Quit",
            pygame_menu.events.EXIT,
            align=pygame_menu.locals.ALIGN_LEFT,
            margin=(100, 0),
            padding=(0, 0),
            background_color=(0, 0, 0),
            selection_effect=pygame_menu.widgets.LeftArrowSelection(
                arrow_right_margin=15,
                arrow_vertical_offset=0,
            ),
            cursor=pygame.SYSTEM_CURSOR_HAND,
        )

        # Add vertical space
        self.main_menu.add.vertical_margin(250)

        # Add the "Database" button to the main menu (renamed from Users)
        self.main_menu.add.button(
            "Users",
            self.init_users_database,
            align=pygame_menu.locals.ALIGN_RIGHT,
            margin=(-110, 0),
            padding=(0, 0),
            background_color=(0, 0, 0),
            selection_effect=pygame_menu.widgets.LeftArrowSelection(
                arrow_right_margin=15,
                arrow_vertical_offset=0,
            ),
            cursor=pygame.SYSTEM_CURSOR_HAND,
        )

        # Add vertical space
        self.main_menu.add.vertical_margin(50)

        # Add the "Toggle Music" button to the main menu
        self.main_menu.add.button(
            "Toggle Music",
            self.toggle_bg_music,
            align=pygame_menu.locals.ALIGN_RIGHT,
            margin=(-110, 0),
            padding=(0, 0),
            background_color=(0, 0, 0),
            selection_effect=pygame_menu.widgets.LeftArrowSelection(
                arrow_right_margin=15,
                arrow_vertical_offset=0,
            ),
            cursor=pygame.SYSTEM_CURSOR_HAND,
        )

        # Add vertical space
        self.main_menu.add.vertical_margin(50)

        # Add the "Settings" button to the main menu
        self.main_menu.add.button(
            "Settings",
            self.init_settings,
            align=pygame_menu.locals.ALIGN_RIGHT,
            margin=(-110, 0),
            padding=(0, 0),
            background_color=(0, 0, 0),
            selection_effect=pygame_menu.widgets.LeftArrowSelection(
                arrow_right_margin=15,
                arrow_vertical_offset=0,
            ),
            cursor=pygame.SYSTEM_CURSOR_HAND,
        )

        # Add vertical space
        self.main_menu.add.vertical_margin(50)

        # Add the "Credits" button to the main menu
        self.main_menu.add.button(
            "Credits",
            self.init_credits,
            align=pygame_menu.locals.ALIGN_RIGHT,
            margin=(-110, 0),
            padding=(0, 0),
            background_color=(0, 0, 0),
            selection_effect=pygame_menu.widgets.LeftArrowSelection(
                arrow_right_margin=15,
                arrow_vertical_offset=0,
            ),
            cursor=pygame.SYSTEM_CURSOR_HAND,
        )

    def start_main_menu(self):
        # Set the background music for the main menu
        mixer.music.load(f"{CWD}/resources/sounds/main_menu_bg_music.ogg")
        mixer.music.set_volume(0.1)

        # Play the background music
        if not self.bg_music_muted:
            mixer.music.play(-1)

        self.main_menu_running = True
        self.balloons_game_running = False
        self.pong_game_running = False
        self.dino_game_running = False
        self.credits_running = False

        # Set the main menu as the main menu of the game
        self.main_menu.mainloop(self.screen)

    def init_credits(self):
        # Create the credits dialog
        self.credits_dict = {
            "Game Development": "Mohamed Abdelnasser, Abdelrahman Saeed",
            "Graphics": "Mohamed Abdelnasser, Abdelrahman Saeed",
            "Music & SFX": "Mohamed Abdelnasser, Abdelrahman Saeed",
            "Computer Vision": "Mohamed Abdelnasser, Abdelrahman Saeed",
            "Level Design": "Mohamed Abdelnasser, Abdelrahman Saeed",
            "Testing": "Mohamed Abdelnasser, Abdelrahman Saeed",
            "Production": "Mohamed Abdelnasser, Abdelrahman Saeed",
            "Powered by": "Pygame, OpenCV, Mediapipe, CV Zone",
            "3D Models": "No 3D models used",
            "Contact Mohamed": "mohamed.y.abdelnasser@gmail.com",
            "Contact Abdelrahman": "abdosaaed749@gmail.com",
            "Special Thanks": "No one",
        }

        # Load the background image
        self.credits_bg_image = pygame.image.load(
            f"{CWD}/resources/images/credits_bg.png"
        )

        # Resize the background image to fit the screen
        self.credits_bg_image = pygame.transform.scale(
            self.credits_bg_image, (self.user_screen_width, self.user_screen_height)
        )

        self.text_rects = []
        self.texts = []

        # Add the game name to the top center of the screen
        font = pygame.font.Font(self.font_path, 50)
        text = font.render(self.game_name, True, (255, 255, 255), (0, 0, 0))
        self.texts.append(text)
        text_rect = text.get_rect(center=(self.screen.get_width() // 2, 150))
        self.text_rects.append(text_rect)

        # Add the credits to the screen
        font = pygame.font.Font(self.font_path, 30)
        y = 300
        for key, value in self.credits_dict.items():
            text_key = font.render(key, True, (255, 255, 255), (0, 0, 0))
            text_value = font.render(value, True, (255, 255, 255), (0, 0, 0))
            self.texts.append(text_key)
            self.texts.append(text_value)
            text_rect_key = text_key.get_rect(
                center=((self.screen.get_width() // 4) - 100, y)
            )
            text_rect_value = text_value.get_rect(
                center=(
                    ((self.screen.get_width() // 4) * 3 - 200),
                    y,
                )
            )
            self.text_rects.append(text_rect_key)
            self.text_rects.append(text_rect_value)
            self.screen.blit(text, text_rect)
            y += 50

        # Add the "Press ESC to return to the main menu" text to the bottom center of the screen
        text = font.render(
            "Press ESC to return to the main menu",
            True,
            (255, 255, 255),
            (0, 0, 0),
        )
        self.texts.append(text)
        text_rect = text.get_rect(
            center=(self.screen.get_width() // 2, self.screen.get_height() - 100)
        )
        self.text_rects.append(text_rect)

        # Start the credits dialog
        self.start_credits()

    def start_credits(self):

        # Set the credits dialog as running
        self.credits_running = True
        self.balloons_game_running = False
        self.main_menu_running = False
        self.pong_game_running = False

        is_space = False

        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    exit()

                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.start_main_menu()

                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_SPACE:
                        is_space = True

            # Draw the credits background image to the screen
            self.screen.blit(
                self.credits_bg_image,
                (
                    self.screen.get_width() / 2 - self.credits_bg_image.get_width() / 2,
                    self.screen.get_height() / 2
                    - self.credits_bg_image.get_height() / 2,
                ),
            )

            # Make the credits scroll
            for text, text_rect in zip(self.texts, self.text_rects):
                self.screen.blit(text, text_rect)

                if is_space:
                    text_rect.y -= 1
                if text_rect.y < 0:
                    text_rect.y = self.screen.get_height()

            # Update the display
            pygame.display.flip()

    def toggle_bg_music(self):
        # Mute or unmute the background music
        if self.bg_music_muted:
            self.unmute_bg_music()
            self.bg_music_muted = False
        else:
            self.mute_bg_music()
            self.bg_music_muted = True

    def mute_bg_music(self):
        # Mute the background music
        mixer.music.set_volume(0)

    def unmute_bg_music(self):
        # Unmute the background music
        mixer.music.set_volume(0.1)

    def init_balloons_game(self):
        # Set the background music for the main menu
        mixer.music.load(f"{CWD}/resources/sounds/balloon_game_bg_music.ogg")
        mixer.music.set_volume(0.1)

        # Play the background music
        if not self.bg_music_muted:
            mixer.music.play(-1)

        # Load the balloon popping sounds
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
        for sound in self.balloon_popping_sounds:
            sound.set_volume(0.2)

        self.balloon_game_over_sound = mixer.Sound(
            f"{CWD}/resources/sounds/game-over.ogg"
        )
        self.balloon_game_over_sound.set_volume(0.5)

        # Load the balloon popping fill sounds
        self.balloon_popping_fill_sounds = mixer.Sound(
            f"{CWD}/resources/sounds/balloon-inflation.ogg"
        )
        self.balloon_popping_fill_sounds.set_volume(0.2)

        # Initialize the background image for the Balloons game
        self.balloons_game_bg_image = cv2.imread(
            f"{CWD}/resources/images/balloons_game_bg.png"
        )

        # Swap the color channels
        self.balloons_game_bg_image = cv2.cvtColor(
            self.balloons_game_bg_image, cv2.COLOR_BGR2RGB
        )

        # Add alpha channel to the background image
        self.balloons_game_bg_image = cv2.cvtColor(
            self.balloons_game_bg_image, cv2.COLOR_RGB2RGBA
        )

        # Initialize the pin image
        self.pin_image = pygame.image.load(f"{CWD}/resources/images/pin.png")

        # Make the pin image smaller
        self.pin_image = pygame.transform.scale(self.pin_image, (70, 70))

        # Initialize the balloons list
        self.balloons = []

        # Set the main menu as not running and the Balloons game as running
        self.main_menu_running = False
        self.balloons_game_running = True
        self.pong_game_running = False
        self.credits_running = False

        # Take an initial camera image
        _, self.camera_image = self.cap.read()

        # Initialize the Balloons game screen ratio
        self.balloon_screen_ratio = 2.5

        # Scale the camera image to be half the size of the screen
        self.camera_image = cv2.resize(
            self.camera_image,
            (
                int(self.user_screen_width // self.balloon_screen_ratio),
                int(self.user_screen_height // self.balloon_screen_ratio),
            ),
        )

        # Add rounded corners to the camera image
        self.camera_image = img_with_rounded_corners(
            self.camera_image, 30, 2, (0, 0, 0)
        )

        # Set the entire camera image to be black
        self.camera_image[:, :] = 0

        # Get the camera image dimensions and the background image dimensions
        bg_height, bg_width, _ = self.balloons_game_bg_image.shape
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
        self.scale_x_cam = self.user_screen_width / self.balloons_game_bg_image.shape[1]
        self.scale_y_cam = (
            self.user_screen_height / self.balloons_game_bg_image.shape[0]
        )

        # Initialize the translate value for x and y
        self.translation_x_cam = int(self.start_x_cam * self.scale_x_cam)
        self.translation_y_cam = int(self.start_y_cam * self.scale_y_cam)

        # Initialize the score
        self.balloons_score = 0

        # Initialize the wave
        self.balloons_wave = 1

        # Initialize the max number of waves
        self.max_balloons_waves = 5

        # Initialize the max wave time
        self.max_wave_time = 20

        # Initialize the wave wait time
        self.balloon_wave_wait_time = 3
        self.balloon_first_wave_wait_time = 10

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

        self.waves_balloons = []

        for wave_number in range(self.max_balloons_waves):
            balloons = []
            for _ in range(
                random.randint(
                    ballons_number_per_wave[wave_number][0],
                    ballons_number_per_wave[wave_number][1],
                )
            ):
                is_combo = random_bool_by_chance(
                    ballons_combo_probability_per_wave[wave_number]
                )

                balloon_img_path = (
                    random.choice(combo_balloon_image_paths)
                    if is_combo
                    else random.choice(normal_balloon_image_paths)
                )
                balloon_img = pygame.image.load(balloon_img_path)
                balloon_img = pygame.transform.scale(balloon_img, (250, 250))
                balloon_rect = balloon_img.get_rect()

                # Randomize the balloon rect position
                balloon_rect.update(
                    (
                        random.randint(0, self.end_x_cam) + self.start_x_cam + 110,
                        self.end_y_cam + 100,
                        100,
                        100,
                    )
                )

                speed = (
                    random.randint(
                        combo_ballons_speed_per_wave[wave_number][0],
                        combo_ballons_speed_per_wave[wave_number][1],
                    )
                    if is_combo
                    else random.randint(
                        normal_ballons_speed_per_wave[wave_number][0],
                        normal_ballons_speed_per_wave[wave_number][1],
                    )
                )
                apperance_time = biased_random_int(
                    0, self.max_wave_time, (0, self.max_wave_time // 2), 10
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
            self.waves_balloons.append(balloons)

    def start_balloons_game_timer(self):

        if self.balloons_wave > self.max_balloons_waves:
            self.end_balloons_game()

        # Add a start timer for the game
        start_time = time.time()

        # Play the balloon popping fill sound
        self.balloon_popping_fill_sounds.play()

        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    exit()

                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.start_main_menu()

            # Convert the background image to a Pygame image
            self.balloons_game_bg_image_pygame = pygame.image.frombuffer(
                self.balloons_game_bg_image.tobytes(),
                (
                    self.balloons_game_bg_image.shape[1],
                    self.balloons_game_bg_image.shape[0],
                ),
                "RGBA",
            )

            # Resize the background image to fit the screen
            self.balloons_game_bg_image_pygame = pygame.transform.scale(
                self.balloons_game_bg_image_pygame,
                (self.user_screen_width, self.user_screen_height),
            )

            # Draw the balloon game background image to the center of the screen
            self.screen.blit(
                self.balloons_game_bg_image_pygame,
                (
                    self.screen.get_width() / 2
                    - self.balloons_game_bg_image_pygame.get_width() / 2,
                    self.screen.get_height() / 2
                    - self.balloons_game_bg_image_pygame.get_height() / 2,
                ),
            )

            time_elapsed = int(time.time() - start_time)
            other_time_remaining = self.balloon_wave_wait_time - time_elapsed
            wave_1_time_remaining = self.balloon_first_wave_wait_time - time_elapsed

            time_remaining = (
                other_time_remaining
                if self.balloons_wave != 1
                else wave_1_time_remaining
            )

            # Add the timer to the center of the screen
            font = pygame.font.Font(self.font_path, 40)
            text = font.render(
                f"Wave {self.balloons_wave} starts in {time_remaining} seconds",
                True,
                (255, 255, 255),
                (0, 0, 0),
            )
            if self.balloons_wave == 1:
                text_rect = text.get_rect(
                    center=(
                        self.screen.get_width() // 2,
                        self.screen.get_height() // 2 - 200,
                    )
                )
            else:
                text_rect = text.get_rect(
                    center=(
                        self.screen.get_width() // 2,
                        self.screen.get_height() // 2,
                    )
                )
            self.screen.blit(text, text_rect)

            # Add the game name to the top center of the screen
            font = pygame.font.Font(self.font_path, 50)
            text = font.render("Balloons Game", True, (255, 255, 255), (0, 0, 0))
            text_rect = text.get_rect(center=(self.screen.get_width() // 2, 150))
            self.screen.blit(text, text_rect)

            # Show instructions if the wave is 1
            if self.balloons_wave == 1:
                font = pygame.font.Font(self.font_path, 30)
                text = font.render(
                    "Pop the balloons with your fingers",
                    True,
                    (255, 255, 255),
                    (0, 0, 0),
                )
                text_rect = text.get_rect(
                    center=(
                        self.screen.get_width() // 2,
                        self.screen.get_height() // 2,
                    )
                )
                self.screen.blit(text, text_rect)

                text = font.render(
                    "Single balloons give 1 point",
                    True,
                    (255, 255, 255),
                    (0, 0, 0),
                )
                text_rect = text.get_rect(
                    center=(
                        self.screen.get_width() // 2,
                        self.screen.get_height() // 2 + 50,
                    )
                )
                self.screen.blit(text, text_rect)

                text = font.render(
                    "Combo balloons give points based on the number of the balloons",
                    True,
                    (255, 255, 255),
                    (0, 0, 0),
                )
                text_rect = text.get_rect(
                    center=(
                        self.screen.get_width() // 2,
                        self.screen.get_height() // 2 + 100,
                    )
                )
                self.screen.blit(text, text_rect)

                text = font.render(
                    "If you miss a normal balloon you lose a point",
                    True,
                    (255, 255, 255),
                    (0, 0, 0),
                )
                text_rect = text.get_rect(
                    center=(
                        self.screen.get_width() // 2,
                        self.screen.get_height() // 2 + 150,
                    )
                )
                self.screen.blit(text, text_rect)

                text = font.render(
                    "Total of 5 waves with 20 seconds each",
                    True,
                    (255, 255, 255),
                    (0, 0, 0),
                )
                text_rect = text.get_rect(
                    center=(
                        self.screen.get_width() // 2,
                        self.screen.get_height() // 2 + 200,
                    )
                )
                self.screen.blit(text, text_rect)

                text = font.render(
                    "Press ESC anytime to return to the main menu",
                    True,
                    (255, 255, 255),
                    (0, 0, 0),
                )
                text_rect = text.get_rect(
                    center=(
                        self.screen.get_width() // 2,
                        self.screen.get_height() // 2 + 250,
                    )
                )
                self.screen.blit(text, text_rect)

            # Update the display
            pygame.display.flip()

            if time_remaining <= 0:
                break

        time.sleep(1)

        # Start the Balloons game
        self.start_balloons_game()

    def start_balloons_game(self):

        start_time = time.time()

        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    exit()

                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.start_main_menu()

            # Take a camera image
            _, self.camera_image = self.cap.read()

            # Swap the color channels
            self.camera_image = cv2.cvtColor(self.camera_image, cv2.COLOR_BGR2RGB)

            # Flip the camera image horizontally
            self.camera_image = cv2.flip(self.camera_image, 1)

            # Scale the camera image to be half the size of the screen
            self.camera_image = cv2.resize(
                self.camera_image,
                (
                    int(self.user_screen_width // self.balloon_screen_ratio),
                    int(self.user_screen_height // self.balloon_screen_ratio),
                ),
            )

            # Get the right and left hand centers
            hands_data = detect_hands(self.finger_detector, self.camera_image)
            try:
                fingers_centers_right = hands_data["right_hand"]["fingers_centers"]
            except:
                fingers_centers_right = [(-1, -1) for _ in range(5)]

            try:
                fingers_centers_left = hands_data["left_hand"]["fingers_centers"]
            except:
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

            # Add rounded corners to the camera image
            self.camera_image = img_with_rounded_corners(
                self.camera_image, 30, 2, (0, 0, 0)
            )

            # Initialize the edited background image
            self.balloons_game_bg_image_edited = self.balloons_game_bg_image.copy()

            # Add the camera image to the background image
            self.balloons_game_bg_image_edited[
                self.start_y_cam : self.end_y_cam, self.start_x_cam : self.end_x_cam
            ] = self.camera_image

            # Convert the background image to a Pygame image
            self.balloons_game_bg_image_pygame = pygame.image.frombuffer(
                self.balloons_game_bg_image_edited.tobytes(),
                (
                    self.balloons_game_bg_image.shape[1],
                    self.balloons_game_bg_image.shape[0],
                ),
                "RGBA",
            )

            # Resize the background image to fit the screen
            self.balloons_game_bg_image_pygame = pygame.transform.scale(
                self.balloons_game_bg_image_pygame,
                (self.user_screen_width, self.user_screen_height),
            )

            # Draw the balloon game background image to the center of the screen
            self.screen.blit(
                self.balloons_game_bg_image_pygame,
                (
                    self.screen.get_width() / 2
                    - self.balloons_game_bg_image_pygame.get_width() / 2,
                    self.screen.get_height() / 2
                    - self.balloons_game_bg_image_pygame.get_height() / 2,
                ),
            )

            # Draw the pins on the fingers centers
            for finger_rect in fingers_centers_rects:
                self.screen.blit(
                    self.pin_image,
                    (finger_rect.left - 40, finger_rect.top - 30),
                )

            # Add score to the screen
            font = pygame.font.Font(self.font_path, 36)
            text = font.render(
                f"Score:{self.balloons_score}",
                True,
                (255, 255, 255),
                (0, 0, 0),
            )
            self.screen.blit(text, (30, (self.screen.get_height() // 2 - 20)))

            # Calculate the elapsed time
            elapsed_time = int(time.time() - start_time)

            # Add time to the screen
            text = font.render(
                f"Time:{elapsed_time}",
                True,
                (255, 255, 255),
                (0, 0, 0),
            )
            self.screen.blit(text, (30, (self.screen.get_height() // 2 + 50)))

            # Add wave to the screen
            text = font.render(
                f"Wave:{self.balloons_wave}",
                True,
                (255, 255, 255),
                (0, 0, 0),
            )
            self.screen.blit(text, (30, (self.screen.get_height() // 2 + 120)))

            # Add game name to the top center of the screen
            font = pygame.font.Font(self.font_path, 50)
            text = font.render("Balloons Game", True, (255, 255, 255), (0, 0, 0))
            text_rect = text.get_rect(center=(self.screen.get_width() // 2, 150))
            self.screen.blit(text, text_rect)

            # Get the current wave balloons
            balloons = self.waves_balloons[self.balloons_wave - 1]

            # Sort the balloons by appearance time
            balloons.sort(key=lambda x: x["time"])

            # Draw random balloons that move up the screen
            for balloon in balloons:
                # Skip the balloon if its appearance time has not come yet
                if elapsed_time < balloon["time"]:
                    continue

                if balloon["is_popped"]:
                    continue

                # Remove the balloon if it goes off the screen
                if balloon["rect"].top <= self.start_y_cam + balloon["rect"].height:

                    # Remove a point if the balloon is not a combo balloon
                    if not balloon["is_combo"]:
                        self.balloons_score = max(0, self.balloons_score - 1)

                    balloon["is_popped"] = True
                    random.choice(self.balloon_popping_sounds).play()
                    break

                # Move the balloon up the screen and draw it
                balloon["rect"].move_ip(0, -balloon["speed"])
                self.screen.blit(
                    balloon["image"],
                    (balloon["rect"].left - 70, balloon["rect"].top - 40),
                )

                # Check if the balloon is popped by the fingers
                for finger_rect in fingers_centers_rects:
                    if balloon["rect"].colliderect(finger_rect):
                        if balloon["type"] == 1:
                            self.balloons_score = max(0, self.balloons_score + 2)
                        elif balloon["type"] == 2:
                            self.balloons_score = max(0, self.balloons_score + 3)
                        elif balloon["type"] == 3:
                            self.balloons_score = max(0, self.balloons_score + 5)
                        else:
                            self.balloons_score = max(0, self.balloons_score + 1)

                        balloon["is_popped"] = True
                        random.choice(self.balloon_popping_sounds).play()
                        break

            # Check if the balloons are all popped or the wave time is over
            if len(balloons) == 0 or elapsed_time > self.max_wave_time:
                self.balloons_wave += 1
                self.start_balloons_game_timer()
                break

            # Update the display
            pygame.display.flip()

            # Update the clock and delta time
            self.dt = self.clock.tick(30) / 1000

    def end_balloons_game(self):
        # Play the game over sound
        self.balloon_game_over_sound.play()

        self.balloons_score = max(0, self.balloons_score)

        while True:
            # Convert the background image to a Pygame image
            self.balloons_game_bg_image_pygame = pygame.image.frombuffer(
                self.balloons_game_bg_image.tobytes(),
                (
                    self.balloons_game_bg_image.shape[1],
                    self.balloons_game_bg_image.shape[0],
                ),
                "RGBA",
            )

            # Resize the background image to fit the screen
            self.balloons_game_bg_image_pygame = pygame.transform.scale(
                self.balloons_game_bg_image_pygame,
                (self.user_screen_width, self.user_screen_height),
            )

            # Draw the balloon game background image to the center of the screen
            self.screen.blit(
                self.balloons_game_bg_image_pygame,
                (
                    self.screen.get_width() / 2
                    - self.balloons_game_bg_image_pygame.get_width() / 2,
                    self.screen.get_height() / 2
                    - self.balloons_game_bg_image_pygame.get_height() / 2,
                ),
            )

            # Draw the balloon game background image to the center of the screen
            self.screen.blit(
                self.balloons_game_bg_image_pygame,
                (
                    self.screen.get_width() / 2
                    - self.balloons_game_bg_image_pygame.get_width() / 2,
                    self.screen.get_height() / 2
                    - self.balloons_game_bg_image_pygame.get_height() / 2,
                ),
            )

            # Add the game over text to the top of the screen
            font = pygame.font.Font(self.font_path, 50)
            text = font.render(
                f"Game Over",
                True,
                (255, 255, 255),
                (0, 0, 0),
            )
            text_rect = text.get_rect(
                center=(
                    self.screen.get_width() // 2,
                    self.screen.get_height() // 2 - 50,
                )
            )
            self.screen.blit(text, text_rect)

            # Add the score to the center of the screen
            font = pygame.font.Font(self.font_path, 36)
            text = font.render(
                f"Score:{self.balloons_score}",
                True,
                (255, 255, 255),
                (0, 0, 0),
            )
            text_rect = text.get_rect(
                center=(
                    self.screen.get_width() // 2,
                    self.screen.get_height() // 2 + 70,
                )
            )
            self.screen.blit(text, text_rect)

            # Add "Press ESC to return to the main menu" to the center of the screen
            font = pygame.font.Font(self.font_path, 24)
            text = font.render(
                f"Press ESC to return to the main menu",
                True,
                (255, 255, 255),
                (0, 0, 0),
            )
            text_rect = text.get_rect(
                center=(
                    self.screen.get_width() // 2,
                    self.screen.get_height() - 50,
                )
            )
            self.screen.blit(text, text_rect)

            # Update the display
            pygame.display.flip()

            # If the user presses the escape key, return to the main menu
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    exit()

                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.start_main_menu()

    def init_pong_game(self):

        # Set the background music for the main menu
        mixer.music.load(f"{CWD}/resources/sounds/pong_game_bg_music.ogg")
        mixer.music.set_volume(0.1)

        # Play the background music
        if not self.bg_music_muted:
            mixer.music.play(-1)

        # Initialize the background image for the Pong game
        self.pong_game_bg_image = cv2.imread(f"{CWD}/resources/images/pong_game_bg.png")

        # Swap the color channels
        self.pong_game_bg_image = cv2.cvtColor(
            self.pong_game_bg_image, cv2.COLOR_BGR2RGB
        )

        # Add alpha channel to the background image
        self.pong_game_bg_image = cv2.cvtColor(
            self.pong_game_bg_image, cv2.COLOR_RGB2RGBA
        )

        # Initialize the ball radius
        self.ball_raduis = 10

        # Initialize the ball speed
        self.ball_speed_x = random.choice([-7, 7])
        self.ball_speed_y = random.choice([-7, 7])

        # Initialize the paddle dimensions
        self.paddle_width = 10
        self.paddle_height = 80

        # Initialize the speed
        self.speed_increment_interval = 7
        self.speed_increment = 3

        # Initialize the scores
        self.player1_score = 0
        self.player2_score = 0

        # Set the main menu as not running and the Pong game as running
        self.main_menu_running = False
        self.balloons_game_running = False
        self.pong_game_running = True
        self.credits_running = False

        # Take an initial camera image
        _, self.camera_image = self.cap.read()

        # Initialize the screen ratio
        self.pong_screen_ratio = 3.5

        # Scale the camera image to be a third of the size of the screen
        self.camera_image = cv2.resize(
            self.camera_image,
            (
                int(self.user_screen_width // self.pong_screen_ratio),
                int(self.user_screen_height // self.pong_screen_ratio),
            ),
        )

        # Add rounded corners to the camera image
        self.camera_image = img_with_rounded_corners(
            self.camera_image, 30, 2, (0, 0, 0)
        )

        # Set the entire camera image to be black
        self.camera_image[:, :] = 0

        # Get the camera image dimensions and the background image dimensions
        bg_height, bg_width, _ = self.pong_game_bg_image.shape
        image_height, image_width, _ = self.camera_image.shape

        # Calculate the top-left coordinates for the camera image
        top_left_x = (bg_width - image_width) // 2
        top_left_y = (bg_height - image_height) // 2

        # Calculate the start and end coordinates for the camera image
        self.start_x_cam = top_left_x + 300
        self.start_y_cam = top_left_y + 100
        self.end_x_cam = top_left_x + image_width + 300
        self.end_y_cam = top_left_y + image_height + 100

        # Initialize the scale value for x and y
        self.scale_x_cam = self.user_screen_width / self.pong_game_bg_image.shape[1]
        self.scale_y_cam = self.user_screen_height / self.pong_game_bg_image.shape[0]

        # Initialize the translate value for x and y
        self.translation_x_cam = int(self.start_x_cam * self.scale_x_cam)
        self.translation_y_cam = int(self.start_y_cam * self.scale_y_cam)

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
        self.pong_first_wave_wait_time = 10

        # Load hit sounds
        self.hit_sounds = [
            mixer.Sound(f"{CWD}/resources/sounds/ball-hit-1.ogg"),
            mixer.Sound(f"{CWD}/resources/sounds/ball-hit-2.ogg"),
            mixer.Sound(f"{CWD}/resources/sounds/ball-hit-3.ogg"),
            mixer.Sound(f"{CWD}/resources/sounds/ball-hit-4.ogg"),
            mixer.Sound(f"{CWD}/resources/sounds/ball-hit-5.ogg"),
            mixer.Sound(f"{CWD}/resources/sounds/ball-hit-6.ogg"),
        ]
        for sound in self.hit_sounds:
            sound.set_volume(0.2)

        # Load whistle sound
        self.point_whistle_sound = mixer.Sound(
            f"{CWD}/resources/sounds/referee-whistle-1.ogg"
        )
        self.pong_game_over_sound = mixer.Sound(
            f"{CWD}/resources/sounds/referee-whistle-2.ogg"
        )
        self.point_whistle_sound.set_volume(0.2)
        self.pong_game_over_sound.set_volume(0.5)

        # Load game over sound
        self.ball_drop_sound = mixer.Sound(f"{CWD}/resources/sounds/ball-dropping.ogg")
        self.ball_drop_sound.set_volume(0.2)

        # Initialize the max score
        # self.max_score = 7
        self.max_score = 1  #!

        # Start the Pong game timer
        self.start_pong_game_timer()

    def start_pong_game_timer(self):
        # Add a start timer for the game
        start_time = time.time()

        # Play the ball drop sound
        self.ball_drop_sound.play()

        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    exit()

                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.start_main_menu()

            # Convert the background image to a Pygame image
            self.pong_game_bg_image_pygame = pygame.image.frombuffer(
                self.pong_game_bg_image.tobytes(),
                (
                    self.pong_game_bg_image.shape[1],
                    self.pong_game_bg_image.shape[0],
                ),
                "RGBA",
            )

            # Resize the background image to fit the screen
            self.pong_game_bg_image_pygame = pygame.transform.scale(
                self.pong_game_bg_image_pygame,
                (self.user_screen_width, self.user_screen_height),
            )

            # Draw the Pong game background image to the center of the screen
            self.screen.blit(
                self.pong_game_bg_image_pygame,
                (
                    self.screen.get_width() / 2
                    - self.pong_game_bg_image_pygame.get_width() / 2,
                    self.screen.get_height() / 2
                    - self.pong_game_bg_image_pygame.get_height() / 2,
                ),
            )

            time_elapsed = int(time.time() - start_time)
            time_remaining = self.pong_first_wave_wait_time - time_elapsed

            # Add the timer to the center of the screen
            font = pygame.font.Font(self.font_path, 40)
            text = font.render(
                f"Game starts in {time_remaining} seconds",
                True,
                (255, 255, 255),
                (0, 0, 0),
            )
            text_rect = text.get_rect(
                center=(
                    self.screen.get_width() // 2,
                    self.screen.get_height() // 2 - 200,
                )
            )
            self.screen.blit(text, text_rect)

            # Add the game name to the top center of the screen
            font = pygame.font.Font(self.font_path, 50)
            text = font.render("Pong Game", True, (255, 255, 255), (0, 0, 0))
            text_rect = text.get_rect(center=(self.screen.get_width() // 2, 150))
            self.screen.blit(text, text_rect)

            # Show instructions
            font = pygame.font.Font(self.font_path, 30)
            text = font.render(
                "Move the paddles with your hands",
                True,
                (255, 255, 255),
                (0, 0, 0),
            )
            text_rect = text.get_rect(
                center=(
                    self.screen.get_width() // 2,
                    self.screen.get_height() // 2,
                )
            )
            self.screen.blit(text, text_rect)

            text = font.render(
                "Each player controls a paddle on their side",
                True,
                (255, 255, 255),
                (0, 0, 0),
            )
            text_rect = text.get_rect(
                center=(
                    self.screen.get_width() // 2,
                    self.screen.get_height() // 2 + 50,
                )
            )
            self.screen.blit(text, text_rect)

            text = font.render(
                "Each player gets a point if the ball goes past the other player's paddle",
                True,
                (255, 255, 255),
                (0, 0, 0),
            )
            text_rect = text.get_rect(
                center=(
                    self.screen.get_width() // 2,
                    self.screen.get_height() // 2 + 100,
                )
            )
            self.screen.blit(text, text_rect)

            text = font.render(
                f"First player to reach {self.max_score} points wins",
                True,
                (255, 255, 255),
                (0, 0, 0),
            )
            text_rect = text.get_rect(
                center=(
                    self.screen.get_width() // 2,
                    self.screen.get_height() // 2 + 150,
                )
            )
            self.screen.blit(text, text_rect)

            text = font.render(
                "Press ESC anytime to return to the main menu",
                True,
                (255, 255, 255),
                (0, 0, 0),
            )
            text_rect = text.get_rect(
                center=(
                    self.screen.get_width() // 2,
                    self.screen.get_height() // 2 + 200,
                )
            )
            self.screen.blit(text, text_rect)

            # Update the display
            pygame.display.flip()

            if time_remaining <= 0:
                break

        time.sleep(1)

        # Start the Pong game
        self.start_pong_game()

    def start_pong_game(self):

        round_start_time = time.time()

        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    exit()

                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.start_main_menu()

            # Increase the ball speed every interval
            current_time = time.time()
            if current_time - round_start_time > self.speed_increment_interval:
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
                round_start_time = current_time

            # Take a camera image
            _, self.camera_image = self.cap.read()

            # Swap the color channels
            self.camera_image = cv2.cvtColor(self.camera_image, cv2.COLOR_BGR2RGB)

            # Flip the camera image horizontally
            self.camera_image = cv2.flip(self.camera_image, 1)

            # Scale the camera image to be a third of the size of the screen
            self.camera_image = cv2.resize(
                self.camera_image,
                (
                    int(self.user_screen_width // self.pong_screen_ratio),
                    int(self.user_screen_height // self.pong_screen_ratio),
                ),
            )

            is_left_hand = False
            is_right_hand = False

            # Get the hands data
            self.camera_image = self.hand_tracking.findFingers(self.camera_image)
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

                if self.paddle1_y < self.play_field_rect.height:
                    self.paddle1_y = self.play_field_rect.height + 10
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

                if self.paddle2_y < self.play_field_rect.height:
                    self.paddle2_y = self.play_field_rect.height + 10
                elif self.paddle2_y > self.play_field_rect.bottom - 75:
                    self.paddle2_y = (
                        self.play_field_rect.bottom - self.paddle_height - 10 - 10
                    )

            # Change the ball speed based on the ball direction
            self.ball_x += self.ball_speed_x
            self.ball_y += self.ball_speed_y

            # Check if the ball hits the top or bottom of the screen
            if self.ball_y <= self.play_field_rect.height + self.ball_raduis:
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

            # Check if the ball hits the left or right of the screen
            if self.ball_x <= self.play_field_rect.left + self.ball_raduis:
                self.point_whistle_sound.play()
                self.player2_score += 1
                self.ball_x = self.play_field_rect.centerx
                self.ball_y = self.play_field_rect.centery
                self.ball_speed_x = random.choice([-7, 7])
                self.ball_speed_y = random.choice([-7, 7])
                round_start_time = time.time()

            elif self.ball_x >= self.play_field_rect.right - self.ball_raduis:
                self.point_whistle_sound.play()
                self.player1_score += 1
                self.ball_x = self.play_field_rect.centerx
                self.ball_y = self.play_field_rect.centery
                self.ball_speed_x = random.choice([-7, 7])
                self.ball_speed_y = random.choice([-7, 7])
                round_start_time = time.time()

            # Add rounded corners to the camera image
            self.camera_image = img_with_rounded_corners(
                self.camera_image, 30, 2, (0, 0, 0)
            )

            # Initialize the edited background image
            self.pong_game_bg_image_edited = self.pong_game_bg_image.copy()

            # Add the camera image to the background image
            self.pong_game_bg_image_edited[
                self.start_y_cam : self.end_y_cam, self.start_x_cam : self.end_x_cam
            ] = self.camera_image

            # Convert the background image to a Pygame image
            self.pong_game_bg_image_pygame = pygame.image.frombuffer(
                self.pong_game_bg_image_edited.tobytes(),
                (
                    self.pong_game_bg_image.shape[1],
                    self.pong_game_bg_image.shape[0],
                ),
                "RGBA",
            )

            # Resize the background image to fit the screen
            self.pong_game_bg_image_pygame = pygame.transform.scale(
                self.pong_game_bg_image_pygame,
                (self.user_screen_width, self.user_screen_height),
            )

            # Draw the Pong game background image to the center of the screen
            self.screen.blit(
                self.pong_game_bg_image_pygame,
                (
                    self.screen.get_width() / 2
                    - self.pong_game_bg_image_pygame.get_width() / 2,
                    self.screen.get_height() / 2
                    - self.pong_game_bg_image_pygame.get_height() / 2,
                ),
            )

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

            # Add game name to the top center of the screen
            font = pygame.font.Font(self.font_path, 50)
            text = font.render("Pong Game", True, (255, 255, 255), (0, 0, 0))
            text_rect = text.get_rect(center=(self.screen.get_width() // 2, 150))
            self.screen.blit(text, text_rect)

            # Add player scores to the top left and right of the play field
            # Todo: Add player names
            font = pygame.font.Font(self.font_path, 30)
            text = font.render(
                f"Player 1: {self.player1_score}",
                True,
                (255, 255, 255),
                (0, 0, 0),
            )
            self.screen.blit(
                text,
                (
                    self.start_x_play_field + 20,
                    self.start_y_play_field - text.get_height() - 20,
                ),
            )

            text = font.render(
                f"Player 2: {self.player2_score}",
                True,
                (255, 255, 255),
                (0, 0, 0),
            )
            self.screen.blit(
                text,
                (
                    self.start_x_play_field
                    + self.play_field_rect.width
                    - text.get_width()
                    - 20,
                    self.start_y_play_field - text.get_height() - 20,
                ),
            )

            # Add hands detected text to the left and right of the camera image
            font = pygame.font.Font(self.font_path, 30)
            if is_left_hand:
                text = font.render(
                    "Player 1",
                    True,
                    (0, 255, 0),
                    (0, 0, 0),
                )
            else:
                text = font.render(
                    "Player 1",
                    True,
                    (255, 0, 0),
                    (0, 0, 0),
                )
            self.screen.blit(
                text,
                (
                    (self.translation_x_cam + 20),
                    self.start_y_play_field - text.get_height() - 20,
                ),
            )

            if is_right_hand:
                text = font.render(
                    "Player 2",
                    True,
                    (0, 255, 0),
                    (0, 0, 0),
                )
            else:
                text = font.render(
                    "Player 2",
                    True,
                    (255, 0, 0),
                    (0, 0, 0),
                )
            self.screen.blit(
                text,
                (
                    self.translation_x_cam
                    + self.play_field_rect.width
                    - text.get_width()
                    - 20,
                    self.start_y_play_field - text.get_height() - 20,
                ),
            )

            if (
                self.player1_score == self.max_score
                or self.player2_score == self.max_score
            ):
                self.end_pong_game()
                break

            # Update the display
            pygame.display.flip()

            # Update the clock and delta time
            self.dt = self.clock.tick(30) / 1000

    def end_pong_game(self):
        # Play the game over sound
        self.pong_game_over_sound.play()

        # Get the winner
        winner = "Player 1" if self.player1_score == self.max_score else "Player 2"

        while True:
            # Convert the background image to a Pygame image
            self.pong_game_bg_image_pygame = pygame.image.frombuffer(
                self.pong_game_bg_image.tobytes(),
                (
                    self.pong_game_bg_image.shape[1],
                    self.pong_game_bg_image.shape[0],
                ),
                "RGBA",
            )

            # Resize the background image to fit the screen
            self.pong_game_bg_image_pygame = pygame.transform.scale(
                self.pong_game_bg_image_pygame,
                (self.user_screen_width, self.user_screen_height),
            )

            # Draw the Pong game background image to the center of the screen
            self.screen.blit(
                self.pong_game_bg_image_pygame,
                (
                    self.screen.get_width() / 2
                    - self.pong_game_bg_image_pygame.get_width() / 2,
                    self.screen.get_height() / 2
                    - self.pong_game_bg_image_pygame.get_height() / 2,
                ),
            )

            # Add the game over text to the top of the screen
            font = pygame.font.Font(self.font_path, 50)
            text = font.render(
                f"Game Over",
                True,
                (255, 255, 255),
                (0, 0, 0),
            )
            text_rect = text.get_rect(
                center=(
                    self.screen.get_width() // 2,
                    self.screen.get_height() // 2 - 50,
                )
            )
            self.screen.blit(text, text_rect)

            # Add the winner to the center of the screen
            font = pygame.font.Font(self.font_path, 36)
            text = font.render(
                f"{winner} wins",
                True,
                (255, 255, 255),
                (0, 0, 0),
            )
            text_rect = text.get_rect(
                center=(
                    self.screen.get_width() // 2,
                    self.screen.get_height() // 2 + 70,
                )
            )
            self.screen.blit(text, text_rect)

            # Add "Press ESC to return to the main menu" to the center of the screen
            font = pygame.font.Font(self.font_path, 24)
            text = font.render(
                f"Press ESC to return to the main menu",
                True,
                (255, 255, 255),
                (0, 0, 0),
            )
            text_rect = text.get_rect(
                center=(
                    self.screen.get_width() // 2,
                    self.screen.get_height() - 50,
                )
            )

            self.screen.blit(text, text_rect)

            # Update the display
            pygame.display.flip()

            # If the user presses the escape key, return to the main menu
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    exit()

                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.start_main_menu()

    def init_dino_game(self):
        # Set game state
        self.main_menu_running = False
        self.balloons_game_running = False
        self.pong_game_running = False
        self.dino_game_running = False
        self.credits_running = False
        self.dino_game_running = True
        
        # Set the background music for the Dino game
        mixer.music.load(f"{CWD}/resources/sounds/main_menu_bg_music.ogg")  # Replace with dino game music if available
        mixer.music.set_volume(0.1)
        
        # Play the background music
        if not self.bg_music_muted:
            mixer.music.play(-1)
            
        # Load the ball drop sound if it's not already loaded
        if not hasattr(self, 'ball_drop_sound'):
            self.ball_drop_sound = mixer.Sound(f"{CWD}/resources/sounds/ball-dropping.ogg")
            self.ball_drop_sound.set_volume(0.2)
            
        # Initialize the background image for the game (using Pong's background for consistency)
        if not hasattr(self, 'pong_game_bg_image'):
            self.pong_game_bg_image = cv2.imread(f"{CWD}/resources/images/pong_game_bg.png")
            # Swap the color channels
            self.pong_game_bg_image = cv2.cvtColor(self.pong_game_bg_image, cv2.COLOR_BGR2RGB)
            # Add alpha channel to the background image
            self.pong_game_bg_image = cv2.cvtColor(self.pong_game_bg_image, cv2.COLOR_RGB2RGBA)
            
        # Initialize the wave wait time
        self.pong_first_wave_wait_time = 5  # Using 5 seconds for dino game timer (shorter than Pong's 10 seconds)
            
        # Import dino game module
        from .dino_game import run_dino_game
        print("Starting Dino game...")
        print("Use UP arrow/SPACE to jump and DOWN arrow to duck")
        
        # Create a fullscreen window for the game
        self.original_width = self.screen.get_width()
        self.original_height = self.screen.get_height()
        
        # Get current monitor resolution
        from screeninfo import get_monitors
        try:
            user_screen = get_monitors()[self.user_screen_number]
            screen_width = user_screen.width
            screen_height = user_screen.height
            print(f"Setting up fullscreen Dino game: {screen_width}x{screen_height}")
        except Exception as e:
            print(f"Error getting monitor info: {e}, using default resolution")
            screen_width = 1920
            screen_height = 1080
            
        # Center the game window on the display
        import os
        display_width, display_height = self.user_screen_width, self.user_screen_height

        # Calculate the position to center the window
        x_position = (display_width - screen_width) // 2
        y_position = (display_height - screen_height) // 2

        # First hide any previous pygame windows
        pygame.display.quit()
        
        # Initialize display system with SDL variables for positioning
        pygame.display.init()
        
        # Set environment variables for window position
        # NOTE: SDL_VIDEO_CENTERED is now set right before creating the wide_screen below
        
        # Create a borderless window with your current desktop resolution
        # This will make it fill the screen but still be centered properly
        from screeninfo import get_monitors
        user_screen = get_monitors()[self.user_screen_number]
        screen_width, screen_height = user_screen.width, user_screen.height
        
        # Set environment variable to ensure proper centering
        os.environ['SDL_VIDEO_CENTERED'] = '1'
        
        self.wide_screen = pygame.display.set_mode(
            (screen_width, screen_height),  # Use full screen resolution
            pygame.NOFRAME  # Borderless window that fills the screen
        )
        
        # Start the Dino game timer
        self.start_dino_game_timer()
        
    def start_dino_game_timer(self):
        # Add a start timer for the game, matching Pong's style
        start_time = time.time()

        # Play the countdown sound (using ball drop sound like in Pong)
        self.ball_drop_sound.play()

        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    exit()

                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.start_main_menu()
                        return

            # Load and display the same background as Pong
            # Convert the background image to a Pygame image
            self.pong_game_bg_image_pygame = pygame.image.frombuffer(
                self.pong_game_bg_image.tobytes(),
                (
                    self.pong_game_bg_image.shape[1],
                    self.pong_game_bg_image.shape[0],
                ),
                "RGBA",
            )

            # Resize the background image to fit the screen
            self.pong_game_bg_image_pygame = pygame.transform.scale(
                self.pong_game_bg_image_pygame,
                (self.wide_screen.get_width(), self.wide_screen.get_height()),
            )

            # Position the Dino game screen on the display
            # The game area is centered horizontally and vertically on the screen
            self.wide_screen.blit(
                self.pong_game_bg_image_pygame,  # Background image for the game
                (
                    self.wide_screen.get_width() / 2
                    - self.pong_game_bg_image_pygame.get_width() / 2,  # Center horizontally
                    self.wide_screen.get_height() / 2
                    - self.pong_game_bg_image_pygame.get_height() / 2,  # Center vertically
                ),
            )

            time_elapsed = int(time.time() - start_time)
            time_remaining = self.pong_first_wave_wait_time - time_elapsed

            # Add the timer to the center of the screen in Pong style
            font = pygame.font.Font(self.font_path, 40)
            text = font.render(
                f"Game starts in {time_remaining} seconds",
                True,
                (255, 255, 255),
                (0, 0, 0),
            )
            text_rect = text.get_rect(
                center=(self.wide_screen.get_width() / 2, self.wide_screen.get_height() / 2)
            )
            self.wide_screen.blit(text, text_rect)

            # Create a smaller text object for the instructions
            instruction_font = pygame.font.Font(self.font_path, 20)
            instruction_text = instruction_font.render(
                "Use your head to control the dinosaur. Move UP to jump, DOWN to duck.",
                True,
                (255, 255, 255),
                (0, 0, 0),
            )
            instruction_text_rect = instruction_text.get_rect(
                center=(
                    self.wide_screen.get_width() / 2,
                    self.wide_screen.get_height() / 2 + 100,
                )
            )
            self.wide_screen.blit(instruction_text, instruction_text_rect)

            # Update the display
            pygame.display.update()

            # If the timer is done, break out of the loop and start the game
            if time_remaining <= 0:
                break

        # Transition to the main game
        self.start_dino_game()
        
    def start_dino_game(self):
        """Start the dinosaur game"""
        # Parse camera from other functions
        existing_cap = self.cap

        try:
            import numpy as np
            
            # Note: We're NOT resetting the display here because we've already
            # created self.wide_screen in init_dino_game
            # Just use the existing display that was set up

            # Import the dino game and run it
            from .dino_game import run_dino_game

            # Run the game with the existing screen, camera and background image
            print("Running Dino game with existing display...")
            run_dino_game(
                screen=self.wide_screen,
                existing_cap=existing_cap,
                bg_image=self.pong_game_bg_image
            )

            # Reset to original screen size when returning to menu
            print("Returning to main menu...")
            pygame.display.quit()
            pygame.display.init()
            # Ensure fullscreen is properly set when returning from the game
            self.screen = pygame.display.set_mode(
                (self.user_screen_width, self.user_screen_height),
                pygame.FULLSCREEN,
                display=self.user_screen_number
            )
            
            # Start the main menu again
            self.start_main_menu()
            
        except Exception as e:
            print(f"Error starting dino game: {e}")
            # Make sure we return to the main menu even if there's an error
            self.start_main_menu()
    
    def init_subway_game(self):
        # Placeholder for Subway Game initialization
        print("Subway Game started (stub)")
        # Optionally, return to main menu for now
        self.start_main_menu()

    def init_settings(self):
        """Quick placeholder settings menu"""
        # Just go back to main menu with a message
        print("Settings menu clicked - this will be implemented later")
        self.start_main_menu()
# All old settings code removed
