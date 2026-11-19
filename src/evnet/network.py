"""Epsilon-neighbourhood network, percolation, cut vertices, failure and attack."""
import igraph as ig
import numpy as np
import pandas as pd
from scipy.sparse.csgraph import minimum_spanning_tree


def build_graph(dist, eps):
    """Link two sites when their distance is at most eps miles."""
    i, j = np.where(np.triu(dist <= eps, 1))
    return ig.Graph(n=len(dist), edges=list(zip(i.tolist(), j.tolist())))


def largest_share(g, n=None):
    """Size of the largest connected piece divided by n (default: vertex count)."""
    if g.vcount() == 0:
        return 0.0
    n = g.vcount() if n is None else n
    return max(g.connected_components().sizes()) / n


def mst_links(dist, labels):
    """All MST links, longest first. The first row is the connectivity threshold."""
    d = dist.copy().astype(float)
    d[d == 0] = 1e-9  # scipy treats 0 as "no edge"; duplicate points stay linked
    np.fill_diagonal(d, 0)
    mst = minimum_spanning_tree(np.triu(d)).tocoo()
    links = pd.DataFrame({"miles": mst.data, "from_id": mst.row, "to_id": mst.col})
    links["from"] = labels[links["from_id"]].values
    links["to"] = labels[links["to_id"]].values
    return links.sort_values("miles", ascending=False).reset_index(drop=True)


def percolation(dist, eps_values):
    rows = []
    for eps in eps_values:
        g = build_graph(dist, eps)
        rows.append([eps, len(g.connected_components()), largest_share(g),
                     len(g.articulation_points())])
    return pd.DataFrame(rows, columns=["miles", "pieces", "largest_share", "cut_vertices"])


def critical_sites(g, table):
    """Articulation points with the number of sites each one cuts off.

    sites_cut_off = sites of its piece that are no longer in the biggest
    remaining part once the site is removed.
    """
    membership = np.array(g.connected_components().membership)
    deg = np.array(g.degree())
    rows = []
    for v in g.articulation_points():
        piece = np.where((membership == membership[v]) & (np.arange(g.vcount()) != v))[0]
        h = g.copy()
        h.delete_edges(h.incident(v))
        new = np.array(h.connected_components().membership)[piece]
        lost = len(piece) - np.bincount(new).max()
        rows.append([v, table["name"].iloc[v], table["city"].iloc[v], table["network"].iloc[v],
                     int(deg[v]), int(table["ports"].iloc[v]), int(lost),
                     float((deg < deg[v]).mean()),
                     float((table["ports"].values < table["ports"].iloc[v]).mean())])
    cols = ["id", "name", "city", "operator", "degree", "ports", "sites_cut_off",
            "degree_percentile", "ports_percentile"]
    return pd.DataFrame(rows, columns=cols).sort_values("sites_cut_off", ascending=False).reset_index(drop=True)


def random_failure(dist, eps, p_values, trials, seed):
    """Each site fails independently with probability p.

    Returns mean largest-piece share of all n sites (upper bound 1-p) and of the
    surviving sites (upper bound 1).
    """
    rng = np.random.default_rng(seed)
    g = build_graph(dist, eps)
    n = g.vcount()
    rows = []
    for p in p_values:
        all_n, surv = [], []
        for _ in range(trials):
            failed = np.where(rng.random(n) < p)[0]
            h = g.copy()
            h.delete_vertices(failed)
            all_n.append(largest_share(h, n))
            surv.append(largest_share(h))
        rows.append([p, np.mean(all_n), np.mean(surv)])
    return pd.DataFrame(rows, columns=["p", "largest_share_of_all", "largest_share_of_survivors"])


def targeted_attack(g, steps, criterion):
    """Adaptive attack: remove the top-scoring site, recompute, repeat."""
    h = g.copy()
    h.vs["site"] = list(range(h.vcount()))
    n = g.vcount()
    curve, removed = [largest_share(h, n)], []
    for _ in range(steps):
        score = h.degree() if criterion == "degree" else h.betweenness()
        v = int(np.argmax(score))
        removed.append(h.vs[v]["site"])
        h.delete_vertices([v])
        curve.append(largest_share(h, n))
    return np.array(curve), removed
