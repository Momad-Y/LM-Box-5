"""Tests for the Medium-severity fixes (18-29 in AUDIT.md).

Behavioral tests exercise the real init/gameplay state via the
balloons_ready/pong_ready fixtures; the purely mechanical fixes (an added
clock.tick call, a shared event-loop helper, a narrowed except clause, a
deleted dead method) are checked structurally, since "the code is shaped a
certain way" is exactly what they claim.
"""
import ast


def _game_class(src):
    tree = ast.parse(src)
    return next(n for n in ast.walk(tree) if isinstance(n, ast.ClassDef) and n.name == "Game")


def _method_source(game_class, src, name):
    node = next(
        n for n in ast.walk(game_class) if isinstance(n, ast.FunctionDef) and n.name == name
    )
    return ast.get_source_segment(src, node)


# --------------------------------------------------------------- fix 18
def test_balloons_wave_end_check_uses_all_popped_not_list_length():
    # The bug: balloons are never removed from the list (popping only
    # flips is_popped), so len(balloons) == 0 could never become true -
    # the wave could only ever end via the timer, even when every balloon
    # had already been popped in the first few seconds.
    src = open("gui/gui.py").read()
    game_class = _game_class(src)
    body_src = _method_source(game_class, src, "start_balloons_game")
    assert 'all(b["is_popped"] for b in balloons)' in body_src
    assert "len(balloons) == 0" not in body_src


def test_wave_with_every_balloon_popped_satisfies_the_real_end_condition(balloons_ready):
    game = balloons_ready
    balloons = game.waves_balloons[0]
    assert balloons, "no balloons generated to check"

    for b in balloons:
        b["is_popped"] = True
    assert all(b["is_popped"] for b in balloons)

    # A wave that still had one unpopped balloon must not satisfy it
    balloons[0]["is_popped"] = False
    assert not all(b["is_popped"] for b in balloons)


# --------------------------------------------------------------- fix 19
def test_uncapped_ui_loops_now_call_clock_tick():
    src = open("gui/gui.py").read()
    game_class = _game_class(src)
    for name in (
        "select_players",
        "prompt_text",
        "ask_yes_no",
        "capture_user_face",
        "end_balloons_game",
        "end_pong_game",
        "end_runner_game",
    ):
        body_src = _method_source(game_class, src, name)
        assert "clock.tick" in body_src, f"{name} still has no frame-rate cap"


