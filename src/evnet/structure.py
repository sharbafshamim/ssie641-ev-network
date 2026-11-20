"""Network-structure measures used in the extended Q1/Q2 analysis.

Biconnectivity threshold, reliability of the single points of failure, global
efficiency and harmonic centrality, population-weighted city-pair betweenness,
k-cores, random-walk spectral gap and spectral bisection, Leiden communities,
and the centralities compared in the discussion.
"""
import heapq
import random

import igraph as ig
import numpy as np
import pandas as pd

from .network import build_graph


# ------------------------------------------------------------------ thresholds
def is_biconnected(g):
    """Connected and without a single point of failure (cut vertex)."""
    return g.vcount() > 2 and g.is_connected() and len(g.articulation_points()) == 0


def biconnectivity_threshold(dist, upper=60.0):
    """Smallest eps at which the eps-graph is connected and has no cut vertex.

    Once a graph is connected, adding links can only remove cut vertices, so the
    property is monotone in eps and we can bisect over the distinct link lengths.
    Returns (threshold, cut vertices just below it).
    """
    iu = np.triu_indices(len(dist), 1)
    cand = np.unique(dist[iu][dist[iu] <= upper])
    lo, hi = 0, len(cand) - 1
    if not is_biconnected(build_graph(dist, cand[hi])):
        return np.nan, []
    while lo < hi:
        mid = (lo + hi) // 2
        if is_biconnected(build_graph(dist, cand[mid])):
            hi = mid
        else:
            lo = mid + 1
    below = build_graph(dist, cand[lo - 1]) if lo > 0 else None
    return float(cand[lo]), (below.articulation_points() if below is not None else [])


# ------------------------------------------------------------------ reliability
def prob_any_down(k, p):
    """Chance that at least one of k sites is down when each is down independently with probability p."""
    return 1 - (1 - p) ** k


def split_probability(g, p, trials, rng):
    """Monte Carlo, each site failing independently with probability p.

    Returns the chance that failures split at least one piece of the intact network
    (some surviving sites lose their connection to the rest of their own piece), and
    the mean share of surviving sites cut off from the largest remnant of their piece.
    Pieces that are already separate in the intact network do not count.
    """
    n = g.vcount()
    base = np.array(g.connected_components().membership)
    split, cutoff = 0, []
    for _ in range(trials):
        keep = np.where(rng.random(n) >= p)[0]
        h = g.induced_subgraph(keep.tolist())
        memb = np.array(h.connected_components().membership)
        lost = 0
        for piece in np.unique(base[keep]):
            m = memb[base[keep] == piece]
            lost += len(m) - np.bincount(m).max()
        split += lost > 0
        cutoff.append(lost / len(keep) if len(keep) else 0)
    return split / trials, float(np.mean(cutoff))


# ------------------------------------------------------------------ efficiency and harmonic
def global_efficiency(g, n=None, weights=None):
    """Mean of 1/d over ordered pairs (Latora-Marchiori). Unreachable pairs add 0.

    n: denominator size (default: current vertex count). Using the original n keeps
    curves under node removal comparable, as in Hamim et al. (2025).
    """
    m = g.vcount()
    if m < 2:
        return 0.0
    n = m if n is None else n
    d = np.array(g.distances(weights=weights), dtype=float)
    np.fill_diagonal(d, np.inf)
    return float((1.0 / d).sum() / (n * (n - 1)))


def harmonic(g, weights=None):
    """Harmonic centrality, normalised by n - 1."""
    return np.array(g.harmonic_centrality(weights=weights, normalized=True))


def efficiency_under_removal(g, order, fractions):
    """Relative global efficiency E(f)/E(0) after removing the first f*n sites of `order`."""
    n = g.vcount()
    e0 = global_efficiency(g)
    out = []
    for f in fractions:
        k = int(round(f * n))
        keep = np.setdiff1d(np.arange(n), order[:k])
        out.append(global_efficiency(g.induced_subgraph(keep.tolist()), n) / e0)
    return np.array(out)


