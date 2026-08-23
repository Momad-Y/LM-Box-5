"""The users screen: a grid of player cards.

Replaces a stack of rows that each carried a name and four buttons. Every
action now applies to whichever card is selected and is listed once along
the bottom, so a row never has to hold more than it can fit - which is what
made the old layout collide with itself.
"""

import pygame

from . import ui_kit as ui

COLUMNS = 4
ROWS = 2
PAGE_SIZE = COLUMNS * ROWS

GAMES = ("balloons", "pong", "runner")

ACTIONS = (
    ("ENTER", "RENAME", False),
    ("P", "PHOTO", False),
    ("C", "CLEAR PHOTO", False),
    ("DEL", "DELETE", True),
)


def _card_size(width):
    band = int(width * 0.82)
    gap = ui.cqw(2.4, width)
    card_width = (band - gap * (COLUMNS - 1)) // COLUMNS

    pad = ui.cqw(1.2, width)
    avatar = ui.cqw(8.4, width)
    inner_gap = ui.cqw(0.6, width)
    name = ui.cqw(1.5, width)
    best = ui.cqw(1.15, width)
    card_height = pad * 2 + avatar + inner_gap * 2 + name + best

    return band, gap, card_width, card_height, pad, avatar, inner_gap, name, best


def card_rects(surface, count):
    """Rects for `count` cards laid out in the grid."""
    width, height = surface.get_size()
    band, gap, card_width, card_height, *_ = _card_size(width)

    rows = max(1, (count + COLUMNS - 1) // COLUMNS)
    total_height = rows * card_height + (rows - 1) * gap
    top = int(height * 0.49) - total_height // 2
    left = (width - band) // 2

    rects = []
    for index in range(count):
        row, column = divmod(index, COLUMNS)
        rects.append(
            pygame.Rect(
                left + column * (card_width + gap),
                top + row * (card_height + gap),
                card_width,
                card_height,
            )
        )
    return rects


def best_scores(game, users):
    """Each user's highest score in any game, as {user_id: best or None}.

    Read once per change rather than per frame: the screen redraws 60 times
    a second and this is three queries per card.
    """
    bests = {}
    for user_id, _ in users:
        scores = [game.get_best_score(user_id, key) for key in GAMES]
        scores = [score for score in scores if score is not None]
        bests[user_id] = max(scores) if scores else None
    return bests


def draw(game, entries, selected, page, page_count, bests=None):
    """Paint one frame. `entries` is the page's cards, add-card included."""
    surface = game.screen
    width = surface.get_width()

    game.blit_background(game.get_prompt_background())
    ui.dim_screen(surface)
    ui.draw_title(surface, "USERS", game.font_path)

    _, _, _, _, pad, avatar, inner_gap, name_size, best_size = _card_size(width)

    for index, (rect, entry) in enumerate(zip(card_rects(surface, len(entries)), entries)):
        is_selected = index == selected
        is_add = entry is None
        box = rect.move(0, -ui.cqw(0.7, width)) if is_selected else rect

        if is_selected:
            ui.draw_glow(surface, box)
        ui.draw_panel(surface, box, selected=is_selected, dashed=is_add and not is_selected)

        avatar_rect = pygame.Rect(0, 0, avatar, avatar)
        avatar_rect.midtop = (box.centerx, box.top + pad)

        if is_add:
            ui._draw_dashed_rect(surface, avatar_rect, (255, 255, 255, 90), max(2, ui.cqw(0.25, width)))
            ui.draw_icon(
                surface,
                "plus",
                avatar_rect.inflate(-avatar_rect.width * 0.4, -avatar_rect.height * 0.4),
                (200, 195, 210),
            )
            title, subtitle = "ADD USER", ""
        else:
            user_id, user_name = entry
            ui.draw_face(surface, game.player_face_or_none(user_id), avatar_rect)
            best = (bests or {}).get(user_id)
            title = ui.truncate(user_name.upper(), 12)
            subtitle = f"BEST {best}" if best is not None else "NO SCORES"

        ui.draw_text(
            surface,
            title,
            game.font_path,
            name_size,
            color=ui.SUN if is_selected else ui.INK,
            midtop=(box.centerx, avatar_rect.bottom + inner_gap),
            letter_spacing=ui.cqw(0.06, width),
        )
        if subtitle:
            ui.draw_text(
                surface,
                subtitle,
                game.font_path,
                best_size,
                color=(160, 152, 176),
                midtop=(box.centerx, avatar_rect.bottom + inner_gap * 2 + name_size),
            )

    _draw_actions(game, surface, entries[selected] is not None)

    if page_count > 1:
        ui.draw_text(
            surface,
            f"PAGE {page + 1} / {page_count}",
            game.font_path,
            ui.cqw(1.2, width),
            color=(170, 162, 190),
            midtop=(width // 2, surface.get_height() - ui.cqh(21.0, surface.get_height())),
            letter_spacing=ui.cqw(0.1, width),
        )

    hint = "ARROWS TO MOVE  ·  ESC TO GO BACK"
    if page_count > 1:
        hint = "ARROWS TO MOVE  ·  PGUP / PGDN FOR MORE  ·  ESC TO GO BACK"
    ui.draw_hint(surface, hint, game.font_path)

    game.present()


def _draw_actions(game, surface, on_a_user):
    """The one bar of key legends, dimmed when they don't apply."""
    width = surface.get_width()
    key_size = ui.cqw(1.2, width)
    gap = ui.cqw(2.0, width)

    entries = []
    for key, label, danger in ACTIONS:
        key_width = ui.text_width(key, game.font_path, key_size) + ui.cqw(1.2, width)
        what_width = ui.text_width(label, game.font_path, key_size, ui.cqw(0.08, width))
        entries.append((key, label, danger, max(key_width, what_width)))

    total = sum(entry[3] for entry in entries) + gap * (len(entries) - 1)
    x = (width - total) // 2
    top = surface.get_height() - ui.cqh(15.0, surface.get_height())

    for key, label, danger, cell_width in entries:
        color = ui.PINK if danger else ui.INK
        if not on_a_user:
            color = tuple(channel // 3 for channel in color)

        key_box = pygame.Rect(0, 0, ui.text_width(key, game.font_path, key_size) + ui.cqw(1.1, width), key_size + ui.cqw(0.7, width))
        key_box.midtop = (x + cell_width // 2, top)
        surface.fill(ui.BLACK, key_box)
        pygame.draw.rect(surface, color, key_box, max(2, ui.cqw(0.2, width)))
        ui.draw_text(surface, key, game.font_path, key_size, color=color, center=key_box.center)

        ui.draw_text(
            surface,
            label,
            game.font_path,
            key_size,
            color=color,
            midtop=(x + cell_width // 2, key_box.bottom + ui.cqw(0.4, width)),
            letter_spacing=ui.cqw(0.08, width),
        )
        x += cell_width + gap


# ------------------------------------------------------------------- loop
def run(game):
    """Show the users screen until the player backs out."""
    selected = 0
    page = 0
    stale = True  # re-read the users table only when something changed it

    while True:
        if stale:
            users = game.get_users()
            bests = best_scores(game, users)
            stale = False

        # The add card is the last cell, so it is always reachable
        cards = list(users) + [None]
        page_count = max(1, (len(cards) + PAGE_SIZE - 1) // PAGE_SIZE)
        page = min(page, page_count - 1)

        entries = cards[page * PAGE_SIZE : (page + 1) * PAGE_SIZE]
        selected = min(selected, len(entries) - 1)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "quit"

            if event.type != pygame.KEYDOWN:
                continue

            if event.key == pygame.K_ESCAPE:
                return None

            if event.key == pygame.K_RIGHT:
                selected = (selected + 1) % len(entries)
            elif event.key == pygame.K_LEFT:
                selected = (selected - 1) % len(entries)
            elif event.key == pygame.K_DOWN:
                selected = min(selected + COLUMNS, len(entries) - 1)
            elif event.key == pygame.K_UP:
                selected = max(selected - COLUMNS, 0)
            elif event.key == pygame.K_PAGEDOWN:
                page, selected = (page + 1) % page_count, 0
            elif event.key == pygame.K_PAGEUP:
                page, selected = (page - 1) % page_count, 0
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                _activate(game, entries[selected])
                stale = True
            elif entries[selected] is not None:
                _user_action(game, event.key, *entries[selected])
                stale = True

        game.clock.tick(60)
        draw(game, entries, selected, page, page_count, bests)


def _activate(game, entry):
    """ENTER: add a user on the add card, rename on any other."""
    if entry is None:
        _add_user(game)
        return

    user_id, user_name = entry
    new_name = game.prompt_text(
        f"Rename {user_name}",
        initial=user_name,
        lines=("Type the new name", "ENTER to save, ESC to cancel"),
    )
    if new_name:
        game.rename_user(user_id, new_name)


def _user_action(game, key, user_id, user_name):
    """The single-key actions that need a selected user."""
    if key == pygame.K_p:
        game.capture_user_face(user_id, user_name)
    elif key == pygame.K_c:
        game.clear_user_face(user_id)
    elif key in (pygame.K_DELETE, pygame.K_BACKSPACE):
        if game.ask_yes_no(f"Delete {user_name}?", ("Their scores are removed too",)):
            game.delete_user(user_id)


def _add_user(game):
    """Ask for a name, then offer to take a picture straight away."""
    user_name = game.prompt_text(
        "New user",
        lines=("Type a name", "ENTER to save, ESC to cancel"),
    )
    if not user_name:
        return

    user_id = game.add_user_returning_id(user_name)
    if user_id is None:
        # The database write itself failed (already logged by _db_execute) -
        # nothing was created, so there's no one to offer a photo for.
        return
    if game.ask_yes_no(
        f"Take a photo for {user_name}?",
        (
            "The picture is cut out with a transparent background",
            "so it can be shown in the games later",
        ),
    ):
        game.capture_user_face(user_id, user_name)
