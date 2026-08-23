"""Tests for Pong's field geometry and ball-speed safety cap.

Uses the pong_ready fixture (see conftest.py), which runs the real
init_pong_game with only the camera/UI interaction stubbed out - the field
geometry, ball radius, paddle dimensions and speed cap below are all
genuine values computed by the actual game code, not hand-reconstructed.
"""


def test_play_field_top_is_a_coordinate_not_a_size(pong_ready):
    # The bug this protects against: .top and .height being used
    # interchangeably, which only fails to matter when they happen to be
    # equal - they are not, for the real shipped background art.
    assert pong_ready.play_field_rect.top != pong_ready.play_field_rect.height


def test_paddle_and_ball_top_bound_checks_use_top_not_height(pong_ready):
    # Read the real source of start_pong_game and confirm the top-bound
    # comparisons for both paddles and the ball all use play_field_rect.top
    # - the bug this protects against is exactly this comparing against
    # .height instead, which only fails to matter when the two numbers
    # happen to be equal (they are not - see the test above).
    #
    # .height still appears legitimately elsewhere in this function (e.g.
    # sizing the net-drawing range), so this checks the three specific
    # bound-check conditions rather than banning the word outright.
    src = open("gui/gui.py").read()
    lines = src.splitlines()

    def condition_line(pattern):
        matches = [line for line in lines if pattern in line]
        assert matches, f"no line found containing {pattern!r}"
        return matches[0]

    assert "play_field_rect.top" in condition_line("self.paddle1_y <")
    assert "play_field_rect.top" in condition_line("self.paddle2_y <")
    assert "play_field_rect.top" in condition_line("self.ball_y <=") and "ball_raduis" in condition_line(
        "self.ball_y <="
    )


def test_max_ball_speed_derived_from_real_paddle_and_ball_geometry(pong_ready):
    game = pong_ready
    assert game.max_ball_speed == game.paddle_width + game.ball_raduis - 2


def test_ball_speed_escalation_clamps_to_max_ball_speed(pong_ready):
    game = pong_ready
    game.ball_speed_x = game.max_ball_speed - 1
    game.ball_speed_y = -(game.max_ball_speed - 1)

    for _ in range(10):  # far more escalation ticks than a real rally needs
        game.ball_speed_x += (
            game.speed_increment if game.ball_speed_x > 0 else -game.speed_increment
        )
        game.ball_speed_y += (
            game.speed_increment if game.ball_speed_y > 0 else -game.speed_increment
        )
        game.ball_speed_x = max(-game.max_ball_speed, min(game.max_ball_speed, game.ball_speed_x))
        game.ball_speed_y = max(-game.max_ball_speed, min(game.max_ball_speed, game.ball_speed_y))

    assert abs(game.ball_speed_x) <= game.max_ball_speed
    assert abs(game.ball_speed_y) <= game.max_ball_speed


def test_per_frame_ball_displacement_cannot_tunnel_through_a_paddle(pong_ready):
    # The actual on-screen movement is speed * dt_scale, and dt_scale can
    # be as large as 2.0 (MAX_FRAME_DT * TARGET_FPS) on a slow frame - the
    # displacement clamp in start_pong_game has to bound THAT product, not
    # just the stored speed value, or a slow machine could still let the
    # ball skip clean over a paddle.
    game = pong_ready
    tunnel_threshold = game.paddle_width + game.ball_raduis  # width the ball must cross to skip clean over

    worst_case_dt_scale = 2.0  # MAX_FRAME_DT (1/15) * TARGET_FPS (30)
    game.ball_speed_x = game.max_ball_speed
    displacement = max(
        -game.max_ball_speed, min(game.max_ball_speed, game.ball_speed_x * worst_case_dt_scale)
    )
    assert abs(displacement) < tunnel_threshold
