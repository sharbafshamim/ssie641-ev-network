"""Exact cost of connectivity and cost of robustness (integer programming, src/evnet/exact.py).

    python scripts/run_exact.py                # all standards, all networks (can take about an hour)
    python scripts/run_exact.py --quick        # fewer standards, short time limits

Uses OSRM road distances for site-site, site-candidate and candidate-candidate links
(data/derived/osrm_matrix_blocks.u16.gz). Candidates within 1 mile of an existing fast-charging site
are left out (data/derived/candidates_kept.csv): a new charger there adds at most a mile of reach.

Outputs: results/tables/exact_cost_curve.csv, exact_subnetworks.csv, exact_chosen_sites.csv,
         results/figures/fig10_cost_of_robustness.png, results/exact_summary.json
"""
import argparse
import json
import sys
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from evnet import data, exact, network as net  # noqa: E402

TAB, FIG = ROOT / "results" / "tables", ROOT / "results" / "figures"
NEVI_M, COST = 175.0, {"low": 0.6, "central": 1.0, "high": 1.92}


def load():
    sites = data.site_attributes(pd.read_csv(data.DERIVED / "sites.csv"))
    cand = pd.read_csv(data.DERIVED / "candidates_kept.csv")
    R = data.load_road_miles(len(sites))
    M = data.load_osrm_matrix()
    return sites, cand, R, M


def _job(args):
    name, mask, eps, objective, tl = args
    sites, cand, R, M = _G
    idx = np.where(mask)[0]
    P = exact.Placement(R[np.ix_(idx, idx)], M["SC"][idx], M["CC"], eps, time_limit=tl)
    r = P.solve(objective)
    unreach = P.unreachable_sites()
    r.update(network=name, sites=len(idx), pieces=P.site_pieces(),
             unreachable_sites=len(unreach), unreachable_cities="; ".join(sorted(set(sites["city"].iloc[idx[unreach]]))),
             where="; ".join(cand["city"].iloc[r["chosen"]]))
    if objective == "robustness":
        r["unprotectable_sites"] = len(P.unprotectable())
    return r


def init(g):
    global _G
    _G = g


