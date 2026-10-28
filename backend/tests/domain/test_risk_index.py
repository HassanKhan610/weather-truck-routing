import itertools
import math

import pytest

from routing.domain.risk import RiskLevel, Weather, assess, risk_index

WINDS = [0, 10, 24.9, 25, 30, 34.9, 35, 40, 44.9, 45, 50, 54.9, 55, 70]
RAINS = [0, 0.05, 0.1, 0.2, 0.25, 0.4, 0.5, 0.75, 1.0, 1.01, 2]
SNOWS = [0, 0.4, 0.5, 0.9, 1.0, 1.5, 2.0, 3.0, 3.1]
LOADS = [0, 30_000, 30_001, 40_000, 40_001, 80_000]


@pytest.mark.parametrize("load", LOADS)
def test_index_always_floors_to_the_discrete_level(load):
    for wind, rain, snow in itertools.product(WINDS, RAINS, SNOWS):
        weather = Weather(wind, rain, snow)
        index = risk_index(weather, load)
        assert math.floor(index) == assess(weather, load).level, weather
        assert 0 <= index <= 4


@pytest.mark.parametrize(
    "weather, expected",
    [
        (Weather(0, 0, 0), 0.0),
        (Weather(12.5, 0, 0), 0.5),  # halfway through Low
        (Weather(30, 0, 0), 1.5),  # halfway through Moderate (25-35)
        (Weather(0, 0.375, 0), 2.5),  # halfway through High rain
        (Weather(0, 1.0, 0), 3.99),  # exactly 1.00 is still Severe, capped below No Travel
        (Weather(60, 0, 0), 4.0),
    ],
)
def test_index_shades_within_band(weather, expected):
    assert risk_index(weather, 0) == pytest.approx(expected)


def test_load_rule_lifts_index_to_imposed_level():
    assert risk_index(Weather(36, 0, 0), 45_000) == pytest.approx(RiskLevel.SEVERE)
