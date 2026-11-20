# Coverage Is Not Connectivity: Connectivity Thresholds, Critical Stations, and the Cost of Robustness in New York State's EV Fast-Charging Network

Nov 19, 2026

Joubin Zahiri Khameneh · Shamim Sharbaf · Zeinab Davoodmanesh

SSIE 641 Advanced Topics in Network Science · Final project report · Code: [github.com/sharbafshamim/ssie641-ev-network](https://github.com/sharbafshamim/ssie641-ev-network)

## Abstract

Federal guidance stopped requiring fast chargers every 50 miles in August 2025, leaving each state to choose its own spacing standard. Existing studies fix that number in advance; we treat it as the variable. We model New York's 754 public DC fast-charging sites as a network in which two sites are linked when they lie within ε road miles of each other, and trace how its structure changes with ε. The network becomes one piece at 43.5 miles, where its weakest link joins Saranac Lake to Malone in the North Country, and loses its last single point of failure at 46.2 miles: the former 50-mile benchmark is met with a margin, while a 45-mile standard still rests on one two-port charger. At 30 miles, five sites, four of them rural Tesla Superchargers, are single points of failure. They are isolated rather than small (median 9 neighbours against 50, but 8 ports against 4), and if each site is unavailable 14% of the time, as owner surveys suggest, at least one of them is down 53% of the time. A second kind of critical site sits on the seam between eastern and western New York: removing the 17 highest-betweenness sites (2.3%) cuts the largest piece to 57% at 50 miles, while attacks on the best-connected sites do no more harm than random failure. Standards of 45 miles or more need no new stations; 35 to 40 miles need one or two, at most 2.2% of New York's $175 million NEVI allocation; 30 miles or less cannot be reached from existing charging locations, a gap set by geography rather than budget.

## 1. Introduction

Charging policy is usually measured by coverage: the share of drivers who live near a charger. Coverage and travel are different questions. A region can have many chargers and still be impossible to cross if one gap in the middle is longer than a car can drive. Coverage is a local property; being able to finish a trip is a property of the whole network.

The question matters now. The federal NEVI program's earlier guidance asked states to build fast chargers no more than 50 miles apart along designated Alternative Fuel Corridors. The program's codified standards (23 C.F.R. pt. 680) set equipment minimums but never a spacing rule. On August 11, 2025, the U.S. Department of Transportation issued interim final guidance that replaced all earlier guidance and dropped the 50-mile spacing requirement, leaving states to set their own distances ([Electrification Coalition, 2025](https://electrificationcoalition.org/resource/national-electric-vehicle-infrastructure-nevi-program-updated-guidance/); [Atlas Public Policy, 2025](https://www.atlasevhub.com/weekly-digest/nevi-guidance-whats-changed-and-whats-next/)). New York therefore has to choose a number, and we know of no analysis that says what the number should be or what the alternatives would cost.

New York is a good test case. Its 754 fast-charging sites are spread unevenly between the dense downstate region and a sparse, mountainous north. Its winters cut usable range: in AAA's 2019 tests, five electric vehicles at 20°F with the heater on lost 41% of their range on average ([AAA, 2019](https://newsroom.aaa.com/wp-content/uploads/2019/06/AAA-Electric-Vehicle-Range-Testing-Report.pdf)). And the main routes to Canada, I-87 toward Montreal and I-81 toward Ontario, run through the emptiest parts of the state.

We ask three questions:

1. **Q1.** How close is New York's charging network to breaking apart, and where is it closest?
2. **Q2.** Which stations hold the network together, and are they the big stations or the small ones?
3. **Q3.** For each standard the state might set, how many new stations would it need, and can it afford them?

We answer Q3 across a range of standards rather than at one number. The result is a cost curve on which the state can place its own budget and its own choice of standard.

## 2. Related work

**Spacing standards.** The former NEVI guidance fixed the spacing at 50 miles along designated corridors. The European Union's Alternative Fuels Infrastructure Regulation (AFIR) also fixes it in law: fast-charging pools every 60 km (37.3 miles) in each direction on the core trans-European road network, relaxed to 100 km (62.1 miles) on low-traffic roads of the comprehensive network ([European Commission, 2023](https://www.polisnetwork.eu/wp-content/uploads/2023/06/Day1-EuropeanCommission-AFIR.pdf)). We use these standards as reference points on the cost curve.

**Coverage and gaps.** [Hanig et al. (2025)](https://doi.org/10.1038/s41467-024-55696-8) define a consecutive-coverage metric: the traffic-weighted share of roads within 500 miles of a county that can be driven without a charging gap of 50 miles or more. In 2023, 10% of U.S. counties had at least 75% minimum viable coverage; if every designated corridor received fast chargers, 94% would, and the counties left behind are rural. The 50-mile gap length is an assumption of the method.

**Robustness of charging networks.** [Hamim, Chen and Ukkusuri (2025)](https://doi.org/10.1016/j.jtrangeo.2025.104349) build charging-station networks for twelve U.S. states from weighted Voronoi diagrams and measure the loss of global efficiency under random and targeted station removal. New York is among the three most vulnerable states, falling to 0.2 of its original efficiency with fewer than 10% of stations removed, and the most critical stations do not always sit where demand is highest. Efficiency can fall without the network actually splitting, so this ranks stations by importance rather than identifying the ones whose loss would leave a region unreachable. [Zhang, Chen, Tu and Yin (2022)](https://doi.org/10.3390/wevj13070127) build station-proximity networks for Wuhan and Hangzhou at one fixed threshold, and a Texas study finds the same robustness to random failure and vulnerability to targeted removal ([Wang, Kaushik and Zhang, 2024](https://arxiv.org/abs/2404.14452)). [Zhou et al. (2026)](https://doi.org/10.3390/systems14101194) simulate cascading failures in Chengdu, passing a failed station's load to its neighbours, and conclude that a station's structural prominence does not identify the stations whose loss costs the most service. [Bao and Kontou (2026)](https://doi.org/10.1016/j.rser.2025.116144) link FEMA's National Risk Index and 2023 grid-outage records to U.S. charging stations and find severe weather the main cause of outages that affect chargers. All of these fix the rule that links stations in advance and summarise damage with aggregate curves.

**Network-science methods.** For points linked when they lie within distance r of each other, the smallest r at which the graph is connected equals the longest edge of the Euclidean minimum spanning tree (Penrose, 1997); [Penrose and Yang (2024)](https://arxiv.org/abs/2406.00647) treat the k-connectivity threshold, the r at which no k − 1 vertices can disconnect the graph. [Tian, Bashan, Shi and Liu (2017)](https://doi.org/10.1038/ncomms14223) give a general framework for articulation points, the nodes whose removal disconnects a network, and show that removing them fragments infrastructure networks quickly. Spatial null models that keep a network's spatial statistics while randomising the rest separate what geography alone explains ([Wiedermann et al., 2016](https://arxiv.org/abs/1509.09293)).

**Facility location.** The facility-location literature does cost such decisions, most directly through the flow-refueling location model of [Kuby and Lim (2005)](https://doi.org/10.1016/j.seps.2004.03.001), but one vehicle range at a time. Recent extensions add a budget–service trade-off, which on Hubei Province's highways forms a convex frontier with fast-diminishing returns ([Tang, Liu and Song, 2026](https://doi.org/10.3390/wevj17010046)), and queuing in drivers' path choice, tested on California and Québec networks ([Wang et al., 2026](https://www.gerad.ca/en/papers/G-2026-11)). Both still solve for a fixed range or a few vehicle classes.

Three gaps follow, and this project addresses each one:

- No study treats the spacing threshold as the quantity to be determined, which is exactly the question the 2025 guidance now gives states.
- Existing work ranks stations by importance but does not identify the individual stations whose loss cuts a region off.
- No study traces how the number of stations needed changes across the range of standards a state might choose.

## 3. Data

All inputs are public and are included in the code repository.

| Dataset | Source | What we use |
| --- | --- | --- |
| Fast-charging stations, NY, Sep 23, 2026 | [DOE Alternative Fuels Data Center](https://afdc.energy.gov/stations) | 755 open, public stations with DC fast ports; 3,408 fast ports |
| All public charging, NY, Oct 13, 2026 | DOE Alternative Fuels Data Center | 4,756 Level 1/Level 2 locations as candidate sites; 793 fast-charging sites for the robustness check |
| Census 2020 place centroids | [Census Gazetteer files](https://www.census.gov/geographies/reference-files/time-series/geo/gazetteer-files.html) | internal point of 1,293 New York places |
| Census 2020 place population | [Census P.L. 94-171, table P1](https://data.census.gov/) | total population per place |
| Road distances | [OSRM](https://project-osrm.org/) on OpenStreetMap | driving distances for 54,737 site pairs within 60 miles (queried Nov 19, 2026) |

**Stations and sites.** We keep only DC fast charging. A Level 2 charge takes hours, so it does not support travel between cities, and including it would let dense city charging hide the rural pattern. Stations at identical coordinates are merged into one site, which joins only the two New Baltimore Thruway travel plazas: 754 sites. Of these, 661 offer a CCS plug, which most non-Tesla cars use; 87 stations are Tesla-only. ChargePoint (188 stations), Tesla (125) and Electrify America (86) operate the most stations.

**Cities.** We join the Gazetteer to the census counts on place code and keep the 362 places with at least 5,000 people. They hold 15.3 million people: 76% of New York's 20.2 million residents. The rest live in towns outside any village or census-designated place. New York City is a single place of 8.8 million people, so pairs that include it carry 73% of all population-weighted city pairs. We therefore report weighted coverage both with and without New York City.

**Candidate sites.** New fast chargers are placed only at locations that already host public Level 1 or Level 2 charging: open, public, with no DC fast ports. They already have a grid connection and a host business. Merging identical coordinates gives 4,756 candidate locations.

**Distances.** Links between existing sites use driving distances on the OpenStreetMap road network from the public [OSRM](https://project-osrm.org/) routing service. We queried every pair of sites within 60 straight-line miles of each other (54,737 pairs); no analysis uses a link longer than 60 miles. For those pairs more than 5 miles apart, the median ratio of road to straight-line distance is 1.22, with 90% of pairs between 1.07 and 1.58. This is just above the factor of 1.2 from [Ballou, Rahardja and Sakai (2002)](<https://doi.org/10.1016/S0965-8564(01)00044-1>) often used when road distances are not available. The ratio is right-skewed (Figure 7C); on a log scale, where ratios above and below 1 are symmetric, its geometric mean is 1.25. Links that involve a new station or a city centre have no road distance, so they use straight-line distance × 1.22, the measured factor for trips of this length.

**Limits.** The data shows what is installed, not what is working on a given day, so results describe the network as built. Coordinates are reported by operators and are not audited.

## 4. Methods

Every measure below is computed for each spacing standard ε, from a strict standard to a loose one. Code is in `src/evnet/`; `scripts/run_all.py` and `scripts/run_structure.py` reproduce every table and figure in about six minutes.

**Network.** Each site is a node. Two sites are linked when the distance between them is at most ε miles: an epsilon-neighbourhood (random geometric) graph. ε is the spacing standard, the distance a driver must be able to cover between chargers. We build two versions: all 754 sites, and the 661 CCS sites, which is the network a non-Tesla car can use.

**Q1: where the network splits.** For ε from 5 to 60 miles we record the number of connected pieces and the share of sites in the largest piece (a percolation curve). The smallest ε at which the network is one piece equals the longest link of its minimum spanning tree (MST) (Penrose, 1997), so we compute it exactly. The MST's longest links, in order, are the weakest links in the state. We map the pieces just below the main jump. We also compute the *biconnectivity threshold*: the smallest ε at which the network is one piece and has no single point of failure, the k = 2 case of Penrose and Yang (2024). Once the network is connected, adding links can only remove cut vertices, so we find this threshold exactly by bisection over the link lengths. For each city we compute the standard it needs to reach every other city (its eccentricity, a worst case) and the standard it needs to reach cities holding 90% of the other cities' population (a typical case).

**Q2: which stations hold it together.** An articulation point (cut vertex) is a site whose removal alone splits its piece of the network: a single point of failure. For each one we count the sites cut off from the rest. To answer "big or small", we compare critical and non-critical sites on degree (number of neighbours within ε) and on ports (station size). We then test robustness in four ways:

- *Random failure:* each site fails independently with probability p from 0 to 0.6, 100 trials per p. We report the largest piece as a share of all sites (upper bound 1 − p) and as a share of surviving sites (upper bound 1).
- *Targeted attack:* the adaptive version, which removes the top site, recomputes scores and repeats. Scores are degree and betweenness centrality.
- *Robustness index R:* the mean of the largest-piece curve over the removal fractions ([Schneider et al., 2011](https://doi.org/10.1073/pnas.1009440108)).
- *Global efficiency:* the mean of 1/d over all pairs of sites, where d is the number of links on the shortest route and unreachable pairs add 0 ([Latora and Marchiori, 2001](https://doi.org/10.1103/PhysRevLett.87.198701)), the measure used by Hamim et al. (2025). We add an attack by harmonic centrality, a site's sum of 1/d, which, unlike closeness, stays defined when the network is in pieces.

**Where the critical sites sit.** We place the critical sites with five further tools. *k-core numbers* (the largest k such that the site survives repeatedly peeling away sites with fewer than k neighbours) separate a dense core from the periphery. *Betweenness* is computed by number of links, by road miles, and over city-to-city trips, where each pair of cities sends one unit of flow (or P_a × P_b) along its shortest road routes through the network, with Brandes's ([2008](https://doi.org/10.1016/j.socnet.2007.11.001)) algorithm for pair weights; cities are end points only. The *random walk* on the largest piece has a second eigenvalue λ₂ whose relaxation time τ = 1/(1 − λ₂) grows when the piece has a bottleneck; the sign of the second eigenvector splits the piece along that bottleneck, which we score by its normalised cut ([Shi and Malik, 2000](https://doi.org/10.1109/34.868688)). *Leiden communities* ([Traag, Waltman and van Eck, 2019](https://doi.org/10.1038/s41598-019-41695-z)) maximise modularity at resolutions 0.5, 1 and 2, since modularity cannot resolve small groups in a large network ([Fortunato and Barthélemy, 2007](https://doi.org/10.1073/pnas.0605965104)). Finally we compare degree, harmonic, betweenness, eigenvector and PageRank centrality by how much of each score lies within 60 km of New York City.

**Reliability.** The station list records installed equipment. To ask how often the single points of failure are actually unavailable, we let each site be down independently with probability p = 0.03 (the federal rule of 97% uptime per port), 0.14 (the share of owners reporting a failed charging visit in J.D. Power's 2025 study) or 0.275 (the share of non-working connectors in a 2022 audit of the San Francisco Bay Area, [Rempel et al., 2022](https://arxiv.org/abs/2203.16372)). With k cut vertices, the chance that at least one is down is 1 − (1 − p)^k. A simulation with 1,000 draws per p also counts failures that cut surviving sites off from the rest of their piece.

**Coverage.** Connectivity counts sites, so the dense New York City and Long Island area, about a third of all sites, dominates it. Coverage instead counts pairs of cities. A city is attached to every site within ε of its centre, i.e. a driver leaving home with a full battery of usable range ε. Two cities are connected if a site attached to one and a site attached to the other are in the same piece. With A(c) the set of pieces city c touches and P the population:

```latex
\text{coverage}(\varepsilon) = \frac{1}{n(n-1)} \sum_{a \neq b} \mathbf{1}\left[A(a) \cap A(b) \neq \emptyset\right], \qquad \text{weighted: } \frac{\sum_{a \neq b} P_a P_b \, \mathbf{1}[\cdot]}{\sum_{a \neq b} P_a P_b}
```

As a sensitivity check we cap the access distance at 15 miles, so a city far from any charger cannot count as served through a long first leg.

**Q3: how many new stations.** For each ε we ask how few candidate locations must be upgraded to fast charging so that (a) every existing site is in one network, or (b) every pair of cities is connected. This is a node-weighted Steiner tree problem: the pieces (or cities) are terminals, each candidate costs one station, and nodes within ε are linked. Cities are leaves: a city can attach to the network, but a driver cannot recharge there, so a city never joins two pieces. The problem is NP-hard. We use the shortest-path heuristic of [Takahashi and Matsuyama (1980)](https://cir.nii.ac.jp/crid/1570009750462176256): start from the largest piece, repeatedly join the terminal reachable through the fewest new stations, then drop any station that turns out to be redundant. This gives an upper bound. For objective (a) we also report a lower bound: every plan must connect the largest piece to the farthest piece, so the fewest stations on that one path is a floor. If some piece cannot be reached even with every candidate upgraded, the standard is infeasible with existing locations. Links to new stations use the measured 1.22 detour factor; we repeat Q3 at the standard 1.2 as a sensitivity check. We also evaluate the EU's 60 km and 100 km standards.

**Budget.** New York's five-year NEVI formula apportionment is $175 million through September 2026 ([NYSDOT, 2025](https://ebtc.info/wp-content/uploads/2025/05/NEVI-Powerpoint-EBTC-NYSDOT-2025-1-1.pdf)). Per-site cost varies with grid conditions, so we use three levels for a NEVI-style site of four 150 kW ports: $0.6 million (low end of construction estimates), $1.0 million (average total cost of NEVI projects, $0.92–$1.05 million, [Paren via Denver Gazette, 2024](https://www.denvergazette.com/2024/12/31/colorado-granted-another-17-3-million-by-the-federal-government-to-add-more-ev-fast-chargers-c1197d88-c70c-11ef-bf3d-07ca681e048a/)), and $1.92 million (NYSERDA's maximum award of $1.536 million at its 80% cost share, [Barclay Damon, 2024](https://www.barclaydamon.com/alerts/175-million-of-federal-funds-available-for-electric-vehicle-chargers-in-new-york-state)). Results are stated in stations first and dollars second.

**Winter.** We rerun the analysis with effective range 0.59 × ε, the 41% loss AAA measured at 20°F with cabin heat. Real-world winter losses vary, so we also report losses of 20% and 30% (the range of 20–40% reported by the [IEA, 2025](https://iea.blob.core.windows.net/assets/a93f0635-789d-4431-918d-4a64487b7498/Areelectriccarssuitableforlongroadtrips.pdf)) and 37% (a fleet analysis of more than 10,000 vehicles by Recurrent).

**Control.** Some fragility comes from the shape of New York itself. To separate geography from siting decisions, we draw 754 locations at random, without replacement, from the pool of all 5,510 public charging locations (fast plus Level 1/2), 100 times, and compute the same measures, using straight-line distance × 1.22 for real and random networks alike, since random draws have no road distances. The question is: given the sites actually available, was the fast-charging network sited well? A second control keeps the number of fast-charging sites in each 0.5° × 0.5° cell (59 cells) and draws them from that cell's charging locations, in the spirit of the spatial surrogates of Wiedermann et al. (2016). It asks whether sites were well placed within regions, given how many each region received.

**Robustness.** We repeat Q1, Q2 and Q3 on the October 13, 2026 station list, which has 39 more fast-charging sites.


## 5. Q1: When does the network split?

**Answer: New York's fast-charging network is one connected network from 43.5 road miles, and it is closest to breaking in the North Country, between Saranac Lake and Malone.** The 50-mile benchmark of the former federal guidance is already met with 6.5 miles to spare.

The percolation curve has one sharp jump (Figure 1). Up to 25 miles the largest piece holds only 54–56% of sites: the state is split into a downstate-plus-Capital-Region piece (421 sites at 24 miles) and a western-and-central piece (294 sites), plus nine small pieces around Oneonta and Cooperstown, Watertown, Lake Placid, Potsdam and Massena, Malone, Hancock, Roscoe, Arkville and Indian Lake (Figure 2). At 26 miles the two large pieces join and the largest piece jumps to 96% of sites. The small pieces then join one at a time: five pieces at 29–33 miles, three at 35–37, two from 38 to 43 miles, and one from 44 miles.

The network's weakest links are the longest links of its minimum spanning tree. All are rural, in the Adirondacks, the North Country or the Catskills:

| Rank | Link | Road miles | Straight × 1.2 miles |
| --- | --- | --- | --- |
| 1 | Saranac Lake – Malone | 43.5 | 43.1 |
| 2 | Malone – Massena | 37.2 | 33.9 |
| 3 | Arkville – Tannersville | 34.7 | 30.2 (Arkville joins via Roscoe instead) |
| 4 | Chestertown – Indian Lake | 33.3 | 30.3 |
| 5 | Pulaski – Watertown | 28.3 | 32.1 |
| 6 | Monticello – Roscoe | 27.1 | 26.3 |

A straight-line × 1.2 estimate gets the threshold almost right (43.1 vs 43.5 miles) but misses the order of the links behind it. The Catskill road from Arkville to Tannersville winds far more than the straight line suggests and becomes the third-weakest link, while the I-81 link from Pulaski to Watertown is shorter by road than the estimate. Measuring the critical links directly changes which places matter.

For a non-Tesla driver the picture is the same at the top but more fragile in the middle. The CCS-only network also becomes one piece at 44 miles, but at 30 miles it is in 7 pieces rather than 5, because the Northway links from Warrensburg to Indian Lake (37.1 miles) and to North Hudson (36.1 miles) are bridged only by the Tesla-only Chestertown site.

**A margin against single failures.** The network has no single point of failure from 46.2 miles. Between 43.5 and 46.2 miles one site, the two-port Upstate Auto charger in Saranac Lake, is the only link to Malone. The former 50-mile benchmark is therefore met with 3.8 miles to spare even if any one site fails, while a 45-mile standard is met only as long as that one charger works. For CCS drivers the margin begins at 47.5 miles, once Warren Ford in Warrensburg stops being the only link north. With straight-line distance × 1.2 the two thresholds are 43.1 and 45.7 miles.

**Worst case and typical case.** All 362 cities need the full 43.5 miles to reach every other city: on a network with one bottleneck, every city's eccentricity is set by the same weak link. To reach cities holding 90% of the other cities' population, the median city needs only 26 miles. Just five cities need 43.5 miles even for that (Massena, Ogdensburg, Malone, Potsdam and Canton), and Watertown and Fort Drum need 28.5.

![Percolation curve and number of pieces by spacing standard](../results/figures/fig1_percolation.png)

*Figure 1. Share of sites in the largest piece (A) and number of pieces (B) by spacing standard. The dotted line marks the former 50-mile benchmark.*

![Pieces of the network at a 24-mile standard](../results/figures/fig2_pieces_24mi.png)

*Figure 2. The pieces of the network at 24 miles, just below the main jump. The eight largest are coloured.*

## 6. Q2: Which stations hold the network together?

**Answer: a handful of isolated rural sites, mostly Tesla Superchargers in the Adirondacks and Catskills, and the Thruway service plazas of the Mohawk Valley, not the big downstate hubs.** They are "small" only by degree, the number of neighbours. By ports they are typical or larger.

### 6.1 Single points of failure

At a 30-mile standard five sites are cut vertices (Figure 3). Each one alone cuts a region off from the rest of the state:

| Site | Operator | Neighbours | Ports | Sites cut off |
| --- | --- | --- | --- | --- |
| Tesla Supercharger, Chestertown | Tesla | 8 | 6 | 24 |
| Tesla Supercharger, Peru | Tesla | 12 | 8 | 11 |
| Egglefield Bros, Elizabethtown | Ford dealer | 9 | 2 | 8 |
| Tesla Supercharger, Monticello | Tesla | 9 | 12 | 3 |
| Tesla Supercharger, Roscoe | Tesla | 3 | 8 | 2 |

Three are on the I-87 Northway corridor north of Lake George and two on NY-17 in the Catskills. All five are in the bottom 11% of sites by degree: their median is 9 neighbours against 50 for all sites. Yet their median port count is 8 against 4, and Monticello's 12 ports put it in the top 9% of sites. The pattern holds across standards: at 25 to 45 miles the critical sites' median degree is 6 to 24 against 42 to 73 for all sites, while their median ports range from 2 to 8 against 4. Degree measures where a site is, not how big it is, and here it is a poor guide to importance. Their k-core numbers say the same: at 30 miles the five have a median core number of 6 (range 2–10) against 40 for all sites, in the bottom 5% on average. On complementary cumulative distributions they sit at the bottom of the degree distribution and near the top of the port distribution (Figure 7A–B). The same five sites appear with straight-line distances, a useful check on the road-distance run.

The number of cut vertices falls from 12 to 16 at 20–26 miles to two or fewer from 31 miles, and to none from 46.2 miles. At 44–46 miles one site remains critical: the two-port Upstate Auto charger in Saranac Lake, the only link to Malone. For CCS drivers, at 45 miles Warren Ford in Warrensburg, a two-port dealer charger, is the only link between the Capital Region and 28 Adirondack and North Country sites.

![Single points of failure on a map](../results/figures/fig3_critical_sites.png)

*Figure 3. Single points of failure: all sites at 30 miles (left) and CCS sites at 45 miles (right). Labels give the number of sites each one cuts off.*

### 6.2 Random failure and targeted attack

The network tolerates random failure well and targeted attack on its bridges badly (Figure 4).

| Standard | Random failure R | Attack by degree R | Attack by betweenness R | Largest piece after removals |
| --- | --- | --- | --- | --- |
| 50 miles | 0.698 | 0.696 | 0.240 | 57% after 17 betweenness removals (98% after 17 by degree) |
| 30 miles | 0.638 | 0.633 | 0.148 | 57% after 2 betweenness removals (99% after 2 by degree) |

R is the mean largest-piece share over 0 to 60% of sites removed; its upper bound is 0.70. Under random failure at 50 miles the network stays at that bound: even when 60% of sites fail, 98% of the survivors are still in one piece (68% at 30 miles). An attack by degree removes busy Bronx, Queens and Long Island sites first and does no more damage than random failure. An attack by betweenness removes the corridor sites that link regions: Schoharie, Arkville and Roscoe in the Catskills, then Chittenango, New Baltimore, Ravena, and the Thruway plazas at Little Falls, Herkimer and Frankfort in the Mohawk Valley. At 50 miles, 17 such removals (2.3% of sites) cut the largest piece to 57%. At 30 miles the first two removals are both Little Falls service plazas, and they alone split the state between east and west. This matches Hamim et al.'s finding that targeted removal is far more damaging than random removal, and here the damage is concentrated in a few identifiable sites.

![Random failure versus targeted attack](../results/figures/fig4_failure_attack.png)

*Figure 4. Largest piece as a share of all sites under random failure (100 trials per p), attack by degree, and attack by betweenness, at 50 and 30 miles.*

Measured by global efficiency, the measure of Hamim et al., the order of the strategies is the same (Figure 5). Removing the top 5% of sites by betweenness leaves 64% of the original efficiency at 50 miles and 50% at 30 miles, against 90% under random failure. At 50 miles efficiency falls to 0.2 of its original value only after 26% of sites are removed by betweenness, 50% by degree and 56% at random. Hamim et al. reach that level for New York with fewer than 10% removed; their networks link stations whose weighted Voronoi cells touch, a much sparser rule than ours, so the levels are not comparable, but the ranking of the strategies is. Attack by harmonic centrality behaves like attack by degree: both remove dense downstate sites first.

![Global efficiency under failure and attack](../results/figures/fig9_efficiency.png)

*Figure 5. Global efficiency relative to the intact network under random failure (30 random orders) and adaptive attack by degree, harmonic centrality and betweenness, at 50 and 30 miles. The dotted line is the 0.2 collapse level used by Hamim et al. (2025).*

### 6.3 Two kinds of critical site: edges and seams

**Answer: the single points of failure are at the edges of the network; the high-betweenness sites are on a seam between eastern and western New York, and three different methods find the same seam.** The edge sites have low core numbers and few neighbours and sit at the end of a chain into the Adirondacks or the Catskills. None of them is in the top ten by any version of betweenness.

- *Spectral split.* The second eigenvector of the random walk splits the 50-mile network into 438 eastern and 316 western sites with only 78 links between them (normalised cut 0.0055). The sites on the cut are at Oneonta, Cooperstown, Amsterdam, Fultonville, Johnstown, Little Falls, Herkimer, Ellenville, Monticello and Roscoe (Figure 6B). At 30 miles the cut runs through the Capital Region: Schenectady, Amsterdam, Fultonville and Schoharie.
- *Communities.* Leiden finds six communities at 50 miles (modularity 0.61). 14 of the 17 highest-betweenness sites lie on a community boundary, against 49% of all sites. At 30 miles 13 of the 17 do, but only one of the five cut vertices. Resolution 0.5 gives similar groups; resolution 2 breaks the network into dozens of fragments, so we do not use it.
- *Betweenness by road miles and city pairs.* Weighting by road miles or counting city-to-city trips moves the ranking toward the Catskills at 50 miles (Roscoe, Monticello, Castle Creek) and toward the Hudson Valley and the Thruway at 30 miles (Ravena, Fultonville, Fishkill, Little Falls). The rank correlation with plain betweenness is only 0.38–0.43, so the choice of weight changes which sites a state would protect. Population weighting puts three New York City sites first, because the city is a single place of 8.8 million people whose trips begin and end on its own chargers; we therefore use the unweighted city-pair version.

The random-walk relaxation time shows the same split from the other side (Figure 6A). It falls steadily with ε, from 2,473 steps at 30 miles to 414 at 50, with no jump at 43.5 miles, because joining the seven North Country sites barely changes the main east–west bottleneck. A new station at Paul Smiths connects the North Country at 40 miles but leaves the relaxation time unchanged to four digits. The spectral gap measures the seam; the minimum spanning tree and the cut vertices measure the edges. Protecting one kind of site does not protect the other.

**Why degree misleads.** On this network, scores built from walks concentrate where sites are dense. 21% of sites lie within 60 km of New York City, but they hold 78% of the eigenvector score and 42% of the degree, and every one of the top ten sites by degree, harmonic centrality or eigenvector centrality is there. Betweenness puts 9% of its score there and none of its top ten; PageRank, which splits a site's score among its neighbours, is less concentrated (25%). The same localisation of eigenvector centrality near New York City appears on the state's highway interchanges. The friendship paradox appears too: at 30 miles a site's neighbours have 61 neighbours on average against 57 for sites themselves (103 against 98 at 50 miles), so following links leads to denser places than choosing a site at random. Both explain why the degree attack removes redundant downstate sites and does no more damage than random failure.

![Random-walk relaxation time and spectral split](../results/figures/fig10_spectral.png)

*Figure 6. (A) Relaxation time 1/(1 − λ₂) of a random walk on the largest piece, by spacing standard. (B) The split of the 50-mile network by the sign of the second eigenvector; ringed sites are on the cut.*

![Distributions](../results/figures/fig11_distributions.png)

*Figure 7. (A) Neighbours within 30 miles and (B) fast-charging ports, as complementary cumulative distributions on log–log axes, for all sites and the five single points of failure at 30 miles. (C) Road distance divided by straight-line distance for site pairs more than 5 miles apart, in logarithmic bins (bar area is the share of pairs).*

### 6.4 Coverage is not connectivity

Measured by people and cities instead of sites, the network looks better at loose standards and worse at strict ones (Figure 8). Half of the 362 cities have a fast charger within 1.9 miles of their centre; the farthest are Ogdensburg (28.6 miles), Norwich (20.2), Albion (18.3), Medina (17.9) and Port Jervis (16.8).

| Standard | Connectivity (sites) | Coverage (city pairs) | Coverage, population-weighted | Weighted, without NYC | Coverage, access ≤ 15 mi |
| --- | --- | --- | --- | --- | --- |
| 20 miles | 0.536 | 0.607 | 0.661 | 0.552 | 0.596 |
| 30 miles | 0.988 | 0.973 | 0.992 | 0.987 | 0.951 |
| 40 miles | 0.991 | 0.973 | 0.992 | 0.987 | 0.951 |
| 50 miles | 1.000 | 1.000 | 1.000 | 1.000 | 0.973 |

At 30 to 43 miles 99% of sites are connected, yet 2.7% of city pairs are not: the cut-off North Country piece holds only a few sites but several cities (Malone, Massena, Potsdam, Canton, Ogdensburg). Every pair of cities is connected from 44 miles. With access capped at 15 miles coverage never reaches 1, because Ogdensburg, Norwich, Albion, Medina and Port Jervis have no charger within 15 miles: for those cities the problem is access, not spacing.

Under failure, coverage separates the two kinds of attack even more clearly. At 50 miles, random failure and degree attack leave coverage at R = 0.99, but betweenness attack cuts it to 0.47 (0.56 population-weighted). What breaks is the link between regions, not service within a region.

![Connectivity versus coverage by spacing standard](../results/figures/fig5_coverage_curve.png)

*Figure 8. Connectivity (share of sites) versus city-pair coverage, plain, population-weighted, and with city access capped at 15 miles.*

### 6.5 How often is a single point of failure down?

**Answer: at a 30-mile standard, probably often.** If each site is unavailable independently with probability p:

| Unavailability p | Source | At least one of the 5 cut vertices down, 30 miles | Some piece splits, simulated, 30 miles | At least one of the 2 down, 35 miles | Saranac Lake down, 45 miles |
| --- | --- | --- | --- | --- | --- |
| 0.03 | NEVI 97% uptime rule | 14% | 16% | 6% | 3% |
| 0.14 | J.D. Power 2025, failed visits | 53% | 59% | 26% | 14% |
| 0.275 | Rempel et al. 2022, Bay Area audit | 80% | 91% | 47% | 28% |

The simulation counts any failure that cuts surviving sites off from the rest of their piece, including sites whose only neighbours fail, so it is a little higher than the formula; at 40 miles, where there is no cut vertex, it still gives 6% at p = 0.14. Even under the federal uptime rule, which covers only NEVI-funded ports, a 30-mile network would be split about one day in seven. Few sites are cut off at a time (an expected 1.4 to 13 of 754), but they are the only fast chargers in their region.

## 7. Q3: How many new stations does each standard need, and can New York afford them?

**Answer: none at 45 or 50 miles, one or two between 35 and 40 miles, all in the North Country, at a small fraction of the federal budget. At 30 miles and below, money is not the constraint: no chain of existing public charging locations crosses the North Country gap.**

### 7.1 The cost curve

The table gives the stations needed to put every existing site into one network (objective a), with the heuristic's lower and upper bounds and the cost at the central $1.0 million per site (Figure 9).

| Standard | Pieces now | Lower bound | New stations | Where (upgraded Level 2 locations) | Central cost | Share of $175M |
| --- | --- | --- | --- | --- | --- | --- |
| 50 miles | 1 | 0 | 0 | none needed | $0 | 0% |
| 45 miles | 1 | 0 | 0 | none needed | $0 | 0% |
| 40 miles | 2 | 1 | 1 | Paul Smiths | $1.0M | 0.6% |
| 35 miles | 3 | 2 | 2 | Paul Smiths, Massena | $2.0M | 1.1% |
| 30 miles | 5 | 1 | 2+, infeasible | Windham, Newcomb; Malone–Massena–Potsdam unreachable | — | — |
| 25 miles | 10 | 4 | 8+, infeasible | 8 sites, Catskills to Tug Hill; Malone–Massena–Potsdam unreachable | — | — |
| 20 miles | 26 | 3 | 10+, infeasible | 10 sites; much of the North Country unreachable | — | — |

At every feasible standard the upper bound equals the lower bound, so these counts are optimal, not just upper bounds. Across the cost range of $0.6–$1.92 million per site, the feasible standards cost between $0 and $3.8 million, at most 2.2% of New York's NEVI allocation, which could fund 91 to 291 such sites. Paul Smiths, on the road north from Saranac Lake toward Malone, appears at both 35 and 40 miles: a single station there closes the state's weakest link. The EU's 60 km standard (37.3 miles) needs that one station too, which is also its lower bound; its 100 km standard (62.1 miles) needs none.

The stricter standards fail for a physical reason. At 30 miles and below, the piece around Malone, Massena and Potsdam cannot be reached even if every one of the 4,756 public Level 1/Level 2 locations were upgraded: no chain of existing locations crosses the gap within the standard. Meeting those standards needs new host sites, which is a siting and grid-connection problem rather than a budget problem.

Two checks bear on this conclusion:

- *Detour factor.* With the standard 1.2 factor instead of the measured 1.22 for new links, 30 miles becomes feasible with five stations (Windham, Newcomb, Canton, Gouverneur, Hogansburg), and the other counts do not change. Whether 30 miles is reachable at all turns on less than a mile of road in the St. Lawrence Valley; a site-specific road survey of those candidate locations would settle it.
- *Coverage objective.* Connecting every pair of cities rather than every site needs 0 stations at 45–50 miles, 1 at 40 (Paul Smiths) and 3 at 35 (Gouverneur, Paul Smiths, Canton), and is infeasible at 30 miles and below. At the 1.2 factor it is feasible at 30 miles with four stations (Gouverneur, Ogdensburg, Waddington, Hogansburg).

![Cost curve: stations needed and share of the NEVI allocation](../results/figures/fig6_cost_curve.png)

*Figure 9. (A) New stations needed for each standard, for the whole network and for all city pairs; red circles mark standards that cannot be met from existing locations. (B) Cost of connecting the whole network as a share of New York's $175M NEVI allocation; grey bars are partial counts for infeasible standards.*

### 7.2 Winter

Winter makes the network need a much longer nominal range (Figure 10). With 41% less range, a driver needs a nominal 74 road miles between chargers for the whole network to be connected. At the old 50-mile benchmark, the winter-effective range of 29.5 miles leaves the network in five pieces and 2.7% of city pairs disconnected, and the North Country gap cannot be closed from existing locations. A nominal 60-mile standard (35.4 effective) needs two winter stations, at Paul Smiths and Massena; a 70-mile standard needs one, at Ogdensburg. The station at Paul Smiths does double duty: it tightens the summer standard and keeps the North Country connected in winter. Winter losses vary, and so does the answer: with 20% to 41% less range, the nominal standard needed for one network is 54 to 74 miles, and 58 to 78 miles for a network with no single point of failure. At the old 50-mile benchmark the network is in two pieces with a 20% loss and in five with 37% or more.

![City-pair coverage in mild weather and in winter](../results/figures/fig7_winter.png)

*Figure 10. City-pair coverage by nominal spacing standard, in mild weather and with a 41% winter range loss.*

## 8. Control and robustness

### 8.1 Is the network well sited?

**Answer: yes along the corridors, no better than chance at the edges.** We compare the real network with 100 random networks of 754 locations drawn from all 5,510 public charging locations in New York (Figure 11). Both use straight-line distance × 1.22, so the real network's threshold here is 43.8 miles.

| Measure | Real network | Random mean | Random 5th–95th percentile | Random draws that do better |
| --- | --- | --- | --- | --- |
| Connectivity threshold (miles) | 43.8 | 45.1 | 36.6–53.9 | 43% |
| Coverage at 30 miles | 0.962 | 0.770 | 0.599–0.956 | 2% |
| Weighted coverage at 30 miles | 0.984 | 0.809 | 0.654–0.980 | 2% |
| Pieces at 30 miles | 5 | 8.4 | 5–12 | 1% |
| Single points of failure at 30 miles | 5 | 8.5 | 4–13 | 7% |
| Coverage at 40 miles | 0.973 | 0.971 | 0.956–1.000 | 43% |

At 30 miles the real network beats 98% of random draws on coverage and 99% on the number of pieces. Random draws often split the state into two large halves; the real network avoids that because fast chargers were placed along the Thruway and the other main corridors. The overall threshold, by contrast, is ordinary: 43% of random networks connect the whole state at a shorter distance, and coverage at 40 miles is the same as chance. Random networks do not close the North Country gap either, because the available locations are where people and businesses are. The remaining weak point is therefore geographic, which agrees with Q3: closing it needs new host sites, not better choices among existing ones.

**Within regions.** When the random draws keep the number of fast-charging sites in each of the 59 half-degree cells, they come much closer to the real network. Their mean coverage at 30 miles is 0.915 against 0.962, and 18% of them do better (2% in the unconstrained control); 21% have fewer pieces at 30 miles, and 60% connect the state at a shorter distance. Most of the corridor advantage therefore comes from how many chargers each region received, and less from where inside each region they were placed.

![Real network versus 100 random networks](../results/figures/fig8_control.png)

*Figure 11. The real network (red line) against 100 random networks drawn from all 5,510 public charging locations.*

### 8.2 Newer station data

The October 13, 2026 station list has 793 fast-charging sites, 39 more than September. Of the 48 stations added, 18 are EVolve NY stations opened in 2020–2022 that were missing from the September extract, including Keene, Schroon Lake, Westport and Liberty in the Adirondacks and Catskills. The new sites have no road distances, so this comparison uses straight-line distance × 1.22 for both lists. On that basis the headline results do not change: the threshold stays at 43.8 miles, the weakest link is still Saranac Lake – Malone, and Q3 needs the same 3, 1 and 1 stations at 30, 35 and 40 miles for both lists. These counts differ from Section 7.1 (infeasible, 2 and 1) because of the distance model, not the data: on road distances the North Country gaps are slightly longer, which makes 30 miles infeasible and adds Massena at 35 miles. The critical sites change at the edges: at 30 miles Elizabethtown is no longer a cut vertex, and at 35 miles Chestertown drops out, most likely because the new Schroon Lake site gives the Northway corridor a second route past it.

### 8.3 Other checks

- *Population weighting.* Removing New York City's weight lowers weighted coverage at 20 miles from 0.66 to 0.55 but changes it by less than 0.01 from 30 miles up. The conclusions do not depend on New York City's size.
- *Plug type.* The CCS-only network has the same threshold and the same weakest link but more pieces at strict standards, and at 45 miles its most critical site is a two-port dealer charger in Warrensburg.
- *Distance model.* A straight-line × 1.2 estimate gives a threshold within 0.4 miles of the road value and the same five single points of failure at 30 miles. What it misses is the order of the weaker links (Section 5).

## 9. Discussion

**What a state should take from this.** The choice of standard is a choice about one region. Apart from one Catskill link (Arkville to Tannersville, 34.7 miles), every decision between 30 and 50 miles is about the Adirondacks and the North Country. At 45 to 50 miles the state has nothing to build. At 35 to 40 miles it needs one or two stations, at Paul Smiths and Massena, for 1–2% of its NEVI allocation. At 30 miles or less it needs new host sites where none exist today. A state that set its standard on coverage figures alone would miss this, because the cut-off region holds only about 1% of sites and 3% of city pairs.

**Protecting what exists.** The sites that matter most are not the ones a capacity-based or demand-based plan would protect. A few rural Superchargers, a two-port dealer charger in Elizabethtown and the Thruway service plazas at Little Falls carry the connection between regions. Reliability requirements, maintenance priority and backup power at these few sites would protect statewide travel more than adding ports where chargers are already dense. Betweenness, not degree, is the measure that finds the seam sites; cut vertices and the minimum spanning tree find the edge sites, and the two lists do not overlap. With the reliability that owner surveys report, at least one of the five edge sites at 30 miles is down about half the time. Several of them are Tesla-only, so opening them to other cars would also remove the CCS network's extra fragility.

**How this compares.** Our results agree with Hamim et al. (2025) that targeted removal is far worse than random failure and that critical stations are not where demand is, and they locate that fragility: a few corridor and rural sites, not the dense core. They also sharpen Zhou et al.'s (2026) point that structural prominence is not service importance: here the most prominent sites by degree or eigenvector centrality are the least important for keeping the state connected. Where Tang et al. (2026) find a smooth, convex budget–service frontier, New York's cost curve is a step: no stations, then one or two, then no feasible plan at any budget.

**Coverage is not connectivity.** The two measures disagree in both directions. At 30–43 miles 99% of sites are connected while 2.7% of city pairs are not; with a 15-mile access cap, five cities stay unserved at any spacing. A spacing standard cannot fix an access gap, and a coverage target cannot fix a spacing gap.

### Limitations

- *Distances.* Road distances come from OSRM's public demo server on current OpenStreetMap data, for pairs within 60 straight-line miles, stored to 0.05 miles. Links to candidate sites and city centres use straight-line distance × 1.22, and whether 30 miles is feasible depends on that factor (Section 7.1).
- *Installed, not working.* The station list records installed equipment. Section 6.5 treats failures as independent with survey-based rates; storms and grid outages make them correlated in space, which would raise the chance that neighbouring critical sites fail together.
- *Measures.* Global efficiency here counts links on an ε-graph, while Hamim et al. use Voronoi adjacency, so only the order of strategies is comparable. Betweenness rankings depend on the weight used (Section 6.3).
- *Plug access.* We treat Tesla-only sites as unusable for other cars. Some are being opened to other brands, which the data does not record.
- *Heuristic.* Q3 counts at infeasible standards are partial; at feasible standards they match the lower bound and are optimal.
- *Cost.* Per-site costs are national NEVI averages and a NYSERDA award cap, not New York site estimates; grid upgrades in remote areas may cost more.
- *Network model.* A link means two sites are within range, not that a driver would route that way, and traffic is not modelled.

### Conclusion

New York's fast-charging network already meets the former 50-mile federal benchmark, and the 45-mile standard as well. Along its main corridors it is better sited than 98% of random placements from the same locations. Its weak points are a few isolated rural chargers and Thruway plazas that link the regions, and one geographic gap in the North Country that no existing public charging location can bridge at strict standards. Protecting the corridor chargers and adding one or two North Country stations, starting at Paul Smiths, would do more for statewide travel than any number of chargers where chargers are already dense.

**Future work.** Measure road distances to the candidate sites as well; add station-level reliability data so that "installed" can be replaced by "working"; and model correlated failures from storms and grid outages, for example by overlaying FEMA's National Risk Index on the critical sites (Bao and Kontou, 2026).

## Code and data availability

All code, input data, result tables and figures are at [github.com/sharbafshamim/ssie641-ev-network](https://github.com/sharbafshamim/ssie641-ev-network). `python scripts/run_all.py` and `python scripts/run_structure.py` rebuild every table and figure; `notebooks/ev_network_final.ipynb` walks through the results question by question.

## Acknowledgements

Station data is provided by the U.S. Department of Energy's Alternative Fuels Data Center; population data by the U.S. Census Bureau; road distances by the OSRM project on OpenStreetMap data. An AI assistant (Claude, Anthropic) was used to review the literature, check the regulatory and cost sources, refactor and extend the analysis code, and draft this report. The authors are responsible for the research questions, the framing, and the final interpretations.

## References

- American Automobile Association. (2019). *AAA electric vehicle range testing.* <https://newsroom.aaa.com/wp-content/uploads/2019/06/AAA-Electric-Vehicle-Range-Testing-Report.pdf>
- Atlas Public Policy. (2025). NEVI guidance: What's changed and what's next. *EV Hub Weekly Digest.* <https://www.atlasevhub.com/weekly-digest/nevi-guidance-whats-changed-and-whats-next/>
- Ballou, R. H., Rahardja, H., & Sakai, N. (2002). Selected country circuity factors for road travel distance estimation. *Transportation Research Part A, 36*(9), 843–848. <https://doi.org/10.1016/S0965-8564(01)00044-1>
- Bao, W., & Kontou, E. (2026). Electric vehicle charging stations at risk from hazardous events and power outages: Analytics and resilience implications. *Renewable and Sustainable Energy Reviews, 226,* 116144. <https://doi.org/10.1016/j.rser.2025.116144>
- Barclay Damon LLP. (2024). $175 million of federal funds available for electric vehicle chargers in New York State. <https://www.barclaydamon.com/alerts/175-million-of-federal-funds-available-for-electric-vehicle-chargers-in-new-york-state>
- Brandes, U. (2008). On variants of shortest-path betweenness centrality and their generic computation. *Social Networks, 30*(2), 136–145. <https://doi.org/10.1016/j.socnet.2007.11.001>
- Csardi, G., & Nepusz, T. (2006). The igraph software package for complex network research. *InterJournal, Complex Systems,* 1695. <https://igraph.org>
- Electrification Coalition. (2025). National Electric Vehicle Infrastructure (NEVI) program updated guidance. <https://electrificationcoalition.org/resource/national-electric-vehicle-infrastructure-nevi-program-updated-guidance/>
- European Commission. (2023). *AFIR: Targets for light-duty vehicle recharging infrastructure* (Regulation (EU) 2023/1804) [Presentation]. <https://www.polisnetwork.eu/wp-content/uploads/2023/06/Day1-EuropeanCommission-AFIR.pdf>
- Federal Highway Administration. (2025). National Electric Vehicle Infrastructure Formula Program guidance (interim final). 90 Fed. Reg. 39025 (Aug. 13, 2025). Docket No. FHWA-2025-0010.
- Fortunato, S., & Barthélemy, M. (2007). Resolution limit in community detection. *Proceedings of the National Academy of Sciences, 104*(1), 36–41. <https://doi.org/10.1073/pnas.0605965104>
- Hamim, O. F., Chen, X., & Ukkusuri, S. V. (2025). Developing a framework for resilience assessment of electric vehicle charging station networks. *Journal of Transport Geography, 128,* 104349. <https://doi.org/10.1016/j.jtrangeo.2025.104349>
- Hanig, L., Ledna, C., Nock, D., Harper, C. D., Yip, A., Wood, E., & Spurlock, C. A. (2025). Finding gaps in the national electric vehicle charging station coverage of the United States. *Nature Communications, 16,* 561. <https://doi.org/10.1038/s41467-024-55696-8>
- International Energy Agency. (2025). *Are electric cars suitable for long road trips?* <https://iea.blob.core.windows.net/assets/a93f0635-789d-4431-918d-4a64487b7498/Areelectriccarssuitableforlongroadtrips.pdf>
- J.D. Power. (2025). *2025 U.S. Electric Vehicle Experience (EVX) Public Charging Study* [Press release]. <https://www.jdpower.com/business/press-releases/2025-us-electric-vehicle-experience-evx-public-charging-study>
- Kuby, M., & Lim, S. (2005). The flow-refueling location problem for alternative-fuel vehicles. *Socio-Economic Planning Sciences, 39*(2), 125–145. <https://doi.org/10.1016/j.seps.2004.03.001>
- Latora, V., & Marchiori, M. (2001). Efficient behavior of small-world networks. *Physical Review Letters, 87*(19), 198701. <https://doi.org/10.1103/PhysRevLett.87.198701>
- Luxen, D., & Vetter, C. (2011). Real-time routing with OpenStreetMap data. *Proceedings of the 19th ACM SIGSPATIAL GIS,* 513–516. <https://project-osrm.org>
- National Electric Vehicle Infrastructure Standards and Requirements, 23 C.F.R. pt. 680 (2023). 88 Fed. Reg. 12752. <https://www.govinfo.gov/content/pkg/FR-2023-02-28/html/2023-03500.htm>
- New York State Department of Transportation. (2025). *NEVI formula program update* (Eastern Border Transportation Coalition, May 2025). <https://ebtc.info/wp-content/uploads/2025/05/NEVI-Powerpoint-EBTC-NYSDOT-2025-1-1.pdf>
- New York State Energy Research and Development Authority. (n.d.). National Electric Vehicle Infrastructure (NEVI) Program. <https://www.nyserda.ny.gov/All-Programs/Charging-Station-Programs/National-Electric-Vehicle-Infrastructure-Program>
- Paren, as reported by Denver Gazette. (2024, Dec. 31). Colorado granted another $17.3 million by the federal government to add more EV fast-chargers. <https://www.denvergazette.com/2024/12/31/colorado-granted-another-17-3-million-by-the-federal-government-to-add-more-ev-fast-chargers-c1197d88-c70c-11ef-bf3d-07ca681e048a/>
- Penrose, M. D. (1997). The longest edge of the random minimal spanning tree. *Annals of Applied Probability, 7*(2), 340–361.
- Penrose, M. D., & Yang, X. (2024). Fluctuations of the connectivity threshold and largest nearest-neighbour link. arXiv:2406.00647. <https://arxiv.org/abs/2406.00647>
- Recurrent. (2025). Winter range data from more than 10,000 electric vehicles, as reported by *Auto Service World.* <https://www.autoserviceworld.com/?p=281243>
- Rempel, D., Cullen, C., Bryan, M. M., & Cezar, G. V. (2022). Reliability of open public electric vehicle direct current fast chargers. arXiv:2203.16372. <https://arxiv.org/abs/2203.16372>
- Schneider, C. M., Moreira, A. A., Andrade, J. S., Havlin, S., & Herrmann, H. J. (2011). Mitigation of malicious attacks on networks. *Proceedings of the National Academy of Sciences, 108*(10), 3838–3841. <https://doi.org/10.1073/pnas.1009440108>
- Shi, J., & Malik, J. (2000). Normalized cuts and image segmentation. *IEEE Transactions on Pattern Analysis and Machine Intelligence, 22*(8), 888–905. <https://doi.org/10.1109/34.868688>
- Takahashi, H., & Matsuyama, A. (1980). An approximate solution for the Steiner problem in graphs. *Mathematica Japonica, 24*(6), 573–577.
- Tang, C., Liu, H., & Song, G. (2026). Designing heterogeneous electric vehicle charging networks with endogenous service duration. *World Electric Vehicle Journal, 17*(1), 46. <https://doi.org/10.3390/wevj17010046>
- Tian, L., Bashan, A., Shi, D.-N., & Liu, Y.-Y. (2017). Articulation points in complex networks. *Nature Communications, 8,* 14223. <https://doi.org/10.1038/ncomms14223>
- Traag, V. A., Waltman, L., & van Eck, N. J. (2019). From Louvain to Leiden: Guaranteeing well-connected communities. *Scientific Reports, 9,* 5233. <https://doi.org/10.1038/s41598-019-41695-z>
- U.S. Census Bureau. (2021). *2020 Census Redistricting Data (P.L. 94-171), table P1;* *2020 Gazetteer files, places.* <https://www.census.gov/geographies/reference-files/time-series/geo/gazetteer-files.html>
- U.S. Department of Energy, Alternative Fuels Data Center. (2026). Alternative fueling station locator. Retrieved September 23 and October 13, 2026. <https://afdc.energy.gov/stations>
- Wang, J., Kaushik, H. D., & Zhang, J. (2024). Optimal planning of electric vehicle charging stations: Integrating public charging networks and transportation congestion. arXiv:2404.14452. <https://arxiv.org/abs/2404.14452>
- Wang, W., Dems, A., Adulyasak, Y., Arslan, O., & Cordeau, J.-F. (2026). *Electric vehicle fast-charging facility location with endogenous queuing in path selection* (Les Cahiers du GERAD G-2026-11). HEC Montréal. <https://www.gerad.ca/en/papers/G-2026-11>
- Wiedermann, M., Donges, J. F., Kurths, J., & Donner, R. V. (2016). Spatial network surrogates for disentangling complex system structure from spatial embedding of nodes. arXiv:1509.09293. <https://arxiv.org/abs/1509.09293>
- Zhang, P., Chen, J., Tu, L., & Yin, L. (2022). Layout evaluation of new energy vehicle charging stations: A perspective using the complex network robustness theory. *World Electric Vehicle Journal, 13*(7), 127. <https://doi.org/10.3390/wevj13070127>
- Zhou, Duan, Liu, Liu, & Wang. (2026). Robustness of a POI-derived urban EV charging-station network under capacity-constrained cascading failures: A scenario analysis of six districts in Chengdu, China. *Systems, 14*(10), 1194. <https://doi.org/10.3390/systems14101194>
