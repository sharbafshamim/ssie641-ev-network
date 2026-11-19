# Coverage Is Not Connectivity

**Connectivity thresholds, critical stations, and the cost of robustness in New York State's EV fast-charging network**

SSIE 641 Advanced Topics in Network Science, final project.
Joubin Zahiri Khameneh · Shamim Sharbaf · Zeinab Davoodmanesh

The 754 public DC fast-charging sites in New York (DOE station list, September 23, 2026) are modelled as an
epsilon-neighbourhood network: two sites are linked when a driver can cover the distance between them. The
spacing standard ε is the variable we study, because federal NEVI guidance dropped its 50-mile spacing rule in
August 2025 and left the number to the states.

## Answers in brief

| Question | Answer |
| --- | --- |
| **Q1.** How close is the network to breaking apart, and where? | One connected network from **43.5 road miles**. Weakest link: **Saranac Lake – Malone**, then Malone – Massena (37.2) and Arkville – Tannersville (34.7). The two large regions join at 26 miles; every remaining gap is in the Catskills, Adirondacks or North Country. |
| **Q2.** Which stations hold it together: big or small? | At 30 miles, **five single points of failure**: Chestertown, Peru, Elizabethtown, Monticello, Roscoe (four Tesla Superchargers). They are **isolated, not small**: median degree 9 vs 50, median ports 8 vs 4. Removing the 17 highest-betweenness sites (2.3%) shrinks the largest piece to 57% at 50 miles; at 30 miles the two **Little Falls Thruway plazas** alone do it. Degree attack does no more than random failure. |
| **Q3.** How many new stations per standard, and can NY afford them? | **0 at 45–50 miles, 1 at 40 (Paul Smiths), 2 at 35 (Paul Smiths, Massena)**, all provably optimal, at most 2.2% of NY's $175M NEVI allocation. **30 miles and below cannot be met** by upgrading existing public charging locations: new host sites are needed. |
| Control | Better sited than 98% of 100 random networks at 30 miles; no better than chance on the overall threshold: the North Country gap is geographic. |
| Winter (−41% range) | One network needs a nominal 74 road miles; a 60-mile standard needs two winter stations (Paul Smiths, Massena). |
| Second state: Maine (extension c) | One network only from **151 road miles** (Medway – Van Buren). A 50-mile standard needs **6 new stations** (19–60% of Maine's $19.3M NEVI funds); 40 miles and below are infeasible. Critical sites are again isolated, not small, but Maine's network is sited **worse than 95% of random networks** from its own charging locations. |

The full report is in `paper/` and in the project's Claude doc.

## Repository layout

```
data/raw/                     input data (public; see below)
data/derived/                 sites.csv, ny_places.csv, candidates.csv, OSRM road distances
src/evnet/                    analysis package
    data.py                   loading AFDC and Census files, sites, candidates
    distance.py               haversine, circuity, OSRM road-distance builder
    network.py                epsilon graph, MST threshold, cut vertices, random failure, targeted attack
    coverage.py               city-pair coverage (plain, population-weighted, access cap)
    placement.py              Q3: node-weighted Steiner heuristic with lower/upper bounds and feasibility
    control.py                random-siting control
scripts/run_all.py            runs everything -> results/tables, results/figures, results/summary.json
scripts/build_notebook.py     builds notebooks/ev_network_final.ipynb
scripts/run_maine.py          extension (c): the same analysis for Maine, compared with New York
scripts/osrm_fetch_browser.js browser script used to download the OSRM road distances
scripts/build_report.sh       builds paper/report.pdf from paper/report.md
notebooks/ev_network_final.ipynb   question-by-question walkthrough (executed)
notebooks/ev_network_v3.ipynb      earlier exploratory notebook
results/                      every table and figure used in the paper
paper/                        proposal and final report (report.docx, report.pdf, report.md)
```

## Reproduce

```bash
pip install -r requirements.txt
python scripts/run_all.py          # about 3 minutes
python scripts/run_maine.py        # Maine comparison, a few seconds
python scripts/build_notebook.py
jupyter nbconvert --to notebook --execute --inplace notebooks/ev_network_final.ipynb
```

### Distances

Links between existing sites use OpenStreetMap driving distances from the public OSRM server, queried on
Nov 19, 2026 for every site pair within 60 straight-line miles (54,737 pairs; no analysis uses a longer link).
They are stored compactly in `data/derived/road_miles_pairs_le60.u16.gz` (uint16, miles × 20, upper-triangle
order) and unpacked to `data/derived/road_miles.npy` on first run (`evnet.data.unpack_road_miles`). They were downloaded
with `scripts/osrm_fetch_browser.js` (run in a browser tab on router.project-osrm.org). The median
road/straight-line ratio for those pairs is 1.22, which is used for links to new stations and city centres.
To rebuild the full matrix from OSRM (network access required):

```python
import sys; sys.path.insert(0, "src")
import numpy as np, pandas as pd
from evnet.distance import osrm_road_miles
s = pd.read_csv("data/derived/sites.csv")
np.save("data/derived/road_miles.npy", osrm_road_miles(s.Latitude.values, s.Longitude.values))
```

## Data sources

| File | Source |
| --- | --- |
| `alt_fuel_stations_Sep_23_2026.csv` | DOE Alternative Fuels Data Center, Station Locator: NY, electric, open, public, DC fast |
| `all_station_Oct_13_2026.csv` | DOE Alternative Fuels Data Center, Station Locator: NY, all electric stations |
| `2020_gaz_place_36.txt` | U.S. Census Bureau, 2020 Gazetteer files, places, New York |
| `DECENNIALPL2020.P1-Data.csv` | U.S. Census Bureau, 2020 Census P.L. 94-171, table P1, places in New York |
| `maine/alt_fuel_stations_ME_Nov_19_2026.csv` | DOE Alternative Fuels Data Center, Station Locator: Maine, all public electric stations |
| `maine/2020_gaz_place_23.txt` | U.S. Census Bureau, 2020 Gazetteer files, places, Maine |
| `maine/DECENNIALPL2020.P1-Data.csv` | U.S. Census Bureau, 2020 Census P.L. 94-171, table P1, places in Maine (via data.census.gov) |

Budget and cost parameters (`scripts/run_all.py`): NY five-year NEVI apportionment $175M (NYSDOT, 2025);
per-site cost $0.6M / $1.0M / $1.92M (NEVI construction estimates; average NEVI project cost reported by Paren,
2024; NYSERDA maximum award $1.536M at 80% cost share). Maine NEVI funds $19.3M (MaineDOT). Winter range
loss 41% (AAA, 2019). Maine road distances for all site pairs: `data/derived/me_road_miles_allpairs.u16.gz`.

## Method notes

- **Threshold** = longest edge of the minimum spanning tree (exact).
- **Single points of failure** = articulation points; `sites_cut_off` = sites no longer in the largest remaining part.
- **Coverage**: a city (≥ 5,000 people) attaches to every site within ε of its centre; two cities are connected if
  they attach to the same piece.
- **Q3** is a node-weighted Steiner tree problem (NP-hard). We use the shortest-path heuristic of Takahashi &
  Matsuyama (1980) with redundancy pruning (upper bound), report a path-based lower bound, and flag standards
  that are infeasible even with every candidate upgraded.

## License

Code: MIT. Data: public-domain U.S. government data.