def main(quick=False):
    t0 = time.time()
    G = load()
    sites, cand, R, M = G
    full = np.ones(len(sites), bool)
    nets = {"all": full, "ccs": sites["ccs"].values, "hpc150": sites["hpc150"].values,
            "nevi_grade": sites["nevi_grade"].values, "working": ~sites["unavailable"].values}
    eps_list = [30, 40, 50] if quick else [20, 25, 30, 35, 40, 45, 50, 55, 60]
    tl_conn, tl_rob = (60, 120) if quick else (600, 1500)
    jobs = [("all", full, e, "connectivity", tl_conn) for e in eps_list]
    jobs += [("all", full, e, "robustness", tl_rob) for e in eps_list]
    for name in ["ccs", "hpc150", "nevi_grade", "working"]:
        for e in ([40, 50] if quick else [30, 40, 50, 60]):
            jobs.append((name, nets[name], e, "connectivity", tl_conn))
        jobs.append((name, nets[name], 50, "robustness", tl_rob))
    # hardest first so the pool finishes together
    jobs.sort(key=lambda j: (j[3] != "robustness", j[2]))
    with Pool(2, initializer=init, initargs=(G,)) as pool:
        res = pool.map(_job, jobs, chunksize=1)
    df = pd.DataFrame(res).drop(columns=["chosen"])
    df = df.sort_values(["network", "objective", "eps"]).reset_index(drop=True)
    for lvl, c in COST.items():
        df[f"cost_{lvl}_M"] = df["stations"] * c
    df["share_of_NEVI_central_pct"] = 100 * df["stations"] * COST["central"] / NEVI_M
    main_df = df[df["network"] == "all"]
    main_df.to_csv(TAB / "exact_cost_curve.csv", index=False)
    df[df["network"] != "all"].to_csv(TAB / "exact_subnetworks.csv", index=False)
    picks = []
    for r in res:
        for c in r["chosen"]:
            picks.append([r["network"], r["objective"], r["eps"], cand["name"].iloc[c], cand["city"].iloc[c],
                          cand["lat"].iloc[c], cand["lon"].iloc[c]])
    pd.DataFrame(picks, columns=["network", "objective", "miles", "name", "city", "lat", "lon"]).to_csv(
        TAB / "exact_chosen_sites.csv", index=False)

    # descriptive facts for each subnetwork (threshold, weakest link, cut vertices)
    rows = []
    for name, mask in nets.items():
        idx = np.where(mask)[0]
        Rs = R[np.ix_(idx, idx)]
        lk = net.mst_links(Rs, sites["city"].iloc[idx].reset_index(drop=True))
        rows.append([name, len(idx), round(lk["miles"].iloc[0], 1), f'{lk["from"].iloc[0]} - {lk["to"].iloc[0]}',
                     len(net.build_graph(Rs, 30).articulation_points()), len(net.build_graph(Rs, 50).articulation_points()),
                     len(net.build_graph(Rs, 50).connected_components())])
    pd.DataFrame(rows, columns=["network", "sites", "threshold_road_miles", "weakest_link", "cut_vertices_30",
                                "cut_vertices_50", "pieces_50"]).to_csv(TAB / "subnetwork_structure.csv", index=False)

    # figure: cost of connectivity vs cost of robustness
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from run_all import BLUE, INK2, ORANGE, RED, save
    fig, axes = plt.subplots(1, 2, figsize=(9.5, 3.6))
    ax = axes[0]
    for obj, col, lab in [("connectivity", BLUE, "cost of connectivity"), ("robustness", ORANGE, "cost of robustness")]:
        q = main_df[main_df["objective"] == obj]
        ax.plot(q["eps"], q["stations"], c=col, marker="o", ms=4, label=lab)
        gap = q[q["status"] != "optimal"]
        if len(gap):
            ax.vlines(gap["eps"], gap["lower_bound"], gap["stations"], color=col, lw=3, alpha=0.35)
        part = q[q["unreachable_sites"] > 0]
        ax.scatter(part["eps"], part["stations"], s=90, facecolors="none", edgecolors=RED, lw=1.3)
    ax.scatter([], [], s=90, facecolors="none", edgecolors=RED, label="part of the network unreachable")
    ax.set_xlabel("spacing standard (road miles)")
    ax.set_ylabel("new fast-charging stations (exact)")
    ax.set_title("A. Connectivity vs robustness", loc="left")
    ax.legend(fontsize=7)
    ax = axes[1]
    for obj, col in [("connectivity", BLUE), ("robustness", ORANGE)]:
        q = main_df[main_df["objective"] == obj]
        ax.fill_between(q["eps"], q["stations"] * COST["low"] / NEVI_M * 100, q["stations"] * COST["high"] / NEVI_M * 100,
                        color=col, alpha=0.18, lw=0)
        ax.plot(q["eps"], q["stations"] * COST["central"] / NEVI_M * 100, c=col)
    ax.set_xlabel("spacing standard (road miles)")
    ax.set_ylabel("% of NY's \\$175M NEVI allocation")
    ax.set_title("B. Cost (band: \\$0.6M-\\$1.92M per site)", loc="left")
    save(fig, "fig10_cost_of_robustness")

    summ = {"runtime_s": round(time.time() - t0, 1),
            "candidates_kept": len(cand), "candidate_rule": "public L1/L2 locations more than 1 straight mile from any fast-charging site",
            "queried_share_CC_le60": M["queried_share_CC_le60"]}
    json.dump(summ, open(ROOT / "results" / "exact_summary.json", "w"), indent=2)
    print(main_df[["objective", "eps", "pieces", "stations", "lower_bound", "status", "unreachable_sites", "where"]].to_string())
    print(f"done in {time.time() - t0:.0f} s")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    main(ap.parse_args().quick)
