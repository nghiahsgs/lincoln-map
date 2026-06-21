# Lincoln UAM Case Study — Section 3 (GIS / Context)

🌍 **Live map:** https://nghiahsgs.github.io/lincoln-map/

Deliverables for **Section 3** of the group UAM/eVTOL report — *Lincoln Context & GIS Analyst (Ly)*.
Provides the real-world constraints (urban layout, CAA airspace, weather, vertiport candidates and
obstacle zones) that ground the technical sections in an actual operating environment.

Method: **map real demand → overlay real constraints → score the space → derive vertiports.**
Sites are *not* hand-picked — they fall out of a suitability model fed with live OpenStreetMap data.

## Contents

| File | What it is |
|------|------------|
| [`scripts/fetch_and_analyze.py`](scripts/fetch_and_analyze.py) | **Data + analysis pipeline.** Pulls 740+ real POIs from OpenStreetMap (Overpass API), runs the grid suitability model, and writes `data.js`. Standard library only. |
| [`data.js`](data.js) | Auto-generated real data (demand POIs, heatmap, constraints, derived vertiports). |
| [`index.html`](index.html) | **Interactive map** for the presentation — real demand layers, demand heatmap, obstacle/airspace constraints, and the derived V1–V8 vertiports. |
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
