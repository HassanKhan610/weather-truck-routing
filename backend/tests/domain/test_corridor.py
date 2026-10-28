import pytest

from routing.domain.corridor import build_corridor, corridor_cells


def test_cells_cover_the_path_with_a_buffer():
    cells = corridor_cells([[(30.0, -90.0), (31.0, -90.0)]], step=0.1, buffer_deg=0.3)
    assert (30.5, -90.0) in cells  # on the path
    assert (30.5, -90.3) in cells  # at the edge of the buffer (wider east-west at 30°N)
    assert (30.5, -90.5) not in cells
    assert (29.6, -90.0) not in cells  # beyond the buffer south of the origin


def test_cells_are_on_the_step_grid_and_unique():
    cells = corridor_cells([[(30.03, -90.07), (30.9, -89.2)]], step=0.25, buffer_deg=0.5)
    assert len(cells) == len(set(cells))
    for lat, lon in cells:
        assert lat / 0.25 == pytest.approx(round(lat / 0.25))
        assert lon / 0.25 == pytest.approx(round(lon / 0.25))


def test_long_diagonal_segments_are_densified():
    # one straight segment 5 degrees long: every cell along it must be included
    cells = set(corridor_cells([[(30.0, -95.0), (35.0, -90.0)]], step=0.5, buffer_deg=0.5))
    assert all((30.0 + k * 0.5, -95.0 + k * 0.5) in cells for k in range(11))


def test_overlapping_routes_share_cells():
    path = [(30.0, -90.0), (31.0, -90.0)]
    one = corridor_cells([path], step=0.1)
    assert corridor_cells([path, path], step=0.1) == one


def test_step_grows_until_cell_budget_fits():
    long_trip = [[(32.8, -96.8), (39.7, -105.0)]]  # Dallas -> Denver
    grid = build_corridor(long_trip, max_cells=250)
    assert grid.step_deg > 0.1
    assert len(grid.cells) <= 250


def test_short_trip_uses_finest_grid():
    grid = build_corridor([[(32.8, -96.8), (32.9, -96.8)]], max_cells=250)
    assert grid.step_deg == 0.1


def test_single_point_path_and_empty_input():
    assert build_corridor([[(30.0, -90.0)]]).cells
    with pytest.raises(ValueError):
        build_corridor([[]])
