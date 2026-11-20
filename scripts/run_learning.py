"""Learning to place stations: a New York benchmark and a graph neural network that prunes candidates.

Benchmark (data/benchmark/ny_placement_benchmark.npz + instances.csv)
    Each instance is the New York network after a failure scenario (none, independent loss of 10% of
    sites, or a regional outage of every site within 25 miles of a random centre) at one range
    standard eps (30, 40, 50, 60 miles). The label is the exact optimal set of new candidate sites that
    restores the connectivity the full candidate graph allows (exact.Placement, connectivity objective).
    Everything is New York: 754 existing fast-charging sites, 2,703 candidate sites, OSRM road miles.

Model
    A three-layer GraphSAGE (mean aggregation, written in plain PyTorch) on the eps-graph over
    sites and candidates. Node features: is-site, scaled degree, number of distinct site pieces
    within reach, distance to nearest site / eps, whether the node is a cut vertex of the full graph,
    scaled coordinates, eps / 60. It scores each candidate's probability of being in the optimum.

Use of the model
    Keep the top-k scored candidates, solve the exact ILP on that reduced set, and grow k (x2) until the
    reduced problem reaches the same connectivity as the full one. The answer is always feasible; the
    gap to the exact optimum and the time saved are reported. Baselines prune by the hand-made
    "site pieces within reach" score and at random; the heuristic greedy Steiner (placement.py) is the
    non-exact reference.

Split: instances from scenario seeds 0-59 train, 60-79 test; eps 50 is also held out entirely
(train on 30/40/60, test on 50) to measure transfer across range standards.

    python scripts/run_learning.py            # about 40-60 minutes on 2 cores
    python scripts/run_learning.py --quick    # small benchmark, minutes
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
from evnet import data, exact  # noqa: E402

BENCH, TAB, FIG = ROOT / "data" / "benchmark", ROOT / "results" / "tables", ROOT / "results" / "figures"


# ---------------------------------------------------------------- instances
def scenario(kind, seed, nS, SS):
    rng = np.random.default_rng(1000 + seed)
    keep = np.ones(nS, bool)
    if kind == "independent":
        keep[rng.choice(nS, int(0.1 * nS), replace=False)] = False
    elif kind == "regional":
        c = rng.integers(nS)
        keep[SS[c] <= 25] = False
    return keep


def features(P, SC, eps, pts):
    """Node features over [sites | candidates] of a Placement."""
    import igraph as ig
    A, nS = P.A, P.nS
    n = A.shape[0]
    deg = np.asarray(A.sum(1)).ravel()
    site_lab = exact._components(A, np.r_[np.ones(nS, bool), np.zeros(n - nS, bool)])
    pieces = np.zeros(n)
    for v in range(n):
        nb = A.indices[A.indptr[v]:A.indptr[v + 1]]
        s = site_lab[nb[nb < nS]]
        pieces[v] = len(np.unique(s))
    d_site = np.r_[np.zeros(nS), SC.min(0)] / eps
    e = np.column_stack(A.nonzero())
    g = ig.Graph(n=n, edges=e[e[:, 0] < e[:, 1]].tolist())
    cut = np.zeros(n)
    cut[g.articulation_points()] = 1
    xy = (pts - pts.mean(0)) / pts.std(0)
    X = np.column_stack([np.r_[np.ones(nS), np.zeros(n - nS)], np.log1p(deg) / 5, np.log1p(pieces),
                         np.minimum(d_site, 3), cut, xy, np.full(n, eps / 60)])
    return X.astype(np.float32)


def _solve_instance(args):
    eps, kind, seed = args
    SS, SC, CC, pts_s, pts_c = _G
    keep = scenario(kind, seed, len(SS), SS)
    idx = np.where(keep)[0]
    P = exact.Placement(SS[np.ix_(idx, idx)], SC[idx], CC, eps, time_limit=300)
    t = time.time()
    r = P.solve("connectivity")
    X = features(P, SC[idx], eps, np.r_[pts_s[idx], pts_c])
    y = np.zeros(P.nC, np.int8)
    y[r["chosen"]] = 1
    e = np.column_stack(P.A.nonzero())
    return dict(eps=eps, kind=kind, seed=seed, keep=keep, X=X, y=y, edges=e.astype(np.int32),
                stations=r["stations"], status=r["status"], seconds=time.time() - t,
                target_pieces=P.site_pieces(np.ones(P.nC)))


def _init(g):
    global _G
    _G = g


# ---------------------------------------------------------------- model
def make_model(d_in, hidden=64):
    import torch
    import torch.nn as nn

    class SAGE(nn.Module):
        def __init__(self):
            super().__init__()
            self.inp = nn.Linear(d_in, hidden)
            self.self_ = nn.ModuleList([nn.Linear(hidden, hidden) for _ in range(3)])
            self.nbr = nn.ModuleList([nn.Linear(hidden, hidden) for _ in range(3)])
            self.out = nn.Linear(hidden, 1)

        def forward(self, X, A):
            h = torch.relu(self.inp(X))
            for s, m in zip(self.self_, self.nbr):
                h = torch.relu(s(h) + m(torch.sparse.mm(A, h))) + h
            return self.out(h).squeeze(-1)

    return SAGE()


def norm_adj(edges, n):
    import torch
    e = torch.as_tensor(edges.T, dtype=torch.long)
    deg = torch.bincount(e[0], minlength=n).clamp(min=1).float()
    return torch.sparse_coo_tensor(e, 1.0 / deg[e[0]], (n, n)).coalesce()


def train(insts, epochs=60, seed=0):
    import torch
    torch.manual_seed(seed)
    model = make_model(insts[0]["X"].shape[1])
    opt = torch.optim.Adam(model.parameters(), lr=3e-3, weight_decay=1e-5)
    tensors = [(torch.as_tensor(i["X"]), norm_adj(i["edges"], len(i["X"])), torch.as_tensor(i["y"], dtype=torch.float32),
                len(i["X"]) - len(i["y"])) for i in insts]
    pos = sum(float(t[2].sum()) for t in tensors)
    neg = sum(len(t[2]) for t in tensors) - pos
    lossf = torch.nn.BCEWithLogitsLoss(pos_weight=torch.tensor(min(neg / max(pos, 1), 200.0)))
    hist = []
    for ep in range(epochs):
        tot = 0
        for k in np.random.default_rng(ep).permutation(len(tensors)):
            X, A, y, nS = tensors[k]
            opt.zero_grad()
            loss = lossf(model(X, A)[nS:], y)
            loss.backward()
            opt.step()
            tot += float(loss)
        hist.append(tot / len(tensors))
    return model, hist


def score(model, inst):
    import torch
    with torch.no_grad():
        nS = len(inst["X"]) - len(inst["y"])
        return model(torch.as_tensor(inst["X"]), norm_adj(inst["edges"], len(inst["X"])))[nS:].numpy()


# ---------------------------------------------------------------- pruned exact solve
def pruned_solve(inst, s, SS, SC, CC, k0=60):
    """Exact ILP on the top-k candidates by score s, doubling k until full connectivity is reached."""
    idx = np.where(inst["keep"])[0]
    eps, t0, k = inst["eps"], time.time(), k0
    order = np.argsort(-s)
    while True:
        cand = np.sort(order[:k])
        P = exact.Placement(SS[np.ix_(idx, idx)], SC[np.ix_(idx, cand)], CC[np.ix_(cand, cand)], eps, time_limit=300)
        if P.site_pieces(np.ones(len(cand))) <= inst["target_pieces"]:
            r = P.solve("connectivity")
            if r["status"] == "optimal":
                return r["stations"], time.time() - t0, k
        if k >= len(s):
            return np.nan, time.time() - t0, k
        k = min(2 * k, len(s))


def pieces_score(inst):
    nS = len(inst["X"]) - len(inst["y"])
    return inst["X"][nS:, 2] - 0.01 * inst["X"][nS:, 3]


# ---------------------------------------------------------------- main
def main(quick=False):
    t0 = time.time()
    sites = pd.read_csv(data.DERIVED / "sites.csv")
    M = data.load_osrm_matrix()
    SS, SC, CC = data.load_road_miles(len(sites)), M["SC"], M["CC"]
    cand = pd.read_csv(data.DERIVED / "candidates_kept.csv")
    pts_s = sites[["Latitude", "Longitude"]].values
    pts_c = cand[["lat", "lon"]].values
    eps_list = [40, 50] if quick else [30, 40, 50, 60]
    n_seed = (8, 10) if quick else (60, 80)
    jobs = [(e, "none", 0) for e in eps_list]
    for e in eps_list:
        for sd in range(n_seed[1]):
            jobs.append((e, "independent" if sd % 2 == 0 else "regional", sd))
    G = (SS, SC, CC, pts_s, pts_c)
    with Pool(2, initializer=_init, initargs=(G,)) as pool:
        insts = pool.map(_solve_instance, jobs, chunksize=2)
    print(f"benchmark: {len(insts)} instances in {time.time() - t0:.0f}s")

    BENCH.mkdir(parents=True, exist_ok=True)
    meta = pd.DataFrame([{k: i[k] for k in ["eps", "kind", "seed", "stations", "status", "seconds", "target_pieces"]}
                         | {"sites_working": int(i["keep"].sum()), "positives": int(i["y"].sum())} for i in insts])
    meta.to_csv(BENCH / "instances.csv", index_label="instance")
    np.savez_compressed(BENCH / "ny_placement_benchmark.npz",
                        keep=np.array([i["keep"] for i in insts]), labels=np.array([i["y"] for i in insts]),
                        eps=meta["eps"].values, candidate_lat=pts_c[:, 0], candidate_lon=pts_c[:, 1],
                        site_lat=pts_s[:, 0], site_lon=pts_s[:, 1])

    split = n_seed[0]
    tr_seed = [i for i in insts if i["seed"] < split and i["kind"] != "none"]
    te_seed = [i for i in insts if i["seed"] >= split or i["kind"] == "none"]
    tr_eps = [i for i in insts if i["eps"] != 50 and i["seed"] < split]
    te_eps = [i for i in insts if i["eps"] == 50]

    rows, curves = [], {}
    for split_name, tr, te in [("held-out scenarios", tr_seed, te_seed), ("held-out eps 50", tr_eps, te_eps)]:
        model, hist = train(tr, epochs=20 if quick else 60)
        curves[split_name] = hist
        rng = np.random.default_rng(0)
        for inst in te:
            s_gnn = score(model, inst)
            for method, s in [("GNN pruning + ILP", s_gnn), ("pieces-score pruning + ILP", pieces_score(inst)),
                              ("random pruning + ILP", rng.random(len(inst["y"])))]:
                st, sec, k = pruned_solve(inst, s, SS, SC, CC)
                # recall of the optimal set within the top-|opt| scores
                m = int(inst["y"].sum())
                rec = float(inst["y"][np.argsort(-s)[:max(m, 1)]].sum() / max(m, 1))
                rows.append(dict(split=split_name, eps=inst["eps"], kind=inst["kind"], seed=inst["seed"], method=method,
                                 stations=st, optimum=inst["stations"], gap=st - inst["stations"], seconds=sec,
                                 exact_seconds=inst["seconds"], candidates_kept=k, recall_at_opt=rec))
    res = pd.DataFrame(rows)
    res.to_csv(TAB / "learning_results.csv", index=False)
    summ = (res.groupby(["split", "method"])
               .agg(instances=("gap", "size"), optimal_share=("gap", lambda g: float((g == 0).mean())),
                    mean_gap=("gap", "mean"), max_gap=("gap", "max"), recall_at_opt=("recall_at_opt", "mean"),
                    mean_seconds=("seconds", "mean"), exact_seconds=("exact_seconds", "mean"),
                    candidates_kept=("candidates_kept", "median")).reset_index())
    summ["speedup"] = summ["exact_seconds"] / summ["mean_seconds"]
    summ.to_csv(TAB / "learning_summary.csv", index=False)
    print(summ.to_string())

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 2, figsize=(10, 3.8))
    for (name, h), c in zip(curves.items(), ["#2a6fdb", "#e07b39"]):
        ax[0].plot(h, color=c, lw=2, label=name)
    ax[0].set(xlabel="epoch", ylabel="training loss", title="GNN training")
    ax[0].legend(frameon=False)
    s = summ[summ.split == "held-out scenarios"]
    ax[1].barh(s["method"], s["recall_at_opt"], color="#2a6fdb", height=0.5)
    for y, (r, sp) in enumerate(zip(s["recall_at_opt"], s["speedup"])):
        ax[1].text(r + 0.01, y, f"{r:.2f}  (x{sp:.1f} faster)", va="center", fontsize=9)
    ax[1].set(xlim=(0, 1.15), xlabel="share of optimal sites in the top-|opt| scores",
              title="Held-out failure scenarios")
    for a in ax:
        a.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(FIG / "fig13_learning.png", dpi=200)
    json.dump({"instances": len(insts), "summary": summ.to_dict("records"), "minutes": (time.time() - t0) / 60},
              open(ROOT / "results" / "learning_summary.json", "w"), indent=1, default=float)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    main(ap.parse_args().quick)
