"""The settings screen: three labelled panels instead of one long column.

Rows are declared as data below, so adding a setting is one entry in a list
- there is no row count for the layout to fall out of step with. Every
change writes straight through `change_setting`, which applies and saves it.
"""

import pygame

from . import ui_kit as ui
from .settings_config import (
    BALLOONS_WAVES_RANGE,
    CAMERA_NUMBERS,
    DIFFICULTIES,
    GESTURE_SENSITIVITY_RANGE,
    PONG_POINTS_RANGE,
    VOLUME_RANGE,
)


class Row:
    """One setting. `kind` decides how it draws and how arrows change it."""

    def __init__(self, label, key, kind, values=None, step=1):
        self.label = label
        self.key = key
        self.kind = kind  # "meter" | "choice" | "switch"
        self.values = values
        self.step = step

    # -- value handling ----------------------------------------------------
    def adjust(self, game, direction):
        """Move this setting one notch. Returns the new value."""
        current = game.settings[self.key]

        if self.kind == "meter":
            low, high = self.values
            return max(low, min(high, int(current) + direction * self.step))

        if self.kind == "choice":
            options = self.values
            index = options.index(current) if current in options else 0
            return options[(index + direction) % len(options)]

        return not bool(current)

    def meter_fill(self, value):
        """How many segments are lit, and how many there are."""
        low, high = self.values
        total = (high - low) // self.step + 1
        filled = int(round((int(value) - low) / self.step)) + 1
        return max(0, min(total, filled)), total


PANELS = (
    (
        "AUDIO",
        (
            Row("MUSIC", "music_volume", "meter", VOLUME_RANGE, step=5),
            Row("SOUND", "sound_volume", "meter", VOLUME_RANGE, step=5),
        ),
    ),
    (
        "CAMERA",
        (
            Row("DEVICE", "camera_number", "choice", CAMERA_NUMBERS),
            Row("SENSITIVITY", "gesture_sensitivity", "meter", GESTURE_SENSITIVITY_RANGE),
            Row("SHOW FPS", "show_fps", "switch"),
        ),
    ),
    (
        "GAMEPLAY",
        (
            Row("DIFFICULTY", "difficulty", "choice", DIFFICULTIES),
            Row("PONG POINTS", "pong_points_to_win", "meter", PONG_POINTS_RANGE),
            Row("BALLOON WAVES", "balloons_waves", "meter", BALLOONS_WAVES_RANGE),
        ),
    ),
)

ROWS = [row for _, rows in PANELS for row in rows]


def _metrics(width):
    band = int(width * 0.84)
    gap = ui.cqw(2.4, width)
    panel_width = (band - gap * (len(PANELS) - 1)) // len(PANELS)
    return band, gap, panel_width


class Metrics:
    """Every measurement the settings screen is laid out from.

    Panel heights and row positions both come from here, so they cannot
    disagree. They used to be worked out separately from the nominal font
    sizes, while the drawing used the fonts' real line heights and a switch
    that is taller than a line of text - so the last control in a panel
    overran the bottom padding and sat on the border.
    """

    def __init__(self, game):
        width, height = game.screen.get_size()
        path = game.font_path

        self.width, self.height = width, height
        self.pad = ui.cqw(1.4, width)
        # The border is drawn inside the rect, so the padding has to sit
        # inside it as well. Without this the last control ended up closer
        # to the edge than the heading, by exactly the border's thickness.
        self.border = max(2, ui.cqw(0.3, width))
        self.rule_gap = ui.cqw(0.5, width)
        self.rule_height = max(2, ui.cqw(0.2, width))
        self.row_gap = ui.cqw(1.1, width)
        self.label_gap = ui.cqw(0.45, width)

        self.heading_size = ui.cqw(1.5, width)
        self.label_size = ui.cqw(1.25, width)
        self.value_size = ui.cqw(1.3, width)
        self.meter_height = ui.cqw(1.1, width)
        self.switch_height = self.value_size + ui.cqw(0.6, width)

        # Rendered line heights, which exceed the nominal point size
        self.heading_height = ui.font(path, self.heading_size).get_height()
        self.label_height = ui.font(path, self.label_size).get_height()
        self.value_height = ui.font(path, self.value_size).get_height()

    def control_height(self, kind):
        """How tall the control under a row's label actually draws."""
        if kind == "meter":
            return self.meter_height
        if kind == "switch":
            return self.switch_height
        return self.value_height

    def row_height(self, row):
        return self.label_height + self.label_gap + self.control_height(row.kind)

    def body_height(self, rows):
        return sum(self.row_height(row) for row in rows) + self.row_gap * (len(rows) - 1)

    @property
    def header_height(self):
        """Border and top padding through to the first row's label."""
        return (
            self.border + self.pad + self.heading_height
            + self.rule_gap + self.rule_height + self.row_gap
        )

    def panel_height(self, rows):
        return self.header_height + self.body_height(rows) + self.pad + self.border


