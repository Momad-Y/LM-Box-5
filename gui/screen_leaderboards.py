"""The leaderboards screen: a podium for the top three, a list for the rest.

Games are tabs along the top rather than a left/right toggle hidden in the
title, so which board you are looking at - and that there are others - is
visible without pressing anything.
"""

import pygame

from . import ui_kit as ui

GAMES = (("balloons", "BALLOONS"), ("pong", "PONG"), ("runner", "RUNNER"))

# Podium columns run 2nd, 1st, 3rd so the winner stands in the middle
PODIUM_ORDER = (1, 0, 2)
BLOCK_HEIGHTS = (7.0, 5.0, 3.6)  # first, second, third, as % of canvas width
REST_LIMIT = 5


def _tab_rects(surface, game):
    """A rect per game tab, laid out from the centre."""
    width, height = surface.get_size()
    size = ui.cqw(1.4, width)
    gap = ui.cqw(0.8, width)
    pad_x = ui.cqw(1.8, width)

    widths = [
        ui.text_width(title, game.font_path, size, ui.cqw(0.12, width)) + pad_x * 2
        for _, title in GAMES
    ]
    total = sum(widths) + gap * (len(widths) - 1)

    x = (width - total) // 2
    top = ui.cqh(18.0, height)
    rects = []
    for tab_width in widths:
        rects.append(pygame.Rect(x, top, tab_width, size + ui.cqw(0.9, width)))
        x += tab_width + gap
    return rects


def _draw_tabs(game, surface, selected):
    width = surface.get_width()
    size = ui.cqw(1.4, width)
    for index, (rect, (_, title)) in enumerate(zip(_tab_rects(surface, game), GAMES)):
        active = index == selected
        ui.fill_rect(surface, rect, ui.PANEL_FILL, 235 if active else 184)
        pygame.draw.rect(
            surface, ui.SUN if active else (160, 155, 175), rect, max(2, ui.cqw(0.25, width))
        )
        ui.draw_text(
            surface,
            title,
            game.font_path,
            size,
            color=ui.SUN if active else ui.INK,
            center=rect.center,
            letter_spacing=ui.cqw(0.12, width),
        )


def _draw_podium(game, surface, entries):
    """The top three, tallest block in the middle."""
    width, height = surface.get_size()
    band = int(width * 0.58)
    gap = ui.cqw(2.0, width)
    column = (band - gap * 2) // 3
    left = (width - band) // 2
    baseline = ui.cqh(62.0, height)

    face_size = ui.cqw(7.0, width)
    name_size = ui.cqw(1.25, width)
    score_size = ui.cqw(1.7, width)
    step = ui.cqw(0.5, width)

    for slot, place in enumerate(PODIUM_ORDER):
        if place >= len(entries):
            continue

        user_id, name, best = entries[place]
        color = ui.PODIUM_COLORS[place]
        block_height = ui.cqw(BLOCK_HEIGHTS[place], width)
        x = left + slot * (column + gap)

        # Dark ground first, then the metal tinted over it, so the block
        # reads as coloured without going opaque over the artwork
        block = pygame.Rect(x, baseline - block_height, column, block_height)
        ui.fill_rect(surface, block, ui.PANEL_FILL, 184)
        ui.fill_rect(surface, block, color, 56)
        pygame.draw.line(surface, color, block.topleft, block.topright, max(2, ui.cqw(0.3, width)))
        ui.draw_text(
            surface,
            str(place + 1),
            game.font_path,
            ui.cqw(2.4, width),
            color=color,
            center=block.center,
        )

        score_rect = ui.draw_text(
            surface,
            str(best),
            game.font_path,
            score_size,
            color=color,
            midtop=(block.centerx, block.top - step - score_size),
        )
        name_rect = ui.draw_text(
            surface,
            ui.truncate(name.upper(), 13),
            game.font_path,
            name_size,
            color=ui.INK,
            midtop=(block.centerx, score_rect.top - step - name_size),
            letter_spacing=ui.cqw(0.04, width),
        )

        face = game.player_face_or_none(user_id)
        face_rect = pygame.Rect(0, 0, face_size, face_size)
        face_rect.midbottom = (block.centerx, name_rect.top - step)
        ui.draw_face(surface, face, face_rect)


def _draw_rest(game, surface, entries):
    """Places four downwards, as a compact list."""
    width, height = surface.get_size()
    band = int(width * 0.54)
    left = (width - band) // 2
    size = ui.cqw(1.3, width)
    row_height = size + ui.cqw(0.7, width)
    gap = ui.cqw(0.5, width)

    rows = entries[3 : 3 + REST_LIMIT]
    if not rows:
        return

    bottom = height - ui.cqh(13.0, height)
    top = bottom - len(rows) * (row_height + gap) + gap

    for index, (_user_id, name, best) in enumerate(rows):
        rect = pygame.Rect(left, top + index * (row_height + gap), band, row_height)
        ui.fill_rect(surface, rect, ui.PANEL_FILL, 184)

        pad = ui.cqw(0.8, width)
        ui.draw_text(
            surface,
            str(index + 4),
            game.font_path,
            size,
            color=(170, 162, 190),
            midleft=(rect.left + pad, rect.centery),
        )
        ui.draw_text(
            surface,
            ui.truncate(name.upper(), 22),
            game.font_path,
            size,
            color=ui.INK,
            midleft=(rect.left + pad + ui.cqw(3.0, width), rect.centery),
            letter_spacing=ui.cqw(0.05, width),
        )
        ui.draw_text(
            surface,
            str(best),
            game.font_path,
            size,
            color=ui.INK,
            midright=(rect.right - pad, rect.centery),
        )


def draw(game, selected, entries=None):
    surface = game.screen
    width = surface.get_width()

    game.blit_background(game.get_prompt_background())
    ui.dim_screen(surface)
    ui.draw_title(surface, "LEADERBOARDS", game.font_path)
    _draw_tabs(game, surface, selected)

    if entries is None:
        entries = game.get_leaderboard(GAMES[selected][0])
    if entries:
        _draw_podium(game, surface, entries)
        _draw_rest(game, surface, entries)
    else:
        ui.draw_text(
            surface,
            "NO SCORES YET - GO AND PLAY A ROUND",
            game.font_path,
            ui.cqw(1.6, width),
            color=(190, 182, 205),
            center=(width // 2, surface.get_height() // 2),
            letter_spacing=ui.cqw(0.1, width),
        )

    ui.draw_hint(
        surface, "LEFT / RIGHT TO CHANGE GAME  ·  ESC TO GO BACK", game.font_path
    )
    game.present()


# ------------------------------------------------------------------- loop
def run(game):
    """Show the leaderboards until the player backs out."""
    selected = 0
    shown = None  # the board is only re-read when the tab changes

    while True:
        if shown != selected:
            entries = game.get_leaderboard(GAMES[selected][0])
            shown = selected

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "quit"

            if event.type != pygame.KEYDOWN:
                continue

            if event.key == pygame.K_ESCAPE:
                return None
            if event.key in (pygame.K_RIGHT, pygame.K_DOWN):
                selected = (selected + 1) % len(GAMES)
            elif event.key in (pygame.K_LEFT, pygame.K_UP):
                selected = (selected - 1) % len(GAMES)

        game.clock.tick(60)
        draw(game, selected, entries)
