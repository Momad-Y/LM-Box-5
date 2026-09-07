"""The game must still run on a machine with no audio device.

pygame.mixer.init() raises when there is no usable audio endpoint - no
sound card, a VM, a container, a driver already holding the device. It was
called unguarded during Game.__init__, so that raised before a window ever
appeared: a missing speaker cost you the entire game, in which the sound is
incidental and the camera is the point.

This was not theoretical. Running the packaged Windows build under Wine
died exactly here, with "WASAPI can't find requested audio endpoint", which
is what surfaced it.
"""
import pygame
import pytest

from gui import gui as gui_mod
from gui.audio import SilentSound, start_audio


@pytest.fixture
def deaf(monkeypatch):
    """A machine whose mixer refuses to start."""
    def refuse():
        raise pygame.error("WASAPI can't find requested audio endpoint")

    monkeypatch.setattr(gui_mod.mixer, "init", refuse)
    return refuse


# ------------------------------------------------------------ the stand-in
def test_silent_sound_answers_everything_the_games_call():
    silent = SilentSound()
    # Whatever a real Sound is asked to do here, this must absorb.
    assert silent.play() is None
    assert silent.set_volume(0.5) is None
    assert silent.stop() is None
    assert silent.get_volume() == 0.0
    assert silent.get_num_channels() == 0


def test_start_audio_reports_failure_instead_of_raising(deaf):
    assert start_audio() is False


def test_start_audio_reports_success_when_the_mixer_starts(monkeypatch):
    monkeypatch.setattr(gui_mod.mixer, "init", lambda: None)
    assert start_audio() is True


# ------------------------------------------------------------ the real game
def test_the_game_starts_with_no_audio_device(sandboxed_data_dir, sandboxed_camera, deaf):
    # The actual regression: this used to raise pygame.error from __init__.
    Game = sandboxed_data_dir.Game
    Game.run = lambda self: None
    game = Game()
    try:
        assert game.audio_available is False
    finally:
        game.release_resources()


def test_sounds_are_silent_stand_ins_when_there_is_no_device(game, monkeypatch):
    monkeypatch.setattr(game, "audio_available", False)
    sound = game.load_sound("balloon-pop-1.ogg")
    assert isinstance(sound, SilentSound)
    # The call every game loop makes, on a machine with no speakers
    assert sound.play() is None


def test_sounds_are_real_when_a_device_exists(game):
    assert game.audio_available is True
    assert isinstance(game.load_sound("balloon-pop-1.ogg"), pygame.mixer.Sound)


def test_music_is_skipped_rather_than_attempted_without_a_device(game, monkeypatch):
    monkeypatch.setattr(game, "audio_available", False)

    def fail(*args, **kwargs):
        raise AssertionError("tried to load music with no audio device")

    monkeypatch.setattr(gui_mod.mixer.music, "load", fail)
    monkeypatch.setattr(gui_mod.mixer.music, "play", fail)

    game.play_music("bg-music.ogg")  # must simply do nothing


def test_a_whole_round_can_be_played_deaf(balloons_ready, monkeypatch):
    # End to end: a Balloons round drives pop sounds, the game-over cue and
    # background music. With the stand-ins in place none of that may raise.
    game = balloons_ready
    monkeypatch.setattr(game, "audio_available", False)
    game.balloon_popping_sounds = [SilentSound() for _ in range(3)]
    game.balloon_game_over_sound = SilentSound()
    game.balloon_popping_fill_sounds = SilentSound()

    from tests.test_screen_smoke import run_frames

    assert run_frames(game, game.start_balloons_game, frames=3) >= 1


# --------------------------------------------------------------- structural
def test_no_sound_is_constructed_outside_load_sound():
    # The reason this file exists: ~25 Sound constructions and ~15 .play()
    # calls are spread through the games, and guarding them individually is
    # how 24 of 25 get fixed. load_sound() is the single place that decides.
    import ast

    source = open("gui/gui.py").read()
    tree = ast.parse(source)
    load_sound = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "load_sound"
    )
    outside = source.replace(ast.get_source_segment(source, load_sound), "")

    assert "mixer.Sound(" not in outside
    assert "mixer.init()" not in outside, "mixer must only be started via start_audio()"