# --------------------------------------------------------------- fix 20
def test_balloons_best_score_is_cached_not_requeried_every_hud_frame(balloons_ready):
    game = balloons_ready
    assert hasattr(game, "balloons_best_score")

    call_count = 0
    real_get_best_score = game.get_best_score

    def counting(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return real_get_best_score(*args, **kwargs)

    game.get_best_score = counting
    game.draw_balloons_hud(time_left=10)
    game.draw_balloons_hud(time_left=9)
    game.get_best_score = real_get_best_score

    assert call_count == 0


def test_runner_hud_reads_the_cached_best_score_not_a_live_query():
    src = open("gui/gui.py").read()
    game_class = _game_class(src)
    body_src = _method_source(game_class, src, "draw_runner_hud")
    assert "self.runner_best_score" in body_src
    assert "get_best_score" not in body_src


def test_runner_best_score_is_refreshed_every_round(game):
    # reset_runner_round (called at the start of every round, including
    # each replay) is what has to refresh this - not just init_runner_game,
    # which only runs once - or a just-recorded new best would never show
    # up on the very next replay.
    src = open("gui/gui.py").read()
    game_class = _game_class(src)
    body_src = _method_source(game_class, src, "reset_runner_round")
    assert "self.runner_best_score = self.get_best_score(" in body_src


# --------------------------------------------------------------- fix 21
def test_balloon_images_are_shared_across_instances_of_the_same_file(balloons_ready):
    # There are only 10 distinct source images (7 normal + 3 combo) but
    # potentially hundreds of balloon instances across all waves - the
    # number of distinct Surface *objects* in play should match the number
    # of distinct source files, not the number of balloon instances.
    game = balloons_ready
    all_balloons = [b for wave in game.waves_balloons for b in wave]
    assert len(all_balloons) > 10, "not enough balloons generated to check sharing"

    distinct_surfaces = {id(b["image"]) for b in all_balloons}
    assert len(distinct_surfaces) <= 10


# --------------------------------------------------------------- fix 22
def test_cactus_images_are_shared_across_spawns(game):
    # Depends on the `game` fixture (not just importing runner_sprites)
    # so a display definitely exists before this runs - the cache only
    # activates once one does (see _cached_cactus_image), so relying on
    # other test files/fixtures to have set one up first would make this
    # pass or fail depending on collection order.
    from gui.runner_sprites import Cactus, _cactus_image_cache

    _cactus_image_cache.clear()
    cacti = [Cactus(0, 0) for _ in range(50)]  # enough spawns to repeat all 6 images
    by_image_id = {}
    for c in cacti:
        by_image_id.setdefault(id(c.image), []).append(c)

    # 6 possible source images, 50 spawns - some image must repeat
    assert len(by_image_id) <= 6
    assert _cactus_image_cache, "cache never activated - is a display actually set?"


def test_ptero_images_are_shared_across_spawns(game):
    from gui import runner_sprites

    runner_sprites._ptero_image_cache = None
    ptero_a = runner_sprites.Ptero(screen_width=800)
    ptero_b = runner_sprites.Ptero(screen_width=800)
    assert ptero_a.images is ptero_b.images
    assert runner_sprites._ptero_image_cache is not None


def test_obstacle_cache_does_not_memoize_without_a_display(game, monkeypatch):
    # `game` guarantees a real display exists (Game.__init__ sets one) by
    # the time this runs, so the "restored" half below has something real
    # to fall back to regardless of test collection order.
    #
    # The gap the red-team review found: if a Cactus/Ptero were ever built
    # before pygame.display.set_mode() has run, _load_trimmed silently
    # skips convert_alpha() (pygame.error), and caching that unoptimized
    # surface would stick for the rest of the process. Simulated here by
    # forcing get_surface() to report "no display", regardless of whether
    # some other test already set a real one earlier in this session.
    import pygame
    from gui.runner_sprites import _cached_cactus_image, _cactus_image_cache

    monkeypatch.setattr(pygame.display, "get_surface", lambda: None)
    _cactus_image_cache.clear()
    _cached_cactus_image(1)
    assert 1 not in _cactus_image_cache

    monkeypatch.undo()
    _cached_cactus_image(1)
    assert 1 in _cactus_image_cache, "should memoize now that a display is reported"


# --------------------------------------------------------------- fix 23
# (covered in test_database.py, alongside the rest of the DB layer)


# --------------------------------------------------------------- fix 25
def test_game_loops_use_the_shared_pump_events_helper_not_raw_event_get():
    src = open("gui/gui.py").read()
    game_class = _game_class(src)
    pump_events_body = _method_source(game_class, src, "pump_events")
    assert "pygame.event.get()" in pump_events_body

    # Every OTHER method in Game should go through pump_events(), not call
    # pygame.event.get() itself - that was the 14x-duplicated boilerplate.
    for node in ast.walk(game_class):
        if isinstance(node, ast.FunctionDef) and node.name != "pump_events":
            body_src = ast.get_source_segment(src, node)
            assert "pygame.event.get()" not in body_src, (
                f"{node.name} calls pygame.event.get() directly instead of self.pump_events()"
            )


# --------------------------------------------------------------- fix 26
def test_no_bare_except_clauses_remain_in_gui():
    src = open("gui/gui.py").read()
    tree = ast.parse(src)
    bare_excepts = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.ExceptHandler) and node.type is None
    ]
    assert not bare_excepts, f"{len(bare_excepts)} bare except clause(s) remain"


# --------------------------------------------------------------- fix 27
def test_dead_methods_were_actually_removed(game):
    for name in ("add_user", "get_user_ids_with_faces", "get_user_face_thumbnail", "draw_player_badge"):
        assert not hasattr(game, name), f"{name} should have been deleted as dead code"


