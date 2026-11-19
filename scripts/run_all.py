"""Run the full analysis and write every table and figure used in the paper.

    python scripts/run_all.py            # full run (about 10 minutes)
    python scripts/run_all.py --quick    # fewer random trials, for testing

Outputs: results/tables/*.csv, results/figures/*.png, results/summary.json
"""
import argparse
import json
import sys
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from evnet import control, coverage as cov, data, distance, network as net, placement  # noqa: E402

TAB = ROOT / "results" / "tables"
FIG = ROOT / "results" / "figures"
TAB.mkdir(parents=True, exist_ok=True)
FIG.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------- parameters
NEVI_NY_ALLOCATION_M = 175.0          # NY five-year NEVI formula apportionment, $M (NYSDOT, 2025)
SITE_COST_M = {"low": 0.6,            # low end of NEVI-compliant 4 x 150 kW sites
               "central": 1.0,        # average NEVI project cost, about $0.92M-$1.05M (Paren, 2024)
               "high": 1.92}          # NYSERDA max award $1.536M at an 80% cost share (NYSERDA PON 5865)
WINTER_RANGE_LOSS = 0.41              # AAA (2019): 20 F with cabin heat
FALLBACK_CIRCUITY = 1.27              # median road/straight ratio measured in notebook v3
STANDARDS = [20, 25, 30, 35, 40, 45, 50]
V3_GREEDY = {50: 0, 45: 0, 40: 1, 35: 3, 30: 3, 25: 4, 20: 8}  # notebook v3, Section 11.3

# validated categorical palette (dataviz reference palette, light mode)
BLUE, ORANGE, AQUA, YELLOW, MAGENTA, GREEN, VIOLET, RED = (
    "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948")
GREY, INK, INK2 = "#c9c8c2", "#0b0b0b", "#52514e"
plt.rcParams.update({
    "figure.dpi": 150, "savefig.dpi": 200, "savefig.bbox": "tight",
    "font.size": 9, "axes.titlesize": 10, "axes.labelsize": 9,
    "axes.edgecolor": INK2, "axes.labelcolor": INK, "xtick.color": INK2, "ytick.color": INK2,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": "#e8e7e3", "grid.linewidth": 0.6,
    "lines.linewidth": 2, "legend.frameon": False,
})


def save(fig, name):
    fig.savefig(FIG / f"{name}.png")
    plt.close(fig)


def map_axes(ax, title):
    ax.set_aspect(1 / np.cos(np.radians(42.5)))
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.set_title(title, loc="left")
    ax.grid(False)


