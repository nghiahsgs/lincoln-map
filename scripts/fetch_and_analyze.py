#!/usr/bin/env python3
"""
Lincoln UAM case study — real data pipeline.

1. Pull REAL points of interest for Lincoln (UK) from OpenStreetMap via the
   Overpass API: hospitals, schools/universities, restaurants/cafes, parks,
   community centres, transport hubs, supermarkets, parking, etc.
2. Build a demand surface and run a grid-based SUITABILITY model to derive
   candidate vertiport locations (demand near, exclusion zones away).
3. Write everything to data.js (window.LINCOLN_DATA) so index.html can render
   it directly from file:// without a server.

No third-party packages — uses only the Python standard library.
"""

import json, math, urllib.request, urllib.error, time, sys, os

# ---- Study area: Lincoln, UK (south, west, north, east) ----
BBOX = (53.180, -0.600, 53.290, -0.470)
CENTER = (53.2268, -0.5430)  # Brayford Pool

# Known fixed obstacles / airfields (real coordinates, public knowledge)
CATHEDRAL = (53.2344, -0.5360)   # ~83 m tall on ~75 m ridge -> ~160 m AMSL
CASTLE    = (53.2345, -0.5405)
WADDINGTON = (53.1662, -0.5240)  # active RAF base ~6.5 km south
SCAMPTON   = (53.3076, -0.5510)  # former Red Arrows base ~8.5 km north

OUT_DIR = os.path.join(os.path.dirname(__file__), "..")
DATA_JS = os.path.join(OUT_DIR, "data.js")

OVERPASS_MIRRORS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]

# category -> (overpass selector, demand weight, color)
# weight reflects value as an eVTOL demand generator for a small UK city.
CATEGORIES = {
    "hospital":   dict(weight=5.0, color="#e84393", label="Hospital / clinic"),
    "transport":  dict(weight=5.0, color="#0984e3", label="Transport hub (rail/bus)"),
    "university": dict(weight=4.0, color="#6c5ce7", label="University / college"),
    "school":     dict(weight=2.0, color="#00b894", label="School"),
    "community":  dict(weight=3.0, color="#fdcb6e", label="Community / civic"),
    "retail":     dict(weight=3.0, color="#e17055", label="Supermarket / mall"),
    "park":       dict(weight=2.0, color="#55efc4", label="Park / green space"),
    "food":       dict(weight=1.0, color="#b2bec3", label="Restaurant / cafe"),
}

# Overpass QL: one query, many tag filters. `out center;` gives way centroids.
def build_query():
    s, w, n, e = BBOX
    b = f"({s},{w},{n},{e})"
    parts = []
    def add(sel):
        parts.append(f'node{sel}{b};')
        parts.append(f'way{sel}{b};')
    add('["amenity"~"^(hospital|clinic|doctors)$"]')
    add('["amenity"~"^(school|college|university|kindergarten)$"]')
    add('["amenity"~"^(restaurant|cafe|fast_food|pub|bar)$"]')
    add('["amenity"~"^(community_centre|library|townhall|arts_centre|theatre|cinema)$"]')
    add('["amenity"~"^(bus_station)$"]')
    add('["railway"="station"]')
    add('["leisure"~"^(park|recreation_ground|garden|sports_centre|stadium)$"]')
    add('["shop"~"^(supermarket|mall|department_store)$"]')
    add('["amenity"="parking"]')        # candidate open-space siting
    body = "\n".join(parts)
    return f"[out:json][timeout:90];\n(\n{body}\n);\nout center tags;"

def fetch_overpass():
    query = build_query()
    data = urllib.parse.urlencode({"data": query}).encode()
    headers = {"User-Agent": "lincoln-uam-case-study/1.0 (academic GIS project)"}
    for url in OVERPASS_MIRRORS:
        try:
            print(f"[overpass] querying {url} ...", file=sys.stderr)
            req = urllib.request.Request(url, data=data, headers=headers)
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.load(r)
        except Exception as ex:
            print(f"[overpass] {url} failed: {ex}", file=sys.stderr)
            time.sleep(2)
    raise SystemExit("All Overpass mirrors failed. Check your connection and retry.")

