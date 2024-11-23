import pygame
import pygame_menu
from pygame_menu.themes import Theme
from pygame.locals import *
from pygame import mixer
import cv2
import numpy as np
import random
import time

from screeninfo import get_monitors

from utils import img_with_rounded_corners


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
        icon = pygame.image.load("./resources/images/5-lmbox-icon.png")
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

        # Initialize the player's position
        self.player_pos = pygame.Vector2(
            self.screen.get_width() / 2, self.screen.get_height() / 2
        )

        # Initialize a boolean for whether the game is running
        self.balloons_game_running = False

        # Initialize a boolean for whether the main menu is running
        self.main_menu_running = False

        # Initialize a boolean for whether the background music is muted
        self.bg_music_muted = False

        # Seed the random number generator
        random.seed(time.time())

        # Initialize the themes and main menu
        self.init_theme()
        self.init_main_menu()

        # Initialize the camera
        self.init_camera()

        # Start the main menu
        self.start_main_menu()

    def init_camera(self):
        # Initialize the camera
        self.cap = cv2.VideoCapture(self.user_camera_number)

        if not self.cap.isOpened():
            raise Exception("Could not open the camera.")

        # Set the camera resolution
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.user_screen_width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.user_screen_height)

        # Set the camera frame rate
        self.cap.set(cv2.CAP_PROP_FPS, 30)

        # Initialize the camera image
        self.camera_image = None

    def init_theme(self):
        # Set the background image
        self.menu_bg_image = pygame_menu.baseimage.BaseImage(
            image_path="./resources/images/main_menu_bg.png",
            drawing_mode=pygame_menu.baseimage.IMAGE_MODE_FILL,
        )

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
        )

        # Set the background music
        mixer.music.load("./resources/sounds/main_menu_bg_music.ogg")
        mixer.music.set_volume(0.1)

        # Add the game title to the main menu
        self.main_menu.add.label(
            self.game_name,
            font_size=100,
            margin=(0, 0),
            padding=(0, 0),
            selectable=False,
            background_color=(0, 0, 0),
        )

        # Add vertical space to the main menu
        self.main_menu.add.vertical_margin(230)

        # Add the "Settings" button to the main menu
        self.main_menu.add.button(
            "Settings",
            self.init_balloons_game,
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

        # Add the "Credits" button to the main menu
        self.main_menu.add.button(
            "Credits",
            self.init_balloons_game,
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

        # Add the "Quit" button to the main menu
        self.main_menu.add.button(
            "Quit",
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
        # Play the background music
        if not self.bg_music_muted:
            mixer.music.play()

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

        # Stop the background music
        mixer.music.stop()

        # Initialize the background image for the Balloons game
        self.balloons_game_bg_image = cv2.imread(
            "./resources/images/balloons_game_bg.png"
        )

        # Swap the color channels
        self.balloons_game_bg_image = cv2.cvtColor(
            self.balloons_game_bg_image, cv2.COLOR_BGR2RGB
        )

        # Add alpha channel to the background image
        self.balloons_game_bg_image = cv2.cvtColor(
            self.balloons_game_bg_image, cv2.COLOR_RGB2RGBA
        )

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

        # Initialize the score
        self.balloons_score = 0

        # Initialize the time
        self.balloons_timer = 0

        # Initialize the wave
        self.balloons_wave = 1

        # Initialize the timer
        pygame.time.set_timer(1, 1000)

        # Initialize the game wait time
        self.game_wait_time = 5

        # Initialize the balloons
        self.init_balloons()

        # Start the Balloons game timer
        self.start_balloons_game_timer()

        # Start the Balloons game
        self.start_balloons_game()

    def init_balloons(self):
        # Initialize the normal balloon image paths
        normal_balloon_image_paths = [
            "./resources/images/balloon-red.png",
            "./resources/images/balloon-green.png",
            "./resources/images/balloon-blue.png",
            "./resources/images/balloon-yellow.png",
            "./resources/images/balloon-purple.png",
            "./resources/images/balloon-orange.png",
            "./resources/images/balloon-gray.png",
        ]

        # Initialize the combo balloon image paths
        combo_balloon_image_paths = [
            "./resources/images/balloon-combo-1.png",
            "./resources/images/balloon-combo-2.png",
            "./resources/images/balloon-combo-3.png",
        ]

        # Fill the balloons list with random balloons
        for _ in range(10):
            is_combo = random.choice(
                [True, False, False, False, False, False, False, False, False, False]
            )

            balloon_img_path = (
                random.choice(combo_balloon_image_paths)
                if is_combo
                else random.choice(normal_balloon_image_paths)
            )
            balloon_img = pygame.image.load(balloon_img_path)
            balloon_img = pygame.transform.scale(balloon_img, (250, 250))
            balloon_rect = pygame.Rect(
                random.randint(self.start_x, self.end_x) + self.start_x,
                random.randint(self.start_y, self.end_y) + self.start_y,
                50,
                50,
            )
            speed = random.randint(10, 20) if is_combo else random.randint(1, 10)
            self.balloons.append(
                {"rect": balloon_rect, "image": balloon_img, "speed": speed}
            )

    def start_balloons_game_timer(self):

        # Add a start timer for the game
        start_time = time.time()

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

            time_elapsed = int(time.time() - start_time)
            time_remaining = self.game_wait_time - time_elapsed

            # Add the timer to the center of the screen
            font = pygame.font.Font(pygame_menu.font.FONT_8BIT, 50)
            text = font.render(
                f"Game Starting in {time_remaining} seconds",
                True,
                (255, 255, 255),
                (0, 0, 0),
            )
            text_rect = text.get_rect(
                center=(self.screen.get_width() // 2, self.screen.get_height() // 2)
            )
            self.screen.blit(text, text_rect)

            # Update the display
            pygame.display.flip()

            if time_remaining <= 0:
                break

        time.sleep(1)

    def start_balloons_game(self):

        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    exit()

                # if event.type == 1:
                #     self.balloons_wave += 1
                #     self.init_balloons()

                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.start_main_menu()

                if event.type == 1:
                    self.balloons_timer += 1

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

            # Add rounded corners to the camera image
            self.camera_image = img_with_rounded_corners(
                self.camera_image, 30, 2, (0, 0, 0)
            )

            # Add the camera image to the background image
            self.balloons_game_bg_image[
                self.start_y : self.end_y, self.start_x : self.end_x
            ] = self.camera_image

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

            # Add score to the screen
            font = pygame.font.Font(pygame_menu.font.FONT_8BIT, 36)
            text = font.render(
                f"Score is {max(0, self.balloons_score)}",
                True,
                (255, 255, 255),
                (0, 0, 0),
            )
            self.screen.blit(text, (30, (self.screen.get_height() // 2 - 50)))

            # Add time to the screen
            font = pygame.font.Font(pygame_menu.font.FONT_8BIT, 36)
            text = font.render(
                f"Time is {int(self.balloons_timer) - self.game_wait_time}",
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
            self.screen.blit(text, (30, (self.screen.get_height() // 2 + 150)))

            # Add game name to the top center of the screen
            font = pygame.font.Font(pygame_menu.font.FONT_8BIT, 50)
            text = font.render("Balloons Game", True, (255, 255, 255), (0, 0, 0))
            text_rect = text.get_rect(center=(self.screen.get_width() // 2, 150))
            self.screen.blit(text, text_rect)

            # Draw random balloons that move up the screen
            for balloon in self.balloons:
                balloon["rect"].move_ip(0, -balloon["speed"])
                self.screen.blit(balloon["image"], balloon["rect"])
                if balloon["rect"].top <= self.start_y + 100:
                    self.balloons.remove(balloon)
                    self.balloons_score -= 1

            # Update the display
            pygame.display.flip()

            # Update the clock and delta time
            self.dt = self.clock.tick(30) / 1000


if __name__ == "__main__":
    game = Game()
