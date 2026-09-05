"""Tests for background music continuity.

The main menu is re-entered constantly - Users, Leaderboards, Settings and
Credits all return straight back to it - and every return used to reload
the menu theme and play it from the top, so it restarted from the first bar
every few seconds. The menu now leaves its own track alone; the games still
restart theirs, because a new round should sound like one.
"""
import pytest

from gui import gui as gui_mod


@pytest.fixture
def music(game, monkeypatch):
    """Record what the app asks pygame's music player to do."""

    calls = {"load": [], "play": 0, "volume": [], "busy": False}

    def fake_load(path):
        calls["load"].append(path.rsplit("/", 1)[-1])
        calls["busy"] = True

    def fake_play(loops=0):
        calls["play"] += 1

    monkeypatch.setattr(gui_mod.mixer.music, "load", fake_load)
    monkeypatch.setattr(gui_mod.mixer.music, "play", fake_play)
    monkeypatch.setattr(gui_mod.mixer.music, "set_volume", calls["volume"].append)
    monkeypatch.setattr(gui_mod.mixer.music, "get_busy", lambda: calls["busy"])
    # Nothing is playing yet, and no track is loaded
    game._current_music = None
    return calls


def test_asking_for_the_playing_track_again_does_not_reload_it(game, music):
    game.play_music("bg-music.ogg")
    game.play_music("bg-music.ogg")
    game.play_music("bg-music.ogg")

    assert music["load"] == ["bg-music.ogg"], "the menu theme was restarted"
    assert music["play"] == 1


def test_a_track_still_starts_when_nothing_is_playing(game, music):
    game.play_music("bg-music.ogg")
    assert music["load"] == ["bg-music.ogg"]
    assert music["play"] == 1


def test_the_menu_theme_restarts_after_a_game_took_the_music_over(game, music):
    # The case that makes matching on the filename necessary: music is still
    # "busy" after a round, but it is the game's theme, not the menu's.
    game.play_music("bg-music.ogg")
    game.play_music("runner-bg-music.ogg", restart=True)
    game.play_music("bg-music.ogg")

    assert music["load"] == ["bg-music.ogg", "runner-bg-music.ogg", "bg-music.ogg"]


def test_a_game_restarts_its_own_track_on_a_replay(game, music):
    # Playing the same game twice in a row should start the round's music
    # again rather than joining it mid-way.
    game.play_music("balloon-bg-music.ogg", restart=True)
    game.play_music("balloon-bg-music.ogg", restart=True)

    assert music["load"] == ["balloon-bg-music.ogg"] * 2
    assert music["play"] == 2


def test_a_track_left_alone_still_follows_the_volume_setting(game, music):
    # The settings screen changes music volume live; skipping the reload
    # must not also skip keeping the volume in sync.
    game.play_music("bg-music.ogg")
    game.music_volume = 0.25
    music["volume"].clear()

    game.play_music("bg-music.ogg")

    assert music["volume"] == [0.25]
    assert music["load"] == ["bg-music.ogg"], "volume sync should not reload the track"


def test_music_stopping_on_its_own_lets_the_track_start_again(game, music):
    game.play_music("bg-music.ogg")
    music["busy"] = False  # e.g. the mixer was stopped

    game.play_music("bg-music.ogg")

    assert music["load"] == ["bg-music.ogg"] * 2


# ------------------------------------------------------ real entry points
def test_returning_to_the_main_menu_does_not_restart_its_music(game, music, monkeypatch):
    # Drives the genuine entry point: Game.run() calls start_main_menu()
    # again every time another screen returns.
    monkeypatch.setattr(gui_mod.screen_menu, "run", lambda g: "quit")

    game.start_main_menu()
    game.start_main_menu()
    game.start_main_menu()

    assert music["load"] == ["bg-music.ogg"], "menu music restarted on re-entry"
    assert music["play"] == 1


def test_every_background_track_goes_through_play_music():
    # A call site loading music directly would bypass the continuity check
    # and reintroduce the restart.
    import ast

    source = open("gui/gui.py").read()
    tree = ast.parse(source)
    play_music = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "play_music"
    )
    outside = source.replace(ast.get_source_segment(source, play_music), "")

    assert "mixer.music.load" not in outside
    assert "mixer.music.play" not in outside
