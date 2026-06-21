# Section 3 — Lincoln Case Study: Context & GIS Analysis

**Author / Role:** Ly — *Lincoln Context & GIS Analyst (supporting realism and location-specific details).*
**Purpose:** Provide the real-world constraints (urban layout, airspace, weather, demand) and a **data-driven GIS method** that derives candidate vertiport locations — so the technical sections are grounded in an actual operating environment, not guesswork.

> **Method in one line:** *map real demand → overlay real constraints → score the space → derive vertiports.* We do **not** hand-pick sites; the candidate sites come out of a suitability model fed with live OpenStreetMap data.

---

## 3.1 Why Lincoln?

Lincoln is a compact historic city in Lincolnshire, East Midlands (England), population ~100,000. It is a strong realism test case for Urban Air Mobility because it packs almost every UAM constraint into a small footprint:

- A dense **historic core** with a protected skyline (Lincoln Cathedral and Castle on a steep ridge).
- **Heavily constrained military airspace** — "Bomber County", with active/former RAF airfields close to the city.
- **Mixed terrain** — the limestone ridge ("Lincoln Edge") gives a sharp uphill/downhill split and local wind effects.
- Real **multimodal hubs** (rail, bus, park-and-ride) and a clear **medical** use-case (Lincoln County Hospital).

City-centre reference (Brayford Pool): **53.2268° N, 0.5430° W**.

---

## 3.2 The data (this is the key fix — no fabricated points)

All demand points are pulled live from **OpenStreetMap via the Overpass API** by `scripts/fetch_and_analyze.py`. The latest run returned **740 real points of interest** inside the Lincoln study area (bbox 53.18–53.29 N, −0.60 to −0.47 W):

| Category | Count | Demand weight | Why this weight |
|----------|------:|:-------------:|-----------------|
| Restaurant / cafe / pub | 306 | 1.0 | General activity / footfall |
| Park / green space | 256 | 2.0 | Recreation demand **and** potential landing surface |
| Community / civic (library, theatre, sports) | 50 | 3.0 | Civic trip generators |
| School | 45 | 2.0 | Steady local demand |
| Supermarket / mall | 38 | 3.0 | Retail trip generators |
| Hospital / clinic | 22 | 5.0 | High-value medical eVTOL use-case |
| University / college | 20 | 4.0 | Large concentrated demand |
| Transport hub (rail/bus) | 3 | 5.0 | Multimodal interchange |

*(Parking sites are also fetched — 389 of them — used only as "open-space" siting bonus, not as demand.)*
Weights are an editable assumption in the script; re-running the script refreshes every number above from current OSM.

---

## 3.3 The constraints

**Obstacles (hard no-fly):**

- **Lincoln Cathedral** (53.2344° N, 0.5360° W) — ~83 m tall on a ~75 m ridge → top ≈ **160 m AMSL**; protected heritage. 400 m no-fly buffer.
- **Lincoln Castle** (53.2345° N, 0.5405° W) — Norman walls, protected. 250 m buffer.

**Airspace (UK CAA / military):** Lincoln sits inside one of the busiest military airspace clusters in the UK. Operations fall under the UK Air Navigation Order and CAA UAS rules.

| Airfield | From city | Status | Airspace effect |
|----------|-----------|--------|-----------------|
| **RAF Waddington** (53.166° N, 0.524° W) | ~6.5 km **S** | Active (RC-135 / ISTAR) | **5 km Flight Restriction Zone** + **MATZ** (~5 NM, surface–3000 ft + stub). Hard exclusion in the model. |
| **RAF Scampton** (53.308° N, 0.551° W) | ~8.5 km **N** | Closing (former Red Arrows) | Legacy FRZ during transition. |
| **RAF Cranwell** (53.03° N, 0.48° W) | ~22 km **S** | Active (training) | Adds regional airspace density. |

Other design rules baked into the thinking: **120 m (400 ft) AGL** standard ceiling, **congested-area / assembly-of-people** separation over the centre, and **BVLOS** approval needed for any network-scale service.

---

## 3.4 Weather

