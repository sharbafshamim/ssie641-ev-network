"""Control: compare the real network with random networks from the same site pool."""
import numpy as np
import pandas as pd

from .coverage import coverage
from .distance import haversine
from .network import build_graph, mst_links


def network_stats(lat, lon, city_lat, city_lon, pop, factor):
    dist = factor * haversine(lat, lon, lat, lon)
    C = factor * haversine(city_lat, city_lon, lat, lon)
    threshold = mst_links(dist, pd.Series(np.arange(len(lat))))["miles"].iloc[0]
    g30, g40 = build_graph(dist, 30), build_graph(dist, 40)
    u30, w30 = coverage(g30, C, 30, pop)
    u40, _ = coverage(g40, C, 40, pop)
    return [threshold, u30, u40, w30, len(g30.articulation_points()), len(g30.connected_components())]


COLUMNS = ["mst_threshold", "coverage_30", "coverage_40", "weighted_coverage_30", "cut_vertices_30", "pieces_30"]
BETTER_IF_LOWER = {"mst_threshold", "cut_vertices_30", "pieces_30"}


def random_control(real_lat, real_lon, pool_lat, pool_lon, city_lat, city_lon, pop,
                   factor, draws=100, seed=42):
    rng = np.random.default_rng(seed)
    real = network_stats(real_lat, real_lon, city_lat, city_lon, pop, factor)
    rows = []
    for _ in range(draws):
        pick = rng.choice(len(pool_lat), size=len(real_lat), replace=False)
        rows.append(network_stats(pool_lat[pick], pool_lon[pick], city_lat, city_lon, pop, factor))
    rand = pd.DataFrame(rows, columns=COLUMNS)
    share_better = [((rand[c] < r) if c in BETTER_IF_LOWER else (rand[c] > r)).mean()
                    for c, r in zip(COLUMNS, real)]
    summary = pd.DataFrame({"real": real, "random_mean": rand.mean().values,
                            "random_p05": rand.quantile(0.05).values,
                            "random_p95": rand.quantile(0.95).values,
                            "share_random_better": share_better}, index=COLUMNS)
    return summary, rand
