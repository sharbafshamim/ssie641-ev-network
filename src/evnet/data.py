"""Loading and preparing the input data.

All inputs are public:
- AFDC Alternative Fueling Station Locator extracts for New York (DOE).
- Census 2020 Gazetteer place file and P.L. 94-171 table P1 (total population).
"""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
DERIVED = ROOT / "data" / "derived"

AFDC_SEP = RAW / "alt_fuel_stations_Sep_23_2026.csv"
AFDC_ALL_OCT = RAW / "all_station_Oct_13_2026.csv"
GAZETTEER = RAW / "2020_gaz_place_36.txt"
CENSUS_P1 = RAW / "DECENNIALPL2020.P1-Data.csv"

NY_POP_2020 = 20_201_249  # New York State resident population, Census 2020



def _flag_plugs(df):
    df = df.copy()
    df["EV Connector Types"] = df["EV Connector Types"].fillna("")
    df["ccs"] = df["EV Connector Types"].str.contains("J1772COMBO")
    df["tesla_only"] = df["EV Connector Types"] == "TESLA"
    return df


def load_dcfc(path=AFDC_SEP):
    """Open, public stations with at least one DC fast port."""
    df = pd.read_csv(path, low_memory=False)
    df["EV DC Fast Count"] = df["EV DC Fast Count"].fillna(0)
    df = df[df["EV DC Fast Count"] > 0]
    if "Status Code" in df:
        df = df[df["Status Code"] == "E"]
    if "Access Code" in df:
        df = df[df["Access Code"] == "public"]
    cols = ["ID", "Station Name", "City", "Latitude", "Longitude",
            "EV DC Fast Count", "EV Network", "EV Connector Types"]
    return _flag_plugs(df[cols])


def make_sites(stations):
    """Merge stations with identical coordinates into one site.

    groupby sorts by (Latitude, Longitude); this order is the row/column order of
    data/derived/road_miles.npy, so it must not change.
    """
    sites = stations.groupby(["Latitude", "Longitude"], as_index=False).agg(
        name=("Station Name", "first"),
        city=("City", "first"),
        network=("EV Network", "first"),
        n_stations=("ID", "count"),
        ports=("EV DC Fast Count", "sum"),
        ccs=("ccs", "max"),
        tesla_only=("tesla_only", "min"),
    )
    return sites


def load_places(min_pop=5000, gazetteer=GAZETTEER, census_p1=CENSUS_P1, out_name="ny_places.csv"):
    """Census 2020 places with population and internal point."""
    gaz = pd.read_csv(gazetteer, sep="\t")
    gaz.columns = gaz.columns.str.strip()
    pop = pd.read_csv(census_p1, usecols=["GEO_ID", "P1_001N"]).iloc[1:]
    pop["GEOID"] = pop["GEO_ID"].str[-7:].astype(int)
    pop["pop"] = pop["P1_001N"].astype(int)
    places = gaz.merge(pop[["GEOID", "pop"]], on="GEOID")
    places = places[["GEOID", "NAME", "pop", "INTPTLAT", "INTPTLONG"]]
    places.columns = ["geoid", "name", "pop", "lat", "lon"]
    if out_name:
        places.to_csv(DERIVED / out_name, index=False)
    return places[places["pop"] >= min_pop].reset_index(drop=True), places


def load_candidates(path=AFDC_ALL_OCT, out_name="candidates.csv"):
    """Public, open Level 1 / Level 2 locations with no DC fast port."""
    st = pd.read_csv(path, low_memory=False)
    for c in ["EV Level1 EVSE Num", "EV Level2 EVSE Num", "EV DC Fast Count"]:
        st[c] = st[c].fillna(0)
    slow = st[((st["EV Level1 EVSE Num"] > 0) | (st["EV Level2 EVSE Num"] > 0))
              & (st["EV DC Fast Count"] == 0)]
    slow = slow[(slow["Status Code"] == "E") & (slow["Access Code"] == "public")]
    cand = slow.groupby(["Latitude", "Longitude"], as_index=False).agg(
        name=("Station Name", "first"), city=("City", "first"),
        l1=("EV Level1 EVSE Num", "sum"), l2=("EV Level2 EVSE Num", "sum"))
    cand.columns = ["lat", "lon", "name", "city", "l1", "l2"]
    if out_name:
        cand.to_csv(DERIVED / out_name, index=False)
    return cand


def load_road_miles(n_sites):
    """Road distances (OSRM) between sites, if the file exists; else None.

    Pairs more than 60 straight-line miles apart may be stored as 1e6 (not
    queried); no analysis here uses links longer than 60 miles.
    """
    path = DERIVED / "road_miles.npy"
    packed = DERIVED / "road_miles_pairs_le60.u16.gz"
    if not path.exists() and packed.exists():
        np.save(path, unpack_road_miles(packed))
    if not path.exists():
        return None
    R = np.load(path)
    if R.shape != (n_sites, n_sites):
        raise ValueError(f"road_miles.npy has shape {R.shape}, expected {(n_sites, n_sites)}")
    return R