Lincoln is inland and eastern → **relatively dry** (~580–620 mm/yr, Pennine rain shadow) but exposed to **easterly** North-Sea winds.

- **Wind:** prevailing south-westerly; cold easterly outbreaks in winter/spring. The Lincoln Edge ridge causes **local funnelling/turbulence** near the uphill area — relevant to approach paths.
- **Fog:** notable risk. The Witham valley and fenland to the south-east are prone to **radiation fog / low cloud**, especially autumn–winter mornings — a direct hit on eVTOL availability.
- **Design implication:** assume seasonal downtime from fog and crosswind limits; avoid the most fog-prone low ground and the most turbulent ridge edges.

---

## 3.5 The suitability model (how vertiports are derived)

Implemented in `scripts/fetch_and_analyze.py`:

1. **Grid** the study area at **120 m** resolution.
2. **Score each cell** by weighted demand within a **650 m** catchment, using linear distance decay: `score += weight × (1 − dist/650)`.
3. **Hard-exclude** any cell within the Cathedral/Castle no-fly buffers or inside **RAF Waddington's 5 km FRZ**.
4. **Open-space bonus** (+20%) if a park or car park lies within 220 m — i.e. a realistic place to actually land.
5. **Coverage-driven selection** (the important bit): pick spaced local maxima (**700 m** apart) and **keep adding** vertiports until **85% of weighted demand** is within **900 m** of a site, or the next site scores below 5% of the best. **The number of vertiports is therefore an output, not a fixed cap.**

This is transparent and reproducible: change a weight, a buffer, or the coverage target, re-run, and both the count and the map update.

> **Why this matters:** an earlier draft hard-capped the result at 8 sites — that was an arbitrary stop, not a finding. With the coverage rule, the latest run derives **19 vertiports for ~87% demand coverage**. Lowering the target or widening the access radius gives fewer, larger hubs; raising it gives a denser network.

---

## 3.6 Result — derived vertiport network

The latest run derives **19 vertiports** reaching **~87% weighted demand coverage**. They form a natural tier structure (scores are relative suitability, higher = better):

**Tier 1 — primary hubs (highest demand, build first):**

| ID | Suitability | Cumulative coverage | Anchors it serves (within 650 m) |
|----|:-----------:|:-------------------:|----------------------------------|
| **V1** | 297 | 48% | City-centre / Brayford core — hospitals, transport, university (highest raw demand; needs careful congested-area handling) |
| **V2** | 157 | 57% | University of Lincoln campus |
| **V3** | 93 | 61% | Inner-city civic + colleges |
| **V4** | 61 | 62% | **Lincoln Central Bus Station** — multimodal interchange |
| **V7** | 38 | 65% | **Lincoln County Hospital** — medical eVTOL pad |

**Tier 2 — local / coverage pads (V5–V6, V8–V19):** fill out the network toward the 85% target, anchored on neighbourhood surgeries, secondary campuses and parks (e.g. Richmond Medical Centre, Lindum/Minster Medical Practice, Bishop GrosseTeste University).

**Recommendation to the technical team:** phase the rollout — **launch Tier 1 (V1–V4, V7)** to capture the multimodal hub, university and hospital use-cases, then extend to Tier 2 as demand proves out. Every site stays clear of the Cathedral no-fly and the Waddington FRZ by construction.

*(Exact count, scores and anchors refresh whenever the script is re-run against current OSM, or when the coverage target / weights are changed.)*

---

## 3.7 Summary for the technical sections

- **Demand is real and reproducible** — 740 OSM POIs, not invented points.
- **Vertiports are derived, not assumed** — output of a documented suitability model.
- **Build toward the multimodal hub, university and hospital first**; keep clear of the Cathedral ridge and Waddington's MATZ/FRZ.
- **Design for a 120 m AGL ceiling**, CAA coordination with RAF Waddington, and weather downtime from fog and ridge turbulence.

See `index.html` for the interactive map (toggle demand layers, heatmap, constraints, and the derived vertiports). Re-run `python3 scripts/fetch_and_analyze.py` to refresh all data.
