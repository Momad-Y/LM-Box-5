import pygame
import pygame_menu
from pygame_menu.themes import Theme
from pygame.locals import *
from pygame import mixer

import cv2

import random
import time
import os

from screeninfo import get_monitors

from .utils import img_with_rounded_corners, random_bool_by_chance, biased_random_int

from models import initialize_hand_detector, detect_hands

# Get the current working directory
CWD = os.path.dirname(os.path.abspath(__file__))


class Game:
    def __init__(self):
        self.user_screen_number = 0  # The screen number to display the game on
        self.game_name = "LM Box 5"  # The name of the game
        self.default_screen_width = 1280  # The default screen width
        self.default_screen_height = 720  # The default screen height
        self.user_camera_number = 0  # The camera number to use for the game

        # Start Pygame
        pygame.init()

        # Initialize the mixer for sound
        mixer.init()

        # Set the icon
        icon = pygame.image.load(f"{CWD}/resources/images/5-lmbox-icon.png")
        pygame.display.set_icon(icon)

        # Get the user's screen resolution
        user_screen = get_monitors()[self.user_screen_number]
        self.user_screen_width = user_screen.width
        self.user_screen_height = user_screen.height

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

        # Initialize a boolean for whether the game is running
        self.balloons_game_running = False

        # Initialize a boolean for whether the main menu is running
        self.main_menu_running = False

        # Initialize a boolean for whether the background music is muted
        self.bg_music_muted = False

        # Seed the random number generator
        random.seed(time.time())

        # Initialize the camera
        self.init_camera()

        # Initialize the finger detection
        self.init_finger_detection()

        # Initialize the themes and main menu
        self.init_theme()
        self.init_main_menu()

        # Start the main menu
        self.start_main_menu()

    def init_camera(self):
        # Initialize the camera
        self.cap = cv2.VideoCapture(self.user_camera_number)

        # Check if the camera is opened
        if not self.cap.isOpened():
            raise Exception("Could not open the camera.")

        # Set the camera resolution
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.user_screen_width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.user_screen_height)

        # Set the camera frame rate
        self.cap.set(cv2.CAP_PROP_FPS, 30)

        # Initialize the camera image
        self.camera_image = None

    def init_finger_detection(self):
        # Initialize the HandDetector object
        self.hand_detector = initialize_hand_detector()

    def init_theme(self):
        # Set the background image
        self.menu_bg_image = pygame_menu.baseimage.BaseImage(
            image_path=f"{CWD}/resources/images/main_menu_bg.png",
            drawing_mode=pygame_menu.baseimage.IMAGE_MODE_FILL,
        )

        self.game_over_sound = mixer.Sound(f"{CWD}/resources/sounds/game-over.ogg")
        self.game_over_sound.set_volume(0.5)

        # Set the font
        self.font = pygame_menu.font.FONT_8BIT

        # Create a theme
        self.theme = Theme(
            background_color=self.menu_bg_image,
            title_bar_style=pygame_menu.widgets.MENUBAR_STYLE_NONE,
            widget_font_color=(251, 251, 251),
            widget_font_size=50,
            widget_font=self.font,
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

        # Add the "Play Runner" button to the main menu
        self.main_menu.add.button(
            "Play Runner",
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

        # Add the "Users" button to the main menu
        self.main_menu.add.button(
            "Users",
            pygame_menu.events.EXIT,
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
            pygame_menu.events.EXIT,
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
            pygame_menu.events.EXIT,
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

        # Set the main menu as the main menu of the game
        self.main_menu.mainloop(self.screen)

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

        # Take an initial camera image
        _, self.camera_image = self.cap.read()

        # Scale the camera image to be half the size of the screen
        self.camera_image = cv2.resize(
            self.camera_image,
            (
                int(self.user_screen_width // 2.5),
                int(self.user_screen_height // 2.5),
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
        self.start_x = top_left_x
        self.start_y = top_left_y + 50
        self.end_x = top_left_x + image_width
        self.end_y = top_left_y + image_height + 50

        # Initialize the scale value for x and y
        self.scale_x = self.user_screen_width / self.balloons_game_bg_image.shape[1]
        self.scale_y = self.user_screen_height / self.balloons_game_bg_image.shape[0]

        # Initialize the translate value for x and y
        self.translation_x = int(self.start_x * self.scale_x)
        self.translation_y = int(self.start_y * self.scale_y)

        # Initialize the score
        self.balloons_score = 0

        # Initialize the wave
        self.balloons_wave = 1

        # Initialize the max number of waves
        self.max_balloons_waves = 5

        # Initialize the max wave time
        self.max_wave_time = 20

        # Initialize the wave wait time
        self.wave_wait_time = 3

        # Initialize the balloons
        self.init_balloons()

        # Start the Balloons game timer
        self.start_balloons_game_wave_timer()

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
                        random.randint(0, self.end_x) + self.start_x + 110,
                        self.end_y + 100,
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

    def start_balloons_game_wave_timer(self):

        if self.balloons_wave > self.max_balloons_waves:
            self.end_balloons_game()

        # Add a start timer for the game
        start_time = time.time()

        # Play the balloon popping fill sound
        self.balloon_popping_fill_sounds.play()

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

            time_elapsed = int(time.time() - start_time)
            other_time_remaining = self.wave_wait_time - time_elapsed
            wave_1_time_remaining = (
                2 - time_elapsed
            )  #! 10 Should be the time for the first wave not 2

            time_remaining = (
                other_time_remaining
                if self.balloons_wave != 1
                else wave_1_time_remaining
            )

            # Add the timer to the center of the screen
            font = pygame.font.Font(pygame_menu.font.FONT_8BIT, 40)
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
            font = pygame.font.Font(pygame_menu.font.FONT_8BIT, 50)
            text = font.render("Balloons Game", True, (255, 255, 255), (0, 0, 0))
            text_rect = text.get_rect(center=(self.screen.get_width() // 2, 150))
            self.screen.blit(text, text_rect)

            # Show instructions if the wave is 1
            if self.balloons_wave == 1:
                font = pygame.font.Font(pygame_menu.font.FONT_8BIT, 30)
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
                    int(self.user_screen_width // 2.5),
                    int(self.user_screen_height // 2.5),
                ),
            )

            # Get the right and left hand centers
            hands_data = detect_hands(self.hand_detector, self.camera_image)
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
                    int(finger_center[0] * self.scale_x) + self.translation_x,
                    int(finger_center[1] * self.scale_y) + self.translation_y,
                )

                fingers_centers_rects.append(
                    pygame.Rect(finger_center[0], finger_center[1], 20, 20)
                )

            for finger_center in fingers_centers_left:
                if finger_center == (-1, -1):
                    continue

                finger_center = (
                    int(finger_center[0] * self.scale_x) + self.translation_x,
                    int(finger_center[1] * self.scale_y) + self.translation_y,
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
                self.start_y : self.end_y, self.start_x : self.end_x
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
            font = pygame.font.Font(pygame_menu.font.FONT_8BIT, 36)
            text = font.render(
                f"Score is {max(0, self.balloons_score)}",
                True,
                (255, 255, 255),
                (0, 0, 0),
            )
            self.screen.blit(text, (30, (self.screen.get_height() // 2 - 20)))

            # Calculate the elapsed time
            elapsed_time = int(time.time() - start_time)

            # Add time to the screen
            font = pygame.font.Font(pygame_menu.font.FONT_8BIT, 36)
            text = font.render(
                f"Time is {elapsed_time}",
                True,
                (255, 255, 255),
                (0, 0, 0),
            )
            self.screen.blit(text, (30, (self.screen.get_height() // 2 + 50)))

            # Add wave to the screen
            font = pygame.font.Font(pygame_menu.font.FONT_8BIT, 36)
            text = font.render(
                f"Wave is {self.balloons_wave}",
                True,
                (255, 255, 255),
                (0, 0, 0),
            )
            self.screen.blit(text, (30, (self.screen.get_height() // 2 + 120)))

            # Add game name to the top center of the screen
            font = pygame.font.Font(pygame_menu.font.FONT_8BIT, 50)
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
                if balloon["rect"].top <= self.start_y + balloon["rect"].height:

                    # Remove a point if the balloon is not a combo balloon
                    if not balloon["is_combo"]:
                        self.balloons_score -= 1

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
                            self.balloons_score += 2
                        elif balloon["type"] == 2:
                            self.balloons_score += 3
                        elif balloon["type"] == 3:
                            self.balloons_score += 5
                        else:
                            self.balloons_score += 1

                        balloon["is_popped"] = True
                        random.choice(self.balloon_popping_sounds).play()
                        break

            # Check if the balloons are all popped or the wave time is over
            if len(balloons) == 0 or elapsed_time > self.max_wave_time:
                self.balloons_wave += 1
                self.start_balloons_game_wave_timer()
                break

            # Update the display
            pygame.display.flip()

            # Update the clock and delta time
            self.dt = self.clock.tick(30) / 1000

    def end_balloons_game(self):
        # Play the game over sound
        self.game_over_sound.play()

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
            font = pygame.font.Font(pygame_menu.font.FONT_8BIT, 80)
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
            font = pygame.font.Font(pygame_menu.font.FONT_8BIT, 60)
            text = font.render(
                f"Score is {max(0, self.balloons_score)}",
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
            font = pygame.font.Font(pygame_menu.font.FONT_8BIT, 30)
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
