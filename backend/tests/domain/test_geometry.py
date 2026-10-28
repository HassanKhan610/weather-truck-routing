from datetime import datetime, timedelta, timezone

import pytest

from routing.domain.geometry import (
    RouteGeometry,
    Step,
    checkpoint_positions,
    detour_point,
    generate_checkpoints,
    haversine_mi,
    similar,
    simplify,
    vertex_profile,
)

DEPART = datetime(2026, 11, 2, 6, 0, tzinfo=timezone.utc)

# Three equal-length edges heading north along a meridian (~69.1 mi per degree).
STRAIGHT = ((0.0, 0.0), (1.0, 0.0), (2.0, 0.0), (3.0, 0.0))


def route(steps=(), distance=None, duration=3.0 * 3600, coords=STRAIGHT):
    length = sum(haversine_mi(a, b) for a, b in zip(coords, coords[1:]))
    return RouteGeometry(coords, tuple(steps), distance or length, duration)


def test_haversine_known_distance():
    dallas, houston = (32.7767, -96.7970), (29.7604, -95.3698)
    assert haversine_mi(dallas, houston) == pytest.approx(225, abs=2)


def test_one_degree_of_latitude():
    assert haversine_mi((0, 0), (1, 0)) == pytest.approx(69.09, abs=0.05)


# --- vertex profile ------------------------------------------------------------------


def test_step_durations_drive_vertex_times():
    # first edge is a slow 2-hour city step, last two edges a fast 1-hour highway step
    r = route([Step(0, 1, 7200), Step(1, 3, 3600)])
    _, seconds = vertex_profile(r)
    assert seconds == pytest.approx([0, 7200, 9000, 10800])


def test_miles_are_rescaled_to_api_odometer_distance():
    miles, _ = vertex_profile(route(distance=300))
    assert miles == pytest.approx([0, 100, 200, 300])


def test_zero_length_arrive_step_does_not_lose_time():
    r = route([Step(0, 3, 10000), Step(3, 3, 800)], duration=10800)
    _, seconds = vertex_profile(r)
    assert seconds[-1] == pytest.approx(10800)


def test_missing_steps_fall_back_to_constant_speed():
    _, seconds = vertex_profile(route(duration=300))
    assert seconds == pytest.approx([0, 100, 200, 300])


# --- checkpoint placement ------------------------------------------------------------


@pytest.mark.parametrize(
    "total, interval, expected",
    [
        (100, 25, [0, 25, 50, 75, 100]),  # exact multiple: no duplicate destination
        (60, 25, [0, 25, 50, 60]),  # destination appended
        (8, 10, [0, 8]),  # shorter than one interval
        (0, 10, [0]),
    ],
)
def test_checkpoint_positions(total, interval, expected):
    assert checkpoint_positions(total, interval) == pytest.approx(expected)


def test_checkpoint_positions_survive_float_division():
    assert checkpoint_positions(0.3, 0.1) == pytest.approx([0, 0.1, 0.2, 0.3])


def test_interval_must_be_positive():
    with pytest.raises(ValueError):
        checkpoint_positions(10, 0)


def test_checkpoint_eta_uses_step_speeds_not_average_speed():
    r = route([Step(0, 1, 7200), Step(1, 3, 3600)], distance=300)
    cps = generate_checkpoints(r, 50, DEPART)
    by_mile = {round(c.position_mi): c for c in cps}
    assert by_mile[50].eta == DEPART + timedelta(hours=1)  # halfway through the slow step
    assert by_mile[150].eta == DEPART + timedelta(hours=2, minutes=15)
    assert by_mile[300].eta == DEPART + timedelta(hours=3)


def test_checkpoint_coordinates_are_interpolated():
    cps = generate_checkpoints(route(distance=300), 50, DEPART)
    assert (cps[1].lat, cps[1].lon) == pytest.approx((0.5, 0.0))
    assert (cps[-1].lat, cps[-1].lon) == pytest.approx((3.0, 0.0))


def test_checkpoints_start_at_origin_and_end_at_destination():
    cps = generate_checkpoints(route(distance=130), 50, DEPART)
    assert [c.position_mi for c in cps] == pytest.approx([0, 50, 100, 130])
    assert cps[0].eta == DEPART


def test_route_needs_two_points():
    with pytest.raises(ValueError):
        generate_checkpoints(route(coords=((0, 0),), distance=1), 10, DEPART)


# --- alternatives helpers ------------------------------------------------------------


def test_detour_point_is_perpendicular_to_travel_direction():
    # travelling north: left is west, right is east
    left = detour_point((0, 0), (2, 0), side=1, fraction=0.25)
    right = detour_point((0, 0), (2, 0), side=-1, fraction=0.25)
    assert left == pytest.approx((1.0, -0.5), rel=1e-3)
    assert right == pytest.approx((1.0, 0.5), rel=1e-3)


def test_similar_routes_detected_by_distance_and_duration():
    a = RouteGeometry(STRAIGHT, (), 100, 3600)
    assert similar(a, RouteGeometry(STRAIGHT, (), 101, 3650))
    assert not similar(a, RouteGeometry(STRAIGHT, (), 110, 3600))


@pytest.mark.parametrize("seed", range(25))
def test_last_vertex_lands_exactly_on_api_totals(seed):
    # Regression: float rescaling once put the destination a hair past distance_mi,
    # which scoring rejected as "outside the route".
    import random

    rng = random.Random(seed)
    coords = tuple((32 + rng.random() * 7, -105 + rng.random() * 8) for _ in range(60))
    distance, duration = rng.uniform(100, 1500), rng.uniform(3600, 90000)
    r = RouteGeometry(coords, (Step(0, 59, duration),), distance, duration)
    miles, seconds = vertex_profile(r)
    assert miles[-1] == distance
    assert seconds[-1] == duration
    assert generate_checkpoints(r, 10, DEPART)[-1].position_mi == distance


# --- display simplification ------------------------------------------------------------


def test_simplify_drops_collinear_points_and_keeps_corners():
    line = [(0.0, x / 10) for x in range(11)] + [(1.0, 1.0)]
    assert simplify(line, 0.001) == [(0.0, 0.0), (0.0, 1.0), (1.0, 1.0)]


def test_simplify_keeps_deviations_above_tolerance():
    line = [(0, 0), (0.01, 0.5), (0, 1)]
    assert simplify(line, 0.001) == line
    assert simplify(line, 0.02) == [(0, 0), (0, 1)]


def test_simplify_short_and_degenerate_inputs():
    assert simplify([(1, 1)], 0.1) == [(1, 1)]
    assert simplify([(1, 1), (1, 1), (1, 1)], 0.1) == [(1, 1), (1, 1)]


def test_simplify_real_route_stays_within_tolerance(load_fixture):
    from routing.clients.ors import parse_directions

    route = parse_directions(load_fixture("ors_directions_dallas_fort_worth.json"))[0]
    simple = simplify(route.coordinates, 0.0005)
    assert len(simple) < len(route.coordinates) / 3
    assert simple[0] == route.coordinates[0] and simple[-1] == route.coordinates[-1]
