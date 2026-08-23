"""The screens wrapped around a round of play: how-to, get-ready, the
heads-up display, and the state where there is no camera to play with.

All three games share these, so a stat chip, a viewport or a key legend
looks and sits the same wherever you meet it. Everything is positioned
against the fixed canvas, as the menus are.
"""

import pygame

from . import ui_kit as ui

# The how-to screen is shown the first time a game is picked in a session
# and skipped after that: it earns its keypress once, not every round.
INSTRUCTIONS = {
    "balloons": (
        "BALLOONS",
        (
            "Raise your hands. A pin follows each fingertip.",
            "Touch a balloon to pop it. A single balloon is 1 point.",
            "A combo balloon is worth as many points as it holds.",
            "Let a plain balloon float away and you lose a point.",
            "{waves} waves, 20 seconds each.",
        ),
        "YOUR FINGERTIPS BECOME PINS",
    ),
    "pong": (
        "PONG",
        (
            "Each player moves the paddle on their own side with one hand.",
            "Raise and lower your hand; the paddle follows its height.",
            "Get the ball past the other paddle to win the point.",
            "First to {points} points takes the match.",
        ),
        "YOUR HAND'S HEIGHT IS THE PADDLE'S",
    ),
    "runner": (
        "RUNNER",
        (
            "Sit where the camera can see your head and shoulders.",
            "Rise up to jump the cacti and the low birds.",
            "Duck down to go under the high birds.",
            "The lines are set from where you sat during the countdown.",
            "You score for distance. One hit ends the run.",
        ),
        "THE LINES SIT AROUND YOU",
    ),
}


# Pong needs two people in frame at once, so its prompt says so
READY_PROMPT = {
    "pong": "ENTER WHEN BOTH OF YOU ARE READY",
}
DEFAULT_READY_PROMPT = "ENTER WHEN YOU ARE READY"


# ------------------------------------------------------------------ pieces
def draw_game_title(game, key):
    """The shared title bar - the same black box every other screen in the
    app uses - at the top of an in-play screen.

    Balloons, Pong and Runner used to show nothing here: Balloons and Runner
    had their stat chips instead, and Pong had nothing at all, which is what
    made its top edge look empty next to the other two. One title, reused
    from the name INSTRUCTIONS already gives this game, fixes that everywhere
    at once - and returns its rect so a stat row can sit directly under it.
    """
    title = INSTRUCTIONS[key][0]
    return ui.draw_title(game.screen, title, game.font_path)


def _stat_geometry(game, chips):
    """Cell sizes and the shared chip height, for both the horizontal bar
    and the vertical column - one set of measurements so a chip looks and
    reads identically wherever it is used.
    """
    width = game.screen.get_width()

    metrics = dict(
        key_size=ui.cqw(1.05, width),
        value_size=ui.cqw(2.1, width),
        pad_x=ui.cqw(1.4, width),
        pad_y=ui.cqw(1.0, width),
        row_gap=ui.cqw(0.25, width),
        border=max(2, ui.cqw(0.25, width)),
    )
    min_width = ui.cqw(9.0, width)

    # Rendered line heights, not the nominal point sizes: a font draws taller
    # than it is asked for, so sizing the chip on the point size left the
    # value sitting on the bottom border with no padding under it.
    metrics["key_height"] = ui.font(game.font_path, metrics["key_size"]).get_height()
    metrics["value_height"] = ui.font(game.font_path, metrics["value_size"]).get_height()

    cells = []
    for key, value, color in chips:
        cell_width = max(
            min_width,
            ui.text_width(key, game.font_path, metrics["key_size"], ui.cqw(0.14, width))
            + metrics["pad_x"] * 2,
            ui.text_width(str(value), game.font_path, metrics["value_size"])
            + metrics["pad_x"] * 2,
        )
        cells.append((key, str(value), color, cell_width))

    height = (
        metrics["border"] * 2 + metrics["pad_y"] * 2 + metrics["key_height"]
        + metrics["row_gap"] + metrics["value_height"]
    )
    return cells, height, metrics


