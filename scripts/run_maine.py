"""Extension (c): repeat the analysis for a second, lower-density state (Maine).

    python scripts/run_all.py     # New York first (this script reads results/summary.json)
    python scripts/run_maine.py

Inputs (data/raw/maine/): AFDC station locator export for Maine (Nov 19, 2026), Census 2020 Gazetteer
places for Maine, Census 2020 P.L. 94-171 table P1 for Maine places. Road distances between every pair of
Maine fast-charging sites come from OSRM (data/derived/me_road_miles_allpairs.u16.gz).

Outputs: results/tables/maine_*.csv, results/tables/ny_vs_maine.csv, results/figures/fig9_maine.png,
results/summary_maine.json
"""
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from evnet import control, coverage as cov, data, distance, network as net, placement  # noqa: E402
from run_all import (BLUE, GREY, INK, INK2, ORANGE, RED, SITE_COST_M, STANDARDS,  # noqa: E402
                     WINTER_RANGE_LOSS, map_axes, save)

TAB, FIG = ROOT / "results" / "tables", ROOT / "results" / "figures"
MAINE_NEVI_M = 19.3      # Maine's NEVI formula funds, $M (MaineDOT)
NY_LAND_SQMI = 47_126    # Census 2020 land area
ME_LAND_SQMI = 30_843


