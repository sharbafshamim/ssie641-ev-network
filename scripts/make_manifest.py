"""Write data/MANIFEST.csv: every input file with its source, retrieval date, size, rows and SHA-256."""
import csv
import gzip
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENTRIES = [
    ("data/raw/alt_fuel_stations_Sep_23_2026.csv", "DOE AFDC Station Locator, NY, electric, DC fast, open, public", "2026-09-23"),
    ("data/raw/all_station_Oct_13_2026.csv", "DOE AFDC Station Locator, NY, all electric stations", "2026-10-13"),
    ("data/raw/2020_gaz_place_36.txt", "U.S. Census Bureau, 2020 Gazetteer, places, New York", "2026-09-26"),
    ("data/raw/DECENNIALPL2020.P1-Data.csv", "U.S. Census Bureau, 2020 Census P.L. 94-171 table P1, NY places (data.census.gov)", "2026-09-26"),
    ("data/raw/nysdot_aadt_principal_arterials_2026-11-19.json.gz",
     "NYSDOT RoadwayData AADT layer (gisdev.dot.ny.gov .../Roadways/RoadwayData/MapServer/13), functional classes 1,2,3,11,12,14",
     "2026-11-19"),
    ("data/derived/road_miles_pairs_le60.u16.gz", "OSRM demo server (router.project-osrm.org), site pairs within 60 straight miles", "2026-11-19"),
    ("data/derived/osrm_matrix_blocks.u16.gz", "OSRM demo server, sites/candidates/cities blocks listed in data/jobs/osrm_job_matrix.json", "2026-11-19"),
    ("data/derived/osrm_routes.json.gz", "OSRM demo server, routes for OD pairs in data/jobs/osrm_job_routes.json", "2026-11-19"),
]


def rows_of(p):
    if p.suffix == ".gz":
        raw = gzip.decompress(p.read_bytes())
        return "" if p.name.endswith(".u16.gz") else raw.count(b"\n")
    return sum(1 for _ in open(p, "rb")) - 1


with open(ROOT / "data" / "MANIFEST.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["file", "source", "retrieved", "bytes", "rows", "sha256"])
    for rel, src, date in ENTRIES:
        p = ROOT / rel
        if not p.exists():
            continue
        w.writerow([rel, src, date, p.stat().st_size, rows_of(p), hashlib.sha256(p.read_bytes()).hexdigest()])
print(open(ROOT / "data" / "MANIFEST.csv").read())