def panel_rects(game):
    """A rect per panel, all sharing a top edge."""
    metrics = Metrics(game)
    width = metrics.width
    band, gap, panel_width = _metrics(width)

    tallest = max(metrics.panel_height(rows) for _, rows in PANELS)
    top = int(metrics.height * 0.52) - tallest // 2
    left = (width - band) // 2

    return [
        pygame.Rect(
            left + index * (panel_width + gap),
            top,
            panel_width,
            metrics.panel_height(rows),
        )
        for index, (_, rows) in enumerate(PANELS)
    ]


def draw(game, selected):
    """Paint one frame. `selected` indexes into the flat ROWS list."""
    surface = game.screen
    width = surface.get_width()

    game.blit_background(game.get_prompt_background())
    ui.dim_screen(surface)
    ui.draw_title(surface, "SETTINGS", game.font_path)

    metrics = Metrics(game)
    pad = metrics.pad

    row_index = 0
    for (title, rows), rect in zip(PANELS, panel_rects(game)):
        ui.draw_panel(surface, rect, fill_alpha=214)

        ui.draw_text(
            surface,
            title,
            game.font_path,
            metrics.heading_size,
            color=ui.SUN,
            topleft=(rect.left + pad, rect.top + metrics.border + pad),
            letter_spacing=ui.cqw(0.14, width),
        )
        rule_y = rect.top + metrics.border + pad + metrics.heading_height + metrics.rule_gap
        ui.fill_rect(
            surface,
            pygame.Rect(rect.left + pad, rule_y, rect.width - pad * 2, metrics.rule_height),
            ui.WHITE,
            52,
        )

        y = rect.top + metrics.header_height
        for row in rows:
            _draw_row(game, surface, metrics, row, rect, y, row_index == selected)
            y += metrics.row_height(row) + metrics.row_gap
            row_index += 1

    ui.draw_hint(
        surface,
        "UP / DOWN TO MOVE  ·  LEFT / RIGHT TO CHANGE  ·  ESC TO GO BACK",
        game.font_path,
    )
    game.present()


def _draw_row(game, surface, metrics, row, panel, y, selected):
    """One label and the control beneath it."""
    width = surface.get_width()
    value = game.settings[row.key]
    inner_width = panel.width - metrics.pad * 2
    left = panel.left + metrics.pad

    ui.draw_text(
        surface,
        row.label,
        game.font_path,
        metrics.label_size,
        color=ui.SUN if selected else (215, 208, 230),
        topleft=(left, y),
        letter_spacing=ui.cqw(0.06, width),
    )

    control_top = y + metrics.label_height + metrics.label_gap

    if row.kind == "meter":
        filled, total = row.meter_fill(value)
        ui.draw_meter(
            surface,
            pygame.Rect(left, control_top, inner_width, metrics.meter_height),
            filled,
            total,
            color=ui.SUN if selected else ui.WIRE,
        )
        return

    if row.kind == "choice":
        color = ui.SUN if selected else ui.INK
        ui.draw_text(surface, "<", game.font_path, metrics.value_size, color=color, topleft=(left, control_top))
        ui.draw_text(
            surface,
            str(value),
            game.font_path,
            metrics.value_size,
            color=color,
            midtop=(left + inner_width // 2, control_top),
            letter_spacing=ui.cqw(0.08, width),
        )
        arrow_width = ui.text_width(">", game.font_path, metrics.value_size)
        ui.draw_text(
            surface,
            ">",
            game.font_path,
            metrics.value_size,
            color=color,
            topleft=(left + inner_width - arrow_width, control_top),
        )
        return

    # switch
    on = bool(value)
    cell_width = ui.text_width("OFF", game.font_path, metrics.value_size) + ui.cqw(1.4, width)
    height = metrics.switch_height
    for index, (text, active) in enumerate((("OFF", not on), ("ON", on))):
        cell = pygame.Rect(left + index * (cell_width + ui.cqw(0.4, width)), control_top, cell_width, height)
        if active:
            surface.fill(ui.SUN if selected else ui.WIRE, cell)
        else:
            ui.fill_rect(surface, cell, ui.WHITE, 36)
        ui.draw_text(
            surface,
            text,
            game.font_path,
            metrics.value_size,
            color=(6, 18, 26) if active else (205, 198, 220),
            center=cell.center,
        )


# ------------------------------------------------------------------- loop
def run(game):
    """Show the settings screen until the player backs out."""
    selected = 0

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "quit"

            if event.type != pygame.KEYDOWN:
                continue

            if event.key == pygame.K_ESCAPE:
                return None

            if event.key == pygame.K_DOWN:
                selected = (selected + 1) % len(ROWS)
            elif event.key == pygame.K_UP:
                selected = (selected - 1) % len(ROWS)
            elif event.key in (pygame.K_RIGHT, pygame.K_LEFT):
                row = ROWS[selected]
                direction = 1 if event.key == pygame.K_RIGHT else -1
                game.change_setting(row.key, row.adjust(game, direction))

        game.clock.tick(60)
        draw(game, selected)
