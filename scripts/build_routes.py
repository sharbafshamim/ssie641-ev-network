"""Turn raw OSRM routes (data/derived/osrm_routes_raw.json.gz) into the route records used by trips.py.

Raw input: one record per OD pair in data/jobs/osrm_job_routes.json, {i, j, m (metres), p (polyline6)},
downloaded with the OSRM route service (overview=full) on 2026-11-19.

Output data/derived/osrm_routes.json.gz, one record per pair:
    i, j        OD node indices (data/derived/od_nodes.csv)
    miles       route length
    geom        [lon, lat, position in miles] sampled about once per mile
    chargers    flat [site, position, offset, ...] for every fast-charging site within 1 mile of the route
                (offset = straight-line miles from the route to the site; a stop costs a 2 x offset detour)
"""
import gzip
import json
import sys
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parents[1]
MI_PER_DEG_LAT = 69.05


def decode_polyline(s, precision=6):
    coords, idx, lat, lon, f = [], 0, 0, 0, 10 ** precision
    while idx < len(s):
        for which in (0, 1):
            shift = result = 0
            while True:
                b = ord(s[idx]) - 63
                idx += 1
                result |= (b & 0x1F) << shift
                shift += 5
                if b < 0x20:
                    break
            d = ~(result >> 1) if result & 1 else result >> 1
            if which == 0:
                lat += d
            else:
                lon += d
        coords.append((lon / f, lat / f))
    return np.array(coords)


def project(lon, lat, lat0=42.9):
    return np.column_stack([lon * MI_PER_DEG_LAT * np.cos(np.radians(lat0)), lat * MI_PER_DEG_LAT])


def main(raw=ROOT / "data" / "derived" / "osrm_routes_raw.json.gz", out=ROOT / "data" / "derived" / "osrm_routes.json.gz",
         buffer_mi=1.0):
    job = json.load(open(ROOT / "data" / "jobs" / "osrm_job_routes.json"))
    sites = np.array(job["sites"])
    S = project(sites[:, 0], sites[:, 1])
    recs = json.loads(gzip.decompress(open(raw, "rb").read()))
    res = []
    for r in recs:
        if r is None or r.get("failed"):
            res.append({"i": r["i"] if r else None, "j": r["j"] if r else None, "failed": (r or {}).get("failed", "missing")})
            continue
        g = decode_polyline(r["p"])
        P = project(g[:, 0], g[:, 1])
        seg = np.r_[0, np.cumsum(np.hypot(*np.diff(P, axis=0).T))]
        miles = r["m"] / 1609.344
        pos = seg * (miles / seg[-1]) if seg[-1] > 0 else seg   # rescale to OSRM's length
        # densify so no route vertex gap exceeds 0.25 mile (straight motorway segments can be long)
        tgt = np.arange(0, pos[-1], 0.25)
        D = np.column_stack([np.interp(tgt, pos, P[:, 0]), np.interp(tgt, pos, P[:, 1])])
        d, k = cKDTree(D).query(S, distance_upper_bound=buffer_mi)
        near = np.where(np.isfinite(d))[0]
        ch = np.column_stack([near, tgt[k[near]], d[near]]) if len(near) else np.zeros((0, 3))
        ch = ch[np.argsort(ch[:, 1])]
        samp = np.arange(0, pos[-1] + 1e-9, 1.0)
        geom = np.column_stack([np.interp(samp, pos, g[:, 0]), np.interp(samp, pos, g[:, 1]), samp])
        res.append({"i": r["i"], "j": r["j"], "miles": round(miles, 3), "geom": np.round(geom, 5).tolist(),
                    "chargers": np.round(ch, 3).ravel().tolist()})
    open(out, "wb").write(gzip.compress(json.dumps(res).encode()))
    ok = [x for x in res if not x.get("failed")]
    print(f"{len(res)} routes, {len(res) - len(ok)} failed, median {np.median([x['miles'] for x in ok]):.0f} mi, "
          f"median chargers per route {np.median([len(x['chargers']) // 3 for x in ok]):.0f}")


if __name__ == "__main__":
    main(*sys.argv[1:])
