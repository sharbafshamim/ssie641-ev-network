"""City-pair coverage: can people in one city reach another city?

A city is attached to every charging site within `access` miles of its centre
(default: the spacing standard eps, i.e. a driver who leaves home with a full
battery of usable range eps). Two cities are connected when a site attached to
one and a site attached to the other are in the same piece of the network.
"""
import numpy as np

from .network import build_graph


def coverage(g, C, eps, pop, access=None, exclude=None):
    """Return (unweighted, population-weighted) coverage.

    C: cities x sites distance matrix. exclude: optional boolean mask of cities
    whose population weight is set to zero (they still count in the unweighted share).
    """
    a = eps if access is None else min(access, eps)
    membership = np.array(g.connected_components().membership)
    M = np.zeros((len(C), membership.max() + 1 if len(membership) else 1))
    i, j = np.where(C <= a)
    M[i, membership[j]] = 1
    reach = (M @ M.T) > 0
    np.fill_diagonal(reach, False)
    n = len(pop)
    w = np.outer(pop, pop).astype(float)
    if exclude is not None:
        w[exclude, :] = 0
        w[:, exclude] = 0
    np.fill_diagonal(w, 0)
    return reach.sum() / (n * (n - 1)), (w * reach).sum() / w.sum()


def coverage_after(dist, C, eps, pop, failed, access=None):
    keep = np.setdiff1d(np.arange(len(dist)), failed)
    g = build_graph(dist[np.ix_(keep, keep)], eps)
    return coverage(g, C[:, keep], eps, pop, access)


def random_failure_coverage(dist, C, eps, pop, p_values, trials, seed):
    rng = np.random.default_rng(seed)
    n = len(dist)
    out = []
    for p in p_values:
        us, ws = [], []
        for _ in range(trials):
            u, w = coverage_after(dist, C, eps, pop, np.where(rng.random(n) < p)[0])
            us.append(u)
            ws.append(w)
        out.append([p, np.mean(us), np.mean(ws)])
    return np.array(out)


def attack_coverage(dist, C, eps, pop, removed):
    out = []
    for k in range(len(removed) + 1):
        out.append(coverage_after(dist, C, eps, pop, removed[:k]))
    return np.array(out)
