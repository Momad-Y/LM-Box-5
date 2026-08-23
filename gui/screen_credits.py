"""The credits screen: a two-column list of who did what.

Replaces a version whose rows each scrolled and wrapped independently, so
after a few seconds of holding SPACE the columns no longer lined up with
each other. The list scrolls as one block here, and only if it is taller
than the space it has.
"""

import pygame

from . import ui_kit as ui

CREDITS = (
    ("GAME DEVELOPMENT", "Mohamed Abdelnasser, Abdelrahman Saeed"),
    ("GRAPHICS", "Mohamed Abdelnasser, Abdelrahman Saeed"),
    ("ART STYLE", "Mostly rectangles"),
    ("MUSIC & SFX", "Mohamed Abdelnasser, Abdelrahman Saeed"),
    ("COMPUTER VISION", "Mohamed Abdelnasser, Abdelrahman Saeed"),
    ("ACCURACY", "The computer vision usually works"),
    ("LEVEL DESIGN", "One balloon wave, one pong table, one runner"),
    ("TESTING", "Ourselves, repeatedly, at 2 AM"),
    ("PRODUCTION", "Two guys and a GitHub repo"),
    ("POWERED BY", "Pygame, OpenCV, MediaPipe, CVZone, and spite"),
    ("3D MODELS", "None. We could not afford the polygons"),
    ("LEGAL", "Totally not a dinosaur game anymore"),
    ("BUGS FIXED", "Most of them, probably"),
    ("PRIVACY", "100% local - camera, photo and scores never leave this device"),
    ("CONTACT MOHAMED", "mohamed.y.abdelnasser@gmail.com"),
    ("CONTACT ABDELRAHMAN", "abdosaaed749@gmail.com"),
    ("SPECIAL THANKS", "No one. We did this ourselves and we want credit"),
)

SCROLL_SPEED = 30  # pixels per second, once the list outgrows its panel


def panel_rect(surface):
    """The panel, no taller than its contents need."""
    width, height = surface.get_size()
    available = height - ui.cqh(13.0, height) - ui.cqh(20.0, height)
    panel_height = min(available, content_height(surface))

    rect = pygame.Rect(int(width * 0.08), 0, int(width * 0.84), panel_height)
    rect.centery = ui.cqh(20.0, height) + available // 2
    return rect


def draw(game, offset):
    """Paint one frame. `offset` scrolls the list within its panel.

    Loops rather than scrolling to the end and holding: once the last row
    has passed, the same list is already following behind it, so the roll
    never runs dry and never has to snap back to the top.
    """
    surface = game.screen
    width = surface.get_width()

    game.blit_background(game.get_prompt_background())
    ui.dim_screen(surface)
    ui.draw_title(surface, "CREDITS", game.font_path)

    panel = panel_rect(surface)
    ui.draw_panel(surface, panel, fill_alpha=214)

    pad = ui.cqw(2.0, width)
    size = ui.cqw(1.3, width)
    row_height = size + ui.cqw(1.4, width)
    period = loop_period(surface)

    # Clip so a scrolling row disappears at the panel edge rather than
    # drawing over the title and the hint
    previous_clip = surface.get_clip()
    surface.set_clip(panel.inflate(-4, -4))

    for index, (label, value) in enumerate(CREDITS):
        base_y = pad + index * row_height - offset
        # Position within one loop, then also one loop earlier - whichever
        # of the two actually falls inside the panel is the one that draws
        for y in (
            panel.top + base_y % period,
            panel.top + base_y % period - period,
        ):
            if panel.top - row_height < y < panel.bottom:
                ui.draw_text(
                    surface,
                    label,
                    game.font_path,
                    size,
                    color=ui.SUN,
                    topleft=(panel.left + pad, y),
                    letter_spacing=ui.cqw(0.08, width),
                )
                ui.draw_text(
                    surface,
                    value,
                    game.font_path,
                    size,
                    color=ui.INK,
                    midright=(panel.right - pad, y + size // 2),
                )

    surface.set_clip(previous_clip)

    ui.draw_hint(surface, "ESC TO GO BACK", game.font_path)
    game.draw_fps()
    game.present()


def content_height(surface):
    """How tall the list would be drawn in one pass, unlooped.

    Used only to decide whether the list needs to scroll at all - a list
    that already fits its panel sits still rather than looping pointlessly.
    """
    width = surface.get_width()
    row_height = ui.cqw(1.3, width) + ui.cqw(1.4, width)
    return len(CREDITS) * row_height + ui.cqw(2.0, width) * 2


def loop_period(surface):
    """How far the list scrolls before it repeats.

    One row-height of blank space is added after the last credit, so the
    loop reads as a seam between passes rather than the same row appearing
    twice in a row. Shared between draw() (which wraps each row's position
    by this) and run() (which wraps the scroll offset by the same amount,
    so it never grows without bound over a long-running session).
    """
    width = surface.get_width()
    row_height = ui.cqw(1.3, width) + ui.cqw(1.4, width)
    return len(CREDITS) * row_height + row_height


def run(game):
    """Show the credits until the player backs out."""
    offset = 0.0

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "quit"
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                return None

        # Only loop if there is more list than panel; a list that fits
        # should sit still rather than drift off the top
        overflow = content_height(game.screen) - panel_rect(game.screen).height
        if overflow > 0:
            offset = (offset + SCROLL_SPEED * game.clock.get_time() / 1000) % loop_period(
                game.screen
            )
        else:
            offset = 0

        game.clock.tick(60)
        draw(game, offset)
