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
- Links to new stations use the measured detour factor 1.27, not 1.2; 1.2 is kept as a sensitivity check.
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

The whole network is one piece from the longest link of its minimum spanning tree.
Road distances (notebook v3): 43.5 miles. Calibrated straight-line × 1.27 (this run): 45.6 miles.
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
print(f"nominal standard needed for one network in winter: {S['winter_nominal_needed']:.1f} miles (road: {43.5/0.59:.1f})")
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
## 7. Summary

- **Q1.** One network from 43.5 road miles (45.6 calibrated); weakest link Saranac Lake – Malone. The two large
  regions join at 27 miles; the remaining small pieces are all in the Catskills, Adirondacks and North Country.
- **Q2.** At 30 miles six sites are single points of failure, five on the I-87 Northway corridor. They are
  isolated (median degree 7.5 vs 47), not small (median ports 5 vs 4). Betweenness attack removes them first:
  18 removals (2.4%) cut the largest piece below 90% at 50 miles; degree attack does no more than random failure.
- **Coverage.** At 30–45 miles 98–99% of sites but only 96–97% of city pairs are connected; every pair from 46 miles.
- **Q3.** 0 stations at 50 miles, 1 at 40–45, 3 at 35 (all North Country), at most 3.3% of the $175M NEVI
  allocation. 30 miles and below cannot be met from existing public charging locations (feasible at 30 with 6 if
  the detour factor is 1.2).
- **Winter.** One network needs a nominal 74 road miles; at 60 miles nominal two stations (Paul Smiths, Massena) suffice.
- **Control.** Better than all 100 random networks at 30 miles; no better than chance on the overall threshold:
  the North Country gap is geographic.
""")

nb["cells"] = C
nb["metadata"]["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
out = ROOT / "notebooks" / "ev_network_final.ipynb"
nbf.write(nb, out)
print("wrote", out)