def adaptive_order(g, criterion, steps):
    """Removal order of an adaptive attack (top site removed, scores recomputed)."""
    h = g.copy()
    h.vs["site"] = list(range(h.vcount()))
    order = []
    for _ in range(steps):
        if criterion == "degree":
            score = h.degree()
        elif criterion == "betweenness":
            score = h.betweenness()
        elif criterion == "harmonic":
            score = h.harmonic_centrality()
        else:
            raise ValueError(criterion)
        v = int(np.argmax(score))
        order.append(h.vs[v]["site"])
        h.delete_vertices([v])
    return np.array(order)


def random_order_efficiency(g, fractions, trials, rng):
    n = g.vcount()
    return np.mean([efficiency_under_removal(g, rng.permutation(n), fractions) for _ in range(trials)], axis=0)


# ------------------------------------------------------------------ city-pair betweenness
def city_pair_betweenness(site_dist, city_site_dist, eps, pop):
    """Betweenness of each site over city-to-city trips, by road miles.

    Graph: sites linked when within eps; each city linked to the sites within eps
    of its centre (as in the coverage measure). Cities are end points only: a
    route cannot pass through a city. For every pair of cities that can reach each
    other, one unit of flow (unweighted) or P_a * P_b (population-weighted) is split
    over the shortest routes, as in Brandes (2008) with pair weights.

    Returns two arrays (unweighted, weighted), each the share of the total flow of
    connected city pairs that passes through the site.
    """
    n, m = len(site_dist), len(city_site_dist)
    adj = [[] for _ in range(n + m)]
    i, j = np.where(np.triu(site_dist <= eps, 1))
    for a, b, w in zip(i, j, site_dist[i, j]):
        adj[a].append((b, w))
        adj[b].append((a, w))
    ci, si = np.where(city_site_dist <= eps)
    for c, s, w in zip(ci, si, city_site_dist[ci, si]):
        adj[n + c].append((s, w))
        adj[s].append((n + c, w))
    W = np.vstack([np.ones(m), np.asarray(pop, float)]).T          # m x 2 pair weights
    bc = np.zeros((n, 2))
    total = np.zeros(2)
    tol = 1e-9
    for src in range(m):
        s = n + src
        dist = {s: 0.0}
        sigma = {s: 1.0}
        pred = {s: []}
        order = []
        heap = [(0.0, s)]
        done = set()
        while heap:
            d, v = heapq.heappop(heap)
            if v in done:
                continue
            done.add(v)
            order.append(v)
            if v >= n and v != s:            # a destination city: do not route through it
                continue
            for w, lw in adj[v]:
                nd = d + lw
                if w not in dist or nd < dist[w] - tol:
                    dist[w] = nd
                    sigma[w] = sigma[v]
                    pred[w] = [v]
                    heapq.heappush(heap, (nd, w))
                elif abs(nd - dist[w]) <= tol and w not in done:
                    sigma[w] += sigma[v]
                    pred[w].append(v)
        delta = {v: np.zeros(2) for v in order}
        for w in reversed(order):
            tw = W[w - n] if (w >= n and w != s) else 0.0
            if w >= n and w != s:
                total += W[src] * W[w - n]
            for v in pred[w]:
                delta[v] += sigma[v] / sigma[w] * (tw + delta[w])
            if w < n:
                bc[w] += W[src] * delta[w]
    total = np.where(total > 0, total, 1)
    return bc[:, 0] / total[0], bc[:, 1] / total[1]


