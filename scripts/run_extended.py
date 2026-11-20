"""Extended analyses: trips on real routes, traffic weighting, Hanig-style coverage, realistic ranges,
150 kW / NEVI-grade networks, growth over time, reliability, additional baselines with confidence
intervals, and the random-geometric-graph benchmark.

    python scripts/run_extended.py

Inputs beyond run_all.py: data/derived/osrm_routes.json.gz (OSRM routes between the 67 cities with
25,000+ people and five Canada border crossings), data/derived/osrm_matrix_blocks.u16.gz (road
distances to cities), data/raw/nysdot_aadt_principal_arterials_2026-11-19.json.gz (NYSDOT AADT).
"""
import gzip
import json
import os
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy.spatial import cKDTree  # noqa: E402
from scipy.stats import beta  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from evnet import coverage as cov, data, distance, exact, network as net, trips  # noqa: E402
from run_all import AQUA, BLUE, GREY, INK2, ORANGE, RED, VIOLET, YELLOW, map_axes, save  # noqa: E402

TAB, FIG = ROOT / "results" / "tables", ROOT / "results" / "figures"
NY_LAND_SQMI = 47_126          # Census 2020 land area of New York State
RANGES = {"smallest 2024 EV (114 mi)": 114, "150 mi": 150, "median MY2024 EV (283 mi)": 283}
WINTER = 0.59
FACTOR = 1.22
RNG = np.random.default_rng(2026)


def wilson(k, n, z=1.96):
    """95% Wilson interval for a proportion k/n."""
    if n == 0:
        return (np.nan, np.nan)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0, c - h), min(1, c + h))


# ------------------------------------------------------------------ AADT lookup
def aadt_lookup():
    raw = json.loads(gzip.decompress(open(data.RAW / "nysdot_aadt_principal_arterials_2026-11-19.json.gz", "rb").read()))
    pts, vals, fcs = [], [], []
    for route, fc, aadt, seglen, direc, county, paths in raw:
        if not aadt:
            continue
        for path in paths:
            for lon, lat in path:
                pts.append((lon, lat))
                vals.append(aadt)
                fcs.append(fc)
    pts = np.array(pts)
    xy = np.column_stack([pts[:, 0] * 69.0 * np.cos(np.radians(42.5)), pts[:, 1] * 69.0])
    tree = cKDTree(xy)
    vals = np.array(vals, float)

    def lookup(lon, lat, max_mi=0.3):
        q = np.column_stack([np.asarray(lon) * 69.0 * np.cos(np.radians(42.5)), np.asarray(lat) * 69.0])
        d, i = tree.query(q)
        return np.where(d <= max_mi, vals[i], 0.0)

    return lookup, len(raw)