def classify(tags):
    a = tags.get("amenity", "")
    l = tags.get("leisure", "")
    if a in ("hospital", "clinic", "doctors"): return "hospital"
    if a == "university" or a == "college":    return "university"
    if a in ("school", "kindergarten"):        return "school"
    if a in ("restaurant", "cafe", "fast_food", "pub", "bar"): return "food"
    if a in ("community_centre", "library", "townhall", "arts_centre", "theatre", "cinema"):
        return "community"
    if a == "bus_station" or tags.get("railway") == "station": return "transport"
    if l in ("park", "recreation_ground", "garden"): return "park"
    if l in ("sports_centre", "stadium"):            return "community"
    if tags.get("shop") in ("supermarket", "mall", "department_store"): return "retail"
    if a == "parking": return "parking"
    return None

def to_points(osm):
    pts = []
    for el in osm.get("elements", []):
        if el["type"] == "node":
            lat, lon = el.get("lat"), el.get("lon")
        else:
            c = el.get("center") or {}
            lat, lon = c.get("lat"), c.get("lon")
        if lat is None or lon is None:
            continue
        tags = el.get("tags", {})
        cat = classify(tags)
        if not cat:
            continue
        name = tags.get("name", "")
        pts.append(dict(lat=lat, lon=lon, cat=cat, name=name))
    return pts

# ---- geometry helpers (equirectangular metres, fine for a city) ----
def metres(a, b):
    latm = math.radians((a[0] + b[0]) / 2)
    dx = (b[1] - a[1]) * math.cos(latm) * 111320
    dy = (b[0] - a[0]) * 110540
    return math.hypot(dx, dy)

def suitability(points):
    """Grid-based suitability. Each cell scored by weighted demand within RADIUS,
    minus hard exclusion (Cathedral / Waddington FRZ). Candidates = local maxima
    on/near open space, kept apart by MIN_SEP."""
    RADIUS = 650.0          # demand catchment (m)
    MIN_SEP = 750.0         # min spacing between vertiports (m)
    STEP_M = 120.0          # grid resolution (m)
    CATHEDRAL_NOFLY = 400.0 # hard no-fly around Cathedral/Castle ridge (m)
    WADDINGTON_FRZ = 5000.0 # CAA flight restriction zone (m)

    demand = [p for p in points if p["cat"] in CATEGORIES]
    open_space = [p for p in points if p["cat"] in ("park", "parking")]

    s, w, n, e = BBOX
    # grid steps in degrees
    dlat = STEP_M / 110540
    dlon = STEP_M / (111320 * math.cos(math.radians(CENTER[0])))

    cells = []
    lat = s
    while lat <= n:
        lon = w
        while lon <= e:
            c = (lat, lon)
            # hard exclusions
            if metres(c, CATHEDRAL) < CATHEDRAL_NOFLY or metres(c, CASTLE) < CATHEDRAL_NOFLY:
                lon += dlon; continue
            if metres(c, WADDINGTON) < WADDINGTON_FRZ:
                lon += dlon; continue
            # demand score (linear decay)
            score = 0.0
            for p in demand:
                d = metres(c, (p["lat"], p["lon"]))
                if d < RADIUS:
                    score += CATEGORIES[p["cat"]]["weight"] * (1 - d / RADIUS)
            if score > 0:
                # bonus: near open space (realistic landing surface)
                near_open = any(metres(c, (o["lat"], o["lon"])) < 220 for o in open_space)
                if near_open:
                    score *= 1.20
                cells.append(dict(lat=lat, lon=lon, score=round(score, 2), open=near_open))
            lon += dlon
        lat += dlat

    cells.sort(key=lambda x: -x["score"])

    # greedy non-maximum suppression -> spaced candidates
    chosen = []
    for cell in cells:
        cc = (cell["lat"], cell["lon"])
        if metres(cc, WADDINGTON) < WADDINGTON_FRZ:
            continue
        if all(metres(cc, (k["lat"], k["lon"])) >= MIN_SEP for k in chosen):
            chosen.append(cell)
        if len(chosen) >= 8:
            break

    # describe each candidate by what demand it serves
    for i, k in enumerate(chosen, 1):
        cc = (k["lat"], k["lon"])
        served = {}
        names = []
        for p in demand:
            d = metres(cc, (p["lat"], p["lon"]))
            if d < RADIUS:
                served[p["cat"]] = served.get(p["cat"], 0) + 1
                if p["cat"] in ("hospital", "transport", "university") and p["name"]:
                    names.append(p["name"])
        k["id"] = f"V{i}"
        k["served"] = served
        k["anchors"] = sorted(set(names))[:4]
    return chosen, cells

