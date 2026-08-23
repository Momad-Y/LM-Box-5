"""Drawing vocabulary shared by every hand-drawn screen.

The screens are drawn straight onto the fixed 1920x1080 game canvas rather
than built as pygame_menu grids. Menus were laid out on a fixed row count,
so adding a single widget silently moved the column split and threw the
layout out; positioning against the canvas has no such coupling.

Sizes here are expressed as fractions of the canvas so the whole design
scales with it: `cqw(2.9)` is 2.9% of the canvas width, matching the units
the design mock was built in.
"""

import functools

import pygame

# ---------------------------------------------------------------- palette
INK = (244, 236, 255)  # body text
SUN = (255, 201, 60)  # selection
WIRE = (79, 216, 255)  # meters, secondary highlight
PINK = (255, 47, 146)  # destructive
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)

GOLD = (255, 215, 0)
SILVER = (213, 213, 213)
BRONZE = (224, 139, 60)
PODIUM_COLORS = (GOLD, SILVER, BRONZE)

PANEL_FILL = (10, 4, 22)
PANEL_ALPHA = 209  # .82 of opaque, as in the mock
PANEL_ALPHA_SELECTED = 230
DIM_FILL = (12, 5, 26)
DIM_ALPHA = 158  # .62

BORDER = (255, 255, 255, 82)
BORDER_SOLID = (128, 124, 136)

CANVAS_WIDTH = 1920
CANVAS_HEIGHT = 1080


def cqw(percent, width=CANVAS_WIDTH):
    """Length as a percentage of the canvas width."""
    return int(round(width * percent / 100))


def cqh(percent, height=CANVAS_HEIGHT):
    """Length as a percentage of the canvas height."""
    return int(round(height * percent / 100))


# ------------------------------------------------------------------ text
@functools.lru_cache(maxsize=64)
def _font(path, size):
    return pygame.font.Font(path, size)


def font(path, size):
    """A cached font. Screens redraw every frame, so this matters."""
    return _font(path, max(8, int(size)))


def truncate(text, limit):
    """Shorten a name that would otherwise run into its neighbour."""
    if len(text) <= limit:
        return text
    return text[: max(1, limit - 1)] + "…"


def draw_text(
    surface,
    text,
    path,
    size,
    color=INK,
    center=None,
    topleft=None,
    midtop=None,
    midleft=None,
    midright=None,
    background=None,
    letter_spacing=0,
):
    """Render a line of text and return the rect it occupied.

    `letter_spacing` is applied by drawing glyph by glyph: the pixel font has
    no tracking of its own, and the design leans on it for the label style.
    """
    face = font(path, size)

    if letter_spacing:
        glyphs = [face.render(char, True, color) for char in text]
        width = sum(g.get_width() for g in glyphs) + letter_spacing * max(
            0, len(glyphs) - 1
        )
        rendered = pygame.Surface((max(1, width), face.get_height()), pygame.SRCALPHA)
        x = 0
        for glyph in glyphs:
            rendered.blit(glyph, (x, 0))
            x += glyph.get_width() + letter_spacing
    else:
        rendered = face.render(text, True, color)

    rect = rendered.get_rect()
    if center is not None:
        rect.center = center
    elif topleft is not None:
        rect.topleft = topleft
    elif midtop is not None:
        rect.midtop = midtop
    elif midleft is not None:
        rect.midleft = midleft
    elif midright is not None:
        rect.midright = midright

    if background is not None:
        pad_x, pad_y = cqw(0.9), cqw(0.35)
        box = rect.inflate(pad_x * 2, pad_y * 2)
        surface.fill(background, box)

    surface.blit(rendered, rect)
    return rect


def text_width(text, path, size, letter_spacing=0):
    """Width the same text would occupy, without drawing it."""
    face = font(path, size)
    if not letter_spacing:
        return face.size(text)[0]
    return sum(face.size(c)[0] for c in text) + letter_spacing * max(0, len(text) - 1)