def main(quick=False):
    t0 = time.time()
    trials = 20 if quick else 100
    draws = 20 if quick else 100
    S = {}  # headline numbers for summary.json

    # ============================================================ 1. data
    stations = data.load_dcfc(data.AFDC_SEP)
    sites = data.make_sites(stations)
    sites.to_csv(data.DERIVED / "sites.csv", index=False)
    S["stations"] = len(stations)
    S["fast_ports"] = int(stations["EV DC Fast Count"].sum())
    S["sites"] = len(sites)
    S["ccs_sites"] = int(sites["ccs"].sum())
    S["tesla_only_stations"] = int(stations["tesla_only"].sum())
    S["ccs_stations"] = int(stations["ccs"].sum())
    ops = stations["EV Network"].value_counts().head(10)
    ops.rename("stations").to_csv(TAB / "operators_top10.csv")

    places, all_places = data.load_places(5000)
    pop = places["pop"].values.astype(float)
    S["places_all"] = len(all_places)
    S["places_5000"] = len(places)
    S["pop_places_5000"] = int(pop.sum())
    S["share_state_pop_in_places_5000"] = float(pop.sum() / data.NY_POP_2020)
    S["share_place_pop_in_places_5000"] = float(pop.sum() / all_places["pop"].sum())
    nyc = places["name"].eq("New York city").values
    w = np.outer(pop, pop)
    np.fill_diagonal(w, 0)
    S["nyc_share_of_pair_weight"] = float(w[nyc].sum() * 2 / w.sum() - w[np.ix_(nyc, nyc)].sum() / w.sum())

    cand = data.load_candidates(data.AFDC_ALL_OCT)
    S["candidates"] = len(cand)

    # ============================================================ 2. distances
    straight = distance.haversine(sites.Latitude, sites.Longitude, sites.Latitude, sites.Longitude)
    D12 = distance.BALLOU_FACTOR * straight
    R = data.load_road_miles(len(sites))
    if R is not None:
        circ = distance.circuity(R, straight)
        factor = round(circ["median"], 2)
        S["distance_source"] = "OSRM road network"
        S["circuity"] = circ
    else:
        factor = FALLBACK_CIRCUITY
        R = factor * straight
        S["distance_source"] = f"straight line x {factor} (road_miles.npy not found)"
        S["circuity"] = {"median": FALLBACK_CIRCUITY, "note": "from notebook v3"}
    S["detour_factor_new_links"] = factor
    DLAB = "road" if S["distance_source"].startswith("OSRM") else f"calibrated x{factor}"
    ALL_KEY, CCS_KEY = f"all_{DLAB.split()[0]}", f"ccs_{DLAB.split()[0]}"
    print("distances:", S["distance_source"], "| factor for new links:", factor)

    ccs_idx = np.where(sites["ccs"])[0]
    sites_ccs = sites.iloc[ccs_idx].reset_index(drop=True)
    R_ccs = R[np.ix_(ccs_idx, ccs_idx)]

    # ------------------------------------------------ site map
    fig, ax = plt.subplots(figsize=(6.5, 5))
    nc_ = ~sites["ccs"]
    ax.scatter(sites.Longitude[nc_], sites.Latitude[nc_], s=sites.ports[nc_] * 2.5, c=GREY,
               label="no CCS plug (mostly Tesla-only)", edgecolors="white", linewidths=0.3)
    ax.scatter(sites.Longitude[~nc_], sites.Latitude[~nc_], s=sites.ports[~nc_] * 2.5, c=BLUE,
               label="CCS plug", edgecolors="white", linewidths=0.3, alpha=0.85)
    map_axes(ax, f"DC fast-charging sites in New York (n = {len(sites)}; dot size = ports)")
    ax.legend(loc="lower right")
    save(fig, "figS1_sites_map")

    # ============================================================ 3. Q1
    eps_values = np.arange(5, 101)
    perc = {k: net.percolation(d, eps_values) for k, d in
            [(ALL_KEY, R), ("all_straight_x1.2", D12), (CCS_KEY, R_ccs)]}
    pc = pd.concat({k: v.set_index("miles") for k, v in perc.items()}, axis=1)
    pc.to_csv(TAB / "q1_percolation.csv")

    links = {ALL_KEY: net.mst_links(R, sites["city"]),
             "all_straight_x1.2": net.mst_links(D12, sites["city"]),
             "all_straight_xfactor": net.mst_links(factor * straight, sites["city"]),
             CCS_KEY: net.mst_links(R_ccs, sites_ccs["city"])}
    pd.concat({k: v.head(15)[["miles", "from", "to"]] for k, v in links.items()}, axis=1).to_csv(
        TAB / "q1_weakest_links.csv")
    S["threshold"] = {k: float(v["miles"].iloc[0]) for k, v in links.items()}
    S["weakest_link"] = f'{links[ALL_KEY]["from"].iloc[0]} - {links[ALL_KEY]["to"].iloc[0]}'
    # eps where largest piece first holds >= 90% of sites
    lr = perc[ALL_KEY].set_index("miles")["largest_share"]
    S["eps_largest_ge_90pct"] = int(lr[lr >= 0.9].index.min())
    S["largest_share_at"] = {int(e): float(lr[e]) for e in [20, 24, 25, 28, 30, 35, 40, 44, 50]}

    fig, axes = plt.subplots(1, 2, figsize=(9, 3.4))
    for k, col, lab in [(ALL_KEY, BLUE, f"all sites, {DLAB}"), ("all_straight_x1.2", ORANGE, "all sites, straight x 1.2"),
                        (CCS_KEY, AQUA, f"CCS sites, {DLAB}")]:
        axes[0].plot(eps_values, perc[k]["largest_share"], c=col, label=lab)
        axes[1].plot(eps_values, perc[k]["pieces"], c=col, label=lab)
    for ax in axes:
        ax.axvline(50, c=INK2, lw=0.8, ls=":")
        ax.set_xlabel("spacing standard (miles)")
    axes[0].set_ylabel("share of sites in largest piece")
    axes[1].set_ylabel("number of pieces")
    axes[1].set_yscale("log")
    axes[0].set_title("A. Percolation curve", loc="left")
    axes[1].set_title("B. Pieces", loc="left")
    axes[0].legend(loc="lower right")
    save(fig, "fig1_percolation")

    # pieces just below the jump
    g24 = net.build_graph(R, 24)
    memb = np.array(g24.connected_components().membership)
    sizes = pd.Series(memb).value_counts()
    rows = []
    for k, (piece, size) in enumerate(sizes.items()):
        members = sites[memb == piece]
        rows.append([k + 1, size, round(members.Latitude.mean(), 2), round(members.Longitude.mean(), 2),
                     ", ".join(members["city"].value_counts().index[:6])])
    pd.DataFrame(rows, columns=["piece", "sites", "mean_lat", "mean_lon", "main_cities"]).to_csv(
        TAB / "q1_pieces_24mi.csv", index=False)
    fig, ax = plt.subplots(figsize=(6.5, 5))
    order = {p: i for i, p in enumerate(sizes.index)}
    cols8 = [BLUE, ORANGE, AQUA, YELLOW, MAGENTA, GREEN, VIOLET, RED]
    colors = [cols8[order[m]] if order[m] < 8 else GREY for m in memb]
    ax.scatter(sites.Longitude, sites.Latitude, c=colors, s=9, edgecolors="none")
    map_axes(ax, "Pieces of the network at a 24-mile standard (8 largest coloured, rest grey)")
    save(fig, "fig2_pieces_24mi")

    # ============================================================ 4. Q2 cut vertices
    rows = []
    for eps in range(20, 61):
        ga, gc = net.build_graph(R, eps), net.build_graph(R_ccs, eps)
        ca, cc = ga.articulation_points(), gc.articulation_points()
        rows.append([eps, len(ga.connected_components()), len(ca), "; ".join(sites["city"].iloc[ca]),
                     len(gc.connected_components()), len(cc), "; ".join(sites_ccs["city"].iloc[cc])])
    ap = pd.DataFrame(rows, columns=["miles", "pieces_all", "cut_all", "cities_all",
                                     "pieces_ccs", "cut_ccs", "cities_ccs"])
    ap.to_csv(TAB / "q2_cut_vertices_by_standard.csv", index=False)

    crit = {}
    for name, d, tbl, eps in [("all", R, sites, 30), ("ccs", R_ccs, sites_ccs, 30),
                              ("all", R, sites, 35), ("ccs", R_ccs, sites_ccs, 35),
                              ("all", R, sites, 45), ("ccs", R_ccs, sites_ccs, 45)]:
        c = net.critical_sites(net.build_graph(d, eps), tbl)
        c.insert(0, "network", name)
        c.insert(1, "miles", eps)
        crit[(name, eps)] = c
    critical = pd.concat(crit.values(), ignore_index=True)
    critical.to_csv(TAB / "q2_critical_sites.csv", index=False)
    S["critical_all_30"] = crit[("all", 30)][["city", "operator", "degree", "ports", "sites_cut_off"]].to_dict("records")
    S["critical_ccs_45"] = crit[("ccs", 45)][["city", "operator", "degree", "ports", "sites_cut_off"]].to_dict("records")

    rows = []
    for eps in [25, 30, 35, 40, 45, 50]:
        for name, d, tbl in [("all", R, sites), ("ccs", R_ccs, sites_ccs)]:
            g = net.build_graph(d, eps)
            c = net.critical_sites(g, tbl)
            rows.append([eps, name, len(c), np.median(g.degree()),
                         c["degree"].median() if len(c) else np.nan,
                         np.median(tbl["ports"]), c["ports"].median() if len(c) else np.nan,
                         (c["operator"] == "Tesla").mean() if len(c) else np.nan])
    big_small = pd.DataFrame(rows, columns=["miles", "network", "critical_sites", "median_degree_all",
                                            "median_degree_critical", "median_ports_all",
                                            "median_ports_critical", "share_tesla_critical"])
    big_small.to_csv(TAB / "q2_big_or_small.csv", index=False)
    S["median_ports_all_sites"] = float(np.median(sites["ports"]))
    S["tesla_share_of_sites"] = float((sites["network"] == "Tesla").mean())

    fig, axes = plt.subplots(1, 2, figsize=(9, 4))
    for ax, (name, eps, tbl) in zip(axes, [("all", 30, sites), ("ccs", 45, sites_ccs)]):
        c = crit[(name, eps)]
        ax.scatter(tbl.Longitude, tbl.Latitude, s=5, c=GREY, edgecolors="none")
        ax.scatter(tbl.Longitude.iloc[c["id"]], tbl.Latitude.iloc[c["id"]],
                   s=20 + 3 * c["sites_cut_off"], c=RED, edgecolors="white", linewidths=0.6)
        c_sorted = c.assign(lat=tbl.Latitude.iloc[c["id"]].values).sort_values("lat")
        for k, (_, r) in enumerate(c_sorted.iterrows()):
            right = k % 2 == 0
            ax.annotate(f'{r["city"]} ({r["sites_cut_off"]})', (tbl.Longitude.iloc[r["id"]], tbl.Latitude.iloc[r["id"]]),
                        xytext=(6 if right else -6, 0), textcoords="offset points", fontsize=7, color=INK,
                        ha="left" if right else "right", va="center")
        map_axes(ax, f"{'All' if name == 'all' else 'CCS'} sites, {eps}-mile standard")
    fig.suptitle("Single points of failure (label: sites cut off)", x=0.02, ha="left", fontsize=10)
    save(fig, "fig3_critical_sites")

    fig, ax = plt.subplots(figsize=(5.5, 3.2))
    ax.plot(ap["miles"], ap["cut_all"], c=BLUE, marker="o", ms=3, label="all sites")
    ax.plot(ap["miles"], ap["cut_ccs"], c=AQUA, marker="o", ms=3, label="CCS sites")
    ax.set_xlabel("spacing standard (miles)")
    ax.set_ylabel("single points of failure")
    ax.legend()
    save(fig, "figS2_cut_vertex_count")

    # ============================================================ 5. random failure
    p_values = np.round(np.arange(0, 0.61, 0.05), 2)
    rows = []
    rf_curves = {}
    for name, d in [("all", R), ("ccs", R_ccs)]:
        for eps in [30, 35, 40, 45, 50]:
            df = net.random_failure(d, eps, p_values, trials, seed=42)
            rf_curves[(name, eps)] = df
            rows.append([name, eps, df["largest_share_of_all"].mean(), df["largest_share_of_survivors"].mean(),
                         df["largest_share_of_survivors"].iloc[-1]])
    rf = pd.DataFrame(rows, columns=["network", "miles", "R_all", "R_survivors", "survivors_connected_p0.6"])
    rf.to_csv(TAB / "q2_random_failure.csv", index=False)

    # ============================================================ 6. targeted attack
    n = len(sites)
    steps = int(0.6 * n)
    f_values = np.arange(steps + 1) / n
    attack = {}
    rows = []
    for eps in [50, 30]:
        g = net.build_graph(R, eps)
        cd, rd = net.targeted_attack(g, steps, "degree")
        cb, rb = net.targeted_attack(g, steps, "betweenness")
        attack[eps] = {"degree": (cd, rd), "betweenness": (cb, rb)}
        rnd = rf_curves[("all", eps)]
        rows.append([eps, rnd["largest_share_of_all"].mean(), cd.mean(), cb.mean(),
                     cb[15], cb[30], int(np.argmax(cb < 0.9))])
        pd.DataFrame({"degree": sites["city"].iloc[rd[:15]].values,
                      "betweenness": sites["city"].iloc[rb[:15]].values}).to_csv(
            TAB / f"q2_attack_first15_{eps}mi.csv", index=False)
    at = pd.DataFrame(rows, columns=["miles", "R_random", "R_degree", "R_betweenness",
                                     "largest_after_15_betweenness", "largest_after_30_betweenness",
                                     "removals_to_drop_below_0.9"])
    at.to_csv(TAB / "q2_targeted_attack.csv", index=False)
    S["attack"] = at.to_dict("records")

    fig, axes = plt.subplots(1, 2, figsize=(9, 3.4), sharey=True)
    for ax, eps in zip(axes, [50, 30]):
        rnd = rf_curves[("all", eps)]
        ax.plot(rnd["p"], rnd["largest_share_of_all"], c=BLUE, marker="o", ms=3, label="random failure")
        ax.plot(f_values, attack[eps]["degree"][0], c=AQUA, label="attack by degree")
        ax.plot(f_values, attack[eps]["betweenness"][0], c=ORANGE, label="attack by betweenness")
        ax.plot(p_values, 1 - p_values, c=INK2, lw=0.8, ls="--", label="upper bound 1 - f")
        ax.set_title(f"{eps}-mile standard", loc="left")
        ax.set_xlabel("share of sites removed")
    axes[0].set_ylabel("largest piece / all sites")
    axes[0].legend(loc="lower left")
    save(fig, "fig4_failure_attack")

    # ============================================================ 7. coverage
    C = factor * distance.haversine(places.lat, places.lon, sites.Latitude, sites.Longitude)
    S["city_nearest_site_median"] = float(np.median(C.min(axis=1)))
    far = places.assign(nearest=C.min(axis=1)).nlargest(8, "nearest")[["name", "pop", "nearest"]]
    far.to_csv(TAB / "coverage_farthest_cities.csv", index=False)
    rows = []
    for eps in range(1, 81):
        g = net.build_graph(R, eps)
        u, wcv = cov.coverage(g, C, eps, pop)
        _, w_ex = cov.coverage(g, C, eps, pop, exclude=nyc)
        u15, w15 = cov.coverage(g, C, eps, pop, access=15)
        rows.append([eps, net.largest_share(g), u, wcv, w_ex, u15, w15])
    cv = pd.DataFrame(rows, columns=["miles", "connectivity", "coverage", "coverage_weighted",
                                     "coverage_weighted_excl_NYC", "coverage_access15", "coverage_weighted_access15"])
    cv.to_csv(TAB / "coverage_curve.csv", index=False)
    S["coverage_at"] = cv.set_index("miles").loc[[10, 20, 24, 30, 40, 44, 50]].round(4).to_dict("index")
    full = cv[cv["coverage"] >= 1 - 1e-12]["miles"]
    S["eps_full_coverage"] = int(full.min()) if len(full) else None

    fig, ax = plt.subplots(figsize=(6, 3.4))
    ax.plot(cv["miles"], cv["connectivity"], c=BLUE, label="connectivity (share of sites)")
    ax.plot(cv["miles"], cv["coverage"], c=ORANGE, label="coverage (city pairs)")
    ax.plot(cv["miles"], cv["coverage_weighted"], c=AQUA, label="coverage (population-weighted)")
    ax.plot(cv["miles"], cv["coverage_access15"], c=VIOLET, lw=1.2, ls="--", label="coverage, access <= 15 mi")
    ax.set_xlabel("spacing standard (miles)")
    ax.set_ylabel("share")
    ax.legend(loc="lower right")
    save(fig, "fig5_coverage_curve")

    # single-site removal by coverage
    rows = []
    for eps in [30, 40, 50]:
        bu, bw = cov.coverage(net.build_graph(R, eps), C, eps, pop)
        for v in range(n):
            u, wcv = cov.coverage_after(R, C, eps, pop, [v])
            if bu - u > 1e-12:
                rows.append([eps, sites["name"].iloc[v], sites["city"].iloc[v], bu - u, bw - wcv])
    pd.DataFrame(rows, columns=["miles", "name", "city", "coverage_lost", "weighted_lost"]).to_csv(
        TAB / "coverage_single_site_loss.csv", index=False)

    rows = []
    cov_curves = {}
    for eps in [50, 30]:
        rnd = cov.random_failure_coverage(R, C, eps, pop, p_values, trials, seed=7)
        dg = cov.attack_coverage(R, C, eps, pop, attack[eps]["degree"][1])
        bt = cov.attack_coverage(R, C, eps, pop, attack[eps]["betweenness"][1])
        cov_curves[eps] = (rnd, dg, bt)
        rows.append([eps, rnd[:, 1].mean(), dg[:, 0].mean(), bt[:, 0].mean(),
                     rnd[:, 2].mean(), dg[:, 1].mean(), bt[:, 1].mean()])
    ca = pd.DataFrame(rows, columns=["miles", "R_random", "R_degree", "R_betweenness",
                                     "Rw_random", "Rw_degree", "Rw_betweenness"])
    ca.to_csv(TAB / "coverage_failure_attack.csv", index=False)
    S["coverage_attack"] = ca.to_dict("records")

    fig, axes = plt.subplots(1, 2, figsize=(9, 3.4), sharey=True)
    for ax, eps in zip(axes, [50, 30]):
        rnd, dg, bt = cov_curves[eps]
        ax.plot(rnd[:, 0], rnd[:, 1], c=BLUE, marker="o", ms=3, label="random failure")
        ax.plot(f_values, dg[:, 0], c=AQUA, label="attack by degree")
        ax.plot(f_values, bt[:, 0], c=ORANGE, label="attack by betweenness")
        ax.set_title(f"{eps}-mile standard", loc="left")
        ax.set_xlabel("share of sites removed")
    axes[0].set_ylabel("city-pair coverage")
    axes[0].legend(loc="lower left")
    save(fig, "figS3_coverage_attack")

    # ============================================================ 8. Q3
    K = factor * distance.haversine(cand.lat, cand.lon, sites.Latitude, sites.Longitude)
    KK = (factor * distance.haversine(cand.lat, cand.lon, cand.lat, cand.lon)).astype(np.float32)
    CK = factor * distance.haversine(places.lat, places.lon, cand.lat, cand.lon)
    rows, picks = [], []
    for obj in ["network", "coverage"]:
        for eps in STANDARDS:
            kw = {"CS": C, "CK": CK, "pop": pop} if obj == "coverage" else {}
            r = placement.place_stations(R, None, K, KK, eps, obj, **kw)
            unreached = (sorted(set(sites["city"].iloc[r["unreached_sites"]])) if obj == "network"
                         else sorted(places["name"].iloc[r["unreached_cities"]]))
            rows.append([obj, eps, r["pieces"], r["lower"], r["upper"], r["feasible"],
                         V3_GREEDY.get(eps) if obj == "coverage" else np.nan,
                         "; ".join(cand["city"].iloc[r["chosen"]]), "; ".join(unreached)])
            for c in r["chosen"]:
                picks.append([obj, eps, cand["name"].iloc[c], cand["city"].iloc[c], cand["lat"].iloc[c], cand["lon"].iloc[c]])
            print(f"  Q3 {obj:8s} {eps} mi: pieces={r['pieces']} lower={r['lower']} upper={r['upper']} feasible={r['feasible']}")
    q3 = pd.DataFrame(rows, columns=["objective", "miles", "pieces_before", "lower_bound", "new_stations",
                                     "feasible", "v3_greedy", "where", "unreachable"])
    q3.to_csv(TAB / "q3_cost_curve.csv", index=False)
    pd.DataFrame(picks, columns=["objective", "miles", "name", "city", "lat", "lon"]).to_csv(
        TAB / "q3_chosen_sites.csv", index=False)
    S["q3"] = q3.drop(columns=["where"]).to_dict("records")

    # sensitivity: new links at the proposal's 1.2 factor instead of the measured one
    K12 = (distance.BALLOU_FACTOR / factor) * K
    KK12 = ((distance.BALLOU_FACTOR / factor) * KK).astype(np.float32)
    CK12 = (distance.BALLOU_FACTOR / factor) * CK
    rows = []
    for obj in ["network", "coverage"]:
        for eps in STANDARDS:
            kw = {"CS": C * distance.BALLOU_FACTOR / factor, "CK": CK12, "pop": pop} if obj == "coverage" else {}
            r = placement.place_stations(R, None, K12, KK12, eps, obj, **kw)
            rows.append([obj, eps, r["lower"], r["upper"], r["feasible"], "; ".join(cand["city"].iloc[r["chosen"]])])
    q3s = pd.DataFrame(rows, columns=["objective", "miles", "lower_bound", "new_stations", "feasible", "where"])
    q3s.to_csv(TAB / "q3_sensitivity_factor1.2.csv", index=False)
    S["q3_factor_1.2"] = q3s.drop(columns=["where"]).to_dict("records")

    # budget
    rows = []
    for _, r in q3.iterrows():
        for lvl, c in SITE_COST_M.items():
            rows.append([r["objective"], r["miles"], r["new_stations"], r["feasible"], lvl, c,
                         r["new_stations"] * c, 100 * r["new_stations"] * c / NEVI_NY_ALLOCATION_M])
    budget = pd.DataFrame(rows, columns=["objective", "miles", "new_stations", "feasible", "cost_level",
                                         "cost_per_site_M", "total_M", "share_of_NEVI_pct"])
    budget.to_csv(TAB / "q3_budget.csv", index=False)
    S["budget"] = {"allocation_M": NEVI_NY_ALLOCATION_M, "site_cost_M": SITE_COST_M,
                   "sites_affordable": {k: int(NEVI_NY_ALLOCATION_M // v) for k, v in SITE_COST_M.items()}}

    fig, axes = plt.subplots(1, 2, figsize=(9, 3.4))
    for obj, col, lab in [("network", BLUE, "whole network connected"), ("coverage", ORANGE, "all city pairs connected")]:
        q = q3[q3["objective"] == obj]
        axes[0].plot(q["miles"], q["new_stations"], c=col, marker="o", ms=4, label=lab)
        bad = q[~q["feasible"]]
        axes[0].scatter(bad["miles"], bad["new_stations"], s=90, facecolors="none", edgecolors=RED, lw=1.4)
        if obj == "network":
            axes[0].plot(q["miles"], q["lower_bound"], c=col, lw=1, ls="--", label="lower bound (network)")
    axes[0].scatter([], [], s=90, facecolors="none", edgecolors=RED, label="not reachable from existing L2 sites")
    axes[0].set_xlabel("spacing standard (miles)")
    axes[0].set_ylabel("new fast-charging stations")
    axes[0].set_title("A. Stations needed", loc="left")
    axes[0].legend(fontsize=7)
    q = q3[q3["objective"] == "network"].reset_index(drop=True)
    x = np.arange(len(q))
    pct = 100 * q["new_stations"] / NEVI_NY_ALLOCATION_M
    feas = q["feasible"].values
    axes[1].bar(x[feas], (pct * SITE_COST_M["central"])[feas], width=0.6, color=BLUE, label="central cost (\\$1.0M/site)")
    axes[1].bar(x[~feas], (pct * SITE_COST_M["central"])[~feas], width=0.6, color=GREY,
                label="partial: standard not reachable")
    axes[1].errorbar(x, pct * SITE_COST_M["central"],
                     yerr=[pct * (SITE_COST_M["central"] - SITE_COST_M["low"]), pct * (SITE_COST_M["high"] - SITE_COST_M["central"])],
                     fmt="none", ecolor=INK2, elinewidth=1, capsize=3, label="range \\$0.6M-\\$1.92M/site")
    axes[1].set_xticks(x, q["miles"])
    axes[1].set_xlabel("spacing standard (miles)")
    axes[1].set_ylabel("% of NY's \\$175M NEVI allocation")
    axes[1].set_title("B. Cost of connecting the whole network", loc="left")
    axes[1].legend(fontsize=7, loc="upper right")
    save(fig, "fig6_cost_curve")

    # ============================================================ 9. winter
    keep_frac = 1 - WINTER_RANGE_LOSS
    S["winter_nominal_needed"] = float(S["threshold"][ALL_KEY] / keep_frac)
    rows = []
    for nominal in range(30, 101, 5):
        e = nominal * keep_frac
        g = net.build_graph(R, e)
        u, wcv = cov.coverage(g, C, e, pop)
        rows.append([nominal, round(e, 1), len(g.connected_components()), net.largest_share(g), u, wcv])
    winter = pd.DataFrame(rows, columns=["nominal_miles", "winter_effective_miles", "pieces", "connectivity",
                                         "coverage", "coverage_weighted"])
    winter.to_csv(TAB / "winter.csv", index=False)
    rows = []
    for nominal in [50, 60, 70]:
        e = nominal * keep_frac
        r = placement.place_stations(R, None, K, KK, e, "network")
        rows.append([nominal, round(e, 1), r["pieces"], r["lower"], r["upper"], r["feasible"],
                     "; ".join(cand["city"].iloc[r["chosen"]])])
    wq3 = pd.DataFrame(rows, columns=["nominal_miles", "winter_effective_miles", "pieces", "lower_bound",
                                      "new_stations", "feasible", "where"])
    wq3.to_csv(TAB / "winter_q3.csv", index=False)
    S["winter_q3"] = wq3.drop(columns=["where"]).to_dict("records")

    fig, ax = plt.subplots(figsize=(6, 3.4))
    summer = cv.set_index("miles")
    ax.plot(summer.index, summer["coverage"], c=BLUE, label="mild weather")
    ax.plot(winter["nominal_miles"], winter["coverage"], c=ORANGE, marker="o", ms=3, label="20 F with heat (-41% range)")
    ax.set_xlim(20, 100)
    ax.set_xlabel("nominal spacing standard (miles)")
    ax.set_ylabel("city-pair coverage")
    ax.legend(loc="lower right")
    save(fig, "fig7_winter")

    # ============================================================ 10. control
    pool_lat = np.append(sites.Latitude.values, cand.lat.values)
    pool_lon = np.append(sites.Longitude.values, cand.lon.values)
    ctrl, rand = control.random_control(sites.Latitude.values, sites.Longitude.values, pool_lat, pool_lon,
                                        places.lat.values, places.lon.values, pop, factor, draws, seed=42)
    ctrl.to_csv(TAB / "control_summary.csv")
    rand.to_csv(TAB / "control_draws.csv", index=False)
    S["control"] = ctrl.round(4).to_dict("index")
    S["control_pool"] = len(pool_lat)

    fig, axes = plt.subplots(1, 3, figsize=(10, 2.8))
    for ax, col, lab in zip(axes, ["mst_threshold", "coverage_30", "cut_vertices_30"],
                            ["connectivity threshold (miles)", "coverage at 30 miles", "single points of failure, 30 mi"]):
        ax.hist(rand[col], bins=20, color=GREY, edgecolor="white")
        ax.axvline(ctrl.loc[col, "real"], c=RED, lw=2, label="real network")
        ax.set_xlabel(lab)
    axes[0].set_ylabel("random networks")
    axes[0].legend()
    save(fig, "fig8_control")

    # ============================================================ 11. October snapshot
    oct_st = data.load_dcfc(data.AFDC_ALL_OCT)
    oct_sites = data.make_sites(oct_st)
    rows = []
    for lab, tbl in [("Sep 23, 2026", sites), ("Oct 13, 2026", oct_sites)]:
        d = factor * distance.haversine(tbl.Latitude, tbl.Longitude, tbl.Latitude, tbl.Longitude)
        lk = net.mst_links(d, tbl["city"])
        aps = {e: "; ".join(tbl["city"].iloc[net.build_graph(d, e).articulation_points()]) for e in [30, 35, 45]}
        Ko = factor * distance.haversine(cand.lat, cand.lon, tbl.Latitude, tbl.Longitude)
        q = {e: placement.place_stations(d, None, Ko, KK, e, "network")["upper"] for e in [30, 35, 40]}
        rows.append([lab, len(tbl), lk["miles"].iloc[0], f'{lk["from"].iloc[0]} - {lk["to"].iloc[0]}',
                     aps[30], aps[35], aps[45], q[30], q[35], q[40]])
    snap = pd.DataFrame(rows, columns=["snapshot", "sites", "threshold", "weakest_link", "cut_30", "cut_35",
                                       "cut_45", "new_stations_30", "new_stations_35", "new_stations_40"])
    snap.to_csv(TAB / "robustness_snapshot.csv", index=False)
    S["snapshot"] = snap.to_dict("records")

    S["runtime_s"] = round(time.time() - t0, 1)
    with open(ROOT / "results" / "summary.json", "w") as f:
        json.dump(S, f, indent=2, default=lambda o: o.item() if hasattr(o, "item") else str(o))
    print(f"done in {S['runtime_s']} s")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    main(ap.parse_args().quick)
