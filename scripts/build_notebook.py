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

This notebook walks through the results question by question. Every number comes from `scripts/run_all.py`,
which writes `results/tables/*.csv`, `results/figures/*.png` and `results/summary.json`. Set `RUN = True` to
rebuild everything (about three minutes). The analysis code lives in `src/evnet/`.

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
    subprocess.run([sys.executable, str(ROOT / "scripts" / "run_all.py")], check=True)

TAB, FIG = ROOT / "results" / "tables", ROOT / "results" / "figures"
S = json.load(open(ROOT / "results" / "summary.json"))
pd.set_option("display.max_colwidth", 120)
def t(name): return pd.read_csv(TAB / name)
def f(name): display(Image(filename=str(FIG / name), width=850))
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
## 4. Q3: How many new stations does each standard need, and can New York afford them?

`lower_bound` and `new_stations` bracket the true minimum for the whole-network objective. `feasible = False`
means some piece cannot be reached even if every candidate location were upgraded.
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
md("### 4.1 Winter (41% range loss at 20°F with heat; AAA 2019)")
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
md("""
## 7. The cost of robustness, solved exactly

`scripts/run_exact.py` solves the station-placement problem as an integer program (HiGHS via SciPy) with lazy
vertex-separator cuts (`src/evnet/exact.py`). *Connectivity*: every pair of sites that the full candidate graph can join
must be joined. *Robustness*: in addition, no single station failure may separate two sites that the full candidate graph
keeps together after that failure (2-vertex-connectivity relative to what is achievable). `lower_bound` equals
`stations` when the solver proved optimality.
""")
code("""
display(t("exact_cost_curve.csv"))
f("fig10_cost_of_robustness.png")
display(t("exact_subnetworks.csv"))
display(t("subnetwork_structure.csv"))
""")
md("## 8. Trips along real roads, traffic weights and the Hanig et al. coverage measure")
code("""
display(t("trips_feasibility.csv"))
display(t("trips_hardest.csv").head(10))
display(t("trips_border.csv"))
display(t("hanig_consecutive_coverage.csv"))
f("fig11_trip_ranges.png")
""")
md("## 9. How the network grew, 2015-2026")
code("""
display(t("history_by_year.csv"))
f("fig12_history.png")
""")
md("## 10. Reliability: unavailable stations and regional outages")
code("""
display(t("reliability_regional_outages.csv"))
display(t("random_failure_ci.csv"))
""")
md("## 11. Random baselines with 95% confidence intervals and random-geometric-graph theory")
code("""
display(t("baselines_with_ci.csv"))
import json
print(json.dumps(json.load(open(ROOT / "results" / "extended_summary.json")).get("rgg", {}), indent=1))
""")
md("## 12. Learning to place stations (benchmark and GNN)")
code("""
display(t("learning_summary.csv"))
f("fig13_learning.png")
""")
md("""
## 13. Summary (OSRM road distances)

- **Q1.** One network from **43.5 road miles**; weakest link Saranac Lake – Malone, then Malone – Massena (37.2),
  Arkville – Tannersville (34.7) and Chestertown – Indian Lake (33.3). The two large regions join at 26 miles.
- **Q2.** At 30 miles five sites are single points of failure (Chestertown, Peru, Elizabethtown, Monticello, Roscoe),
  four of them Tesla Superchargers. They are isolated (median degree 9 vs 50), not small (median ports 8 vs 4).
  Betweenness attack: 17 removals (2.3%) cut the largest piece to 57% at 50 miles; at 30 miles the two Little Falls
  Thruway plazas alone do it. Degree attack does no more than random failure.
- **Coverage.** At 30–43 miles 99% of sites but 97.3% of city pairs are connected; every pair from 44 miles.
- **Q3.** 0 stations at 45–50 miles, 1 at 40 (Paul Smiths), 2 at 35 (Paul Smiths, Massena), all optimal, at most
  2.2% of the $175M NEVI allocation. 30 miles and below cannot be met from existing public charging locations
  (feasible at 30 with 5 if the new-link detour factor is 1.2 instead of the measured 1.22).
- **Winter.** One network needs a nominal 74 road miles; at 60 miles nominal two stations (Paul Smiths, Massena) suffice.
- **Control.** Better than 98% of 100 random networks at 30 miles; no better than chance on the overall threshold:
  the North Country gap is geographic.
""")

nb["cells"] = C
nb["metadata"]["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
out = ROOT / "notebooks" / "ev_network_final.ipynb"
nbf.write(nb, out)
print("wrote", out)
