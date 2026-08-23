"""Tests for every DB read/write path on the Game class.

Always goes through the `game` fixture (see conftest.py), which sandboxes
DATA_DIR to a temp directory before the Game is ever constructed - never
run any of this against the real data/lmbox_users.db.
"""
import sqlite3

import pytest


def test_setup_database_seeds_a_default_user(game):
    users = game.get_users()
    assert len(users) == 1
    assert users[0][1] == "Player 1"


def test_add_user_returning_id_then_get_users(game):
    user_id = game.add_user_returning_id("Alice")
    assert user_id is not None

    users = dict(game.get_users())
    assert users[user_id] == "Alice"


def test_get_user_name_for_unknown_id_is_none(game):
    assert game.get_user_name(999999) is None


def test_rename_user_keeps_the_same_id(game):
    user_id = game.add_user_returning_id("Bob")
    game.rename_user(user_id, "Bobby")
    assert game.get_user_name(user_id) == "Bobby"


def test_add_user_returning_id_rejects_an_empty_name(game):
    assert game.add_user_returning_id("") is None
    assert game.add_user_returning_id("   ") is None


def test_add_user_returning_id_rejects_a_name_over_30_characters(game):
    assert game.add_user_returning_id("x" * 31) is None
    assert game.add_user_returning_id("x" * 30) is not None


def test_add_user_returning_id_strips_surrounding_whitespace(game):
    user_id = game.add_user_returning_id("  Alice  ")
    assert game.get_user_name(user_id) == "Alice"


def test_rename_user_ignores_an_invalid_new_name(game):
    user_id = game.add_user_returning_id("Original")
    game.rename_user(user_id, "")
    assert game.get_user_name(user_id) == "Original"
    game.rename_user(user_id, "x" * 31)
    assert game.get_user_name(user_id) == "Original"


def test_record_score_and_get_best_score(game):
    user_id = game.add_user_returning_id("Scorer")
    assert game.get_best_score(user_id, "balloons") is None

    game.record_score(user_id, "balloons", 10)
    game.record_score(user_id, "balloons", 25)
    game.record_score(user_id, "balloons", 15)

    assert game.get_best_score(user_id, "balloons") == 25


def test_record_score_ignores_a_falsy_user_id(game):
    # A None/0 user id means "nobody was playing" - silently do nothing
    # rather than writing a row with no real owner.
    game.record_score(None, "pong", 100)
    game.record_score(0, "pong", 100)
    assert game.get_leaderboard("pong") == []


def test_get_leaderboard_ranks_best_score_per_user_highest_first(game):
    alice = game.add_user_returning_id("Alice")
    bob = game.add_user_returning_id("Bob")

    game.record_score(alice, "runner", 50)
    game.record_score(alice, "runner", 90)  # Alice's best
    game.record_score(bob, "runner", 70)

    board = game.get_leaderboard("runner")
    assert [row[0] for row in board] == [alice, bob]
    assert board[0][2] == 90


def test_get_leaderboard_excludes_a_deleted_user(game):
    alice = game.add_user_returning_id("Alice")
    game.record_score(alice, "runner", 90)
    game.delete_user(alice)

    assert game.get_leaderboard("runner") == []


def test_delete_user_also_removes_their_scores(game):
    user_id = game.add_user_returning_id("Temp")
    game.record_score(user_id, "balloons", 5)

    game.delete_user(user_id)

    assert game.get_user_name(user_id) is None
    assert game.get_best_score(user_id, "balloons") is None


def test_delete_user_forgets_them_as_a_remembered_player(game):
    user_id = game.add_user_returning_id("Remembered")
    game.settings["player_1_id"] = user_id

    game.delete_user(user_id)

    assert game.settings["player_1_id"] == 0


def test_set_user_face_then_get_user_face_bytes(game):
    user_id = game.add_user_returning_id("Photogenic")
    assert game.get_user_face_bytes(user_id) is None

    game.set_user_face(user_id, b"fake-png-bytes")
    assert game.get_user_face_bytes(user_id) == b"fake-png-bytes"


def test_clear_user_face_removes_the_picture_but_keeps_the_user(game):
    user_id = game.add_user_returning_id("Photogenic")
    game.set_user_face(user_id, b"fake-png-bytes")

    game.clear_user_face(user_id)

    assert game.get_user_face_bytes(user_id) is None
    assert game.get_user_name(user_id) == "Photogenic"


class _BrokenCursor:
    """Raises on every execute, standing in for a locked/corrupt database."""

    lastrowid = None

    def execute(self, *args, **kwargs):
        raise sqlite3.OperationalError("simulated: database is locked")


def test_db_failure_degrades_reads_to_safe_defaults_instead_of_raising(game):
    game.cursor = _BrokenCursor()

    assert game.get_users() == []
    assert game.get_leaderboard("balloons") == []
    assert game.get_best_score(1, "balloons") is None
    assert game.get_user_name(1) is None
    assert game.get_user_face_bytes(1) is None
    assert game.add_user_returning_id("x") is None


def test_db_failure_does_not_raise_on_writes(game):
    game.cursor = _BrokenCursor()

    # None of these should raise - a failed write is logged (see
    # _db_execute) and the caller moves on rather than crashing the round.
    game.record_score(1, "balloons", 10)
    game.rename_user(1, "x")
    game.set_user_face(1, b"data")
    game.clear_user_face(1)
    game.delete_user(1)