def unpack_road_miles(packed_path, sites_path=None, max_straight=60.0):
    """Rebuild the 754 x 754 road matrix from the compact OSRM download.

    The file holds gzip'd little-endian uint16 values (miles x 20, i.e. 0.05-mile
    resolution) for every site pair i < j whose straight-line distance is at most
    60 miles (or every pair when max_straight is None), in row-major upper-triangle
    order. Other pairs get 1e6 (not queried).
    """
    import gzip

    from .distance import haversine

    sites = pd.read_csv(sites_path or DERIVED / "sites.csv")
    lat, lon = sites.Latitude.round(6).values, sites.Longitude.round(6).values
    n = len(sites)
    vals = np.frombuffer(gzip.decompress(open(packed_path, "rb").read()), dtype="<u2")
    i, j = np.triu_indices(n, 1)
    mask = (np.ones(len(i), bool) if max_straight is None
            else haversine(lat, lon, lat, lon)[i, j] <= max_straight)
    if mask.sum() != len(vals):
        raise ValueError(f"{len(vals)} values for {mask.sum()} pairs")
    R = np.full((n, n), 1e6)
    np.fill_diagonal(R, 0)
    R[i[mask], j[mask]] = vals / 20.0
    R[j[mask], i[mask]] = vals / 20.0
    return R


def load_osrm_matrix(job=ROOT / "data" / "jobs" / "osrm_job_matrix.json",
                     packed=DERIVED / "osrm_matrix_blocks.u16.gz", fallback_factor=1.22):
    """Road distances for sites (S), kept candidates (C) and cities (Y) from the OSRM block download.

    The job file lists the points ([sites | kept candidates | cities with >= 5,000 people]) and the
    50 x 50 blocks that were queried (only blocks holding at least one pair within 60 straight-line
    miles, 70 for cities). The packed file holds every block's values (uint16, miles x 20, row-major,
    65535 = no route) in job order. Pairs that were not queried get straight-line x fallback_factor;
    they are all farther apart than any standard studied.
    Returns dict with SC (S x C), CC (C x C), YS (Y x S), YC (Y x C), and points.
    """
    import gzip
    import json

    from .distance import haversine

    J = json.load(open(job))
    pts = np.array(J["pts"])
    nS, nC, nY = J["nS"], J["nC"], J["nY"]
    lon, lat = pts[:, 0], pts[:, 1]
    full = fallback_factor * haversine(lat, lon, lat, lon)
    vals = np.frombuffer(gzip.decompress(open(packed, "rb").read()), dtype="<u2")
    o = 0
    queried = np.zeros(full.shape, bool)
    for a, na, b, nb in J["blocks"]:
        blk = vals[o:o + na * nb].reshape(na, nb).astype(float)
        o += na * nb
        blk = np.where(blk == 65535, np.nan, blk / 20.0)
        sub = full[a:a + na, b:b + nb]
        full[a:a + na, b:b + nb] = np.where(np.isnan(blk), sub, blk)
        queried[a:a + na, b:b + nb] = ~np.isnan(blk)
    if o != len(vals):
        raise ValueError(f"packed file has {len(vals)} values, job expects {o}")
    # symmetrise: use the queried direction where only one exists, the minimum where both do
    q = queried | queried.T
    both = queried & queried.T
    sym = np.where(both, np.minimum(full, full.T), np.where(queried, full, full.T))
    full = np.where(q, sym, full)
    S, C, Y = slice(0, nS), slice(nS, nS + nC), slice(nS + nC, nS + nC + nY)
    return {"SC": full[S, C], "CC": full[C, C], "YS": full[Y, S], "YC": full[Y, C],
            "queried_share_CC_le60": float(q[C, C][full[C, C] <= 60].mean()) if nC else 0.0,
            "pts": pts, "nS": nS, "nC": nC, "nY": nY}


def site_attributes(sites, sep_path=AFDC_SEP, oct_path=AFDC_ALL_OCT):
    """Per-site flags from the October 13, 2026 list, matched to September sites by station ID.

    hpc150: at least one CCS port rated 150 kW or more ("EV CCS 150+ kW Port Count (Beta)").
    nevi_grade: at least four such ports (the federal minimum of four 150 kW CCS ports).
    unavailable: every station at the site is listed as temporarily unavailable (status "T").
    open_year: year the earliest station at the site opened.
    """
    sep = load_dcfc(sep_path)
    raw = pd.read_csv(sep_path, low_memory=False)[["ID", "Open Date"]]
    sep = sep.merge(raw, on="ID", how="left")
    octo = pd.read_csv(oct_path, low_memory=False)
    octo["hpc_ports"] = pd.to_numeric(octo["EV CCS 150+ kW Port Count (Beta)"], errors="coerce").fillna(0)
    octo = octo[["ID", "hpc_ports", "Status Code"]].rename(columns={"Status Code": "oct_status"})
    st = sep.merge(octo, on="ID", how="left")
    st["hpc_ports"] = st["hpc_ports"].fillna(0)
    st["t"] = st["oct_status"].eq("T")
    st["open_year"] = pd.to_datetime(st["Open Date"], errors="coerce").dt.year
    agg = st.groupby(["Latitude", "Longitude"]).agg(hpc_ports=("hpc_ports", "sum"), all_t=("t", "all"),
                                                   open_year=("open_year", "min")).reset_index()
    out = sites.merge(agg, on=["Latitude", "Longitude"], how="left")
    out["hpc150"] = out["hpc_ports"] > 0
    out["nevi_grade"] = out["hpc_ports"] >= 4
    out["unavailable"] = out["all_t"].fillna(False).astype(bool)
    return out
