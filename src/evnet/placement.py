"""Q3: how many new fast-charging stations does a spacing standard need?

New stations may only be placed at existing public Level 1 / Level 2 locations
(candidates). For a standard eps the question is a node-weighted Steiner tree
problem: each existing piece of the network (or each city) is a terminal, each
candidate costs one station, and two nodes are linked when they are at most eps
miles apart. The problem is NP-hard, so we use the shortest-path heuristic of
Takahashi & Matsuyama (1980): start from the largest piece, repeatedly join the
terminal that is cheapest to reach (fewest new stations), then drop any added
station that turns out to be redundant.

Two objectives:
- "network": every existing site ends up in one connected network (the
  proposal's definition: the standard is met everywhere on the network).
- "coverage": every pair of cities with >= 5000 people is connected (city-pair
  coverage = 1). Cities are leaves: a city can attach to the network but a
  driver cannot recharge there, so a city never relays between pieces.

Bounds reported for each standard:
- upper: number of stations the heuristic adds (feasible, so an upper bound);
- lower ("network" only): the largest number of stations needed to reach any
  single piece from the largest piece. Every feasible plan must contain such a
  path, so no plan can use fewer.
- feasible: False when some terminal cannot be reached even if every candidate
  location were upgraded.
"""
import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import connected_components, dijkstra

from .network import build_graph

TINY = 1e-6  # weight for zero-cost moves (scipy drops explicit zero entries)


def _assemble(site_dist, K, KK, eps, CS=None, CK=None, access=None):
    """Directed graph over [pieces | candidates | cities]; edge weight = cost of target."""
    g = build_graph(site_dist, eps)
    memb = np.array(g.connected_components().membership)
    P, nc = memb.max() + 1, K.shape[0]
    rows, cols = [], []

    # piece <-> candidate
    ci, sj = np.where(K <= eps)
    pc = np.unique(np.column_stack([memb[sj], ci]), axis=0)
    rows += [pc[:, 0], P + pc[:, 1]]
    cols += [P + pc[:, 1], pc[:, 0]]
    # candidate <-> candidate
    a, b = np.where(np.triu(KK <= eps, 1))
    rows += [P + a, P + b]
    cols += [P + b, P + a]

    ncity = 0
    if CS is not None:
        acc = eps if access is None else min(access, eps)
        ncity = CS.shape[0]
        base = P + nc
        ti, sj = np.where(CS <= acc)
        tp = np.unique(np.column_stack([ti, memb[sj]]), axis=0)
        rows.append(tp[:, 1])            # piece -> city only (city is a leaf)
        cols.append(base + tp[:, 0])
        ti, cj = np.where(CK <= acc)
        rows.append(P + cj)
        cols.append(base + ti)

    rows, cols = np.concatenate(rows), np.concatenate(cols)
    N = P + nc + ncity
    cost = np.zeros(N)
    cost[P:P + nc] = 1.0
    w = cost[cols] + TINY
    A = csr_matrix((w, (rows, cols)), shape=(N, N))
    A.sum_duplicates()
    A.data[:] = cost[A.indices] + TINY  # duplicates must not add up
    return A, memb, P, nc, ncity


def _connected(A, P, nc, ncity, chosen, terminals):
    """Do pieces + chosen candidates connect every terminal into one part?"""
    keep = np.zeros(A.shape[0], bool)
    keep[:P] = True
    keep[P + np.asarray(chosen, int)] = True
    if ncity:
        keep[P + nc:] = True
    sub = A[keep][:, keep]
    idx = -np.ones(A.shape[0], int)
    idx[keep] = np.arange(keep.sum())
    # cities are leaves; they are connected iff their neighbour is
    if ncity:
        # weak components would let a city join two pieces; check pieces/cands only
        relay = keep.copy()
        relay[P + nc:] = False
        sub2 = A[relay][:, relay]
        _, lab2 = connected_components(sub2, directed=False)
        full = -np.ones(A.shape[0], int)
        full[relay] = lab2
        city_parts = []
        for t in terminals:
            nb = A[:, t].nonzero()[0]
            nb = nb[relay[nb]]
            if len(nb) == 0:
                return False
            city_parts.append(set(full[nb]))
        common = set.intersection(*city_parts)
        return len(common) > 0
    _, lab = connected_components(sub, directed=True, connection="weak")
    return len(set(lab[idx[terminals]])) == 1


def place_stations(site_dist, site_pop_piece_root, K, KK, eps, objective="network",
                   CS=None, CK=None, pop=None, access=None):
    """Run the heuristic for one standard. Returns a dict with bounds and choices."""
    if objective == "coverage":
        A, memb, P, nc, ncity = _assemble(site_dist, K, KK, eps, CS, CK, access)
        terminals = np.arange(P + nc, P + nc + ncity)
        # root: the piece holding the most population-weighted attachments (NYC)
        acc = eps if access is None else min(access, eps)
        big_city = int(np.argmax(pop))
        near = np.where(CS[big_city] <= acc)[0]
        root = int(np.bincount(memb[near]).argmax()) if len(near) else int(np.bincount(memb).argmax())
    else:
        A, memb, P, nc, ncity = _assemble(site_dist, K, KK, eps)
        terminals = np.arange(P)
        root = int(np.bincount(memb).argmax())

    in_tree = np.zeros(A.shape[0], bool)
    in_tree[root] = True
    chosen = []
    lower = 0
    first = True
    while True:
        todo = terminals[~in_tree[terminals]]
        if len(todo) == 0:
            break
        src = np.where(in_tree)[0]
        dist, pred, srcs = dijkstra(A, indices=src, min_only=True, return_predecessors=True)
        reach = np.round(dist[todo] - 0.0, 6)
        if first:
            finite = reach[np.isfinite(reach)]
            lower = int(np.floor(finite.max() + 1e-3)) if len(finite) else 0
            first = False
        if not np.isfinite(reach).any():
            break
        t = int(todo[np.argmin(reach)])
        v = t
        while not in_tree[v]:
            in_tree[v] = True
            if P <= v < P + nc:
                chosen.append(v - P)
            v = pred[v]
    feasible = bool(in_tree[terminals].all())

    # prune redundant stations (latest first)
    if feasible:
        for c in list(reversed(chosen)):
            trial = [x for x in chosen if x != c]
            if _connected(A, P, nc, ncity, trial, terminals):
                chosen = trial

    return {"miles": eps, "objective": objective, "pieces": int(P),
            "upper": len(chosen), "lower": lower if objective == "network" else np.nan,
            "feasible": feasible, "chosen": chosen,
            "unreached": [int(x) for x in terminals[~in_tree[terminals]]],
            "unreached_sites": ([int(i) for i in np.where(np.isin(memb, terminals[~in_tree[terminals]]))[0]]
                                if objective == "network" else []),
            "unreached_cities": ([int(t - P - nc) for t in terminals[~in_tree[terminals]]]
                                 if objective == "coverage" else [])}


def cost_curve(site_dist, K, KK, eps_values, objective="network", **kw):
    return [place_stations(site_dist, None, K, KK, eps, objective, **kw) for eps in eps_values]