# ------------------------------------------------------------------ spectral
def random_walk_spectrum(g):
    """Second eigenvalue of the random-walk matrix P = D^-1 A on the largest piece.

    Returns (lambda2, relaxation time 1/(1 - lambda2), vertex ids of the piece,
    second eigenvector of P on those vertices: its sign gives the spectral split).
    """
    cc = g.connected_components()
    ids = np.array(sorted(cc[int(np.argmax(cc.sizes()))]))
    comp = g.induced_subgraph(ids.tolist())
    A = np.array(comp.get_adjacency().data, dtype=float)
    k = A.sum(1)
    Dm = 1 / np.sqrt(k)
    Nrm = Dm[:, None] * A * Dm[None, :]
    vals, vecs = np.linalg.eigh(Nrm)
    lam2 = float(vals[-2])
    psi2 = Dm * vecs[:, -2]                  # right eigenvector of P
    return lam2, 1 / (1 - lam2), ids, psi2


def spectral_split(g, ids, psi2):
    """Split the piece by the sign of the second eigenvector; return cut size, normalised cut
    and the sites at the seam (endpoints of the cut links)."""
    side = dict(zip(ids.tolist(), (psi2 > 0).tolist()))
    sub = g.induced_subgraph(ids.tolist())
    sidearr = np.array([side[v] for v in ids])
    cut = [(ids[e.source], ids[e.target]) for e in sub.es if sidearr[e.source] != sidearr[e.target]]
    deg = np.array(sub.degree())
    vol1, vol2 = deg[sidearr].sum(), deg[~sidearr].sum()
    ncut = len(cut) / vol1 + len(cut) / vol2 if vol1 and vol2 else np.nan
    seam = sorted(set([a for a, _ in cut] + [b for _, b in cut]))
    return {"cut_links": len(cut), "ncut": float(ncut), "side_sizes": (int(sidearr.sum()), int((~sidearr).sum())),
            "seam_sites": seam, "side": sidearr}


# ------------------------------------------------------------------ communities
def leiden_best(g, resolution=1.0, seeds=10):
    """Best-modularity Leiden partition over several seeds."""
    best = None
    for s in range(seeds):
        random.seed(s)
        part = g.community_leiden(objective_function="modularity", resolution=resolution, n_iterations=-1)
        q = g.modularity(part.membership, resolution=resolution)
        if best is None or q > best[0]:
            best = (q, np.array(part.membership))
    q1 = g.modularity(best[1])                 # report standard modularity (resolution 1)
    return q1, best[1]


def community_boundaries(g, membership):
    """Per community: size, conductance (links leaving / volume), and the boundary sites
    (sites with at least one neighbour in another community)."""
    deg = np.array(g.degree())
    rows, boundary = [], set()
    out_links = np.zeros(membership.max() + 1)
    for e in g.es:
        a, b = membership[e.source], membership[e.target]
        if a != b:
            out_links[a] += 1
            out_links[b] += 1
            boundary.update([e.source, e.target])
    for c in range(membership.max() + 1):
        vol = deg[membership == c].sum()
        rows.append([c, int((membership == c).sum()), out_links[c] / vol if vol else np.nan])
    return pd.DataFrame(rows, columns=["community", "sites", "conductance"]), sorted(boundary)


# ------------------------------------------------------------------ centralities
def centrality_scores(g, weights=None):
    """Degree, harmonic, betweenness, eigenvector, PageRank and k-core number for every site."""
    return pd.DataFrame({
        "degree": g.degree(),
        "core": g.coreness(),
        "harmonic": harmonic(g),
        "betweenness": g.betweenness(weights=weights),
        "eigenvector": g.eigenvector_centrality(scale=True),
        "pagerank": g.pagerank(),
    })


def neighbour_degree_gap(g):
    """Friendship paradox: mean degree of sites against mean degree of their neighbours."""
    deg = np.array(g.degree(), float)
    nb = [deg[g.neighbors(v)].mean() for v in range(g.vcount()) if deg[v] > 0]
    return float(deg.mean()), float(np.mean(nb))


def ccdf(values):
    """Points (x, P(X >= x)) of the complementary cumulative distribution."""
    x = np.sort(np.asarray(values, float))
    u, idx = np.unique(x, return_index=True)
    return u, 1 - idx / len(x)
