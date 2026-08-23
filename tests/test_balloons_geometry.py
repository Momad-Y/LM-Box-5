"""Tests for the balloon spawn region matching where a fingertip can reach.

Before fix 17, balloons spawned across raw background-image pixel values
used directly as canvas coordinates, while fingertip positions were
properly scaled to canvas space - the two regions only partially
overlapped, so some balloons were never poppable and some reachable screen
area never got a balloon.
"""


def test_every_balloon_spawns_within_the_fingertip_reachable_region(balloons_ready):
    game = balloons_ready
    reach_min = game.translation_x_cam
    reach_max = int(game.end_x_cam * game.scale_x_cam)

    all_balloons = [b for wave in game.waves_balloons for b in wave]
    assert all_balloons, "no balloons were generated to check"

    out_of_reach = [b for b in all_balloons if not (reach_min <= b["rect"].left <= reach_max)]
    assert not out_of_reach, (
        f"{len(out_of_reach)}/{len(all_balloons)} balloons spawned outside "
        f"the fingertip-reachable region [{reach_min}, {reach_max}]"
    )


def test_balloon_spawn_region_never_extends_past_the_canvas(balloons_ready):
    game = balloons_ready
    reach_max = int(game.end_x_cam * game.scale_x_cam)
    assert reach_max <= game.screen.get_width()


def test_balloon_spawn_region_is_a_real_range_not_a_single_point(balloons_ready):
    # A degenerate (zero-width) range would make every balloon spawn at
    # exactly the same x - not the bug this fix addresses, but worth
    # catching if the geometry math ever collapses.
    game = balloons_ready
    reach_min = game.translation_x_cam
    reach_max = int(game.end_x_cam * game.scale_x_cam)
    assert reach_max > reach_min
