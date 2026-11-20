"""Exact station placement by integer programming with lazy vertex-separator cuts.

Graph: existing sites S (always present) and candidate locations C (binary x_c = 1 if a
fast charger is added at c). Two nodes are linked when they are at most eps miles apart.
G_all is the graph with every candidate built; G(x) is the graph induced by S and the chosen
candidates.

Connectivity ("cost of connectivity"): minimise sum x_c such that every pair of sites that is
connected in G_all is connected in G(x). Sites that are cut off even in G_all cannot be helped
and are reported as unreachable.

Robustness ("cost of robustness"): additionally, no single node failure may separate two sites
that G_all keeps connected after that failure. In graph terms G(x) must be as 2-vertex-connected
over the sites as G_all allows: for every node v of G(x) and every pair of sites s, t != v,
if s and t are connected in G_all - v they must be connected in G(x) - v. Sites that only hang
on one neighbour even in G_all (dead ends with no candidate nearby) cannot be protected and are
reported.

Both are solved exactly by the classical cut formulation for node-weighted connectivity
problems: start with no constraints, solve, find a violated separation, and add the cut
"at least one candidate in the vertex boundary of the offending component is built"
(conditional on x_v for a candidate v in the robustness case). Each cut is valid because any
path out of the component must pass through its boundary. The loop stops when the solution
has no violation, so the final solution is optimal for the full (exponential) formulation.
MILPs are solved with HiGHS through scipy.optimize.milp.
"""
import time

import igraph as ig
import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import csr_matrix, lil_matrix
from scipy.sparse.csgraph import connected_components


def build_full_graph(SS, SC, CC, eps):
    """Adjacency (csr, bool) over [sites | candidates] with links at distance <= eps."""
    nS, nC = SC.shape
    A = lil_matrix((nS + nC, nS + nC), dtype=bool)
    i, j = np.where(np.triu(SS <= eps, 1))
    A[i, j] = True
    i, j = np.where(SC <= eps)
    A[i, nS + j] = True
    i, j = np.where(np.triu(CC <= eps, 1))
    A[nS + i, nS + j] = True
    A = A.tocsr()
    return (A + A.T).astype(bool).tocsr()


def _components(A, keep):
    """Component labels of the subgraph induced by boolean mask `keep` (-1 elsewhere)."""
    idx = np.where(keep)[0]
    lab = -np.ones(A.shape[0], int)
    if len(idx) == 0:
        return lab
    _, l = connected_components(A[idx][:, idx], directed=False)
    lab[idx] = l
    return lab


