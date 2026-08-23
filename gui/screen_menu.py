"""The main menu: three game cards on the centre line, everything else as
labelled icons in the bottom corners.

Returns an action name to the caller rather than invoking a screen itself,
so the app can dispatch from one place. The old menu called straight into a
game, which then called back into the menu, nesting a stack frame per round
and eventually overflowing.
"""

import os

import pygame

from . import ui_kit as ui

CWD = os.path.dirname(os.path.abspath(__file__))
IMAGES = os.path.join(CWD, "resources", "images")

GAMES = (
    ("balloons", "BALLOONS"),
    ("pong", "PONG"),
    ("runner", "RUNNER"),
)
LEFT_TILES = (("users", "USERS"), ("scores", "SCORES"))
RIGHT_TILES = (("settings", "SETTINGS"), ("credits", "CREDITS"), ("quit", "QUIT"))
TILES = LEFT_TILES + RIGHT_TILES

PONG_FIELD = (2, 48, 32)
BALLOON_FIELD = (45, 27, 78)
RUNNER_FIELD = (255, 182, 193)
RUNNER_GROUND = (123, 107, 114)


def _load(name):
    return pygame.image.load(os.path.join(IMAGES, name)).convert_alpha()


class MenuArt:
    """Sprites for the three game cards, loaded once."""

    def __init__(self):
        self.balloons = [
            _load("balloon-red.png"),
            _load("balloon-yellow.png"),
            _load("balloon-blue.png"),
        ]
        self.runner = _load("runner-run-1.png")
        self.cactus = _load("cactus-1.png")
        self.ptero = _load("ptero-1.png")

    def draw(self, surface, key, rect):
        """Paint a card's artwork inside its frame."""
        drawer = {
            "balloons": self._balloons,
            "pong": self._pong,
            "runner": self._runner,
        }[key]
        clip = surface.get_clip()
        surface.set_clip(rect)
        drawer(surface, rect)
        surface.set_clip(clip)

    def _blit_scaled(self, surface, sprite, rect, width_fraction, left_f, bottom_f):
        width = int(rect.width * width_fraction)
        height = int(sprite.get_height() * width / sprite.get_width())
        scaled = pygame.transform.smoothscale(sprite, (width, height))
        surface.blit(
            scaled,
            (rect.left + int(rect.width * left_f), rect.bottom - int(rect.height * bottom_f) - height),
        )

    def _balloons(self, surface, rect):
        surface.fill(BALLOON_FIELD, rect)
        for sprite, left, bottom in zip(self.balloons, (0.12, 0.38, 0.63), (0.14, 0.30, 0.10)):
            self._blit_scaled(surface, sprite, rect, 0.26, left, bottom)

    def _pong(self, surface, rect):
        surface.fill(PONG_FIELD, rect)

        # Dashed centre net
        net_width = max(2, int(rect.width * 0.02))
        x = rect.centerx - net_width // 2
        for y in range(rect.top + int(rect.height * 0.08), rect.bottom - int(rect.height * 0.08), int(rect.height * 0.12)):
            surface.fill(ui.WHITE, (x, y, net_width, max(2, int(rect.height * 0.06))))

        paddle_w = max(3, int(rect.width * 0.04))
        paddle_h = int(rect.height * 0.34)
        surface.fill(ui.WHITE, (rect.left + int(rect.width * 0.08), rect.top + int(rect.height * 0.30), paddle_w, paddle_h))
        surface.fill(
            ui.WHITE,
            (rect.right - int(rect.width * 0.08) - paddle_w, rect.top + int(rect.height * 0.42), paddle_w, paddle_h),
        )

        radius = max(3, int(rect.width * 0.03))
        pygame.draw.circle(surface, ui.WHITE, (rect.left + int(rect.width * 0.49), rect.centery), radius)

    def _runner(self, surface, rect):
        surface.fill(RUNNER_FIELD, rect)
        ground_y = rect.bottom - int(rect.height * 0.26)
        surface.fill(RUNNER_GROUND, (rect.left, ground_y, rect.width, max(2, int(rect.height * 0.03))))
        self._blit_scaled(surface, self.runner, rect, 0.20, 0.12, 0.26)
        self._blit_scaled(surface, self.cactus, rect, 0.11, 0.58, 0.26)
        self._blit_scaled(surface, self.ptero, rect, 0.15, 0.74, 0.52)


# ------------------------------------------------------------------ layout
def card_rects(surface):
    """The three game cards: (art rect, name rect) per game."""
    width, height = surface.get_size()
    band = int(width * 0.72)
    gap = ui.cqw(2.6, width)
    card_width = (band - gap * 2) // 3
    art_height = card_width * 3 // 4
    name_height = ui.cqw(2.1, width) + ui.cqw(1.2, width)
    spacing = ui.cqw(0.7, width)
    total = art_height + spacing + name_height

    top = int(height * 0.54) - total // 2
    left = (width - band) // 2

    rects = []
    for index in range(3):
        x = left + index * (card_width + gap)
        art = pygame.Rect(x, top, card_width, art_height)
        name = pygame.Rect(x, top + art_height + spacing, card_width, name_height)
        rects.append((art, name))
    return rects


