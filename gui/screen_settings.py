"""The settings screen: one scrolling-free column, grouped by section.

Rows are declared as data below, so adding a setting is one entry in a list
- there is no row count for the layout to fall out of step with. Every
change writes straight through `change_setting`, which applies and saves it.

Used to be three side-by-side panels (Audio/Camera/Gameplay) with Up/Down
walking one flat list ordered panel-by-panel. That flat order didn't match
the 2D layout: Audio only has 2 rows while Camera and Gameplay have 3, so
pressing Down from Audio's last row jumped up and sideways into Camera's
first row instead of moving to whatever was visually below it. A single
column removes the mismatch entirely - the flat list's order and the
on-screen order are the same thing, so Down is always "the next row down".
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


class Metrics:
    """Every measurement the settings screen is laid out from.

    Panel height and row positions both come from here, so they cannot
    disagree. They used to be worked out separately from the nominal font
    sizes, while the drawing used the fonts' real line heights and a switch
    that is taller than a line of text - so the last control overran the
    bottom padding and sat on the border.
    """

    def __init__(self, game):
        width, height = game.screen.get_size()
        path = game.font_path

        self.width, self.height = width, height
        self.pad = ui.cqw(1.1, width)
        # The border is drawn inside the rect, so the padding has to sit
        # inside it as well. Without this the last control ended up closer
        # to the edge than the heading, by exactly the border's thickness.
        self.border = max(2, ui.cqw(0.3, width))
        self.rule_gap = ui.cqw(0.4, width)
        self.rule_height = max(2, ui.cqw(0.2, width))
        self.row_gap = ui.cqw(0.85, width)
        # Space between one section's last row and the next section's
        # heading - bigger than row_gap so the grouping still reads clearly
        # now that every row lives in one column instead of separate boxes.
        self.section_gap = ui.cqw(1.3, width)
        self.label_gap = ui.cqw(0.35, width)

        # Sized smaller than the old 3-panel layout's fonts - stacking all
        # 3 sections into one column means fitting 9 rows and 3 headings
        # between the title and the hint instead of at most 3 rows, and
        # this is the only screen with that much content in one column.
        self.heading_size = ui.cqw(1.3, width)
        self.label_size = ui.cqw(1.1, width)
        self.value_size = ui.cqw(1.15, width)
        self.meter_height = ui.cqw(0.95, width)
        self.switch_height = self.value_size + ui.cqw(0.5, width)

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

    def section_height(self, rows):
        """A section's heading, its rule, and all its rows - top to bottom."""
        return (
            self.heading_height + self.rule_gap + self.rule_height + self.row_gap
            + self.body_height(rows)
        )

    def content_height(self, panels):
        return (
            sum(self.section_height(rows) for _, rows in panels)
            + self.section_gap * (len(panels) - 1)
        )

    def panel_height(self, panels):
        return self.border + self.pad + self.content_height(panels) + self.pad + self.border


def panel_rect(game):
    """The one card every section is stacked inside.

    Centered in the space between the title and the hint rather than at a
    fixed screen percentage - stacking all 3 sections into one column makes
    this panel far taller than any one of the old side-by-side panels ever
    was, and a percentage anchored to screen center pushed its top edge up
    into the title text once the panel got this tall.
    """
    metrics = Metrics(game)
    width, height = metrics.width, metrics.height
    band = int(width * 0.44)
    panel_height = metrics.panel_height(PANELS)

    title_bottom = ui.cqh(6.0, height) + ui.font(game.font_path, ui.cqw(2.9, width)).get_height()
    hint_top = height - ui.cqh(5.0, height) - ui.font(game.font_path, ui.cqw(1.35, width)).get_height()

    margin = ui.cqh(1.5, height)
    top = (title_bottom + margin + hint_top - margin - panel_height) // 2
    top = max(top, title_bottom + margin)

    left = (width - band) // 2

    return pygame.Rect(left, top, band, panel_height)


def draw(game, selected):
    """Paint one frame. `selected` indexes into the flat ROWS list."""
    surface = game.screen
    width = surface.get_width()

    game.blit_background(game.get_prompt_background())
    ui.dim_screen(surface)
    ui.draw_title(surface, "SETTINGS", game.font_path)

    metrics = Metrics(game)
    pad = metrics.pad
    rect = panel_rect(game)
    ui.draw_panel(surface, rect, fill_alpha=214)

    y = rect.top + metrics.border + pad
    row_index = 0
    for section_index, (title, rows) in enumerate(PANELS):
        if section_index > 0:
            y += metrics.section_gap

        ui.draw_text(
            surface,
            title,
            game.font_path,
            metrics.heading_size,
            color=ui.SUN,
            topleft=(rect.left + pad, y),
            letter_spacing=ui.cqw(0.14, width),
        )
        rule_y = y + metrics.heading_height + metrics.rule_gap
        ui.fill_rect(
            surface,
            pygame.Rect(rect.left + pad, rule_y, rect.width - pad * 2, metrics.rule_height),
            ui.WHITE,
            52,
        )
        y = rule_y + metrics.rule_height + metrics.row_gap

        for row_offset, row in enumerate(rows):
            _draw_row(game, surface, metrics, row, rect, y, row_index == selected)
            y += metrics.row_height(row)
            if row_offset < len(rows) - 1:
                y += metrics.row_gap
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
                game.quit_app()

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
