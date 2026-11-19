"""Distances in miles."""
import time

import numpy as np

EARTH_RADIUS_MI = 3958.8
BALLOU_FACTOR = 1.2  # standard circuity factor used in the proposal (Ballou et al., 2002)


def haversine(lat1, lon1, lat2, lon2):
    """Great-circle distance matrix (miles) between two sets of points."""
    lat1, lon1, lat2, lon2 = (np.radians(np.asarray(x, dtype=float)) for x in (lat1, lon1, lat2, lon2))
    dlat = lat1[:, None] - lat2[None, :]
    dlon = lon1[:, None] - lon2[None, :]
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1[:, None]) * np.cos(lat2[None, :]) * np.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_MI * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


def circuity(R, straight, min_miles=5):
    """Road / straight-line ratio over all pairs farther apart than min_miles."""
    iu = np.triu_indices(len(R), 1)
    far = (straight[iu] > min_miles) & (R[iu] < 1e5)
    ratio = R[iu][far] / straight[iu][far]
    return {"median": float(np.median(ratio)),
            "p05": float(np.percentile(ratio, 5)),
            "p95": float(np.percentile(ratio, 95)),
            "n_pairs": int(far.sum())}


def osrm_road_miles(lat, lon, block=50, pause=1.0,
                    server="https://router.project-osrm.org"):
    """Driving distance matrix from the public OSRM table service.

    Only needed to rebuild data/derived/road_miles.npy (about 5 minutes for 754
    sites). Requires network access to the OSRM server.
    """
    import requests

    n = len(lat)
    R = np.zeros((n, n))
    for a in range(0, n, block):
        for b in range(0, n, block):
            src = list(range(a, min(a + block, n)))
            dst = list(range(b, min(b + block, n)))
            ids = src + dst
            pts = ";".join(f"{lon[k]},{lat[k]}" for k in ids)
            s = ";".join(str(k) for k in range(len(src)))
            d = ";".join(str(k) for k in range(len(src), len(ids)))
            url = f"{server}/table/v1/driving/{pts}?sources={s}&destinations={d}&annotations=distance"
            table = np.array(requests.get(url, timeout=60).json()["distances"], dtype=float)
            R[a:a + len(src), b:b + len(dst)] = table / 1609.34
            time.sleep(pause)
    return np.minimum(R, R.T)