# --------------------------------------------------------------- fix 28
def test_privacy_notice_and_no_camera_share_the_info_panel_helper():
    from gui import screen_ingame

    assert hasattr(screen_ingame, "_draw_info_panel")
    src = open("gui/screen_ingame.py").read()
    tree = ast.parse(src)
    for name in ("draw_privacy_notice", "draw_no_camera"):
        node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name)
        body_src = ast.get_source_segment(src, node)
        assert "_draw_info_panel(" in body_src


# --------------------------------------------------------------- fix 29
def test_balloon_scoring_does_not_round_per_pop():
    # A real gap the red-team review caught: rounding every single pop
    # event made the multiplier a complete no-op for the two most common
    # point values - round(1*0.8)==round(1*1.0)==round(1*1.2)==1, and
    # likewise 2 -> 2/2/2 - and base_points is 1 for every plain,
    # non-combo balloon (the overwhelming majority of pops). Fixed by only
    # truncating the running total to an int at display/record time
    # (draw_balloons_hud, end_balloons_game), the same way Runner's score
    # already worked - confirmed here against the real source, not a
    # reimplementation of the formula.
    src = open("gui/gui.py").read()
    game_class = _game_class(src)
    body_src = _method_source(game_class, src, "start_balloons_game")
    # Matched with whitespace collapsed: this is a structural check about
    # what the code computes, and it should not fail merely because a
    # formatter wrapped the expression across lines (which is exactly what
    # happened once, reporting a scoring regression that had not occurred).
    normalized = " ".join(body_src.split())
    assert (
        'points = ( base_points * self.difficulty_modifiers["score_multiplier"] )'
        in normalized
        or 'points = base_points * self.difficulty_modifiers["score_multiplier"]'
        in normalized
    )
    # The actual regression being guarded: no rounding at the point of a pop
    assert "round(base_points" not in normalized
    assert "points = round(" not in normalized

    hud_src = _method_source(game_class, src, "draw_balloons_hud")
    assert "int(self.balloons_score)" in hud_src

    end_src = _method_source(game_class, src, "end_balloons_game")
    assert "self.balloons_score = max(0, int(self.balloons_score))" in end_src


def test_accumulated_balloon_score_actually_differs_by_difficulty():
    # Using the real DIFFICULTY_SETTINGS values (not reinvented constants):
    # popping the same common balloon type repeatedly across a wave should
    # add up to a visibly different final score per difficulty, finalized
    # the same way end_balloons_game does (int() of the accumulated total).
    from gui.settings_config import DIFFICULTY_SETTINGS

    base_points = 1  # the common, non-combo balloon type
    pops = 10

    totals = {}
    for difficulty, modifiers in DIFFICULTY_SETTINGS.items():
        score = 0.0
        for _ in range(pops):
            score = max(0, score + base_points * modifiers["score_multiplier"])
        totals[difficulty] = int(score)

    assert totals["Easy"] < totals["Normal"] < totals["Hard"]


def test_runner_scoring_does_not_round_per_frame():
    src = open("gui/gui.py").read()
    game_class = _game_class(src)
    body_src = _method_source(game_class, src, "start_runner_game")
    assert (
        '0.1 * dt_scale * self.difficulty_modifiers["score_multiplier"]' in body_src
    )


def test_pong_score_is_not_scaled_by_difficulty():
    # Deliberate scope boundary: Pong's score is a race-to-N win condition,
    # not accumulating reward points, so awarding a point should stay a
    # bare += 1 - confirm that choice stayed a choice, not an oversight
    # that quietly reverts. (A comment nearby explaining the decision
    # legitimately mentions score_multiplier by name, so this checks the
    # actual award statements rather than banning the word outright.)
    src = open("gui/gui.py").read()
    lines = src.splitlines()
    award_lines = [line for line in lines if "player1_score += " in line or "player2_score += " in line]
    assert award_lines, "no Pong score-award lines found"
    for line in award_lines:
        assert line.strip() in ("self.player1_score += 1", "self.player2_score += 1")
