"""Guards against a manual/keyboard fallback reappearing in any game.

Runner used to accept Up/Space/Down as a keyboard fallback for jump/duck
when no camera was found - removed because no game in this app should
have a manual-control path; Balloons and Pong are camera-only, and Runner
should be too. Locked in as tests, not just quietly changed, so this isn't
reintroduced without someone remembering why it was pulled.
"""
import ast


def _game_class(src):
    tree = ast.parse(src)
    return next(n for n in ast.walk(tree) if isinstance(n, ast.ClassDef) and n.name == "Game")


def test_no_game_loop_reads_raw_keyboard_state_for_gameplay():
    # pygame.key.get_pressed() polls every key's current state - the shape
    # of a manual-control fallback, as opposed to pump_events()'s discrete
    # KEYDOWN handling (used throughout for menu/UI navigation, which is
    # not a "manual control" in the sense this guards against).
    src = open("gui/gui.py").read()
    game_class = _game_class(src)
    class_src = ast.get_source_segment(src, game_class)
    assert "pygame.key.get_pressed()" not in class_src


def test_runner_requires_a_camera_like_balloons_and_pong(game, monkeypatch):
    monkeypatch.setattr(game.cap, "isOpened", lambda: False)

    required = []
    monkeypatch.setattr(game, "show_camera_required", lambda name: required.append(name))

    def _fail_if_reached(*a, **k):
        raise AssertionError("init_runner_game kept going without a camera")

    monkeypatch.setattr(game, "select_players", _fail_if_reached)

    game.init_runner_game()

    assert required == ["Runner"]
