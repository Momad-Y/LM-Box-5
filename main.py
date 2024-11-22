import pygame
import pygame_menu
from pygame_menu.themes import Theme
from screeninfo import get_monitors


class Game:
    def __init__(self):
        self.user_screen_number = 0
        self.game_name = "LM Box 5"
        self.default_screen_width = 1280
        self.default_screen_height = 720

        # Start Pygame
        pygame.init()

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

        # Initialize the themes and main menu
        self.init_theme()
        self.init_main_menu()

        # Start the main menu
        self.start_main_menu()

    def init_theme(self):
        self.bg_image = pygame_menu.baseimage.BaseImage(
            image_path="./resources/images/main_menu_bg.png",
            drawing_mode=pygame_menu.baseimage.IMAGE_MODE_FILL,
        )

        # Set the font
        self.font = pygame_menu.font.FONT_8BIT

        # Create a theme
        self.theme = Theme(
            background_color=self.bg_image,
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
        self.main_menu.add.vertical_margin(50)

        # Add the "Play Balloons" button to the main menu
        self.main_menu.add.button(
            "Play Balloons",
            self.start_game,
            margin=(0, 0),
            padding=(0, 0),
            background_color=(0, 0, 0),
            selection_effect=pygame_menu.widgets.LeftArrowSelection(
                arrow_right_margin=15,
                arrow_vertical_offset=0,
            ),
            cursor=pygame.SYSTEM_CURSOR_HAND,
        )

        # Add vertical space to the main menu
        self.main_menu.add.vertical_margin(50)

        # Add the "Play Pong" button to the main menu
        self.main_menu.add.button(
            "Play Pong",
            self.start_game,
            margin=(0, 0),
            padding=(0, 0),
            background_color=(0, 0, 0),
            selection_effect=pygame_menu.widgets.LeftArrowSelection(
                arrow_right_margin=15,
                arrow_vertical_offset=0,
            ),
            cursor=pygame.SYSTEM_CURSOR_HAND,
        )

        # Add vertical space to the main menu
        self.main_menu.add.vertical_margin(50)

        # Add the "Play Snake" button to the main menu
        self.main_menu.add.button(
            "Play Runner",
            self.start_game,
            margin=(0, 0),
            padding=(0, 0),
            background_color=(0, 0, 0),
            selection_effect=pygame_menu.widgets.LeftArrowSelection(
                arrow_right_margin=15,
                arrow_vertical_offset=0,
            ),
            cursor=pygame.SYSTEM_CURSOR_HAND,
        )

        # Add vertical space to the main menu
        self.main_menu.add.vertical_margin(100)

        # Add the "Quit" button to the main menu
        self.main_menu.add.button(
            "Quit",
            pygame_menu.events.EXIT,
            margin=(0, 0),
            padding=(0, 0),
            background_color=(0, 0, 0),
            selection_effect=pygame_menu.widgets.LeftArrowSelection(
                arrow_right_margin=15,
                arrow_vertical_offset=0,
            ),
            cursor=pygame.SYSTEM_CURSOR_HAND,
        )

    def start_main_menu(self):
        # Set the main menu as the main menu of the game
        self.main_menu.mainloop(self.screen)

    def start_game(self):
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    exit()

            # fill the screen with a color to wipe away anything from last frame
            self.screen.fill("purple")

            pygame.draw.circle(self.screen, "red", self.player_pos, 40)

            keys = pygame.key.get_pressed()
            if keys[pygame.K_w]:
                self.player_pos.y -= 300 * self.dt
            if keys[pygame.K_s]:
                self.player_pos.y += 300 * self.dt
            if keys[pygame.K_a]:
                self.player_pos.x -= 300 * self.dt
            if keys[pygame.K_d]:
                self.player_pos.x += 300 * self.dt
            if keys[pygame.K_ESCAPE]:
                self.start_main_menu()

            # flip() the display to put your work on screen
            pygame.display.flip()

            self.dt = self.clock.tick(60) / 1000


if __name__ == "__main__":
    game = Game()