def tile_rects(surface, game):
    """Glyph boxes for the five corner tiles, left cluster then right.

    Each tile is spaced by the wider of its glyph and its caption: SETTINGS
    and CREDITS are longer than the boxes they sit under, so spacing on the
    box alone runs the two captions together.
    """
    width, height = surface.get_size()
    glyph = ui.cqw(6.4, width)
    gap = ui.cqw(1.6, width)
    label_gap = ui.cqw(0.5, width)
    label_size = ui.cqw(1.35, width)
    spacing = ui.cqw(0.12, width)
    top = height - ui.cqh(3.0, height) - label_size - label_gap - glyph

    def cell_width(label):
        return max(glyph, ui.text_width(label, game.font_path, label_size, spacing))

    def cluster(tiles, start_x):
        rects = []
        x = start_x
        for _, label in tiles:
            cell = cell_width(label)
            rects.append(pygame.Rect(x + (cell - glyph) // 2, top, glyph, glyph))
            x += cell + gap
        return rects

    left_rects = cluster(LEFT_TILES, ui.cqw(3.5, width))

    right_total = sum(cell_width(label) for _, label in RIGHT_TILES) + gap * (
        len(RIGHT_TILES) - 1
    )
    right_rects = cluster(RIGHT_TILES, width - ui.cqw(3.5, width) - right_total)

    return left_rects + right_rects


# ------------------------------------------------------------------- draw
def draw(game, focus_row, focus_index):
    """Paint one frame of the menu onto the game canvas."""
    surface = game.screen
    width = surface.get_width()

    game.blit_background(game.get_prompt_background())

    ui.draw_text(
        surface,
        "LM BOX 5",
        game.font_path,
        ui.cqw(2.9, width),
        color=ui.INK,
        midtop=(width // 2, ui.cqh(11.0, surface.get_height())),
        background=ui.BLACK,
        letter_spacing=ui.cqw(0.45, width),
    )

    for index, ((key, title), (art, name)) in enumerate(zip(GAMES, card_rects(surface))):
        selected = focus_row == 0 and focus_index == index
        lift = ui.cqw(1.0, width) if selected else 0
        art = art.move(0, -lift)
        name = name.move(0, -lift)

        # Drop shadow first, so a lifted card reads as raised
        shadow = art.move(0, ui.cqw(0.8, width) + lift)
        ui.fill_rect(surface, shadow, (0, 0, 0), 100)

        if selected:
            ui.draw_glow(surface, art)

        game.menu_art.draw(surface, key, art)
        pygame.draw.rect(
            surface,
            ui.SUN if selected else (200, 196, 210),
            art,
            max(2, ui.cqw(0.35, width)),
        )

        surface.fill(ui.BLACK, name)
        ui.draw_text(
            surface,
            title,
            game.font_path,
            ui.cqw(2.1, width),
            color=ui.SUN if selected else ui.INK,
            center=name.center,
            letter_spacing=ui.cqw(0.1, width),
        )

    for index, (rect, (key, label)) in enumerate(zip(tile_rects(surface, game), TILES)):
        selected = focus_row == 1 and focus_index == index
        danger = key == "quit"
        accent = ui.PINK if danger else ui.WIRE
        color = accent if selected else ui.INK

        box = rect.move(0, -ui.cqw(0.7, width)) if selected else rect
        ui.fill_rect(surface, box, ui.PANEL_FILL, 235 if selected else 184)
        pygame.draw.rect(
            surface, color if selected else (170, 166, 180), box, max(2, ui.cqw(0.3, width))
        )
        ui.draw_icon(surface, key, box.inflate(-box.width * 0.42, -box.height * 0.42), color)

        ui.draw_text(
            surface,
            label,
            game.font_path,
            ui.cqw(1.35, width),
            color=color,
            midtop=(rect.centerx, rect.bottom + ui.cqw(0.5, width)),
            letter_spacing=ui.cqw(0.12, width),
        )

    ui.draw_text(
        surface,
        "LEFT / RIGHT TO CHOOSE  ·  ENTER TO PLAY",
        game.font_path,
        ui.cqw(1.35, width),
        color=(190, 182, 205),
        midtop=(width // 2, ui.cqh(74.0, surface.get_height())),
        letter_spacing=ui.cqw(0.12, width),
    )

    game.present()


# ------------------------------------------------------------------- loop
def run(game):
    """Run the menu until the player picks something. Returns an action key."""
    if not hasattr(game, "menu_art"):
        game.menu_art = MenuArt()

    focus_row, focus_index = 0, 0
    rows = (len(GAMES), len(TILES))

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "quit"

            if event.type == pygame.MOUSEMOTION:
                hit = _hit_test(game.screen, game, event.pos)
                if hit is not None:
                    focus_row, focus_index = hit

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                hit = _hit_test(game.screen, game, event.pos)
                if hit is not None:
                    focus_row, focus_index = hit
                    return _action(focus_row, focus_index)

            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_RIGHT, pygame.K_TAB):
                    focus_index = (focus_index + 1) % rows[focus_row]
                elif event.key == pygame.K_LEFT:
                    focus_index = (focus_index - 1) % rows[focus_row]
                elif event.key == pygame.K_DOWN and focus_row == 0:
                    focus_row, focus_index = 1, min(focus_index, len(TILES) - 1)
                elif event.key == pygame.K_UP and focus_row == 1:
                    focus_row, focus_index = 0, min(focus_index, len(GAMES) - 1)
                elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                    return _action(focus_row, focus_index)

        game.clock.tick(60)
        draw(game, focus_row, focus_index)


def _action(row, index):
    return GAMES[index][0] if row == 0 else TILES[index][0]


def _hit_test(surface, game, window_pos):
    """Map a click in the window back to a menu item, or None."""
    pos = game.window_to_canvas(window_pos)
    if pos is None:
        return None

    for index, (art, name) in enumerate(card_rects(surface)):
        if art.collidepoint(pos) or name.collidepoint(pos):
            return 0, index
    for index, rect in enumerate(tile_rects(surface, game)):
        if rect.inflate(0, ui.cqw(2.0, surface.get_width())).collidepoint(pos):
            return 1, index
    return None
