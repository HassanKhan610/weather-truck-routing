import pytest

from routing.domain.risk import RiskLevel
from routing.domain.scoring import (
    RouteScore,
    ScoredCheckpoint,
    explain,
    rank,
    score_route,
    segment_lengths,
)

L, M, H, S, NT = (
    RiskLevel.LOW,
    RiskLevel.MODERATE,
    RiskLevel.HIGH,
    RiskLevel.SEVERE,
    RiskLevel.NO_TRAVEL,
)


def make_score(route_id="A", **kw):
    defaults = dict(
        duration_s=3600,
        distance_mi=100,
        severe_miles=0,
        high_miles=0,
        no_travel_miles=0,
        unknown_miles=0,
        average_risk=0.0,
    )
    return RouteScore(route_id=route_id, **{**defaults, **kw})


# --- segment weighting ---------------------------------------------------------------


def test_segments_split_at_midpoints_and_cover_whole_route():
    assert segment_lengths([0, 25, 50, 75, 100], 100) == [12.5, 25, 25, 25, 12.5]


def test_uneven_spacing_and_final_partial_segment():
    lengths = segment_lengths([0, 50, 90], 90)
    assert lengths == [25, 45, 20]
    assert sum(lengths) == 90


def test_single_checkpoint_represents_entire_route():
    assert segment_lengths([0], 42) == [42]


def test_no_checkpoints():
    assert segment_lengths([], 10) == []


@pytest.mark.parametrize("positions", [[10, 5], [-1, 5], [0, 11]])
def test_invalid_positions_rejected(positions):
    with pytest.raises(ValueError):
        segment_lengths(positions, 10)


# --- route scoring -------------------------------------------------------------------


def cps(*levels, spacing=10):
    return [ScoredCheckpoint(i * spacing, level) for i, level in enumerate(levels)]


def test_severe_miles_are_distance_weighted():
    # checkpoints at 0,10,20,30,40 on a 40 mi route -> segments 5,10,10,10,5
    score = score_route("A", cps(L, S, H, L, L), distance_mi=40, duration_s=1)
    assert score.severe_miles == 10
    assert score.high_miles == 10
    assert score.average_risk == pytest.approx((3 * 10 + 2 * 10) / 40)


def test_no_travel_counts_as_severe_and_flags_route():
    score = score_route("A", cps(L, NT, L), distance_mi=20, duration_s=1)
    assert score.severe_miles == 10
    assert score.no_travel_miles == 10
    assert score.has_no_travel


def test_unknown_forecast_is_reported_not_treated_as_low():
    score = score_route("A", cps(H, H, None), distance_mi=20, duration_s=1)
    assert score.unknown_miles == 5
    assert score.average_risk == pytest.approx(2.0)  # averaged over the 15 known miles only


def test_all_unknown_has_no_average():
    assert score_route("A", cps(None), distance_mi=5, duration_s=1).average_risk is None


# --- ranking -------------------------------------------------------------------------


def ids(scores):
    return [s.route_id for s in rank(scores)]


def test_severe_miles_dominate_everything_else():
    a = make_score("A", severe_miles=5, high_miles=0, duration_s=100)
    b = make_score("B", severe_miles=1, high_miles=50, average_risk=2.5, duration_s=9000)
    assert ids([a, b]) == ["B", "A"]


def test_high_miles_break_severe_tie():
    a = make_score("A", severe_miles=2, high_miles=10)
    b = make_score("B", severe_miles=2, high_miles=3, average_risk=1.9)
    assert ids([a, b]) == ["B", "A"]


def test_average_risk_breaks_high_tie():
    a = make_score("A", average_risk=1.2, duration_s=100)
    b = make_score("B", average_risk=0.8, duration_s=200)
    assert ids([a, b]) == ["B", "A"]


def test_duration_is_last_tiebreaker():
    a = make_score("A", duration_s=5000)
    b = make_score("B", duration_s=4000)
    assert ids([a, b]) == ["B", "A"]


def test_no_travel_route_ranks_last_even_if_otherwise_better():
    a = make_score("A", severe_miles=1, no_travel_miles=1, duration_s=10)
    b = make_score("B", severe_miles=40, high_miles=40, average_risk=3)
    assert ids([a, b]) == ["B", "A"]


def test_float_noise_does_not_change_ranking():
    a = make_score("A", severe_miles=10.000000001, duration_s=100)
    b = make_score("B", severe_miles=10.0, duration_s=200)
    assert ids([a, b]) == ["A", "B"]


def test_exact_tie_keeps_input_order():
    assert ids([make_score("A"), make_score("B")]) == ["A", "B"]


# --- explanation ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "best, other, fragment",
    [
        (dict(), dict(no_travel_miles=1, severe_miles=1), "crosses a No Travel"),
        (dict(severe_miles=1), dict(severe_miles=4), "Fewest Severe-or-worse miles: 1.0 mi vs 4.0"),
        (dict(high_miles=2), dict(high_miles=7), "fewer High-risk miles: 2.0 mi vs 7.0"),
        (dict(average_risk=0.5), dict(average_risk=0.9), "lower average risk: 0.50 vs 0.90"),
        (dict(duration_s=3600), dict(duration_s=5400), "faster route wins: 1h 00m vs 1h 30m"),
        (dict(), dict(), "Equivalent"),
    ],
)
def test_explanation_names_the_deciding_criterion(best, other, fragment):
    ranked = rank([make_score("Route 2", **other), make_score("Route 1", **best)])
    assert ranked[0].route_id == "Route 1" or fragment == "Equivalent"
    assert fragment in explain(ranked)


def test_explanation_when_every_route_is_no_travel():
    ranked = rank([make_score("A", no_travel_miles=1), make_score("B", no_travel_miles=2)])
    assert "Every route crosses a No Travel" in explain(ranked)


def test_explanation_edge_cases():
    assert explain([]) == "No routes to compare."
    assert explain([make_score()]) == "Only one route was available."