def _draw_stat_cell(game, rect, key, value, color, metrics):
    """One chip - a key label over a value - drawn inside `rect`."""
    surface = game.screen
    width = surface.get_width()

    ui.fill_rect(surface, rect, (8, 3, 18), 209)
    pygame.draw.rect(surface, (170, 166, 182), rect, metrics["border"])

    ui.draw_text(
        surface,
        key,
        game.font_path,
        metrics["key_size"],
        color=(165, 158, 180),
        midtop=(rect.centerx, rect.top + metrics["border"] + metrics["pad_y"]),
        letter_spacing=ui.cqw(0.14, width),
    )
    ui.draw_text(
        surface,
        value,
        game.font_path,
        metrics["value_size"],
        color=color,
        midtop=(
            rect.centerx,
            rect.top + metrics["border"] + metrics["pad_y"]
            + metrics["key_height"] + metrics["row_gap"],
        ),
    )


def draw_stat_bar(game, chips, top_percent=3.5, top=None):
    """Score, wave, time and so on as chips along the top edge.

    Along the top rather than down the left, which is where the balloons
    fly and where the old readout sat. `top` is an absolute pixel override
    for callers positioning the row under something else they just drew
    (the game title) - deriving it from that rect's real bottom edge keeps
    the two in step, rather than a hand-picked top_percent that only lines
    up by coincidence at today's font sizes.
    """
    surface = game.screen
    width = surface.get_width()
    gap = ui.cqw(1.2, width)

    cells, height, metrics = _stat_geometry(game, chips)
    total = sum(cell[3] for cell in cells) + gap * (len(cells) - 1)
    x = (width - total) // 2
    if top is None:
        top = ui.cqh(top_percent, surface.get_height())

    for key, value, color, cell_width in cells:
        rect = pygame.Rect(x, top, cell_width, height)
        _draw_stat_cell(game, rect, key, value, color, metrics)
        x += cell_width + gap

    return pygame.Rect((width - total) // 2, top, total, height)


def draw_stat_column(game, chips, x, align="left", center_y=None, top=None):
    """Chips stacked vertically instead of laid out in a row.

    For flanking something in the middle of the screen - Balloons' camera
    feed - rather than running along the top edge, where four chips plus a
    title started to feel like too much at once. `align` is which edge of
    the column sits at `x`: "left" for a column to the right of something,
    "right" for a column to its left. Vertically centred on `center_y`
    unless an absolute `top` is given; every chip in the column shares the
    widest cell's width, so the two boxes line up rather than each hugging
    its own text.
    """
    surface = game.screen
    chip_gap = ui.cqw(1.0, surface.get_width())

    cells, height, metrics = _stat_geometry(game, chips)
    col_width = max(cell[3] for cell in cells)
    total_height = height * len(cells) + chip_gap * (len(cells) - 1)

    if top is None:
        center_y = surface.get_height() // 2 if center_y is None else center_y
        top = center_y - total_height // 2

    left = x if align == "left" else x - col_width
    y = top
    for key, value, color, _cell_width in cells:
        rect = pygame.Rect(left, y, col_width, height)
        _draw_stat_cell(game, rect, key, value, color, metrics)
        y += height + chip_gap

    return pygame.Rect(left, top, col_width, total_height)


def draw_whoami(game, slot=0, best=None, corner="bottom-left"):
    """The player's face and name, so a round is owned.

    Bottom-left by default. Balloons puts its camera feed in the middle of
    the canvas and it reaches the bottom-left corner, so that game asks for
    the top-left instead, which its centred stat chips leave empty.
    """
    surface = game.screen
    width = surface.get_width()

    face_size = ui.cqw(4.6, width)
    name_size = ui.cqw(1.3, width)
    best_size = ui.cqw(1.05, width)
    pad = ui.cqw(0.6, width)
    gap = ui.cqw(0.9, width)
    # Borders are drawn inside the rect, so the padding sits inside them too
    border = max(2, ui.cqw(0.25, width))

    name = ui.truncate(game.player_label(slot).upper(), 14)
    best_text = f"BEST {best}" if best is not None else ""

    text_width = max(
        ui.text_width(name, game.font_path, name_size, ui.cqw(0.05, width)),
        ui.text_width(best_text, game.font_path, best_size),
    )
    box = pygame.Rect(
        ui.cqw(3.0, width),
        0,
        border * 2 + pad * 2 + face_size + gap + text_width + ui.cqw(0.6, width),
        border * 2 + face_size + pad * 2,
    )
    if corner == "top-left":
        box.top = ui.cqh(3.5, surface.get_height())
    else:
        box.bottom = surface.get_height() - ui.cqh(6.5, surface.get_height())
    ui.fill_rect(surface, box, (8, 3, 18), 204)
    pygame.draw.rect(surface, (160, 155, 172), box, border)

    face_rect = pygame.Rect(
        box.left + border + pad, box.top + border + pad, face_size, face_size
    )
    ui.draw_face(surface, game.player_face_or_none(game.current_player_id(slot)), face_rect)

    text_left = face_rect.right + gap
    if best_text:
        ui.draw_text(
            surface, name, game.font_path, name_size, color=ui.INK,
            topleft=(text_left, face_rect.top + ui.cqw(0.3, width)),
            letter_spacing=ui.cqw(0.05, width),
        )
        ui.draw_text(
            surface, best_text, game.font_path, best_size, color=(155, 148, 172),
            topleft=(text_left, face_rect.top + ui.cqw(0.3, width) + name_size + ui.cqw(0.3, width)),
        )
    else:
        ui.draw_text(
            surface, name, game.font_path, name_size, color=ui.INK,
            midleft=(text_left, face_rect.centery),
            letter_spacing=ui.cqw(0.05, width),
        )
    return box


def draw_side_score(game, slot, score, field, right=False, tracked=True):
    """One player's scoreboard, at the end of the field they control.

    Sitting at their own end is what makes the sides unambiguous; a single
    centred pair of scores does not say which is whose.
    """
    surface = game.screen
    width = surface.get_width()

    face_size = ui.cqw(3.6, width)
    name_size = ui.cqw(1.15, width)
    score_size = ui.cqw(2.4, width)
    pad = ui.cqw(0.5, width)
    gap = ui.cqw(0.8, width)
    border = max(2, ui.cqw(0.25, width))

    name = ui.truncate(game.player_label(slot).upper(), 13)
    status = "TRACKING" if tracked else "NO HAND"
    text_width = max(
        ui.text_width(name, game.font_path, name_size, ui.cqw(0.05, width)),
        ui.text_width(status, game.font_path, ui.cqw(0.9, width)),
    )
    score_width = ui.text_width(str(score), game.font_path, score_size)

    box = pygame.Rect(
        0, 0,
        border * 2 + pad * 2 + face_size + gap + text_width + gap + score_width,
        border * 2 + face_size + pad * 2,
    )
    # Above the field when there is room; tucked inside its top corner when
    # there is not, rather than sitting across the top of the play area
    margin = ui.cqw(1.2, width)
    above = field.top - box.height - margin
    box.top = above if above >= ui.cqh(3.0, surface.get_height()) else field.top + margin

    if right:
        box.right = field.right - (margin if box.top > field.top else 0)
    else:
        box.left = field.left + (margin if box.top > field.top else 0)

    ui.fill_rect(surface, box, (8, 3, 18), 209)
    pygame.draw.rect(surface, (170, 166, 182), box, border)

    # Face at the outer edge, score at the inner one, so the pair mirrors
    if right:
        face_rect = pygame.Rect(
            box.right - border - pad - face_size, box.top + border + pad, face_size, face_size
        )
        text_x = face_rect.left - gap
        score_x = box.left + border + pad
        align = "right"
    else:
        face_rect = pygame.Rect(
            box.left + border + pad, box.top + border + pad, face_size, face_size
        )
        text_x = face_rect.right + gap
        score_x = box.right - border - pad - score_width
        align = "left"

    ui.draw_face(surface, game.player_face_or_none(game.current_player_id(slot)), face_rect)

    anchor = {"midright": (text_x, 0)} if align == "right" else {"midleft": (text_x, 0)}
    name_y = face_rect.top + ui.cqw(0.35, width)
    status_y = name_y + name_size + ui.cqw(0.25, width)
    for text, size, color, y in (
        (name, name_size, ui.INK, name_y),
        (status, ui.cqw(0.9, width), ui.WIRE if tracked else (150, 100, 130), status_y),
    ):
        if align == "right":
            ui.draw_text(surface, text, game.font_path, size, color=color,
                         midright=(text_x, y + size // 2))
        else:
            ui.draw_text(surface, text, game.font_path, size, color=color,
                         topleft=(text_x, y))

    ui.draw_text(
        surface, str(score), game.font_path, score_size, color=ui.SUN,
        topleft=(score_x, face_rect.centery - score_size // 2),
    )
    return box


def draw_escape(game, text="ESC TO QUIT"):
    """The one key that always works, kept out of the way."""
    surface = game.screen
    width = surface.get_width()
    size = ui.cqw(1.1, width)
    return ui.draw_text(
        surface,
        text,
        game.font_path,
        size,
        color=(150, 143, 168),
        midright=(width - ui.cqw(3.0, width), surface.get_height() - ui.cqh(4.0, surface.get_height()) - size // 2),
        letter_spacing=ui.cqw(0.1, width),
    )


def draw_viewport(game, rect, frame, tag=None, overlays=()):
    """The camera feed in a labelled frame, filling it edge to edge.

    Scaled to cover the box (uniform zoom, centred crop) rather than
    stretched to fill it - the camera's native aspect (4:3) rarely matches
    the box's own, and a non-uniform stretch is what made a feed look
    squashed in one box and stretched in another. Covering keeps every
    part of the picture in true proportion; whatever doesn't fit is
    cropped off the edges instead of distorted, and the box still fills
    completely - same size, same look, no letterbox bars.

    `overlays` are callables taking the box rect, same as the frame that
    now fills it exactly.
    """
    surface = game.screen
    width = surface.get_width()
    border = max(2, ui.cqw(0.3, width))

    if frame is not None:
        scale = max(rect.width / frame.get_width(), rect.height / frame.get_height())
        scaled_size = (
            max(rect.width, round(frame.get_width() * scale)),
            max(rect.height, round(frame.get_height() * scale)),
        )
        # smoothscale() for an upscale (scale > 1.0): Balloons/Pong's main
        # camera box is architecturally always a 1.5x upscale of the
        # captured frame (the background art's 1280x720 space scaled to the
        # 1920x1080 canvas), and nearest-neighbour's blockiness is visibly
        # noticeable on a player's own live face/hand feed at that factor -
        # confirmed by rendering both side by side. scale() only for a
        # downscale or exact 1:1 (Runner's continuous camera box and every
        # game's pre-round demo/countdown feed, both real downscales), where
        # there's no quality loss to trade away for the lower cost.
        transform = pygame.transform.smoothscale if scale > 1.0 else pygame.transform.scale
        scaled = transform(frame, scaled_size)
        crop = pygame.Rect(0, 0, rect.width, rect.height)
        crop.center = scaled.get_rect().center
        surface.blit(scaled, rect.topleft, area=crop)
    else:
        ui.fill_rect(surface, rect, (10, 4, 22), 235)

    previous_clip = surface.get_clip()
    surface.set_clip(rect)
    for overlay in overlays:
        overlay(rect)
    surface.set_clip(previous_clip)

    pygame.draw.rect(surface, (200, 196, 212), rect, border)

    if tag:
        size = ui.cqw(1.0, width)
        label = ui.draw_text(
            surface, tag, game.font_path, size, color=ui.WIRE,
            topleft=(rect.left + border + ui.cqw(0.5, width), rect.top + border + ui.cqw(0.3, width)),
            background=(0, 0, 0), letter_spacing=ui.cqw(0.12, width),
        )
        return label
    return rect


def threshold_overlay(game, jump_ratio, duck_ratio, nose_ratio=None):
    """Draws Runner's jump and duck lines, and the tracked point, on a feed."""
    width = game.screen.get_width()

    def draw(rect):
        surface = game.screen
        size = ui.cqw(0.85, width)
        thickness = max(2, ui.cqw(0.35, width))

        for ratio, color, label in (
            (jump_ratio, ui.SUN, "JUMP"),
            (duck_ratio, ui.WIRE, "DUCK"),
        ):
            y = rect.top + int(rect.height * ratio)
            surface.fill(color, (rect.left, y - thickness // 2, rect.width, thickness))
            ui.draw_text(
                surface, label, game.font_path, size, color=color,
                midright=(rect.right - ui.cqw(0.4, width), y),
                background=(0, 0, 0), letter_spacing=ui.cqw(0.1, width),
            )

        if nose_ratio is not None:
            radius = max(3, ui.cqw(0.6, width))
            pygame.draw.circle(
                surface, ui.PINK,
                (rect.centerx, rect.top + int(rect.height * nose_ratio)), radius,
            )

    return draw


# ------------------------------------------------------------------ screens
def show_instructions(game, key, **substitutions):
    """The how-to screen. Returns False if the player backed out.

    Shown once per game per session: the rules earn a keypress the first
    time, not on every round.
    """
    if key in game.instructions_seen:
        return True

    title, rules, caption = INSTRUCTIONS[key]
    rules = [rule.format(**substitutions) for rule in rules]

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return False
                if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                    game.mark_instructions_seen(key)
                    return True

        _draw_instructions(game, title, rules, caption, key)
        game.clock.tick(30)


def _draw_instructions(game, title, rules, caption, key):
    surface = game.screen
    width, height = surface.get_size()

    game.blit_background(game.get_prompt_background())
    ui.dim_screen(surface)
    ui.draw_title(surface, title, game.font_path)

    band = int(width * 0.76)
    left = (width - band) // 2
    gap = ui.cqw(3.0, width)
    demo_width = int(band * 0.34)
    rules_left = left + demo_width + gap
    rules_width = band - demo_width - gap

    rule_size = ui.cqw(1.3, width)
    rule_pad = ui.cqw(1.0, width)
    rule_gap = ui.cqw(1.1, width)
    num_size = ui.cqw(3.4, width)
    num_gap = ui.cqw(1.2, width)
    text_left = rules_left + rule_pad + num_size + num_gap
    text_width = rules_width - rule_pad * 2 - num_size - num_gap

    wrapped = [
        _wrap(rule, game.font_path, rule_size, text_width, ui.cqw(0.03, width))
        for rule in rules
    ]
    line_height = ui.font(game.font_path, rule_size).get_height()
    heights = [max(num_size, len(lines) * line_height) + rule_pad * 2 for lines in wrapped]
    total = sum(heights) + rule_gap * (len(heights) - 1)

    top = int(height * 0.48) - total // 2
    _draw_demo(game, pygame.Rect(left, top, demo_width, total), caption, key)

    y = top
    for index, (lines, box_height) in enumerate(zip(wrapped, heights)):
        box = pygame.Rect(rules_left, y, rules_width, box_height)
        ui.fill_rect(surface, box, (10, 4, 22), 204)
        pygame.draw.rect(surface, (150, 145, 162), box, max(2, ui.cqw(0.25, width)))

        num_box = pygame.Rect(box.left + rule_pad, box.top + rule_pad, num_size, num_size)
        pygame.draw.rect(surface, (255, 201, 60, 128), num_box, max(2, ui.cqw(0.2, width)))
        ui.draw_text(
            surface, str(index + 1), game.font_path, rule_size,
            color=ui.SUN, center=num_box.center,
        )

        for line_number, line in enumerate(lines):
            ui.draw_text(
                surface, line, game.font_path, rule_size, color=ui.INK,
                topleft=(text_left, box.top + rule_pad + line_number * line_height),
                letter_spacing=ui.cqw(0.03, width),
            )
        y += box_height + rule_gap

    _draw_ready_pill(game, READY_PROMPT.get(key, DEFAULT_READY_PROMPT))
    ui.draw_hint(surface, "ESC TO GO BACK", game.font_path)
    game.present()


def _draw_demo(game, rect, caption, key):
    """The live camera beside the rules, with this game's guide drawn on it.

    A live feed rather than a diagram, so you are already framing yourself
    while you read.
    """
    surface = game.screen
    width = surface.get_width()

    frame = game.camera_surface()
    overlays = []
    if key == "runner":
        overlays.append(threshold_overlay(game, 0.30, 0.70))
    draw_viewport(game, rect, frame, overlays=overlays)

    # The box is sized to however many lines the caption wraps to, so a long
    # one does not spill out of the bottom of it
    size = ui.cqw(1.15, width)
    lines = _wrap(
        caption, game.font_path, size, rect.width - ui.cqw(1.6, width),
        ui.cqw(0.1, width),
    )
    line_height = ui.font(game.font_path, size).get_height()
    pad = ui.cqw(0.4, width)

    caption_height = len(lines) * line_height + pad * 2
    caption_box = pygame.Rect(rect.left, rect.bottom - caption_height, rect.width, caption_height)
    ui.fill_rect(surface, caption_box, (0, 0, 0), 204)
    for line_number, line in enumerate(lines):
        ui.draw_text(
            surface, line, game.font_path, size, color=ui.SUN,
            midtop=(caption_box.centerx, caption_box.top + pad + line_number * line_height),
            letter_spacing=ui.cqw(0.1, width),
        )


def _draw_ready_pill(game, text):
    surface = game.screen
    width = surface.get_width()
    size = ui.cqw(1.6, width)

    label = ui.text_width(text, game.font_path, size, ui.cqw(0.12, width))
    box = pygame.Rect(0, 0, label + ui.cqw(2.4, width), size + ui.cqw(1.4, width))
    box.midbottom = (width // 2, surface.get_height() - ui.cqh(10.0, surface.get_height()))

    ui.fill_rect(surface, box, (0, 0, 0), 217)
    pygame.draw.rect(surface, ui.SUN, box, max(2, ui.cqw(0.25, width)))
    ui.draw_text(
        surface, text, game.font_path, size, color=ui.SUN,
        center=box.center, letter_spacing=ui.cqw(0.12, width),
    )


def draw_countdown(game, title, heading, seconds, total, sub, viewport=None, overlays=()):
    """The get-ready beat: one big number, and what to do while it runs."""
    surface = game.screen
    width, height = surface.get_size()

    game.blit_background(game.get_prompt_background())
    ui.dim_screen(surface)
    ui.draw_title(surface, title, game.font_path)

    heading_size = ui.cqw(2.0, width)
    digit_size = ui.cqw(14.0, width)
    sub_size = ui.cqw(1.35, width)
    gap = ui.cqw(1.4, width)
    pip = ui.cqw(1.4, width)

    block = heading_size + gap + digit_size + gap + sub_size + gap + pip
    top = height // 2 - block // 2

    ui.draw_text(
        surface, heading, game.font_path, heading_size, color=ui.INK,
        midtop=(width // 2, top), letter_spacing=ui.cqw(0.16, width),
    )
    ui.draw_text(
        surface, str(max(0, seconds)), game.font_path, digit_size, color=ui.SUN,
        midtop=(width // 2, top + heading_size + gap),
    )
    ui.draw_text(
        surface, sub, game.font_path, sub_size, color=(200, 192, 218),
        midtop=(width // 2, top + heading_size + gap + digit_size + gap),
        letter_spacing=ui.cqw(0.08, width),
    )

    # One pip per second, filled for the ones already gone
    pip_gap = ui.cqw(0.8, width)
    pips_width = total * pip + (total - 1) * pip_gap
    pip_y = top + heading_size + gap * 3 + digit_size + sub_size
    for index in range(total):
        cell = pygame.Rect(
            (width - pips_width) // 2 + index * (pip + pip_gap), pip_y, pip, pip
        )
        if index < total - max(0, seconds):
            surface.fill(ui.SUN, cell)
        else:
            ui.fill_rect(surface, cell, ui.WHITE, 56)

    if viewport is not None:
        draw_viewport(game, viewport, game.camera_surface(), "YOU", overlays)

    ui.draw_hint(surface, "ESC TO GO BACK", game.font_path)
    game.draw_fps()
    game.present()


def corner_viewport(game, width_percent=17.0, top_percent=3.5):
    """The small camera box games park in the top-right corner."""
    surface = game.screen
    width, height = surface.get_size()
    box_width = int(width * width_percent / 100)
    return pygame.Rect(
        width - ui.cqw(3.0, width) - box_width,
        ui.cqh(top_percent, height),
        box_width,
        box_width * 3 // 4,
    )


def draw_banner(game, big, small):
    """The between-waves card, in place of a line of text over the field."""
    surface = game.screen
    width, height = surface.get_size()

    big_size = ui.cqw(3.4, width)
    small_size = ui.cqw(1.3, width)
    pad_x = ui.cqw(3.0, width)
    pad_y = ui.cqw(1.0, width)
    gap = ui.cqw(0.4, width)

    box = pygame.Rect(
        0, 0,
        max(
            ui.text_width(big, game.font_path, big_size, ui.cqw(0.14, width)),
            ui.text_width(small, game.font_path, small_size, ui.cqw(0.1, width)),
        ) + pad_x * 2,
        big_size + gap + small_size + pad_y * 2,
    )
    box.center = (width // 2, height // 2)

    ui.fill_rect(surface, box, (0, 0, 0), 217)
    edge = max(2, ui.cqw(0.3, width))
    surface.fill(ui.SUN, (box.left, box.top, box.width, edge))
    surface.fill(ui.SUN, (box.left, box.bottom - edge, box.width, edge))

    ui.draw_text(
        surface, big, game.font_path, big_size, color=ui.SUN,
        midtop=(box.centerx, box.top + pad_y), letter_spacing=ui.cqw(0.14, width),
    )
    ui.draw_text(
        surface, small, game.font_path, small_size, color=(200, 192, 218),
        midtop=(box.centerx, box.top + pad_y + big_size + gap),
        letter_spacing=ui.cqw(0.1, width),
    )
    return box


def show_privacy_notice(game):
    """The one-time "everything stays on this device" screen.

    Shown once, ever, before the very first main menu - gated by
    settings["privacy_notice_seen"] in gui.py, the same shape as
    instructions_seen. CREDITS keeps a permanent copy of the same message
    for anyone who wants to check again later.
    """
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                exit()
            if event.type == pygame.KEYDOWN:
                return

        draw_privacy_notice(game)
        game.clock.tick(30)


def draw_privacy_notice(game):
    """One frame of the privacy notice panel."""
    _draw_info_panel(
        game,
        icon="lock",
        accent_color=ui.WIRE,
        bullet_color=ui.SUN,
        title="100% LOCAL",
        body_text=(
            "Everything runs on this computer. Your camera feed, your photo "
            "and your scores are never uploaded - there is no account and no "
            "internet connection involved."
        ),
        bullet_lines=(
            "You can delete your photo or your profile any time from USERS",
            "See PRIVACY in CREDITS to read this again",
        ),
        footer_hint="PRESS ANY KEY TO CONTINUE",
    )


def show_no_camera(game, game_name):
    """Explain that a camera is needed, and point at the setting that fixes it."""
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                exit()
            if event.type == pygame.KEYDOWN and event.key in (
                pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_KP_ENTER
            ):
                return

        draw_no_camera(game, game_name)
        game.clock.tick(30)


def draw_no_camera(game, game_name):
    """One frame of the no-camera panel."""
    _draw_info_panel(
        game,
        icon="camera",
        accent_color=ui.PINK,
        bullet_color=(180, 172, 200),
        title="NO CAMERA",
        body_text=(
            f"{game_name} is played with your hands, so it needs a working "
            f"camera. Nothing was found on camera {game.settings['camera_number']}."
        ),
        bullet_lines=(
            "Close anything else using the camera, then try again",
            "Or pick a different one under SETTINGS > CAMERA > DEVICE",
        ),
        footer_hint="ESC FOR THE MAIN MENU",
    )


def _draw_info_panel(
    game, icon, accent_color, bullet_color, title, body_text, bullet_lines, footer_hint
):
    """The centred icon/title/body/bullet-list panel shared by the privacy
    notice and the no-camera screen - same layout algorithm, different
    icon, colours and text.
    """
    surface = game.screen
    width, height = surface.get_size()

    game.blit_background(game.get_prompt_background())
    ui.dim_screen(surface)

    pad = ui.cqw(2.6, width)
    glyph_size = ui.cqw(8.0, width)
    title_size = ui.cqw(2.4, width)
    body_size = ui.cqw(1.35, width)
    bullet_size = ui.cqw(1.2, width)
    gap = ui.cqw(1.1, width)

    body = _wrap(body_text, game.font_path, body_size, int(width * 0.52) - pad * 2)
    # Wrapped like the body: some bullets are longer than the panel is wide
    bullets = [
        line
        for bullet in bullet_lines
        for line in _wrap(bullet, game.font_path, bullet_size, int(width * 0.52) - pad * 2)
    ]

    line_height = ui.font(game.font_path, body_size).get_height()
    bullet_height = ui.font(game.font_path, bullet_size).get_height()
    box = pygame.Rect(
        0, 0, int(width * 0.52),
        pad * 2 + glyph_size + gap + title_size + gap
        + len(body) * line_height + gap + len(bullets) * (bullet_height + ui.cqw(0.5, width)),
    )
    box.center = (width // 2, height // 2)

    ui.fill_rect(surface, box, (8, 3, 18), 230)
    pygame.draw.rect(surface, accent_color, box, max(2, ui.cqw(0.35, width)))

    glyph_box = pygame.Rect(0, 0, glyph_size, glyph_size)
    glyph_box.midtop = (box.centerx, box.top + pad)
    pygame.draw.rect(surface, accent_color, glyph_box, max(2, ui.cqw(0.3, width)))
    ui.draw_icon(
        surface, icon,
        glyph_box.inflate(-glyph_size * 0.38, -glyph_size * 0.38), accent_color,
    )

    y = glyph_box.bottom + gap
    ui.draw_text(
        surface, title, game.font_path, title_size, color=accent_color,
        midtop=(box.centerx, y), letter_spacing=ui.cqw(0.1, width),
    )
    y += title_size + gap
    for line in body:
        ui.draw_text(
            surface, line, game.font_path, body_size, color=(210, 203, 228),
            midtop=(box.centerx, y),
        )
        y += line_height
    y += gap
    for bullet in bullets:
        ui.draw_text(
            surface, bullet, game.font_path, bullet_size, color=bullet_color,
            midtop=(box.centerx, y),
        )
        y += bullet_height + ui.cqw(0.5, width)

    ui.draw_hint(surface, footer_hint, game.font_path)
    game.present()


# ------------------------------------------------------------------- utils
def _wrap(text, path, size, max_width, letter_spacing=0):
    """Break a line to fit a width, on word boundaries.

    The spacing has to match what the caller draws with, or a line measured
    as fitting comes out wider than the box it was measured against.
    """
    words = text.split()
    if not words:
        return [""]

    lines, current = [], words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if ui.text_width(candidate, path, size, letter_spacing) <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines
