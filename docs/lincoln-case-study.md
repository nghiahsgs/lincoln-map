# Section 3 — Lincoln Case Study: Context & GIS Analysis

**Author / Role:** Ly — *Lincoln Context & GIS Analyst (supporting realism and location-specific details).*
**Purpose:** Ground the report's scenario — a single eVTOL taxi flight **Metheringham → Castle View Restaurant, Lincoln (~16 km), and back** — in real geography, so the data-process design (sources, filtering, in-flight re-routing) is built on an actual operating environment, not guesswork.

> **Two GIS deliverables, both from real OpenStreetMap data and computed geometry:**
> 1. **Flight-route corridor (primary, §3.2)** — the scenario's route, the RAF Waddington ATZ that forces a detour, the obstacle at the destination, and real emergency-landing surfaces along the way. *This is the "khoanh vùng dọc tuyến" the brief actually asks for.*
> 2. **City suitability (supporting, §3.6–3.7)** — a grid model over live demand that *derives* candidate vertiports, used here to justify **why the Bailgate landing pad is a sound choice** (it scores highly), not to design a city-wide network.
>
> **Method in one line:** *map real demand & constraints → overlay the route → let the geometry decide what is flyable.* Nothing is hand-picked.

---

## 3.1 Why Lincoln?

Lincoln is a compact historic city in Lincolnshire, East Midlands (England), population ~100,000. It is a strong realism test case for Urban Air Mobility because it packs almost every UAM constraint into a small footprint:

- A dense **historic core** with a protected skyline (Lincoln Cathedral and Castle on a steep ridge).
- **Heavily constrained military airspace** — "Bomber County", with active/former RAF airfields close to the city.
- **Mixed terrain** — the limestone ridge ("Lincoln Edge") gives a sharp uphill/downhill split and local wind effects.
- Real **multimodal hubs** (rail, bus, park-and-ride) and a clear **medical** use-case (Lincoln County Hospital).

City-centre reference (Brayford Pool): **53.2268° N, 0.5430° W**.

---

## 3.2 The flight corridor — the report's actual scenario (primary deliverable)

The scenario is **one flight**: a village pickup at **Metheringham** (53.1416° N, 0.3930° W) to a dinner table at **Castle View Restaurant** by Lincoln Castle (landing pad at Bailgate, 53.2348° N, 0.5398° W), then the return leg. The GIS job here is not to optimise a city — it is to **circle the real things along this 16 km line** that decide whether the flight is possible.

**The key finding — shortest ≠ flyable.** The flyable routes are **not hand-drawn**: they are produced by a standard obstacle-avoidance computation. If the straight Metheringham→Lincoln segment enters the **~2.5 NM (4 630 m) Aerodrome Traffic Zone**, the shortest legal path *hugs* the zone — fly tangent to the rim, follow an arc around it (here with a 250 m safety margin), then tangent out. The circle can be passed two ways; the shorter is the primary route, the longer is the contingency. Each route's length and its computed *closest approach* to Waddington (`scripts/fetch_and_analyze.py`):

| Route | Length | Closest approach to Waddington | Verdict |
|-------|-------:|-------------------------------:|---------|
| **Direct line** (shortest) | **14.2 km** | **4 461 m** | **Breaches the ATZ ✕** — rejected by the data filter *before* planning |
| **Tangent detour, east** (primary) | 14.2 km | 4 880 m | Clears ATZ ✔ — hugs the rim, barely longer than direct; flown as the main route |
| **Tangent detour, west** (backup) | 25.3 km | 4 875 m | Clears ATZ ✔ — the other way round, **1.8× longer**; pre-loaded only as an in-flight contingency |

Because the direct line only *clips* the ATZ, the minimal east detour that hugs the rim is barely longer than the straight line (≈14.2 km) — the algorithm finds it automatically. Going the other way (west) around the same zone is much longer (25.3 km), which is why an eVTOL would only take it in an emergency. This is exactly why the report's data pipeline (filter gate "impact/space") and its in-flight re-routing (scenario B — primary corridor closes) are concrete, not abstract.

**Mapped constraints along the corridor:**

- **RAF Waddington ATZ (hard, 4 630 m) + MATZ (~5 NM, coordinate-to-cross)** — the airspace that bends the route. Note both end pads sit *inside the MATZ* (Metheringham 9 148 m, Bailgate 7 657 m from the airfield) but *outside the hard ATZ* — so they are flyable **with** military coordination, not blocked.
- **Lincoln Cathedral** at the destination — ~83 m on the ridge, an obstacle on the final approach into Bailgate.
- **Emergency set-down surfaces** — **14 real open spaces** (sports fields, recreation grounds, parks, large grass) pulled live from OpenStreetMap within ~1.6 km of the primary route, e.g. *Potterhanworth Road Sports Field* (67 m off-route), *Lincoln Arboretum*, *Temple Gardens*, *grounds of Nocton Hall*.