# --------------------------------------------------------------- surfaces
# Every HUD chip and every dimmed backdrop reuses one of a small, stable
# set of (size, colour, alpha) combinations once a screen's layout has
# settled, so these are cached by that key rather than building a fresh
# SRCALPHA surface and filling it on every single call - this runs many
# times a frame across every game's HUD.
_dim_screen_cache = {}
_fill_rect_cache = {}


def dim_screen(surface, alpha=DIM_ALPHA):
    """Darken the backdrop so content reads over it.

    Every screen shares one background image, so without this the artwork
    competes with the text on all of them.
    """
    key = (surface.get_width(), surface.get_height(), alpha)
    veil = _dim_screen_cache.get(key)
    if veil is None:
        veil = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        veil.fill((*DIM_FILL, alpha))
        _dim_screen_cache[key] = veil
    surface.blit(veil, (0, 0))


def fill_rect(surface, rect, color, alpha):
    """Fill a rect with a translucent colour."""
    key = (rect.width, rect.height, color, alpha)
    patch = _fill_rect_cache.get(key)
    if patch is None:
        patch = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        patch.fill((*color, alpha))
        _fill_rect_cache[key] = patch
    surface.blit(patch, rect.topleft)


def draw_panel(
    surface,
    rect,
    selected=False,
    border_color=None,
    dashed=False,
    fill_alpha=None,
):
    """The boxed container every screen builds its content from."""
    alpha = fill_alpha
    if alpha is None:
        alpha = PANEL_ALPHA_SELECTED if selected else PANEL_ALPHA
    fill_rect(surface, rect, PANEL_FILL, alpha)

    color = border_color or (SUN if selected else BORDER_SOLID)
    thickness = max(2, cqw(0.3))
    if dashed:
        _draw_dashed_rect(surface, rect, color, thickness)
    else:
        pygame.draw.rect(surface, color, rect, thickness)
    return rect


def _draw_dashed_rect(surface, rect, color, thickness, dash=14, gap=10):
    """A dashed outline, for the empty states."""
    step = dash + gap
    for x in range(rect.left, rect.right, step):
        end = min(x + dash, rect.right)
        pygame.draw.line(surface, color, (x, rect.top), (end, rect.top), thickness)
        pygame.draw.line(
            surface, color, (x, rect.bottom - thickness), (end, rect.bottom - thickness), thickness
        )
    for y in range(rect.top, rect.bottom, step):
        end = min(y + dash, rect.bottom)
        pygame.draw.line(surface, color, (rect.left, y), (rect.left, end), thickness)
        pygame.draw.line(
            surface, color, (rect.right - thickness, y), (rect.right - thickness, end), thickness
        )


