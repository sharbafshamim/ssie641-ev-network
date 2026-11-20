"""Build notebooks/ev_network_final.ipynb: a question-by-question walkthrough of the results.

    python scripts/build_notebook.py
    jupyter nbconvert --to notebook --execute --inplace notebooks/ev_network_final.ipynb
"""
from pathlib import Path

import nbformat as nbf

ROOT = Path(__file__).resolve().parents[1]
nb = nbf.v4.new_notebook()
C = []


def md(s):
    C.append(nbf.v4.new_markdown_cell(s.strip()))


def code(s):
    C.append(nbf.v4.new_code_cell(s.strip()))


md("""
# Coverage Is Not Connectivity: New York's EV fast-charging network (final)

SSIE 641 final project: Joubin Zahiri Khameneh, Shamim Sharbaf, Zeinab Davoodmanesh.

This notebook walks through the results question by question, in the order of the report (`paper/report.md`).
Every number comes from the scripts in `scripts/`, which write `results/tables/*.csv`, `results/figures/*.png`
and the `results/*summary.json` files:

| Script | What it adds | Time |
| --- | --- | --- |
| `run_all.py` | Q1, Q2, coverage, heuristic Q3, winter, control, October data | about 3 min |
| `run_structure.py` | biconnectivity, reliability, efficiency, betweenness variants, k-cores, spectral split, communities | about 3 min |
| `run_exact.py` | exact cost of connectivity and cost of robustness on road distances (report Section 7) | about 45 min |
| `run_extended.py` | trips on real routes, Hanig-style coverage, growth over time, regional outages, baselines | about 1 hour |
| `run_learning.py` | optional GNN benchmark (needs PyTorch; not used in the report) | long |

Set `RUN = True` to rebuild the first two. The analysis code lives in `src/evnet/`.

Changes from notebook v3 (`notebooks/ev_network_v3.ipynb`):
- Q3 uses a Steiner-tree heuristic (Takahashi & Matsuyama, 1980) with upper and lower bounds and an exact
  feasibility test, for two objectives (whole network, all city pairs), instead of the greedy search.
- Road distances re-queried from OSRM for all site pairs within 60 miles (data/derived/road_miles_pairs_le60.u16.gz);
  links to new stations use the measured detour factor 1.22 for those distances; 1.2 is kept as a sensitivity check.
- "Big or small" is answered by ports as well as degree.
- Population share corrected: places with 5,000+ people hold 76% of the state, not 92%.
- New: budget against the $175M NEVI allocation, winter range, NYC-excluded and access-capped coverage,
  October 2026 data check.
""")
code("""
import json, subprocess, sys
from pathlib import Path
import pandas as pd
from IPython.display import Image, display

ROOT = Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()
RUN = False
if RUN:
    for script in ["run_all.py", "run_structure.py"]:
        subprocess.run([sys.executable, str(ROOT / "scripts" / script)], check=True)

TAB, FIG = ROOT / "results" / "tables", ROOT / "results" / "figures"
S = json.load(open(ROOT / "results" / "summary.json"))
pd.set_option("display.max_colwidth", 120)
def t(name): return pd.read_csv(TAB / name)
def f(name):
    if (FIG / name).exists():
        display(Image(filename=str(FIG / name), width=850))
    else:
        print(f"{name} not found: run the script that makes it")
def tt(name):
    if (TAB / name).exists():
        display(t(name))
    else:
        print(f"{name} not found: run the script that makes it")
""")
md("## 1. Data")
code("""
print("stations:", S["stations"], "| fast ports:", S["fast_ports"], "| sites:", S["sites"], "| CCS sites:", S["ccs_sites"])
print("places >= 5000:", S["places_5000"], "| people:", S["pop_places_5000"],
      f"| share of NY population: {S['share_state_pop_in_places_5000']:.1%}")
print(f"NYC's share of population-weighted city pairs: {S['nyc_share_of_pair_weight']:.0%}")
print("candidate L1/L2 locations:", S["candidates"])
print("distances:", S["distance_source"])
f("figS1_sites_map.png")
""")
md("""
## 2. Q1: When does the network split?

The whole network is one piece from the longest link of its minimum spanning tree: 43.5 road miles.
""")
code("""
print({k: round(v, 1) for k, v in S["threshold"].items()}, "| weakest link:", S["weakest_link"])
display(t("q1_weakest_links.csv").head(8))
f("fig1_percolation.png")
display(t("q1_pieces_24mi.csv"))
f("fig2_pieces_24mi.png")
""")
md("""
## 3. Q2: Which stations hold the network together?

Single points of failure (articulation points) are isolated rural sites: low degree, but typical or large by ports.
""")
code("""
display(t("q2_critical_sites.csv"))
display(t("q2_big_or_small.csv"))
f("fig3_critical_sites.png")
f("figS2_cut_vertex_count.png")
""")
md("### 3.1 Random failure and targeted attack")
code("""
display(t("q2_random_failure.csv"))
display(t("q2_targeted_attack.csv"))
display(t("q2_attack_first15_50mi.csv"))
f("fig4_failure_attack.png")
""")
md("""
### 3.2 Coverage is not connectivity

Coverage counts pairs of cities (362 places with 5,000+ people), plain and population-weighted, with two checks:
weights without New York City, and city access capped at 15 miles.
""")
code("""
cv = t("coverage_curve.csv")
display(cv[cv["miles"].isin([10, 20, 25, 27, 30, 35, 40, 45, 46, 50])].round(3))
display(t("coverage_farthest_cities.csv"))
display(t("coverage_single_site_loss.csv"))
display(t("coverage_failure_attack.csv"))
f("fig5_coverage_curve.png")
f("figS3_coverage_attack.png")
""")
md("""
### 3.3 Network structure (`run_structure.py`; report Sections 5, 6.1, 6.3 and 6.5)

Biconnectivity threshold, reliability of the single points of failure, global efficiency under attack,
betweenness variants, k-cores, random-walk spectral split, Leiden communities, centrality localisation,
EU AFIR standards, a band of winter losses and a region-stratified control.
""")
code("""
SS = json.load(open(ROOT / "results" / "structure_summary.json"))
display(t("s1_thresholds.csv"))
display(t("s2_reliability_cut_vertices.csv").round(3))
display(t("s3_efficiency.csv").round(3))
f("figS4_efficiency.png")
b4 = t("s4_betweenness_top10.csv"); display(b4[b4["rank"] <= 5])
display(t("s5_core_summary.csv").round(3))
display(t("s6_spectral_split.csv"))
display(t("s6_spectral_paul_smiths.csv").round(5))
f("figS5_spectral.png")
display(t("s7_communities.csv").round(3))
display(t("s8_centrality_localisation.csv").round(3))
print("friendship paradox:", SS["friendship_paradox"])
display(t("s9_city_standard_needed.csv").head(10))
display(t("s10_other_standards.csv"))
display(t("s11_winter_band.csv").round(2))
display(t("s12_control_stratified.csv").round(3))
f("figS6_distributions.png")
""")
md("""
## 4. Q3: How many new stations does each standard need, and can New York afford them?

The report's cost curve is the exact one (`run_exact.py`): road distances to 2,703 candidate locations, solved as an
integer program (HiGHS via SciPy) with lazy vertex-separator cuts (`src/evnet/exact.py`). *Connectivity*: every pair of
sites that the full candidate graph can join must be joined. *Robustness*: in addition, no single station failure may
separate two sites that the full candidate graph keeps together after that failure. `lower_bound` equals `stations`
when the solver proved optimality.
""")
code("""
tt("exact_cost_curve.csv")
f("fig10_cost_of_robustness.png")
tt("exact_subnetworks.csv")
tt("subnetwork_structure.csv")
""")
md("""
### 4.1 Checks: Steiner heuristic on straight-line distances to candidates

`lower_bound` and `new_stations` bracket the minimum; `feasible = False` means some piece cannot be reached even if
every candidate were upgraded under the straight-line distance model.
""")
code("""
q3 = t("q3_cost_curve.csv")
display(q3)
display(t("q3_sensitivity_factor1.2.csv"))
b = t("q3_budget.csv")
display(b[b["objective"] == "network"].pivot(index="miles", columns="cost_level", values="share_of_NEVI_pct").round(2))
print("sites the $175M allocation could fund:", S["budget"]["sites_affordable"])
f("fig6_cost_curve.png")
""")
md("### 4.2 Winter (41% range loss at 20°F with heat; AAA 2019)")
code("""
print(f"nominal standard needed for one network in winter: {S['winter_nominal_needed']:.1f} road miles")
display(t("winter.csv"))
display(t("winter_q3.csv"))
f("fig7_winter.png")
""")
md("## 5. Control: is the network well sited?")
code("""
display(t("control_summary.csv").round(3))
f("fig8_control.png")
""")
md("## 6. Robustness: October 13, 2026 station list")
code("""
display(t("robustness_snapshot.csv"))
""")
md("## 7. Further checks (`run_extended.py`; report Section 8.4)\n\n### 7.1 Trips along real roads and the Hanig et al. coverage measure")
code("""
tt("trips_feasibility.csv")
tt("trips_hardest.csv")
tt("trips_border.csv")
tt("hanig_consecutive_coverage.csv")
f("fig11_trip_ranges.png")
""")
md("### 7.2 How the network grew, 2015-2026")
code("""
tt("history_by_year.csv")
f("fig12_history.png")
""")
md("### 7.3 Reliability: unavailable stations and regional outages")
code("""
tt("reliability_regional_outages.csv")
tt("random_failure_ci.csv")
""")
md("### 7.4 Random baselines with 95% confidence intervals and random-geometric-graph theory")
code("""
tt("baselines_with_ci.csv")
import json
p = ROOT / "results" / "extended_summary.json"
if p.exists():
    print(json.dumps(json.load(open(p)).get("rgg", {}), indent=1))
""")
md("## 8. Optional: learning to place stations (`run_learning.py`, needs PyTorch; not in the report)")
code("""
tt("learning_summary.csv")
f("fig13_learning.png")
""")
md("""
## 9. Summary (matches the report's abstract and answers)

- **Q1.** One network from **43.5 road miles**; weakest link Saranac Lake – Malone, then Malone – Massena (37.2),
  Arkville – Tannersville (34.7) and Chestertown – Indian Lake (33.3). No single point of failure from **46.2 miles**.
  The two large regions join at 26 miles.
- **Q2.** At 30 miles five sites are single points of failure (Chestertown, Peru, Elizabethtown, Monticello, Roscoe),
  four of them Tesla Superchargers: isolated (median degree 9 vs 50, core number 6 vs 40), not small (median ports 8 vs 4).
  With 14% unavailability at least one is down 53% of the time. High-betweenness sites sit on an east–west seam found
  by the spectral split and Leiden boundaries; 17 betweenness removals (2.3%) cut the largest piece to 57% at 50 miles,
  while degree attack does no more than random failure.
- **Coverage.** At 30–43 miles 99% of sites but 97.3% of city pairs are connected; every pair from 44 miles.
- **Q3 (exact, road distances).** 0 stations at 45–50 miles, 1 at 37.3–40 (Ogdensburg or Paul Smiths), 2 at 35
  (Paul Smiths, Hogansburg), 6 at 30, at most 6.6% of the $175M NEVI allocation. Cost of robustness: 0 at 50, 1 at 45,
  2 at 40, 6 at 35, 13 at 30. Below 30 miles parts of the North Country cannot be reached from existing locations.
- **Winter.** One network needs a nominal 54–74 road miles for 20–41% range loss.
- **Control.** Better than 98% of 100 random networks at 30 miles; no better than chance on the overall threshold;
  much of the advantage comes from how many chargers each region received.
""")

nb["cells"] = C
nb["metadata"]["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
out = ROOT / "notebooks" / "ev_network_final.ipynb"
nbf.write(nb, out)
print("wrote", out)
