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
