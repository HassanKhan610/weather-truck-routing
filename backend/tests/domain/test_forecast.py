from datetime import datetime, timedelta, timezone

import pytest

from routing.domain.forecast import HourlyForecast
from routing.domain.risk import Weather

T0 = datetime(2026, 11, 2, 0, 0, tzinfo=timezone.utc)


def series(wind=(10, 20, 40), rain=(0, 0.2, 0.4), snow=(0, 0, 1)):
    return HourlyForecast(T0, tuple(wind), tuple(rain), tuple(snow))


def test_exact_hour_returns_that_hour():
    assert series().at(T0 + timedelta(hours=1)) == Weather(20, 0.2, 0)


def test_between_hours_is_linearly_interpolated():
    weather = series().at(T0 + timedelta(hours=1, minutes=30))
    assert weather.wind_mph == pytest.approx(30)
    assert weather.rain_in_hr == pytest.approx(0.3)
    assert weather.snow_in_hr == pytest.approx(0.5)


def test_last_hour_is_inside_the_horizon():
    assert series().at(T0 + timedelta(hours=2)) == Weather(40, 0.4, 1)


@pytest.mark.parametrize("offset", [timedelta(seconds=-1), timedelta(hours=2, seconds=1)])
def test_outside_horizon_is_unavailable(offset):
    assert series().at(T0 + offset) is None


def test_null_neighbour_makes_value_unavailable():
    gappy = series(wind=(10, None, 40))
    assert gappy.at(T0 + timedelta(minutes=30)) is None
    assert gappy.at(T0) == Weather(10, 0, 0)


def test_timezones_are_respected():
    eastern = timezone(timedelta(hours=-5))
    assert series().at(datetime(2026, 11, 1, 20, 0, tzinfo=eastern)) == Weather(
        20, 0.2, 0
    )  # 01:00 UTC


def test_frame_lookup():
    assert series().frame(2) == Weather(40, 0.4, 1)
    assert series().frame(3) is None


def test_single_sample_series():
    one = HourlyForecast(T0, (5,), (0,), (0,))
    assert one.at(T0) == Weather(5, 0, 0)
    assert one.at(T0 + timedelta(minutes=1)) is None


def test_validation():
    with pytest.raises(ValueError):
        HourlyForecast(T0, (1, 2), (0,), (0,))
    with pytest.raises(ValueError):
        HourlyForecast(T0.replace(tzinfo=None), (1,), (0,), (0,))