def main(trials=100, draws=100):
    S = {}
    stations = data.load_dcfc(data.ME_AFDC)
    sites = data.make_sites(stations)
    sites.to_csv(data.DERIVED / "me_sites.csv", index=False)
    places, all_places = data.load_places(5000, data.ME_GAZETTEER, data.ME_CENSUS_P1, "me_places.csv")
    cand = data.load_candidates(data.ME_AFDC, "me_candidates.csv")
    pop = places["pop"].values.astype(float)
    n = len(sites)
    S.update(stations=len(stations), fast_ports=int(stations["EV DC Fast Count"].sum()), sites=n,
             ccs_sites=int(sites["ccs"].sum()), places_5000=len(places), pop_places_5000=int(pop.sum()),
             share_state_pop_in_places_5000=float(pop.sum() / data.ME_POP_2020), candidates=len(cand))

    straight = distance.haversine(sites.Latitude, sites.Longitude, sites.Latitude, sites.Longitude)
    R = data.unpack_road_miles(data.DERIVED / "me_road_miles_allpairs.u16.gz", data.DERIVED / "me_sites.csv", None)
    circ = distance.circuity(R, straight)
    factor = round(circ["median"], 2)
    S["circuity"], S["detour_factor_new_links"] = circ, factor

    # ---------------- Q1
    links = net.mst_links(R, sites["city"])
    S["threshold"] = float(links["miles"].iloc[0])
    links.head(10)[["miles", "from", "to"]].to_csv(TAB / "maine_weakest_links.csv", index=False)
    eps_values = np.arange(5, 101)
    perc = net.percolation(R, eps_values)
    perc.to_csv(TAB / "maine_percolation.csv", index=False)
    ls = perc.set_index("miles")["largest_share"]
    S["largest_share_at"] = {int(e): float(ls[e]) for e in [20, 30, 40, 50, 60, 70]}
    S["eps_largest_ge_90pct"] = int(ls[ls >= 0.9].index.min())

    # ---------------- Q2
    rows = []
    for eps in [30, 40, 50, 60]:
        g = net.build_graph(R, eps)
        c = net.critical_sites(g, sites)
        c.insert(0, "miles", eps)
        rows.append(c)
    crit = pd.concat([r for r in rows if len(r)], ignore_index=True)
    crit.to_csv(TAB / "maine_critical_sites.csv", index=False)
    for eps in [30, 50]:
        c = crit[crit["miles"] == eps]
        g = net.build_graph(R, eps)
        S[f"critical_{eps}"] = {"count": len(c), "pieces": len(g.connected_components()),
                                "median_degree_critical": float(c["degree"].median()) if len(c) else None,
                                "median_degree_all": float(np.median(g.degree())),
                                "median_ports_critical": float(c["ports"].median()) if len(c) else None,
                                "median_ports_all": float(sites["ports"].median()),
                                "sites": c[["city", "operator", "degree", "ports", "sites_cut_off"]].to_dict("records")}

    p_values = np.round(np.arange(0, 0.61, 0.05), 2)
    steps = int(0.6 * n)
    rows = []
    for eps in [50, 30]:
        rf = net.random_failure(R, eps, p_values, trials, seed=42)
        g = net.build_graph(R, eps)
        cd, _ = net.targeted_attack(g, steps, "degree")
        cb, rb = net.targeted_attack(g, steps, "betweenness")
        rows.append([eps, rf["largest_share_of_all"].mean(), cd.mean(), cb.mean(),
                     int(np.argmax(cb < 0.9)) if (cb < 0.9).any() else None,
                     "; ".join(sites["city"].iloc[rb[:8]])])
    att = pd.DataFrame(rows, columns=["miles", "R_random", "R_degree", "R_betweenness",
                                      "removals_to_drop_below_0.9", "first_8_betweenness"])
    att.to_csv(TAB / "maine_attack.csv", index=False)
    S["attack"] = att.to_dict("records")

    # ---------------- coverage
    C = factor * distance.haversine(places.lat, places.lon, sites.Latitude, sites.Longitude)
    rows = []
    for eps in range(5, 101, 5):
        g = net.build_graph(R, eps)
        u, w = cov.coverage(g, C, eps, pop)
        rows.append([eps, net.largest_share(g), u, w])
    cv = pd.DataFrame(rows, columns=["miles", "connectivity", "coverage", "coverage_weighted"])
    cv.to_csv(TAB / "maine_coverage.csv", index=False)
    S["coverage_at"] = cv.set_index("miles").loc[[30, 50, 70]].round(4).to_dict("index")
    S["farthest_cities"] = places.assign(nearest=C.min(axis=1)).nlargest(4, "nearest")[["name", "nearest"]].round(1).values.tolist()

    # ---------------- Q3
    K = factor * distance.haversine(cand.lat, cand.lon, sites.Latitude, sites.Longitude)
    KK = (factor * distance.haversine(cand.lat, cand.lon, cand.lat, cand.lon)).astype(np.float32)
    CK = factor * distance.haversine(places.lat, places.lon, cand.lat, cand.lon)
    rows, chosen50 = [], []
    for obj in ["network", "coverage"]:
        for eps in STANDARDS + [60, 70]:
            kw = {"CS": C, "CK": CK, "pop": pop} if obj == "coverage" else {}
            r = placement.place_stations(R, None, K, KK, eps, obj, **kw)
            unreached = (sorted(set(sites["city"].iloc[r["unreached_sites"]])) if obj == "network"
                         else sorted(places["name"].iloc[r["unreached_cities"]]))
            rows.append([obj, eps, r["pieces"], r["lower"], r["upper"], r["feasible"],
                         "; ".join(cand["city"].iloc[r["chosen"]]), "; ".join(unreached)])
            if obj == "network" and eps == 50:
                chosen50 = r["chosen"]
    q3 = pd.DataFrame(rows, columns=["objective", "miles", "pieces_before", "lower_bound", "new_stations",
                                     "feasible", "where", "unreachable"])
    q3.to_csv(TAB / "maine_q3_cost_curve.csv", index=False)
    S["q3"] = q3.drop(columns=["where", "unreachable"]).to_dict("records")
    S["budget"] = {"allocation_M": MAINE_NEVI_M, "site_cost_M": SITE_COST_M}

    # ---------------- winter
    keep = 1 - WINTER_RANGE_LOSS
    S["winter_nominal_needed"] = S["threshold"] / keep

    # ---------------- control
    pool_lat = np.append(sites.Latitude.values, cand.lat.values)
    pool_lon = np.append(sites.Longitude.values, cand.lon.values)
    ctrl, rand = control.random_control(sites.Latitude.values, sites.Longitude.values, pool_lat, pool_lon,
                                        places.lat.values, places.lon.values, pop, factor, draws, seed=42)
    ctrl.to_csv(TAB / "maine_control_summary.csv")
    S["control"] = ctrl.round(4).to_dict("index")
    S["control_pool"] = len(pool_lat)

    # ---------------- comparison with New York
    ny = json.load(open(ROOT / "results" / "summary.json"))
    nyq = pd.read_csv(TAB / "q3_cost_curve.csv")
    nyq = nyq[nyq["objective"] == "network"].set_index("miles")
    meq = q3[q3["objective"] == "network"].set_index("miles")

    def q3cell(t, e):
        if e not in t.index:
            return ""
        r = t.loc[e]
        return f'{int(r["new_stations"])}' + ("" if r["feasible"] else "+ (infeasible)")

    nyc = pd.read_csv(TAB / "control_summary.csv", index_col=0)
    comp = pd.DataFrame({
        "New York": [ny["sites"], round(ny["sites"] / NY_LAND_SQMI * 1000, 1), ny["threshold"]["all_road"],
                     ny["weakest_link"], len(ny["critical_all_30"]),
                     round(ny["attack"][0]["R_betweenness"], 3), round(ny["attack"][0]["R_random"], 3),
                     q3cell(nyq, 50), q3cell(nyq, 40), q3cell(nyq, 30),
                     f'{nyc.loc["mst_threshold", "share_random_better"]:.0%}',
                     f'{nyc.loc["coverage_30", "share_random_better"]:.0%}', 175.0],
        "Maine": [n, round(n / ME_LAND_SQMI * 1000, 1), S["threshold"],
                  f'{links["from"].iloc[0]} - {links["to"].iloc[0]}', S["critical_30"]["count"],
                  round(att.loc[att.miles == 50, "R_betweenness"].iloc[0], 3),
                  round(att.loc[att.miles == 50, "R_random"].iloc[0], 3),
                  q3cell(meq, 50), q3cell(meq, 40), q3cell(meq, 30),
                  f'{ctrl.loc["mst_threshold", "share_random_better"]:.0%}',
                  f'{ctrl.loc["coverage_30", "share_random_better"]:.0%}', MAINE_NEVI_M],
    }, index=["fast-charging sites", "sites per 1,000 sq mi", "threshold (road miles)", "weakest link",
              "single points of failure at 30 mi", "R, betweenness attack at 50 mi", "R, random failure at 50 mi",
              "new stations at 50 mi", "new stations at 40 mi", "new stations at 30 mi",
              "random networks with a lower threshold", "random networks with better coverage at 30 mi",
              "NEVI allocation ($M)"])
    comp.to_csv(TAB / "ny_vs_maine.csv")
    print(comp.to_string())

    # ---------------- figure
    nyp = pd.read_csv(TAB / "q1_percolation.csv", header=[0, 1], index_col=0)
    fig, axes = plt.subplots(1, 3, figsize=(13, 4))
    ax = axes[0]
    ax.plot(nyp.index, nyp[("all_road", "largest_share")], c=BLUE, label="New York")
    ax.plot(perc["miles"], perc["largest_share"], c=ORANGE, label="Maine")
    ax.axvline(50, c=INK2, lw=0.8, ls=":")
    ax.set_xlim(5, 100)
    ax.set_xlabel("spacing standard (road miles)")
    ax.set_ylabel("share of sites in largest piece")
    ax.set_title("A. Percolation", loc="left")
    ax.legend(loc="lower right")
    ax = axes[1]
    memb = np.array(net.build_graph(R, 50).connected_components().membership)
    order = {p: k for k, p in enumerate(pd.Series(memb).value_counts().index)}
    palette = [BLUE, ORANGE, "#1baf7a", "#eda100"]
    ax.scatter(sites.Longitude, sites.Latitude, s=10, edgecolors="none",
               c=[palette[order[m]] if order[m] < 4 else GREY for m in memb])
    ch = cand.iloc[chosen50]
    ax.scatter(ch.lon, ch.lat, marker="*", s=90, c=INK, edgecolors="white", linewidths=0.5, label="new station (50 mi)")
    for _, r in ch.iterrows():
        ax.annotate(r["city"], (r["lon"], r["lat"]), xytext=(5, 0), textcoords="offset points", fontsize=7,
                    color=INK, va="center")
    ax.legend(loc="lower right", fontsize=7)
    map_axes(ax, "B. Maine at 50 mi: pieces, new stations")
    ax = axes[2]
    for t, col, lab in [(nyq, BLUE, "New York"), (meq, ORANGE, "Maine")]:
        t = t[t.index <= 70]
        ax.plot(t.index, t["new_stations"], c=col, marker="o", ms=4, label=lab)
        bad = t[~t["feasible"]]
        ax.scatter(bad.index, bad["new_stations"], s=80, facecolors="none", edgecolors=RED, lw=1.3)
    ax.scatter([], [], s=80, facecolors="none", edgecolors=RED, label="not reachable from existing sites")
    ax.set_xlabel("spacing standard (miles)")
    ax.set_ylabel("new stations (whole network)")
    ax.set_title("C. Stations needed", loc="left")
    ax.legend(fontsize=7)
    save(fig, "fig9_maine")

    with open(ROOT / "results" / "summary_maine.json", "w") as f:
        json.dump(S, f, indent=2, default=lambda o: o.item() if hasattr(o, "item") else str(o))


if __name__ == "__main__":
    main()