def main():
    S = {}
    sites = data.site_attributes(pd.read_csv(data.DERIVED / "sites.csv"))
    n = len(sites)
    R = data.load_road_miles(n)
    places, _ = data.load_places(5000)
    pop = places["pop"].values.astype(float)
    M = data.load_osrm_matrix()
    C_road = M["YS"]                                   # city -> site road miles
    cand = pd.read_csv(data.DERIVED / "candidates_kept.csv")
    masks = {"all": np.ones(n, bool), "ccs": sites["ccs"].values, "hpc150": sites["hpc150"].values,
             "nevi_grade": sites["nevi_grade"].values, "working": ~sites["unavailable"].values}

    # ============================================================== trips
    routes = json.loads(gzip.decompress(open(data.DERIVED / "osrm_routes.json.gz", "rb").read()))
    nodes = pd.read_csv(data.DERIVED / "od_nodes.csv")
    lookup, n_aadt = aadt_lookup()
    S["aadt_segments"] = n_aadt
    ok = [r for r in routes if not r.get("failed")]
    S["routes"] = len(routes)
    S["routes_failed"] = len(routes) - len(ok)
    rows = []
    for r in ok:
        a, b = nodes.iloc[r["i"]], nodes.iloc[r["j"]]
        g = np.asarray(r["geom"], float)
        aadt = lookup(g[:, 0], g[:, 1])
        rec = {"i": r["i"], "j": r["j"], "from": a["name"], "to": b["name"], "kind": "border" if "gateway" in (a["kind"], b["kind"]) else "city",
               "miles": r["miles"], "gravity": (a["pop"] * b["pop"] / r["miles"] ** 2) if a["kind"] == b["kind"] == "city" else 0.0,
               "mean_aadt": float(aadt[aadt > 0].mean()) if (aadt > 0).any() else 0.0,
               "aadt_matched_share": float((aadt > 0).mean())}
        for name in ["all", "hpc150", "nevi_grade", "working"]:
            rec[f"req_range_{name}"] = trips.required_range(r, masks[name])
        rows.append(rec)
    T = pd.DataFrame(rows)
    T.to_csv(TAB / "trips_required_range.csv", index=False)

    def share(col, U, weight):
        sub = T[T["kind"] == "city"] if weight == "gravity" else T
        w = sub["gravity"] if weight == "gravity" else (sub["mean_aadt"] if weight == "aadt" else np.ones(len(sub)))
        ok_ = sub[col] <= U
        return float((w * ok_).sum() / w.sum())

    rows = []
    for net_name in ["all", "hpc150", "nevi_grade", "working"]:
        for lab, nominal in RANGES.items():
            for season, f in [("mild", 1.0), ("winter 20F", WINTER)]:
                U = nominal * f
                col = f"req_range_{net_name}"
                rows.append([net_name, lab, season, round(U, 1), share(col, U, "gravity"), share(col, U, "aadt"),
                             share(col, U, "none"), int((T[col] > U).sum())])
    TF = pd.DataFrame(rows, columns=["network", "vehicle", "season", "usable_range_mi", "trips_ok_gravity_weighted",
                                     "trips_ok_aadt_weighted", "trips_ok_unweighted", "trips_failing"])
    TF.to_csv(TAB / "trips_feasibility.csv", index=False)
    S["trips_max_required_range"] = {k: float(T[f"req_range_{k}"].replace(np.inf, np.nan).max()) for k in ["all", "hpc150", "nevi_grade", "working"]}
    S["trips_unroutable"] = {k: int(np.isinf(T[f"req_range_{k}"]).sum()) for k in ["all", "hpc150", "nevi_grade", "working"]}
    worst = T.sort_values("req_range_all", ascending=False).head(10)[["from", "to", "miles", "req_range_all", "req_range_hpc150", "req_range_nevi_grade"]]
    worst.to_csv(TAB / "trips_hardest.csv", index=False)
    border = T[T["kind"] == "border"].copy()
    border["gateway"] = np.where(border["from"].str.contains("border|bridge|crossing", case=False), border["from"], border["to"])
    bt = border.groupby("gateway").agg(trips=("miles", "size"), max_req_all=("req_range_all", "max"),
                                       max_req_hpc150=("req_range_hpc150", "max"), max_req_nevi=("req_range_nevi_grade", "max"))
    bt.to_csv(TAB / "trips_border.csv")

    # required range: the trip view of the spacing standard
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.6))
    ax = axes[0]
    city = T[T["kind"] == "city"]
    for name, col, lab in [("all", BLUE, "all fast chargers"), ("hpc150", ORANGE, "150 kW+ CCS"), ("nevi_grade", AQUA, "NEVI-grade (4 x 150 kW)")]:
        v = city[f"req_range_{name}"].replace(np.inf, 2000).values
        w = city["gravity"].values
        o = np.argsort(v)
        ax.plot(v[o], np.cumsum(w[o]) / w.sum(), c=col, label=lab)
    for lab, nominal in RANGES.items():
        ax.axvline(nominal * WINTER, c=INK2, lw=0.7, ls=":")
        ax.text(nominal * WINTER + 2, 0.05, f"{nominal} mi in winter", rotation=90, fontsize=6.5, color=INK2)
    ax.set_xlim(0, 260)
    ax.set_xlabel("usable range needed for the trip (miles)")
    ax.set_ylabel("share of trips (gravity-weighted)")
    ax.set_title("A. Range needed for city-to-city trips", loc="left")
    ax.legend(fontsize=7, loc="lower right")
    ax = axes[1]
    hard = T.sort_values("req_range_all", ascending=False).head(12)
    labels = [f'{a.split(" city")[0].split(" village")[0][:18]} - {b.split(" city")[0].split(" village")[0][:18]}' for a, b in zip(hard["from"], hard["to"])]
    y = np.arange(len(hard))[::-1]
    ax.barh(y, hard["req_range_all"].replace(np.inf, np.nan), color=BLUE, height=0.6)
    ax.set_yticks(y, labels, fontsize=6.5)
    ax.set_xlabel("usable range needed (miles)")
    ax.set_title("B. Hardest trips (all fast chargers)", loc="left")
    save(fig, "fig11_trip_ranges")

    # ============================================================== Hanig-style consecutive coverage
    rows = []
    for name in ["all", "hpc150", "nevi_grade"]:
        for gap in [25, 30, 40, 50, 60]:
            w_share, len_share, ncell = trips.consecutive_coverage(ok, lookup, gap, masks[name])
            rows.append([name, gap, w_share, len_share, ncell])
    H = pd.DataFrame(rows, columns=["network", "gap_threshold_miles", "aadt_weighted_share", "length_share", "corridor_cells"])
    H.to_csv(TAB / "hanig_consecutive_coverage.csv", index=False)
    S["hanig_50"] = H[(H.gap_threshold_miles == 50)].set_index("network")[["aadt_weighted_share", "length_share"]].round(4).to_dict("index")

    # ============================================================== growth over time
    rows = []
    years = [2022, 2026] if os.environ.get("EVNET_FAST") else range(2015, 2027)
    for year in years:
        m = (sites["open_year"] <= year).values
        idx = np.where(m)[0]
        Rs = R[np.ix_(idx, idx)]
        lk = net.mst_links(Rs, sites["city"].iloc[idx].reset_index(drop=True))
        g50, g30 = net.build_graph(Rs, 50), net.build_graph(Rs, 30)
        u50, w50 = cov.coverage(g50, C_road[:, idx], 50, pop)
        P = exact.Placement(Rs, M["SC"][idx], M["CC"], 50, time_limit=240)
        r = P.solve("connectivity")
        print(f"  history {year}: {len(idx)} sites, {r['stations']} stations (lb {r['lower_bound']}, {r['status']}, {r['seconds']}s)", flush=True)
        rows.append([year, len(idx), lk["miles"].iloc[0], f'{lk["from"].iloc[0]} - {lk["to"].iloc[0]}', net.largest_share(g50),
                     len(g50.connected_components()), len(g50.articulation_points()), len(g30.articulation_points()),
                     u50, w50, r["stations"], r["lower_bound"], r["status"], len(P.unreachable_sites())])
    Y = pd.DataFrame(rows, columns=["year", "sites", "threshold_road_miles", "weakest_link", "largest_share_50",
                                    "pieces_50", "cut_vertices_50", "cut_vertices_30", "coverage_50", "coverage_weighted_50",
                                    "stations_needed_50", "stations_lower_bound_50", "solver_status", "unreachable_sites_50"])
    Y.to_csv(TAB / "history_by_year.csv", index=False)
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.4))
    ax = axes[0]
    ax.plot(Y["year"], Y["threshold_road_miles"], c=BLUE, marker="o", ms=4)
    ax.axhline(50, c=INK2, ls=":", lw=0.8)
    ax.set_ylabel("connectivity threshold (road miles)")
    ax.set_title("A. Threshold by year", loc="left")
    ax2 = axes[1]
    ax2.plot(Y["year"], Y["coverage_50"], c=ORANGE, marker="o", ms=4, label="city-pair coverage at 50 mi")
    ax2.plot(Y["year"], Y["largest_share_50"], c=BLUE, marker="o", ms=4, label="sites in largest piece at 50 mi")
    ax2.set_ylim(0, 1.05)
    ax2.set_title("B. Connectivity at 50 miles by year", loc="left")
    ax2.legend(fontsize=7, loc="lower right")
    for a in axes:
        a.set_xlabel("end of year (stations open in 2026, by opening date)")
    save(fig, "fig12_history")

    # ============================================================== reliability
    # (a) temporarily unavailable stations (Oct 13, 2026)
    w = masks["working"]
    idx = np.where(w)[0]
    Rw = R[np.ix_(idx, idx)]
    lk = net.mst_links(Rw, sites["city"].iloc[idx].reset_index(drop=True))
    S["working_network"] = {"unavailable_sites": int((~w).sum()), "unavailable_cities": sorted(sites["city"][~w].tolist()),
                            "threshold": float(lk["miles"].iloc[0]),
                            "cut_vertices_30": len(net.build_graph(Rw, 30).articulation_points())}
    # (b) correlated regional outages vs independent failures with the same number of sites lost
    cand_all = pd.read_csv(data.DERIVED / "candidates.csv")
    pool_lonlat = np.vstack([sites[["Longitude", "Latitude"]].values, cand_all[["lon", "lat"]].values])
    rows = []
    for eps in [50, 30]:
        g_full = net.build_graph(R, eps)
        base_u, _ = cov.coverage(g_full, C_road, eps, pop)
        for radius in [10, 25, 50]:
            res_r, res_i = [], []
            for _ in range(300):
                c0 = pool_lonlat[RNG.integers(len(pool_lonlat))]
                d = distance.haversine([c0[1]], [c0[0]], sites.Latitude, sites.Longitude)[0]
                failed = np.where(d <= radius)[0]
                k = len(failed)
                rand = RNG.choice(n, size=k, replace=False)
                for fset, store in [(failed, res_r), (rand, res_i)]:
                    keep = np.setdiff1d(np.arange(n), fset)
                    g = net.build_graph(R[np.ix_(keep, keep)], eps)
                    u, _ = cov.coverage(g, C_road[:, keep], eps, pop)
                    store.append([k, net.largest_share(g, n) / (len(keep) / n) if len(keep) else 0, u])
            res_r, res_i = np.array(res_r), np.array(res_i)
            rows.append([eps, radius, res_r[:, 0].mean(), np.percentile(res_r[:, 0], 95),
                         res_r[:, 1].mean(), res_i[:, 1].mean(), res_r[:, 2].mean(), res_i[:, 2].mean(),
                         np.percentile(res_r[:, 2], 5), np.percentile(res_i[:, 2], 5),
                         float((res_r[:, 2] < base_u - 1e-9).mean()), float((res_i[:, 2] < base_u - 1e-9).mean())])
    O = pd.DataFrame(rows, columns=["miles", "outage_radius_mi", "sites_lost_mean", "sites_lost_p95",
                                    "survivors_connected_regional", "survivors_connected_independent",
                                    "coverage_regional_mean", "coverage_independent_mean",
                                    "coverage_regional_p05", "coverage_independent_p05",
                                    "share_draws_losing_coverage_regional", "share_draws_losing_coverage_independent"])
    O.to_csv(TAB / "reliability_regional_outages.csv", index=False)

    # ============================================================== baselines with confidence intervals
    pool_all = pool_lonlat
    pd_ = distance.haversine(places.lat, places.lon, pool_all[:, 1], pool_all[:, 0])
    w_pop = (pop[:, None] * np.exp(-pd_ / 10.0)).sum(0)
    w_pop = w_pop / w_pop.sum()
    corridor_xy = np.vstack([np.asarray(r["geom"])[:, :2] for r in ok])
    ct = cKDTree(np.column_stack([corridor_xy[:, 0] * 69.0 * np.cos(np.radians(42.5)), corridor_xy[:, 1] * 69.0]))
    dcor, _ = ct.query(np.column_stack([pool_all[:, 0] * 69.0 * np.cos(np.radians(42.5)), pool_all[:, 1] * 69.0]))
    corridor_pool = np.where(dcor <= 1.0)[0]
    S["pool_sizes"] = {"all": len(pool_all), "corridor": len(corridor_pool)}
    C_straight_city = FACTOR * distance.haversine(places.lat, places.lon, pool_all[:, 1], pool_all[:, 0])
    D_pool = FACTOR * distance.haversine(pool_all[:, 1], pool_all[:, 0], pool_all[:, 1], pool_all[:, 0])

    def stats(ix):
        d = D_pool[np.ix_(ix, ix)]
        thr = net.mst_links(d, pd.Series(np.arange(len(ix))))["miles"].iloc[0]
        g30 = net.build_graph(d, 30)
        u30, _ = cov.coverage(g30, C_straight_city[:, ix], 30, pop)
        return [thr, u30, len(g30.connected_components()), len(g30.articulation_points())]

    real = stats(np.arange(n))
    rows = []
    draws = 200
    for name, sampler in [("uniform over all charging locations", lambda: RNG.choice(len(pool_all), n, replace=False)),
                          ("population-weighted", lambda: RNG.choice(len(pool_all), n, replace=False, p=w_pop)),
                          ("corridor-restricted (within 1 mi of a major route)", lambda: RNG.choice(corridor_pool, n, replace=False))]:
        res = np.array([stats(sampler()) for _ in range(draws)])
        for k, (mname, lower_better) in enumerate([("threshold_miles", True), ("coverage_30", False), ("pieces_30", True), ("cut_vertices_30", True)]):
            better = (res[:, k] < real[k]) if lower_better else (res[:, k] > real[k])
            lo, hi = wilson(int(better.sum()), draws)
            rows.append([name, mname, real[k], res[:, k].mean(), np.percentile(res[:, k], 2.5), np.percentile(res[:, k], 97.5),
                         better.mean(), lo, hi])
    Bdf = pd.DataFrame(rows, columns=["baseline", "measure", "real", "random_mean", "random_p2.5", "random_p97.5",
                                      "share_random_better", "share_ci_low", "share_ci_high"])
    Bdf.to_csv(TAB / "baselines_with_ci.csv", index=False)

    # random failure with 95% bands
    p_values = np.round(np.arange(0, 0.61, 0.05), 2)
    rows = []
    for eps in [50, 30]:
        g = net.build_graph(R, eps)
        for p in p_values:
            v = []
            for _ in range(300):
                failed = np.where(RNG.random(n) < p)[0]
                h = g.copy()
                h.delete_vertices(failed)
                v.append(net.largest_share(h))
            v = np.array(v)
            rows.append([eps, p, v.mean(), np.percentile(v, 2.5), np.percentile(v, 97.5)])
    pd.DataFrame(rows, columns=["miles", "p", "survivors_connected_mean", "p2.5", "p97.5"]).to_csv(
        TAB / "random_failure_ci.csv", index=False)

    # ============================================================== random geometric graph benchmark
    A = NY_LAND_SQMI
    r_conn = np.sqrt(A * np.log(n) / (np.pi * n))           # Penrose / Gupta-Kumar connectivity radius
    r_perc = np.sqrt(4.512 * A / (np.pi * n))               # continuum percolation, mean degree 4.512
    deg = {e: float(np.mean(net.build_graph(R, e).degree())) for e in [10, 15, 20, 24, 25, 26, 30, 43, 44, 50]}
    perc = pd.read_csv(TAB / "q1_percolation.csv", header=[0, 1], index_col=0)
    jump = int(perc[perc[("all_road", "largest_share")] >= 0.9].index.min())
    S["rgg"] = {"n": n, "area_sq_mi": A, "connectivity_radius_straight": float(r_conn), "connectivity_radius_road": float(r_conn * FACTOR),
                "percolation_radius_straight": float(r_perc), "percolation_radius_road": float(r_perc * FACTOR),
                "observed_threshold_road": float(net.mst_links(R, sites["city"])["miles"].iloc[0]),
                "observed_giant_component_jump_road": jump, "mean_degree_at": deg}
    # inhomogeneity: local density near the weakest link vs state average
    kd = cKDTree(np.column_stack([sites.Longitude * 69.0 * np.cos(np.radians(42.5)), sites.Latitude * 69.0]))
    lk = net.mst_links(R, sites["city"])
    ends = [lk["from_id"].iloc[0], lk["to_id"].iloc[0]]
    local = [len(kd.query_ball_point([sites.Longitude.iloc[e] * 69.0 * np.cos(np.radians(42.5)), sites.Latitude.iloc[e] * 69.0], 50.0)) / (np.pi * 50 ** 2) for e in ends]
    lam_min = float(np.mean(local))
    S["rgg"]["density_mean_per_sq_mi"] = n / A
    S["rgg"]["density_near_weakest_link"] = lam_min
    S["rgg"]["inhomogeneous_prediction_road"] = float(FACTOR * np.sqrt(np.log(n) / (np.pi * lam_min)))

    json.dump(S, open(ROOT / "results" / "extended_summary.json", "w"), indent=2,
              default=lambda o: o.item() if hasattr(o, "item") else str(o))
    print(json.dumps(S, indent=1, default=str)[:4000])


if __name__ == "__main__":
    main()
