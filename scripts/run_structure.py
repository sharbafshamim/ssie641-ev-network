"""Network-structure analyses added after the literature review.

    python scripts/run_structure.py            # full run (about 3 minutes)
    python scripts/run_structure.py --quick    # fewer random trials, for testing

Needs the outputs of run_all.py (data/derived/sites.csv and the road matrix).
Writes results/tables/s*_*.csv, results/figures/figS4-S6_*.png and
results/structure_summary.json.

  A  connectivity and biconnectivity thresholds (Penrose 1997; Penrose & Yang 2024)
  B  reliability of the single points of failure (NEVI 97% uptime; J.D. Power 2025; Rempel et al. 2022)
  C  global efficiency and harmonic centrality under failure and attack (Hamim et al. 2025)
  D  betweenness by road miles and over population-weighted city pairs
  E  k-core numbers of the critical sites
  F  random-walk spectral gap, relaxation time and spectral bisection
  G  Leiden communities and their boundaries
  H  degree, harmonic, betweenness, eigenvector and PageRank compared; friendship paradox
  I  standard each city needs to reach every other city (eccentricity) or 90% of the population
  J  EU AFIR standards (60 km, 100 km) and a range of winter range losses
  K  distributions as CCDFs; circuity on a log scale
  L  region-stratified random-siting control
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
sys.path.insert(0, str(ROOT / "scripts"))

from evnet import control, coverage as cov, data, distance, network as net, placement  # noqa: E402
from evnet import structure as st  # noqa: E402
from run_all import AQUA, BLUE, GREY, INK, INK2, ORANGE, RED, VIOLET, map_axes, save  # noqa: E402

TAB, FIG = ROOT / "results" / "tables", ROOT / "results" / "figures"
SEED = 641
FACTOR = 1.22                                   # measured median road / straight-line ratio
AFIR_MI = {"AFIR core, 60 km": 60 / 1.609344, "AFIR low-traffic, 100 km": 100 / 1.609344}
UNAVAILABILITY = {"NEVI 97% uptime rule": 0.03, "J.D. Power 2025 failed visits": 0.14,
                  "Rempel et al. 2022 Bay Area audit": 0.275}
WINTER_LOSSES = {"IEA lower (20%)": 0.20, "30%": 0.30, "Recurrent (37%)": 0.37, "AAA 20 F with heat (41%)": 0.41}
NYC = (40.7128, -74.0060)
PAUL_SMITHS = (44.44867, -74.25810)            # the candidate chosen at 35 and 40 miles in Q3


def main(quick=False):
    t0 = time.time()
    rng = np.random.default_rng(SEED)
    mc = 100 if quick else 1000
    eff_trials = 5 if quick else 30
    S = {"seed": SEED}

    sites = pd.read_csv(data.DERIVED / "sites.csv")
    n = len(sites)
    R = data.load_road_miles(n)
    straight = distance.haversine(sites.Latitude, sites.Longitude, sites.Latitude, sites.Longitude)
    ccs = np.where(sites["ccs"])[0]
    R_ccs = R[np.ix_(ccs, ccs)]
    places, _ = data.load_places(5000)
    pop = places["pop"].values.astype(float)
    C = FACTOR * distance.haversine(places.lat, places.lon, sites.Latitude, sites.Longitude)
    YS = data.load_osrm_matrix()["YS"]          # city -> site road miles
    cand = data.load_candidates(data.AFDC_ALL_OCT)
    K = FACTOR * distance.haversine(cand.lat, cand.lon, sites.Latitude, sites.Longitude)
    KK = (FACTOR * distance.haversine(cand.lat, cand.lon, cand.lat, cand.lon)).astype(np.float32)
    near_nyc = distance.haversine([NYC[0]], [NYC[1]], sites.Latitude, sites.Longitude)[0] <= 60 / 1.609344
    city = sites["city"].values

    # ============================================================ A. thresholds
    rows = []
    for lab, d in [("all sites, road", R), ("CCS sites, road", R_ccs), ("all sites, straight x 1.2", 1.2 * straight)]:
        thr1 = float(net.mst_links(d, pd.Series(np.arange(len(d))))["miles"].iloc[0])
        thr2, last = st.biconnectivity_threshold(d)
        names = sites["city"].values[ccs][last] if lab.startswith("CCS") else city[last]
        rows.append([lab, thr1, thr2, "; ".join(names)])
    A = pd.DataFrame(rows, columns=["network", "connectivity_threshold", "biconnectivity_threshold",
                                    "last_single_points_of_failure"])
    A.to_csv(TAB / "s1_thresholds.csv", index=False)
    S["thresholds"] = A.to_dict("records")
    print(A)

    # ============================================================ B. reliability of cut vertices
    crit_tab = pd.read_csv(TAB / "q2_cut_vertices_by_standard.csv")
    rows = []
    for eps in [30, 35, 40, 45]:
        g = net.build_graph(R, eps)
        cv = net.critical_sites(g, sites)
        k, lost = len(cv), int(cv["sites_cut_off"].sum())
        for lab, p in UNAVAILABILITY.items():
            ps, out = st.split_probability(g, p, mc, rng)
            rows.append([eps, k, "; ".join(cv["city"]), lab, p, st.prob_any_down(k, p), p * lost, ps, out])
    B = pd.DataFrame(rows, columns=["miles", "cut_vertices", "cities", "source", "p_unavailable",
                                    "prob_any_cut_vertex_down", "expected_sites_cut_off",
                                    "prob_some_piece_splits_mc", "survivors_cut_off_share_mc"])
    B.to_csv(TAB / "s2_reliability_cut_vertices.csv", index=False)
    S["reliability"] = B.drop(columns=["cities"]).round(4).to_dict("records")
    del crit_tab

    # ============================================================ C. efficiency under failure and attack
    fractions = np.round(np.arange(0, 0.61, 0.02), 2)
    steps = int(0.6 * n) + 1
    rows, curves = [], {}
    for eps in [50, 30]:
        g = net.build_graph(R, eps)
        e0_hop = st.global_efficiency(g)
        gw = g.copy()
        gw.es["miles"] = [max(R[e.source, e.target], 0.05) for e in g.es]  # 0.05 mi = data resolution
        e0_mi = st.global_efficiency(gw, weights="miles")
        orders = {c: st.adaptive_order(g, c, steps) for c in ["degree", "betweenness", "harmonic"]}
        cur = {"random": st.random_order_efficiency(g, fractions, eff_trials, rng)}
        for c, o in orders.items():
            cur[c] = st.efficiency_under_removal(g, o, fractions)
        curves[eps] = cur
        for strat, y in cur.items():
            below = fractions[y < 0.2]
            rows.append([eps, strat, float(y.mean()), float(below.min()) if len(below) else np.nan,
                         float(np.interp(0.05, fractions, y)), e0_hop, e0_mi])
        hc = st.harmonic(gw, weights="miles")
        top = np.argsort(-hc)[:10]
        pd.DataFrame({"city": city[top], "name": sites["name"].values[top], "harmonic_miles": hc[top]}).to_csv(
            TAB / f"s3_top_harmonic_{eps}mi.csv", index=False)
        pd.DataFrame({k: city[v[:15]] for k, v in orders.items()}).to_csv(TAB / f"s3_attack_order_{eps}mi.csv", index=False)
    Cdf = pd.DataFrame(rows, columns=["miles", "strategy", "R_efficiency", "fraction_to_0.2_relative_efficiency",
                                      "relative_efficiency_after_5pct", "E0_hops", "E0_miles"])
    Cdf.to_csv(TAB / "s3_efficiency.csv", index=False)
    S["efficiency"] = Cdf.round(4).to_dict("records")

    fig, axes = plt.subplots(1, 2, figsize=(9, 3.4), sharey=True)
    for ax, eps in zip(axes, [50, 30]):
        for strat, col in [("random", BLUE), ("degree", AQUA), ("harmonic", VIOLET), ("betweenness", ORANGE)]:
            ax.plot(fractions, curves[eps][strat], c=col, label=f"{'random failure' if strat == 'random' else 'attack by ' + strat}")
        ax.axhline(0.2, c=INK2, lw=0.8, ls=":")
        ax.set_title(f"{eps}-mile standard", loc="left")
        ax.set_xlabel("share of sites removed")
    axes[0].set_ylabel("global efficiency / original")
    axes[0].text(0.01, 0.22, "0.2: collapse level used by Hamim et al. (2025)", ha="left", fontsize=7, color=INK2)
    axes[0].legend(loc="upper right", fontsize=7)
    save(fig, "figS4_efficiency")

    # ============================================================ D. betweenness variants
    rows = []
    bt = {}
    cut = {eps: set(net.build_graph(R, eps).articulation_points()) for eps in [30, 50]}
    for eps in [30, 50]:
        g = net.build_graph(R, eps)
        gw = g.copy()
        gw.es["miles"] = [max(R[e.source, e.target], 0.05) for e in g.es]  # 0.05 mi = data resolution
        b_hop = np.array(g.betweenness())
        b_mi = np.array(gw.betweenness(weights="miles"))
        b_city, b_pop = st.city_pair_betweenness(R, YS, eps, pop)
        bt[eps] = (b_hop, b_mi, b_city, b_pop)
        for lab, b in [("hops", b_hop), ("road miles", b_mi), ("city pairs", b_city), ("city pairs, population-weighted", b_pop)]:
            top = np.argsort(-b)[:10]
            for r, v in enumerate(top):
                rows.append([eps, lab, r + 1, city[v], sites["name"].iloc[v], float(b[v]), v in cut[eps], bool(near_nyc[v])])
    D = pd.DataFrame(rows, columns=["miles", "betweenness", "rank", "city", "name", "score", "cut_vertex", "near_nyc"])
    D.to_csv(TAB / "s4_betweenness_top10.csv", index=False)
    S["betweenness_top3"] = {f"{e}_{b}": D[(D.miles == e) & (D.betweenness == b)].head(3)[["city", "score"]].to_dict("records")
                             for e in [30, 50] for b in D.betweenness.unique()}
    corr = []
    for eps in [30, 50]:
        b_hop, b_mi, b_city, b_pop = bt[eps]
        rk = pd.DataFrame({"hops": b_hop, "miles": b_mi, "city": b_city, "pop": b_pop}).rank()
        corr.append([eps] + rk.corr(method="spearman").loc["hops", ["miles", "city", "pop"]].round(3).tolist())
    S["betweenness_spearman_vs_hops"] = pd.DataFrame(corr, columns=["miles", "road_miles", "city_pairs", "pop_weighted"]).to_dict("records")

    # ============================================================ E. k-cores
    rows = []
    for eps in [30, 50]:
        g = net.build_graph(R, eps)
        core = np.array(g.coreness())
        cv = net.critical_sites(g, sites)
        topb = np.argsort(-bt[eps][0])[:17]
        for lab, ids in [("all sites", np.arange(n)), ("single points of failure", cv["id"].values),
                         ("top 17 by betweenness", topb)]:
            if len(ids):
                rows.append([eps, lab, len(ids), float(np.median(core[ids])), int(core[ids].min()), int(core[ids].max()),
                             float(np.mean([(core < core[v]).mean() for v in ids])), float(np.median(sites["ports"].values[ids]))])
        pd.DataFrame({"city": city, "core": core}).to_csv(TAB / f"s5_core_numbers_{eps}mi.csv", index=False)
    E = pd.DataFrame(rows, columns=["miles", "group", "sites", "median_core", "min_core", "max_core",
                                    "mean_core_percentile", "median_ports"])
    E.to_csv(TAB / "s5_core_summary.csv", index=False)
    S["core"] = E.round(3).to_dict("records")

    # ============================================================ F. spectral gap
    rows = []
    for eps in range(26, 61):
        g = net.build_graph(R, eps)
        lam2, tau, ids, _ = st.random_walk_spectrum(g)
        rows.append([eps, len(ids), lam2, 1 - lam2, tau])
    F = pd.DataFrame(rows, columns=["miles", "largest_piece_sites", "lambda2", "spectral_gap", "relaxation_time"])
    # adding the Paul Smiths station
    ps_d_sites = FACTOR * distance.haversine([PAUL_SMITHS[0]], [PAUL_SMITHS[1]], sites.Latitude, sites.Longitude)[0]
    Rp = np.full((n + 1, n + 1), 1e6)
    Rp[:n, :n] = R
    Rp[n, :n] = Rp[:n, n] = ps_d_sites
    Rp[n, n] = 0
    ps_rows = []
    for eps in [40, 44, 45, 50]:
        a = st.random_walk_spectrum(net.build_graph(R, eps))
        b = st.random_walk_spectrum(net.build_graph(Rp, eps))
        ps_rows.append([eps, a[0], b[0], a[1], b[1], len(a[2]), len(b[2])])
    PS = pd.DataFrame(ps_rows, columns=["miles", "lambda2_now", "lambda2_with_paul_smiths", "tau_now",
                                        "tau_with_paul_smiths", "piece_now", "piece_with_paul_smiths"])
    F.to_csv(TAB / "s6_spectral_gap.csv", index=False)
    PS.to_csv(TAB / "s6_spectral_paul_smiths.csv", index=False)
    S["spectral"] = F[F.miles.isin([26, 30, 35, 40, 43, 44, 45, 50, 60])].round(5).to_dict("records")
    S["spectral_paul_smiths"] = PS.round(5).to_dict("records")
    splits = {}
    rows = []
    for eps in [30, 50]:
        g = net.build_graph(R, eps)
        lam2, tau, ids, psi2 = st.random_walk_spectrum(g)
        sp = st.spectral_split(g, ids, psi2)
        splits[eps] = (ids, psi2, sp)
        seam = sp["seam_sites"]
        rows.append([eps, sp["side_sizes"][0], sp["side_sizes"][1], sp["cut_links"], sp["ncut"],
                     "; ".join(pd.Series(city[seam]).value_counts().index[:10])])
    SP = pd.DataFrame(rows, columns=["miles", "side_a_sites", "side_b_sites", "cut_links", "normalised_cut", "seam_cities"])
    SP.to_csv(TAB / "s6_spectral_split.csv", index=False)
    S["spectral_split"] = SP.round(5).to_dict("records")

    fig, axes = plt.subplots(1, 2, figsize=(9.5, 3.6), gridspec_kw={"width_ratios": [1, 1.1]})
    ax = axes[0]
    ax.plot(F["miles"], F["relaxation_time"], c=BLUE, marker="o", ms=3)
    ax.set_yscale("log")
    ax.axvline(43.5, c=INK2, lw=0.8, ls=":")
    ax.text(44, F["relaxation_time"].max() * 0.8, "one piece from 43.5 mi", fontsize=7, color=INK2)
    ax.set_xlabel("spacing standard (miles)")
    ax.set_ylabel("relaxation time 1/(1 - $\\lambda_2$), steps")
    ax.set_title("A. Random-walk relaxation time, largest piece", loc="left")
    ax = axes[1]
    ids, psi2, sp = splits[50]
    ax.scatter(sites.Longitude, sites.Latitude, s=4, c=GREY, edgecolors="none")
    ax.scatter(sites.Longitude.values[ids], sites.Latitude.values[ids], s=7, c=np.where(psi2 > 0, BLUE, ORANGE), edgecolors="none")
    seam = sp["seam_sites"]
    ax.scatter(sites.Longitude.values[seam], sites.Latitude.values[seam], s=22, facecolors="none", edgecolors=INK, lw=0.8)
    map_axes(ax, "B. Spectral split at 50 miles (ringed: sites on the cut)")
    save(fig, "figS5_spectral")

    # ============================================================ G. Leiden communities
    rows, memb50 = [], None
    top17 = {eps: np.argsort(-bt[eps][0])[:17] for eps in [30, 50]}
    for eps in [30, 50]:
        g = net.build_graph(R, eps)
        for res in [0.5, 1.0, 2.0]:
            q, m = st.leiden_best(g, res, seeds=3 if quick else 10)
            tab, boundary = st.community_boundaries(g, m)
            bset = set(boundary)
            rows.append([eps, res, q, int(m.max() + 1), int(np.sort(tab["sites"])[-1]), float(tab["conductance"].median()),
                         len(boundary), sum(v in bset for v in top17[eps]), sum(v in bset for v in cut[eps]), len(cut[eps])])
            if eps == 50 and res == 1.0:
                memb50 = m
    G = pd.DataFrame(rows, columns=["miles", "resolution", "modularity", "communities", "largest_community",
                                    "median_conductance", "boundary_sites", "top17_betweenness_on_boundary",
                                    "cut_vertices_on_boundary", "cut_vertices"])
    G.to_csv(TAB / "s7_communities.csv", index=False)
    S["communities"] = G.round(4).to_dict("records")

    # ============================================================ H. centralities compared
    rows = []
    g50 = net.build_graph(R, 50)
    cs = st.centrality_scores(g50)
    for m in ["degree", "harmonic", "betweenness", "eigenvector", "pagerank"]:
        sc = cs[m].values
        top = np.argsort(-sc)[:10]
        rows.append([m, sc[near_nyc].sum() / sc.sum(), near_nyc[top].mean(), "; ".join(city[top[:5]])])
    H = pd.DataFrame(rows, columns=["measure", "share_of_score_within_60km_of_NYC", "share_of_top10_within_60km_of_NYC",
                                    "top5_cities"])
    H.to_csv(TAB / "s8_centrality_localisation.csv", index=False)
    S["share_sites_within_60km_nyc"] = float(near_nyc.mean())
    S["centrality_localisation"] = H.round(4).to_dict("records")
    S["friendship_paradox"] = {eps: dict(zip(["mean_degree", "mean_neighbour_degree"],
                                             st.neighbour_degree_gap(net.build_graph(R, eps)))) for eps in [30, 50]}

    # ============================================================ I. bottleneck eccentricity of cities
    need_all = np.full(len(places), np.nan)       # eccentricity: reach every other city
    need_90 = np.full(len(places), np.nan)        # reach cities holding 90% of the other cities' people
    others = pop.sum() - pop
    for eps in np.arange(1, 61, 0.5):
        g = net.build_graph(R, eps)
        memb = np.array(g.connected_components().membership)
        M = np.zeros((len(C), memb.max() + 1))
        i, j = np.where(C <= eps)
        M[i, memb[j]] = 1
        reach = (M @ M.T) > 0
        np.fill_diagonal(reach, False)
        share = (reach * pop[None, :]).sum(1) / others
        ok_all = (reach.sum(1) == len(pop) - 1) & np.isnan(need_all)
        ok_90 = (share >= 0.9) & np.isnan(need_90)
        need_all[ok_all] = eps
        need_90[ok_90] = eps
    I = places[["name", "pop"]].assign(standard_to_reach_all=need_all, standard_to_reach_90pct=need_90).sort_values(
        "standard_to_reach_90pct", ascending=False)
    I.to_csv(TAB / "s9_city_standard_needed.csv", index=False)
    S["city_standard_needed"] = {"reach_all_unique_values": sorted(set(np.round(need_all, 1).tolist())),
                                 "reach_90_median": float(np.nanmedian(need_90)),
                                 "reach_90_top": I.head(8).to_dict("records"),
                                 "reach_90_share_cities_above_30": float((need_90 > 30).mean())}

    # ============================================================ J. AFIR standards and winter band
    rows = []
    for lab, eps in list(AFIR_MI.items()) + [("former NEVI guidance", 50.0)]:
        g = net.build_graph(R, eps)
        u, w = cov.coverage(g, C, eps, pop)
        r = placement.place_stations(R, None, K, KK, eps, "network")
        rows.append([lab, eps, len(g.connected_components()), len(g.articulation_points()), u, w,
                     r["lower"], r["upper"], r["feasible"], "; ".join(cand["city"].iloc[r["chosen"]])])
    J = pd.DataFrame(rows, columns=["standard", "miles", "pieces", "cut_vertices", "coverage", "coverage_weighted",
                                    "lower_bound", "new_stations", "feasible", "where"])
    J.to_csv(TAB / "s10_other_standards.csv", index=False)
    S["other_standards"] = J.round(4).to_dict("records")
    thr1 = float(A.loc[0, "connectivity_threshold"])
    thr2 = float(A.loc[0, "biconnectivity_threshold"])
    rows = []
    for lab, loss in WINTER_LOSSES.items():
        e50 = 50 * (1 - loss)
        g = net.build_graph(R, e50)
        rows.append([lab, loss, thr1 / (1 - loss), thr2 / (1 - loss), e50, len(g.connected_components()),
                     cov.coverage(g, C, e50, pop)[0]])
    W = pd.DataFrame(rows, columns=["winter_case", "range_loss", "nominal_needed_connected", "nominal_needed_biconnected",
                                    "effective_miles_at_nominal_50", "pieces_at_nominal_50", "coverage_at_nominal_50"])
    W.to_csv(TAB / "s11_winter_band.csv", index=False)
    S["winter_band"] = W.round(3).to_dict("records")

    # ============================================================ K. distributions
    g30 = net.build_graph(R, 30)
    cv30 = net.critical_sites(g30, sites)["id"].values
    deg30 = np.array(g30.degree())
    iu = np.triu_indices(n, 1)
    far = (straight[iu] > 5) & (R[iu] < 1e5)
    ratio = R[iu][far] / straight[iu][far]
    S["circuity_log_mean_ratio"] = float(np.exp(np.mean(np.log(ratio))))
    fig, axes = plt.subplots(1, 3, figsize=(10.5, 3.1))
    for ax, vals, lab in [(axes[0], deg30, "neighbours within 30 miles"), (axes[1], sites["ports"].values, "fast-charging ports")]:
        for ids, col, name in [(np.arange(n), BLUE, "all sites"), (cv30, RED, "single points of failure, 30 mi")]:
            x, y = st.ccdf(vals[ids])
            ax.step(x, y, where="post", c=col, label=name, marker="o" if len(ids) < 10 else None, ms=4)
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_xlabel(lab)
    axes[0].set_ylabel("share of sites with at least x")
    axes[0].legend(fontsize=7, loc="lower left")
    axes[0].set_title("A. Degree (CCDF)", loc="left")
    axes[1].set_title("B. Station size (CCDF)", loc="left")
    bins = np.exp(np.linspace(np.log(ratio.min()), np.log(ratio.max()), 40))
    dens, edges = np.histogram(ratio, bins=bins, density=True)
    axes[2].bar(edges[:-1], dens, width=np.diff(edges), align="edge", color=GREY, edgecolor="white")
    axes[2].axvline(1.2, c=ORANGE, lw=1.2, label="Ballou et al. 1.2")
    axes[2].axvline(np.median(ratio), c=BLUE, lw=1.2, label=f"median {np.median(ratio):.2f}")
    axes[2].set_xscale("log")
    axes[2].set_xticks([1, 1.2, 1.5, 2, 3], ["1", "1.2", "1.5", "2", "3"])
    axes[2].minorticks_off()
    axes[2].set_xlabel("road / straight-line distance (log scale)")
    axes[2].set_ylabel("density (bar area = share)")
    axes[2].set_title("C. Circuity, log-binned", loc="left")
    axes[2].legend(fontsize=7)
    save(fig, "figS6_distributions")

    # ============================================================ L. region-stratified control
    pool_lat = np.append(sites.Latitude.values, cand.lat.values)
    pool_lon = np.append(sites.Longitude.values, cand.lon.values)
    cell = lambda la, lo: (np.floor(la / 0.5) * 1000 + np.floor(lo / 0.5)).astype(int)  # noqa: E731
    real_cell, pool_cell = cell(sites.Latitude.values, sites.Longitude.values), cell(pool_lat, pool_lon)
    real = control.network_stats(sites.Latitude.values, sites.Longitude.values, places.lat.values, places.lon.values, pop, FACTOR)
    draws = 20 if quick else 100
    res = []
    for _ in range(draws):
        pick = []
        for c, k in zip(*np.unique(real_cell, return_counts=True)):
            pool = np.where(pool_cell == c)[0]
            pick.extend(rng.choice(pool, size=k, replace=False))
        pick = np.array(pick)
        res.append(control.network_stats(pool_lat[pick], pool_lon[pick], places.lat.values, places.lon.values, pop, FACTOR))
    res = pd.DataFrame(res, columns=control.COLUMNS)
    better = [((res[c] < r) if c in control.BETTER_IF_LOWER else (res[c] > r)).mean() for c, r in zip(control.COLUMNS, real)]
    L = pd.DataFrame({"real": real, "random_mean": res.mean().values, "random_p05": res.quantile(0.05).values,
                      "random_p95": res.quantile(0.95).values, "share_random_better": better}, index=control.COLUMNS)
    L.to_csv(TAB / "s12_control_stratified.csv")
    S["control_stratified"] = {"cells": int(len(np.unique(real_cell))), "cell_degrees": 0.5,
                               "summary": L.round(4).to_dict("index")}

    S["runtime_s"] = round(time.time() - t0, 1)
    with open(ROOT / "results" / "structure_summary.json", "w") as f:
        json.dump(S, f, indent=2, default=lambda o: o.item() if hasattr(o, "item") else str(o))
    print(f"done in {S['runtime_s']} s")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    main(ap.parse_args().quick)
