# Lincoln UAM Case Study — Section 3 (GIS / Context)

🌍 **Live map:** https://nghiahsgs.github.io/lincoln-map/

Deliverables for **Section 3** of the group UAM/eVTOL report — *Lincoln Context & GIS Analyst (Ly)*.
Grounds the report's scenario — a single eVTOL taxi flight **Metheringham → Castle View Restaurant, Lincoln (~16 km)** — in real geography.

Two GIS deliverables, both from real OpenStreetMap data + computed geometry:
1. **Flight-route corridor** — the route (computed tangent-to-circle avoidance of the RAF Waddington ATZ, since the **direct line breaches it**), candidate vertiports derived at real villages along the way (ATZ-blocked villages excluded), the Cathedral obstacle, and real emergency-landing surfaces.
2. **City suitability** — a grid model over live demand that *derives* candidate vertiports (sites are **not** hand-picked), used to justify the Bailgate landing pad.

## Contents

| File | What it is |
|------|------------|
| [`scripts/fetch_and_analyze.py`](scripts/fetch_and_analyze.py) | **Data + analysis pipeline.** Pulls 740+ real POIs from OpenStreetMap (Overpass API), runs the grid suitability model, and writes `data.js`. Standard library only. |
| [`data.js`](data.js) | Auto-generated real data (demand POIs, heatmap, constraints, derived vertiports). |
| [`index.html`](index.html) | **Interactive map** with two tabs — **🛫 Flight route** (Metheringham → Lincoln corridor, RAF Waddington ATZ, primary/backup routes, Cathedral obstacle, real emergency-landing sites) and **🗺️ City suitability** (real demand layers, heatmap, constraints, derived vertiports). |
| [`docs/lincoln-case-study.md`](docs/lincoln-case-study.md) | **Written documentation** for the report. |

## Refresh the data

```
python3 scripts/fetch_and_analyze.py   # re-queries OpenStreetMap, rewrites data.js
```

## View the map

Just open `index.html` in any browser (loads `data.js` locally; needs internet only for map tiles + Leaflet/heat CDN):

```
open index.html        # macOS
```

## Data caveat

Demand is **real** (live OpenStreetMap). Obstacle elevations and airspace radii use standard
CAA buffer sizes around real RAF coordinates and are **approximate**. **Not for real flight planning** —
verify against the current UK AIP and a CAA-recognised drone app before any operation.