def draw_glow(surface, rect, color=SUN, spread=None):
    """A soft halo behind a selected element.

    Drawn as a few expanding translucent outlines rather than a blur, which
    suits the pixel art and costs nothing per frame.
    """
    spread = spread or cqw(1.1)
    steps = 5
    for step in range(steps, 0, -1):
        alpha = int(46 * step / steps)
        grown = rect.inflate(spread * step // steps * 2, spread * step // steps * 2)
        halo = pygame.Surface((grown.width, grown.height), pygame.SRCALPHA)
        pygame.draw.rect(halo, (*color, alpha), halo.get_rect(), max(2, spread // 3))
        surface.blit(halo, grown.topleft)


# ------------------------------------------------------------------ parts
def draw_title(surface, text, path, top_percent=6.0, size_percent=2.9):
    """The black title bar every non-menu screen wears."""
    return draw_text(
        surface,
        text,
        path,
        cqw(size_percent),
        color=INK,
        midtop=(surface.get_width() // 2, cqh(top_percent)),
        background=BLACK,
        letter_spacing=cqw(0.45),
    )


def draw_hint(surface, text, path, bottom_percent=5.0):
    """The key legend along the bottom edge.

    Shrinks to fit rather than running off the sides: the legends list every
    key a screen accepts, so the longest of them (the two-player picker) is
    wider than the canvas at the nominal size.
    """
    width = surface.get_width()
    limit = int(width * 0.94)

    size = cqw(1.35)
    spacing = cqw(0.12)
    while size > cqw(0.8) and text_width(text, path, size, spacing) > limit:
        size -= 1
        spacing = max(0, spacing - 1)

    return draw_text(
        surface,
        text,
        path,
        size,
        color=(190, 182, 205),
        midtop=(width // 2, surface.get_height() - cqh(bottom_percent) - size),
        letter_spacing=spacing,
    )


def draw_meter(surface, rect, filled, total, color=WIRE):
    """A segmented bar. Reads from across a room where a slider does not."""
    gap = max(2, cqw(0.3))
    segment = (rect.width - gap * (total - 1)) / total
    for index in range(total):
        left = rect.left + index * (segment + gap)
        cell = pygame.Rect(int(left), rect.top, int(segment), rect.height)
        if index < filled:
            surface.fill(color, cell)
        else:
            fill_rect(surface, cell, WHITE, 46)


def draw_face(surface, face, rect, placeholder_path=None):
    """A player's cutout scaled into a square, or a dashed empty slot."""
    if face is not None:
        scaled = pygame.transform.smoothscale(face, (rect.width, rect.height))
        surface.blit(scaled, rect.topleft)
        return True

    _draw_dashed_rect(surface, rect, (255, 255, 255, 90), max(2, cqw(0.25)))
    draw_icon(surface, "person", rect.inflate(-rect.width // 2, -rect.height // 2), (150, 145, 160))
    return False


# ------------------------------------------------------------------ icons
# Each glyph is a list of (x, y, w, h) rects on a 16x16 grid, so they scale
# to any size and need no image files. pygame cannot render SVG, and the
# blocky shapes suit the pixel art better than smooth ones would.
ICONS = {
    "users": [(5, 2, 6, 6), (2, 9, 12, 5)],
    "scores": [(1, 8, 4, 7), (6, 3, 4, 12), (11, 6, 4, 9)],
    "settings": [
        (6, 1, 4, 3), (6, 12, 4, 3), (1, 6, 3, 4), (12, 6, 3, 4), (5, 5, 6, 6),
    ],
    "credits": [(7, 1, 2, 14), (1, 7, 14, 2), (3, 3, 3, 3), (10, 10, 3, 3)],
    "quit": [(7, 1, 2, 7), (3, 4, 2, 8), (11, 4, 2, 8), (5, 12, 6, 2)],
    "person": [(5, 2, 6, 6), (2, 10, 12, 5)],
    "plus": [(7, 3, 2, 10), (3, 7, 10, 2)],
    "camera": [(1, 4, 11, 9), (12, 6, 3, 5), (4, 2, 5, 2)],
    "lock": [(4, 1, 2, 6), (10, 1, 2, 6), (4, 1, 8, 2), (3, 8, 10, 7)],
}

# Holes punched out of a glyph after it is drawn, same 16x16 grid
ICON_HOLES = {
    "settings": [(7, 7, 2, 2)],
    "camera": [(4, 7, 5, 3)],
    "lock": [(7, 10, 2, 3)],
}


def draw_icon(surface, name, rect, color=INK):
    """Draw one of the block glyphs to fill a rect."""
    unit_x = rect.width / 16
    unit_y = rect.height / 16

    def to_rect(cell):
        x, y, w, h = cell
        return pygame.Rect(
            int(rect.left + x * unit_x),
            int(rect.top + y * unit_y),
            max(1, int(w * unit_x)),
            max(1, int(h * unit_y)),
        )

    for cell in ICONS[name]:
        surface.fill(color, to_rect(cell))
    for cell in ICON_HOLES.get(name, ()):
        fill_rect(surface, to_rect(cell), PANEL_FILL, 255)
