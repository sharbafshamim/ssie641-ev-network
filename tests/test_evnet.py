"""Unit tests for the analysis package. Run with:  python -m pytest -q"""
import itertools
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from evnet import coverage as cov, distance, exact, network as net, trips  # noqa: E402


def test_haversine_known_distance():
    # Times Square to the New York State Capitol: about 135 miles in a straight line
    d = distance.haversine([40.758], [-73.9855], [42.6526], [-73.7562])[0, 0]
    assert 130 < d < 140


def test_mst_threshold_is_exact_connectivity_threshold():
    rng = np.random.default_rng(0)
    pts = rng.uniform(0, 100, size=(60, 2))
    d = np.sqrt(((pts[:, None] - pts[None]) ** 2).sum(-1))
    thr = net.mst_links(d, pd.Series(range(60)))["miles"].iloc[0]
    assert len(net.build_graph(d, thr).connected_components()) == 1
    assert len(net.build_graph(d, thr - 1e-6).connected_components()) > 1


def test_mst_keeps_colocated_sites_linked():
    d = np.array([[0, 0, 10], [0, 0, 10], [10, 10, 0]], float)
    links = net.mst_links(d, pd.Series(["a", "b", "c"]))
    assert (links["miles"] >= 9).sum() == 1          # only one long link, not two


def test_critical_site_on_a_path():
    d = np.array([[0, 1, 2], [1, 0, 1], [2, 1, 0]], float)
    tbl = pd.DataFrame({"name": list("abc"), "city": list("abc"), "network": ["x"] * 3, "ports": [1, 2, 3]})
    c = net.critical_sites(net.build_graph(d, 1.0), tbl)
    assert list(c["city"]) == ["b"] and int(c["sites_cut_off"].iloc[0]) == 1


def test_coverage_two_pieces():
    d = np.array([[0, 100], [100, 0]], float)
    g = net.build_graph(d, 10)
    C = np.array([[1, 100], [100, 1], [2, 100]], float)       # cities 0 and 2 near site 0, city 1 near site 1
    u, w = cov.coverage(g, C, 10, np.array([1, 1, 1], float))
    assert u == pytest.approx(2 / 6)


def _brute(SS, SC, CC, eps, objective):
    nC = SC.shape[1]
    P = exact.Placement(SS, SC, CC, eps)
    for k in range(nC + 1):
        for combo in itertools.combinations(range(nC), k):
            x = np.zeros(nC)
            x[list(combo)] = 1
            if not P._violations(x, objective):
                return k
    return None


@pytest.mark.parametrize("seed", range(6))
@pytest.mark.parametrize("objective", ["connectivity", "robustness"])
def test_exact_ilp_matches_brute_force(seed, objective):
    rng = np.random.default_rng(seed)
    s = rng.uniform(0, 100, size=(7, 2))
    c = rng.uniform(0, 100, size=(8, 2))
    dist = lambda a, b: np.sqrt(((a[:, None] - b[None]) ** 2).sum(-1))  # noqa: E731
    SS, SC, CC = dist(s, s), dist(s, c), dist(c, c)
    eps = 35.0
    P = exact.Placement(SS, SC, CC, eps, time_limit=60)
    r = P.solve(objective)
    assert r["status"] == "optimal"
    assert r["stations"] == _brute(SS, SC, CC, eps, objective)


def test_trip_greedy_and_required_range():
    route = {"miles": 200, "chargers": [[0, 50, 0.2], [1, 110, 0.5], [2, 170, 0.1]]}
    assert not trips.trip_feasible(route, 60)
    assert trips.trip_feasible(route, 90)
    rr = trips.required_range(route)
    assert 85 < rr < 89
    # masking out the middle charger makes the trip harder
    mask = np.array([True, False, True])
    assert trips.required_range(route, mask) > rr


def test_road_matrix_pack_roundtrip(tmp_path):
    import gzip
    rng = np.random.default_rng(1)
    n = 5
    lat, lon = rng.uniform(42, 43, n), rng.uniform(-75, -74, n)
    sites = pd.DataFrame({"Latitude": lat, "Longitude": lon})
    sp = tmp_path / "sites.csv"
    sites.to_csv(sp, index=False)
    i, j = np.triu_indices(n, 1)
    true = rng.uniform(1, 80, len(i))
    packed = tmp_path / "r.u16.gz"
    packed.write_bytes(gzip.compress(np.round(true * 20).astype("<u2").tobytes()))
    from evnet import data
    R = data.unpack_road_miles(packed, sp, None)
    assert np.allclose(R[i, j], np.round(true * 20) / 20)
    assert np.allclose(R, R.T)
