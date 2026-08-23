"""Tests for the atomic settings.json write (fix 8).

Before this fix, save_settings() wrote straight into the live file; a
crash mid-write left it truncated and every saved preference silently
reset to defaults on the next launch.
"""
import json
import os


def test_save_settings_leaves_no_leftover_tmp_file(game, sandboxed_data_dir):
    game.settings["sound_volume"] = 42
    game.save_settings()

    settings_path = os.path.join(sandboxed_data_dir.DATA_DIR, "settings.json")
    assert not os.path.exists(settings_path + ".tmp")


def test_saved_value_round_trips_through_a_real_reload(game, sandboxed_data_dir):
    game.settings["sound_volume"] = 77
    game.save_settings()

    reloaded = sandboxed_data_dir.Game.__new__(sandboxed_data_dir.Game)
    reloaded.load_settings()
    assert reloaded.settings["sound_volume"] == 77


def test_a_failed_write_does_not_touch_the_existing_settings_file(
    game, sandboxed_data_dir, monkeypatch
):
    game.settings["sound_volume"] = 10
    game.save_settings()

    settings_path = os.path.join(sandboxed_data_dir.DATA_DIR, "settings.json")
    with open(settings_path) as f:
        before = f.read()

    def broken_dump(*args, **kwargs):
        raise TypeError("simulated: something unserializable snuck into settings")

    monkeypatch.setattr(json, "dump", broken_dump)
    game.settings["sound_volume"] = 999
    game.save_settings()  # caught internally - must not raise, must not corrupt the file

    with open(settings_path) as f:
        after = f.read()
    assert after == before
    assert not os.path.exists(settings_path + ".tmp")
