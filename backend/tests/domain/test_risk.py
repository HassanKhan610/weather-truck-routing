import pytest

from routing.domain.risk import RiskLevel, Weather, assess, classify

L, M, H, S, NT = (
    RiskLevel.LOW,
    RiskLevel.MODERATE,
    RiskLevel.HIGH,
    RiskLevel.SEVERE,
    RiskLevel.NO_TRAVEL,
)


def calm(**overrides):
    return Weather(**{"wind_mph": 0, "rain_in_hr": 0, "snow_in_hr": 0, **overrides})


@pytest.mark.parametrize(
    "value, expected",
    [
        (0, L),
        (24.99, L),
        (25, M),
        (34.99, M),
        (35, H),
        (44.99, H),
        (45, S),
        (54.99, S),
        (55, NT),
        (80, NT),
    ],
)
def test_wind_bands_are_lower_inclusive(value, expected):
    assert classify("wind_mph", value) == expected


@pytest.mark.parametrize(
    "value, expected",
    [
        (0, L),
        (0.099, L),
        (0.10, M),
        (0.249, M),
        (0.25, H),
        (0.499, H),
        (0.50, S),
        (1.00, S),  # spec says "> 1.00" for No Travel, so 1.00 itself is Severe
        (1.001, NT),
    ],
)
def test_rain_bands(value, expected):
    assert classify("rain_in_hr", value) == expected


@pytest.mark.parametrize(
    "value, expected",
    [
        (0, L),
        (0.49, L),
        (0.5, M),
        (0.99, M),
        (1.0, H),
        (1.99, H),
        (2.0, S),
        (3.0, S),  # spec says "> 3.0" for No Travel
        (3.01, NT),
    ],
)
def test_snow_bands(value, expected):
    assert classify("snow_in_hr", value) == expected


def test_risk_levels_are_ordered_with_no_travel_highest():
    assert L < M < H < S < NT
    assert NT.label == "No Travel"


@pytest.mark.parametrize(
    "wind, load, expected",
    [
        # >= 55 mph: No Travel for any load
        (55, 0, NT),
        (55, 1, NT),
        # 45-54 mph: No Travel only when load is strictly over 30,000 lb
        (45, 30_000, S),
        (45, 30_001, NT),
        (54.99, 30_001, NT),
        # 35-44 mph: Severe only when load is strictly over 40,000 lb
        (35, 40_000, H),
        (35, 40_001, S),
        (44.99, 80_000, S),
        # below 35 mph the load never matters
        (34.99, 80_000, M),
    ],
)
def test_load_rules(wind, load, expected):
    assert assess(calm(wind_mph=wind), load).level == expected


def test_load_rules_only_raise_never_lower():
    heavy_rain = calm(wind_mph=36, rain_in_hr=1.5)
    assert assess(heavy_rain, 45_000).level == NT


def test_checkpoint_level_is_max_over_factors():
    result = assess(Weather(wind_mph=26, rain_in_hr=0.3, snow_in_hr=0.6), 10_000)
    assert result.level == H
    assert result.reasons == ("rain 0.3 in/hr",)


def test_reasons_include_every_factor_at_the_max_level():
    result = assess(calm(wind_mph=40, rain_in_hr=0.3), 10_000)
    assert result.reasons == ("wind 40 mph", "rain 0.3 in/hr")


def test_reasons_mention_load_when_load_rule_decides():
    result = assess(calm(wind_mph=40), 42_000)
    assert result.level == S
    assert result.reasons == ("wind 40 mph with 42,000 lb load",)


def test_calm_weather_is_low_with_no_reasons():
    assert assess(calm(), 80_000) == assess(calm(), 0)
    assert assess(calm(), 0).level == L
    assert assess(calm(), 0).reasons == ()
