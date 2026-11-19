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
| **Q1.** How close is the network to breaking apart, and where? | One connected network from **43.5 road miles** (45.6 calibrated). Weakest link: **Saranac Lake – Malone**. The two large regions join at 27 miles; every remaining gap is in the Catskills, Adirondacks or North Country. |
| **Q2.** Which stations hold it together: big or small? | At 30 miles, **six single points of failure**, five on the I-87 Northway corridor (Warrensburg, Chestertown, Elizabethtown, Lewis, Peru) plus Roscoe. They are **isolated, not small**: median degree 7.5 vs 47, median ports 5 vs 4. Removing the 18 highest-betweenness sites (2.4%) cuts the largest piece below 90% at 50 miles; removing the 18 busiest by degree does nothing. |
| **Q3.** How many new stations per standard, and can NY afford them? | **0 at 50 miles, 1 at 40–45, 3 at 35**, all in the North Country, at most 3.3% of NY's $175M NEVI allocation. **30 miles and below cannot be met** by upgrading existing public charging locations: new host sites are needed. |
| Control | Better sited than all 100 random networks at 30 miles; no better than chance on the overall threshold: the North Country gap is geographic. |
| Winter (−41% range) | One network needs a nominal 74 road miles; a 60-mile standard needs two winter stations (Paul Smiths, Massena). |

The full report is in `paper/` and in the project's Claude doc.

## Repository layout

```
data/raw/                     input data (public; see below)
data/derived/                 sites.csv, ny_places.csv, candidates.csv (+ road_miles.npy if available)
src/evnet/                    analysis package
    data.py                   loading AFDC and Census files, sites, candidates
    distance.py               haversine, circuity, OSRM road-distance builder
    network.py                epsilon graph, MST threshold, cut vertices, random failure, targeted attack
    coverage.py               city-pair coverage (plain, population-weighted, access cap)
    placement.py              Q3: node-weighted Steiner heuristic with lower/upper bounds and feasibility
    control.py                random-siting control
scripts/run_all.py            runs everything -> results/tables, results/figures, results/summary.json
scripts/build_notebook.py     builds notebooks/ev_network_final.ipynb
notebooks/ev_network_final.ipynb   question-by-question walkthrough (executed)
notebooks/ev_network_v3.ipynb      earlier exploratory notebook (road distances from OSRM)
results/                      every table and figure used in the paper
paper/                        proposal and final report
```

## Reproduce

```bash
pip install -r requirements.txt
python scripts/run_all.py          # about 3 minutes
python scripts/build_notebook.py
jupyter nbconvert --to notebook --execute --inplace notebooks/ev_network_final.ipynb
```

### Distances

Notebook v3 queried driving distances between all 754 sites from the public OSRM server and saved them as
`road_miles.npy`; the median road/straight-line ratio was **1.27** (90% of pairs between 1.10 and 1.48). That
matrix was not available for the final run and the OSRM server could not be reached, so the committed results use
straight-line distance × 1.27 for every link. In v3 the two versions gave the same weakest links and thresholds
within 1–2 miles. To use road distances, put the matrix at `data/derived/road_miles.npy` (754 × 754, rows in the
order of `data/derived/sites.csv`) and rerun `scripts/run_all.py`; it is picked up automatically. To rebuild it
(network access to OSRM required):

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

Budget and cost parameters (`scripts/run_all.py`): NY five-year NEVI apportionment $175M (NYSDOT, 2025);
per-site cost $0.6M / $1.0M / $1.92M (NEVI construction estimates; average NEVI project cost reported by Paren,
2024; NYSERDA maximum award $1.536M at 80% cost share). Winter range loss 41% (AAA, 2019).

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
