"""Trip-level model: can an EV complete a given origin-destination trip on the actual road route?

Each route comes from OSRM (driving route between two cities or a Canada border crossing) with
the fast-charging sites that lie within `max_offset` miles of the route, their position along it
and their offset from it (see scripts/osrm_fetch_browser_routes.js / data/derived/osrm_routes.json.gz).

State-of-charge model (all as fractions of usable range U = nominal range x weather factor):
    leave origin at `start_soc`, never drop below `reserve`, fast-charge to `charge_to`.
    A leg from stop a to stop b costs (pos_b - pos_a) + off_a + off_b miles (detour to and from the
    charger on both ends). The trip is feasible if the greedy "drive to the farthest reachable
    charger" strategy reaches the destination; for this one-dimensional refuelling problem greedy
    is exact for feasibility.
"""
import numpy as np


def _legs_ok(pos, off, L, U, start_soc, charge_to, reserve):
    """Greedy reachability along one route (see module docstring)."""
    budget = (start_soc - reserve) * U
    later = (charge_to - reserve) * U
    cur_pos, cur_off = 0.0, 0.0
    while True:
        if (L - cur_pos) + cur_off <= budget:
            return True
        ok = (pos > cur_pos) & ((pos - cur_pos) + cur_off + off <= budget)
        if not ok.any():
            return False
        # stop where the onward reach (pos - off + later) is largest
        j = np.where(ok)[0][np.argmax((pos - off)[ok])]
        cur_pos, cur_off, budget = pos[j], off[j], later


def trip_feasible(route, U, site_mask=None, start_soc=0.9, charge_to=0.8, reserve=0.1, max_offset=1.0):
    ch = np.asarray(route["chargers"], float).reshape(-1, 3)
    if len(ch):
        keep = ch[:, 2] <= max_offset
        if site_mask is not None:
            keep &= site_mask[ch[:, 0].astype(int)]
        ch = ch[keep]
    return _legs_ok(ch[:, 1], ch[:, 2], route["miles"], U, start_soc, charge_to, reserve)


def required_range(route, site_mask=None, start_soc=0.9, charge_to=0.8, reserve=0.1, max_offset=1.0,
                   lo=10.0, hi=2000.0, tol=0.5):
    """Smallest usable range (miles) that makes the trip feasible, by bisection."""
    if not trip_feasible(route, hi, site_mask, start_soc, charge_to, reserve, max_offset):
        return np.inf
    while hi - lo > tol:
        mid = (lo + hi) / 2
        if trip_feasible(route, mid, site_mask, start_soc, charge_to, reserve, max_offset):
            hi = mid
        else:
            lo = mid
    return hi


def route_gaps(route, site_mask=None, max_offset=1.0):
    """Charger positions along the route (sorted), including the two route ends."""
    ch = np.asarray(route["chargers"], float).reshape(-1, 3)
    if len(ch):
        keep = ch[:, 2] <= max_offset
        if site_mask is not None:
            keep &= site_mask[ch[:, 0].astype(int)]
        ch = ch[keep]
    return np.sort(ch[:, 1]) if len(ch) else np.array([])


def consecutive_coverage(routes, point_weight, gap_threshold, site_mask=None, max_offset=1.0, cell_miles=0.5):
    """Hanig-style consecutive coverage on the corridor network formed by the routes.

    Every route is sampled about once per mile (route["geom"] = [lon, lat, pos]). A sample point is
    covered when the gap between the nearest usable charger behind it and the nearest ahead of it,
    along that route, is below `gap_threshold`. Points from overlapping routes are merged on a
    cell_miles grid (a cell is covered if covered on any route through it) and weighted by
    `point_weight(lon, lat)` (e.g. AADT). Returns (weighted share covered, length share covered).
    """
    cells = {}
    for r in routes:
        if r.get("failed"):
            continue
        p = route_gaps(r, site_mask, max_offset)
        g = np.asarray(r["geom"], float)
        pos = g[:, 2]
        k = np.searchsorted(p, pos)
        prev = np.where(k > 0, p[np.clip(k - 1, 0, None)] if len(p) else -np.inf, -np.inf) if len(p) else np.full(len(pos), -np.inf)
        nxt = np.where(k < len(p), p[np.clip(k, None, len(p) - 1)] if len(p) else np.inf, np.inf) if len(p) else np.full(len(pos), np.inf)
        covered = (nxt - prev) < gap_threshold
        kx = np.round(g[:, 0] * 69.0 * np.cos(np.radians(42.5)) / cell_miles).astype(int)
        ky = np.round(g[:, 1] * 69.0 / cell_miles).astype(int)
        for a, b, cv, lon, lat in zip(kx, ky, covered, g[:, 0], g[:, 1]):
            key = (a, b)
            if key in cells:
                cells[key][0] = cells[key][0] or cv
            else:
                cells[key] = [cv, lon, lat]
    vals = np.array([[v[0], v[1], v[2]] for v in cells.values()], float)
    w = point_weight(vals[:, 1], vals[:, 2])
    return float((w * vals[:, 0]).sum() / w.sum()), float(vals[:, 0].mean()), len(vals)