class Placement:
    def __init__(self, SS, SC, CC, eps, time_limit=600):
        self.nS, self.nC = SC.shape
        self.N = self.nS + self.nC
        self.eps = eps
        self.A = build_full_graph(SS, SC, CC, eps)
        self.time_limit = time_limit
        self.all_lab = _components(self.A, np.ones(self.N, bool))
        self._all_minus = {}

    # ---------------------------------------------------------------- helpers
    def _present(self, x):
        keep = np.zeros(self.N, bool)
        keep[:self.nS] = True
        keep[self.nS:] = x > 0.5
        return keep

    def _boundary(self, comp_mask, exclude=None):
        """Candidate indices adjacent to the node set comp_mask (excluding `exclude`)."""
        nb = np.unique(self.A[np.where(comp_mask)[0]].indices)
        nb = nb[~comp_mask[nb]]
        if exclude is not None:
            nb = nb[nb != exclude]
        return nb[nb >= self.nS] - self.nS

    def _all_lab_minus(self, v):
        if v not in self._all_minus:
            keep = np.ones(self.N, bool)
            keep[v] = False
            self._all_minus[v] = _components(self.A, keep)
        return self._all_minus[v]

    # ---------------------------------------------------------------- separation
    def connectivity_cuts(self, x):
        keep = self._present(x)
        lab = _components(self.A, keep)
        cuts = []
        site_lab, site_all = lab[:self.nS], self.all_lab[:self.nS]
        for g in np.unique(site_all):
            sites = np.where(site_all == g)[0]
            comps = np.unique(site_lab[sites])
            if len(comps) <= 1:
                continue
            for c in comps:
                C = lab == c
                cuts.append((self._boundary(C), None))
        return cuts

    def robustness_cuts(self, x, max_vertices=None):
        keep = self._present(x)
        idx = np.where(keep)[0]
        sub = self.A[idx][:, idx]
        r, c = sub.nonzero()
        g = ig.Graph(n=len(idx), edges=list(zip(r[r < c].tolist(), c[r < c].tolist())))
        aps = [int(idx[a]) for a in g.articulation_points()]
        cuts = []
        for v in aps[:max_vertices] if max_vertices else aps:
            k2 = keep.copy()
            k2[v] = False
            lab = _components(self.A, k2)
            alab = self._all_lab_minus(v)
            sites = np.array([s for s in range(self.nS) if s != v])
            for ga in np.unique(alab[sites]):
                ss = sites[alab[sites] == ga]
                comps = np.unique(lab[ss])
                if len(comps) <= 1:
                    continue
                for cc in comps:
                    C = lab == cc
                    cond = None if v < self.nS else v - self.nS
                    cuts.append((self._boundary(C, exclude=v), cond))
        return cuts

    def unprotectable(self):
        """Sites that some single failure separates even with every candidate built."""
        g = ig.Graph(n=self.N, edges=[(int(a), int(b)) for a, b in zip(*self.A.nonzero()) if a < b])
        bad = set()
        for v in g.articulation_points():
            alab = self._all_lab_minus(v)
            sites = np.array([s for s in range(self.nS) if s != v])
            labs = alab[sites]
            # sites in G_all components of size smaller than the biggest site-holding component
            groups, counts = np.unique(labs, return_counts=True)
            if len(groups) > len(np.unique(self.all_lab[sites])):
                main = groups[np.argmax(counts)]
                bad.update(sites[(labs != main) & (self.all_lab[sites] == self.all_lab[sites][labs == main][0])].tolist())
        return sorted(bad)

    # ---------------------------------------------------------------- solve
    def _violations(self, x, objective):
        cuts = self.connectivity_cuts(x)
        if objective == "robustness" and not cuts:
            cuts = self.robustness_cuts(x)
        return [(b, c) for b, c in cuts if len(b) > 0]

    def _steiner(self, x):
        """Shortest-path (node-weighted) completion of x to a connectivity-feasible solution.

        Repeatedly joins the site component nearest (in new stations) to the root component of each
        G_all component, adding the candidates on the cheapest path. Always feasible, usually close.
        """
        from scipy.sparse.csgraph import dijkstra
        x = x.copy()
        site_all = self.all_lab[:self.nS]
        for g in np.unique(site_all):
            sites = np.where(site_all == g)[0]
            while True:
                lab = _components(self.A, self._present(x))
                comps = lab[sites]
                if len(np.unique(comps)) <= 1:
                    break
                root = lab == np.bincount(comps).argmax()
                cost = np.where(self._present(x), 1e-6, 1.0)          # entering a new candidate costs 1
                W = self.A.multiply(cost[None, :]).tocsr()
                W.data = np.maximum(W.data, 1e-6)
                dist, pred, _ = dijkstra(W, directed=True, indices=np.where(root)[0], min_only=True,
                                      return_predecessors=True)
                others = sites[~root[sites]]
                t = int(others[np.argmin(dist[others])])
                v = t
                while v >= 0 and not root[v]:
                    if v >= self.nS:
                        x[v - self.nS] = 1
                    v = pred[v]
        return x

    def _repair(self, x, objective, pool):
        """Repair x to a feasible solution, adding every cut met on the way to `pool`; None if it fails."""
        x = self._steiner(x)
        for _ in range(self.nC):
            cuts = self._violations(x, objective)
            if not cuts:
                return x
            for cut in cuts:
                pool.add(cut)
            score = np.zeros(self.nC)
            for b, cond in cuts:
                if cond is None or x[cond] > 0.5:
                    score[b] += 1
            score[x > 0.5] = -1
            if score.max() <= 0:
                return None
            x[int(np.argmax(score))] = 1
            x = self._steiner(x)
        return None

    def _prune(self, x, objective):
        """Drop chosen candidates one at a time while the solution stays feasible."""
        for c in np.where(x > 0.5)[0][::-1]:
            x[c] = 0
            if self._violations(x, objective):
                x[c] = 1
        return x

    def solve(self, objective="connectivity", verbose=False, max_iter=2000):
        t0 = time.time()
        pool = _CutPool(self.nC)
        x = np.zeros(self.nC)
        best_ub, best_x = np.inf, None
        it, lb, status = 0, 0, "optimal"
        while True:
            cuts = self._violations(x, objective)
            if not cuts:
                best_x, best_ub = x, x.sum()
                break
            for cut in cuts:
                pool.add(cut)
            xr = self._repair(x, objective, pool)
            if xr is not None:
                xr = self._prune(xr, objective)
                if xr.sum() < best_ub:
                    best_ub, best_x = xr.sum(), xr
            it += 1
            res = milp(c=np.ones(self.nC), integrality=np.ones(self.nC), bounds=Bounds(0, 1),
                       constraints=LinearConstraint(pool.matrix(), lb=pool.rhs(), ub=np.inf),
                       options={"time_limit": max(10, self.time_limit - (time.time() - t0)), "disp": False})
            if res.x is None:
                status = "failed"
                break
            x = np.round(res.x)
            lb = max(lb, int(round(res.fun)))
            if verbose:
                print(f"  iter {it}: {pool.n} cuts, lb {lb}, ub {int(best_ub)}, {time.time() - t0:.1f}s")
            if lb >= best_ub:
                break
            if it >= max_iter or time.time() - t0 > self.time_limit:
                status = "time_limit"
                break
        if best_x is None:                      # no feasible solution found in time
            return {"eps": self.eps, "objective": objective, "stations": None, "chosen": [], "lower_bound": int(lb),
                    "iterations": it, "cuts": pool.n, "status": "no_feasible", "seconds": round(time.time() - t0, 1)}
        chosen = np.where(best_x > 0.5)[0]
        return {"eps": self.eps, "objective": objective, "stations": int(len(chosen)), "chosen": chosen.tolist(),
                "lower_bound": int(lb) if status != "optimal" else int(len(chosen)),
                "iterations": it, "cuts": pool.n, "status": status, "seconds": round(time.time() - t0, 1)}

    def site_pieces(self, x=None):
        keep = self._present(np.zeros(self.nC) if x is None else x)
        return len(np.unique(_components(self.A, keep)[:self.nS]))

    def unreachable_sites(self):
        """Sites not in the G_all component that holds the most sites."""
        lab = self.all_lab[:self.nS]
        vals, counts = np.unique(lab, return_counts=True)
        return np.where(lab != vals[np.argmax(counts)])[0].tolist()


class _CutPool:
    """De-duplicated sparse store of cuts sum_{b} x_b - [x_cond] >= rhs."""

    def __init__(self, nC):
        self.nC, self.rows, self.cols, self.vals, self.rhs_, self.keys = nC, [], [], [], [], set()
        self.n = 0

    def add(self, cut):
        b, cond = cut
        key = (tuple(sorted(int(v) for v in b)), cond)
        if key in self.keys:
            return
        self.keys.add(key)
        for v in b:
            self.rows.append(self.n)
            self.cols.append(int(v))
            self.vals.append(1.0)
        if cond is not None:
            self.rows.append(self.n)
            self.cols.append(int(cond))
            self.vals.append(-1.0)
        self.rhs_.append(0.0 if cond is not None else 1.0)
        self.n += 1

    def matrix(self):
        return csr_matrix((self.vals, (self.rows, self.cols)), shape=(self.n, self.nC))

    def rhs(self):
        return np.array(self.rhs_)