def fc(features):
    return {"type": "FeatureCollection", "features": features}

def point_feature(lat, lon, props):
    return {"type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": props}

def main():
    osm = fetch_overpass()
    points = to_points(osm)
    counts = {}
    for p in points:
        counts[p["cat"]] = counts.get(p["cat"], 0) + 1
    print("[data] real OSM features by category:", counts, file=sys.stderr)

    candidates, cells = suitability(points)

    demand_features = [
        point_feature(p["lat"], p["lon"],
                      dict(cat=p["cat"], name=p["name"],
                           weight=CATEGORIES.get(p["cat"], {}).get("weight", 0)))
        for p in points if p["cat"] in CATEGORIES
    ]
    # heat points: [lat, lon, intensity]
    heat = [[p["lat"], p["lon"], CATEGORIES[p["cat"]]["weight"]]
            for p in points if p["cat"] in CATEGORIES]

    cand_features = [
        point_feature(k["lat"], k["lon"],
                      dict(id=k["id"], score=k["score"], open=k["open"],
                           served=k["served"], anchors=k["anchors"]))
        for k in candidates
    ]

    obstacles = fc([
        point_feature(*CATHEDRAL, dict(name="Lincoln Cathedral",
            note="~83 m tall on a ~75 m ridge → top ≈160 m AMSL. Protected heritage. Hard no-fly.", radius=400)),
        point_feature(*CASTLE, dict(name="Lincoln Castle",
            note="Norman walls, protected heritage.", radius=250)),
    ])
    airspace = fc([
        point_feature(*WADDINGTON, dict(name="RAF Waddington", status="active",
            frz=5000, matz=9260,
            note="Active military airfield ~6.5 km S. 5 km Flight Restriction Zone + ~5 NM MATZ.")),
        point_feature(*SCAMPTON, dict(name="RAF Scampton", status="closing",
            frz=5000,
            note="Former Red Arrows base ~8.5 km N. Legacy FRZ during transition.")),
    ])

    meta = dict(
        bbox=BBOX, center=CENTER, categories=CATEGORIES,
        counts=counts, generated="run scripts/fetch_and_analyze.py",
        method=("Candidate vertiports = grid suitability model: weighted real-OSM demand "
                "within 650 m, minus hard exclusion (Cathedral/Castle 400 m no-fly, "
                "Waddington 5 km FRZ), open-space bonus, 750 m min spacing."),
    )

    payload = dict(
        meta=meta,
        demand=fc(demand_features),
        heat=heat,
        candidates=fc(cand_features),
        obstacles=obstacles,
        airspace=airspace,
    )

    with open(DATA_JS, "w") as f:
        f.write("// AUTO-GENERATED by scripts/fetch_and_analyze.py — real OpenStreetMap data.\n")
        f.write("window.LINCOLN_DATA = ")
        json.dump(payload, f, ensure_ascii=False)
        f.write(";\n")
    print(f"[write] {DATA_JS}", file=sys.stderr)
    print(f"[result] {len(demand_features)} demand POIs, "
          f"{len(cand_features)} candidate vertiports.", file=sys.stderr)
    for k in candidates:
        print(f"   {k['id']}  score={k['score']:>6}  open={k['open']}  "
              f"served={k['served']}  anchors={k['anchors']}", file=sys.stderr)

if __name__ == "__main__":
    main()