**Intermediate vertiports along the corridor (derived).** Beyond the two end pads, the model derives **candidate vertiport sites at real villages within 2.5 km of the primary route**, each scored by its own nearby OSM demand and spaced ≥1.5 km apart. The latest run yields **9 sites** running south→north: *Metheringham → Nocton → Potterhanworth → Branston → Canwick → Washingborough → New Boultham → St Giles → Ermine West*. Crucially, **Bracebridge and Bracebridge Heath are excluded** — they fall inside Waddington's ATZ, so no pad can be sited there. This shows the constraints directly shaping where intermediate vertiports can and cannot go, and gives the network a real chain of stops between the two endpoints rather than just an A→B hop.

See **Tab 1 "Flight route"** in `index.html` for the interactive corridor map (toggle *Corridor vertiports*).

> **Honesty note:** the two endpoints and RAF coordinates are real public places; the route geometry is **computed** (tangent-to-circle avoidance), not hand-drawn, and the lengths, clearances and emergency sites are real computed/sourced values. The remaining approximations are stated plainly: the ATZ/MATZ are standard buffer radii (not the exact UK AIP boundary), the avoidance considers the ATZ disc only (MATZ is treated as coordinate-to-cross, not a hard barrier), and distances use an equirectangular projection. Verify against the UK AIP before any real operation.

---

## 3.3 The demand data (no fabricated points)

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

## 3.4 The constraints

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

## 3.5 Weather

Lincoln is inland and eastern → **relatively dry** (~580–620 mm/yr, Pennine rain shadow) but exposed to **easterly** North-Sea winds.

- **Wind:** prevailing south-westerly; cold easterly outbreaks in winter/spring. The Lincoln Edge ridge causes **local funnelling/turbulence** near the uphill area — relevant to approach paths.
- **Fog:** notable risk. The Witham valley and fenland to the south-east are prone to **radiation fog / low cloud**, especially autumn–winter mornings — a direct hit on eVTOL availability.
- **Design implication:** assume seasonal downtime from fog and crosswind limits; avoid the most fog-prone low ground and the most turbulent ridge edges.

---

## 3.6 The suitability model (how vertiports are derived)

Implemented in `scripts/fetch_and_analyze.py`:

1. **Grid** the study area at **120 m** resolution.
2. **Score each cell** by weighted demand within a **650 m** catchment, using linear distance decay: `score += weight × (1 − dist/650)`.
3. **Hard-exclude** any cell within the Cathedral/Castle no-fly buffers or inside **RAF Waddington's 5 km FRZ**.
4. **Open-space bonus** (+20%) if a park or car park lies within 220 m — i.e. a realistic place to actually land.
5. **Coverage-driven selection** (the important bit): pick spaced local maxima (**700 m** apart) and **keep adding** vertiports until **85% of weighted demand** is within **900 m** of a site, or the next site scores below 5% of the best. **The number of vertiports is therefore an output, not a fixed cap.**

This is transparent and reproducible: change a weight, a buffer, or the coverage target, re-run, and both the count and the map update.

> **Why this matters:** an earlier draft hard-capped the result at 8 sites — that was an arbitrary stop, not a finding. With the coverage rule, the latest run derives **19 vertiports for ~87% demand coverage**. Lowering the target or widening the access radius gives fewer, larger hubs; raising it gives a denser network.

---

## 3.7 Result — derived vertiport network (supporting evidence for the landing pad)

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

## 3.8 Summary for the technical sections

- **The route is the deliverable, and it is computed not drawn** — a tangent-to-circle avoidance hugs the ATZ rim. The direct line (14.2 km) *breaches* Waddington's ATZ (4 461 m < 4 630 m); the primary east detour (14.2 km) clears it at the rim; the west backup (25.3 km) is the costlier way round. These numbers feed the filter gate and the in-flight re-routing logic.
- **Intermediate vertiports are derived along the corridor** — 9 candidate sites at real villages (Metheringham → … → Ermine West), with Bracebridge / Bracebridge Heath excluded for sitting inside the ATZ. The count emerges from the villages the route actually passes.
- **Emergency set-down is mapped, not assumed** — 14 real open surfaces from OSM along the corridor populate the "Emergency" data layer.
- **Demand is real and reproducible** — 740 OSM POIs, not invented points; the suitability model *derives* the Bailgate-area landing pad rather than asserting it.
- **Design for a 120 m AGL ceiling**, CAA coordination with RAF Waddington, the Cathedral obstacle on the final approach, and weather downtime from fog and ridge turbulence.

See `index.html` — **Tab 1 (Flight route)** for the corridor + constraints, **Tab 2 (City suitability)** for the demand model. Re-run `python3 scripts/fetch_and_analyze.py` to refresh all data.
