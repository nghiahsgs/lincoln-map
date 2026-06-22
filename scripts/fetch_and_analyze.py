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

# ---- Route scenario (the actual assignment: ONE flight, A -> B -> A) ----
# "Optimising data in support of platform activity": Metheringham village -> a
# table at Castle View Indian Restaurant by Lincoln Castle, ~16 km. Endpoints are
# real public places; the route polylines are ILLUSTRATIVE corridors (geometry),
# not CAA-approved tracks. We COMPUTE each route's length + closest approach to
# RAF Waddington so "the shortest route is not the flyable route" is evidenced by
# real numbers, not asserted.
METHERINGHAM = (53.1416, -0.3930)  # village pickup pad (public place)
DESTINATION  = (53.2348, -0.5398)  # Bailgate landing pad by the Castle / Castle View restaurant
WADDINGTON_ATZ = 4630.0            # ~2.5 NM Aerodrome Traffic Zone — hard exclusion
WADDINGTON_MATZ = 9260.0           # ~5 NM MATZ — coordinate to cross
ATZ_MARGIN = 250.0                 # safety buffer kept outside the ATZ edge (m)

# Corridor study area for emergency-landing search (covers all routes)
ROUTE_BBOX = (53.090, -0.660, 53.250, -0.380)

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

def post_overpass(query):
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

def fetch_overpass():
    return post_overpass(build_query())

def build_emergency_query():
    """Open, flat, unobstructed surfaces along the corridor = realistic emergency
    set-down options (sports pitches, recreation grounds, golf, large open grass)."""
    s, w, n, e = ROUTE_BBOX
    b = f"({s},{w},{n},{e})"
    sels = [
        '["leisure"="pitch"]', '["leisure"="recreation_ground"]',
        '["leisure"="golf_course"]', '["leisure"="park"]',
        '["landuse"="recreation_ground"]', '["landuse"="meadow"]',
    ]
    parts = []
    for sel in sels:
        parts.append(f'way{sel}{b};')
        parts.append(f'node{sel}{b};')
    body = "\n".join(parts)
    return f"[out:json][timeout:90];\n(\n{body}\n);\nout center tags;"

def fetch_emergency():
    return post_overpass(build_emergency_query())

def build_corridor_query():
    """Settlements (as candidate vertiport sites) + demand POIs along the corridor,
    so intermediate vertiports between Metheringham and Lincoln are derived from real
    villages and their real demand, not invented."""
    s, w, n, e = ROUTE_BBOX
    b = f"({s},{w},{n},{e})"
    parts = []
    def add(sel):
        parts.append(f'node{sel}{b};')
        parts.append(f'way{sel}{b};')
    add('["amenity"~"^(hospital|clinic|doctors|school|college|university|kindergarten|'
        'restaurant|cafe|fast_food|pub|bar|community_centre|library|townhall|'
        'arts_centre|theatre|cinema|bus_station)$"]')
    add('["railway"="station"]')
    add('["leisure"~"^(park|recreation_ground|garden|sports_centre|stadium)$"]')
    add('["shop"~"^(supermarket|mall|department_store|convenience)$"]')
    # real settlements = candidate vertiport locations
    parts.append(f'node["place"~"^(town|village|hamlet|suburb)$"]{b};')
    body = "\n".join(parts)
    return f"[out:json][timeout:90];\n(\n{body}\n);\nout center tags;"

def fetch_corridor():
    return post_overpass(build_corridor_query())

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

def _xy(q, ref_lat):
    """project lat/lon to local metres about a reference latitude."""
    return (q[1] * math.cos(math.radians(ref_lat)) * 111320, q[0] * 110540)

def seg_dist_m(p, a, b):
    """shortest distance (m) from point p to segment a-b."""
    ref = p[0]
    (px, py), (ax, ay), (bx, by) = _xy(p, ref), _xy(a, ref), _xy(b, ref)
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))

def route_metrics(wps):
    """total length (m) and closest approach (m) to RAF Waddington for a polyline."""
    length = sum(metres(wps[i], wps[i + 1]) for i in range(len(wps) - 1))
    clear = min(seg_dist_m(WADDINGTON, wps[i], wps[i + 1]) for i in range(len(wps) - 1))
    return length, clear

def dist_to_route(p, wps):
    """closest distance (m) from a point to a polyline."""
    return min(seg_dist_m(p, wps[i], wps[i + 1]) for i in range(len(wps) - 1))

# ---- shortest path that avoids a circular no-fly disc (real geometry) ----
# Classic result: if the straight A->B segment enters a disc (centre C, radius r),
# the shortest avoiding path "hugs" the circle: tangent A->circle, an arc along the
# rim, tangent circle->B. There are two ways round (clockwise / anticlockwise); the
# shorter is the primary route, the longer is the contingency. Nothing is hand-drawn.

def _ll_to_xy(p, ref_lat):
    return (p[1] * math.cos(math.radians(ref_lat)) * 111320.0, p[0] * 110540.0)

def _xy_to_ll(xy, ref_lat):
    x, y = xy
    return (y / 110540.0, x / (math.cos(math.radians(ref_lat)) * 111320.0))

def _seg_hits_disc(a, b, c, r):
    """does segment a-b (xy) come within r of centre c?"""
    ax, ay = a; bx, by = b; cx, cy = c
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    if L2 == 0:
        return math.hypot(cx - ax, cy - ay) < r
    t = max(0.0, min(1.0, ((cx - ax) * dx + (cy - ay) * dy) / L2))
    return math.hypot(cx - (ax + t * dx), cy - (ay + t * dy)) < r

def tangent_detour(A, B, C, r, samples=26):
    """Return {'straight':bool, 'routes':[(name, [latlon...]), ...]}.
    routes is the two wrap-around options sorted shortest-first; if the straight
    line is already clear, returns it as the single route."""
    ref = C[0]
    a, b, c = _ll_to_xy(A, ref), _ll_to_xy(B, ref), _ll_to_xy(C, ref)
    if not _seg_hits_disc(a, b, c, r):
        return dict(straight=True, routes=[("clear", [A, B])])

    def ang_of(P):  # position angle of P seen from centre, and tangent half-angle
        d = math.hypot(P[0] - c[0], P[1] - c[1])
        return math.atan2(P[1] - c[1], P[0] - c[0]), math.acos(max(-1.0, min(1.0, r / d)))

    alphaA, betaA = ang_of(a)
    alphaB, betaB = ang_of(b)
    out = []
    for name, s in (("ccw", 1), ("cw", -1)):
        thA = alphaA + s * betaA          # tangent point leaving A
        thB = alphaB - s * betaB          # tangent point arriving at B
        sweep = ((thB - thA) % (2 * math.pi)) if s == 1 else ((thA - thB) % (2 * math.pi))
        arc = []
        for i in range(samples + 1):
            ang = thA + (s * sweep) * (i / samples)
            arc.append((c[0] + r * math.cos(ang), c[1] + r * math.sin(ang)))
        xy_path = [a] + arc + [b]
        latlon = [A] + [_xy_to_ll(p, ref) for p in arc] + [B]
        length = sum(metres(latlon[i], latlon[i + 1]) for i in range(len(latlon) - 1))
        out.append((length, name, latlon))
    out.sort(key=lambda x: x[0])
    return dict(straight=False, routes=[(n, ll) for _, n, ll in out])

def suitability(points):
    """Grid-based suitability. Each cell scored by weighted demand within RADIUS,
    minus hard exclusion (Cathedral / Waddington FRZ). Candidates = spaced local
    maxima. The NUMBER of vertiports is NOT a fixed cap — it is driven by demand
    coverage: keep adding sites until TARGET_COVER of weighted demand is within
    ACCESS metres of a vertiport, or the next best site is too low-demand to justify."""
    RADIUS = 650.0          # demand catchment used for scoring (m)
    MIN_SEP = 700.0         # min spacing between vertiports (m)
    STEP_M = 120.0          # grid resolution (m)
    CATHEDRAL_NOFLY = 400.0 # hard no-fly around Cathedral/Castle ridge (m)
    WADDINGTON_FRZ = 5000.0 # CAA flight restriction zone (m)
    ACCESS = 900.0          # walkable access to a vertiport (m) -> coverage radius
    TARGET_COVER = 0.85     # stop once 85% of weighted demand is covered
    SCORE_FLOOR_FRAC = 0.05 # ...or once next site scores <5% of the best site
    MAX_SITES = 40          # safety cap only (not the real limit)

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

    # coverage-driven greedy selection (count emerges from the data, not a cap)
    total_w = sum(CATEGORIES[p["cat"]]["weight"] for p in demand) or 1.0
    top_score = cells[0]["score"] if cells else 0.0
    floor = SCORE_FLOOR_FRAC * top_score
    covered = set()      # indices of demand POIs already within ACCESS of a site
    cov_w = 0.0
    chosen = []
    for cell in cells:
        cc = (cell["lat"], cell["lon"])
        if metres(cc, WADDINGTON) < WADDINGTON_FRZ:
            continue
        if not all(metres(cc, (k["lat"], k["lon"])) >= MIN_SEP for k in chosen):
            continue
        chosen.append(cell)
        for i, p in enumerate(demand):
            if i not in covered and metres(cc, (p["lat"], p["lon"])) < ACCESS:
                covered.add(i)
                cov_w += CATEGORIES[p["cat"]]["weight"]
        cell["coverage"] = round(cov_w / total_w, 3)
        # stop conditions
        if len(chosen) >= MAX_SITES:
            break
        if cell["coverage"] >= TARGET_COVER:
            break
        if cell["score"] < floor and len(chosen) >= 3:
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

def emergency_sites(osm, corridor_wps, max_dist=1600.0, keep=14):
    """Real open surfaces from OSM within `max_dist` of the flight corridor.
    Returns the closest-to-route, named-first set as a small list."""
    raw = []
    seen = set()
    for el in osm.get("elements", []):
        if el["type"] == "node":
            lat, lon = el.get("lat"), el.get("lon")
        else:
            c = el.get("center") or {}
            lat, lon = c.get("lat"), c.get("lon")
        if lat is None or lon is None:
            continue
        tags = el.get("tags", {})
        kind = tags.get("leisure") or tags.get("landuse") or "open space"
        name = tags.get("name", "")
        d = dist_to_route((lat, lon), corridor_wps)
        if d > max_dist:
            continue
        key = (round(lat, 4), round(lon, 4))
        if key in seen:
            continue
        seen.add(key)
        raw.append(dict(lat=lat, lon=lon, kind=kind, name=name, dist=round(d)))
    # prefer named sites, then closest to the route
    raw.sort(key=lambda r: (0 if r["name"] else 1, r["dist"]))
    return raw[:keep]

def corridor_vertiports(corridor_osm, route_wps):
    """Derive intermediate vertiports along the corridor: real settlements within
    reach of the primary route, scored by their real nearby demand, excluding any
    inside the ATZ, spaced apart. The COUNT emerges from how many villages the
    corridor actually passes — nothing hand-placed."""
    CORRIDOR_DIST = 2500.0   # how far off the route a village can be served (m)
    RADIUS = 900.0           # demand catchment for scoring a village pad (m)
    MIN_SEP = 1500.0         # min spacing between corridor vertiports (m)
    MIN_SCORE = 1.0          # a pad must serve at least some real demand
    EXCLUDE_DIST = 4000.0    # report ATZ-blocked villages within this of the direct line

    demand, places = [], []
    for el in corridor_osm.get("elements", []):
        if el["type"] == "node":
            lat, lon = el.get("lat"), el.get("lon")
        else:
            c = el.get("center") or {}
            lat, lon = c.get("lat"), c.get("lon")
        if lat is None or lon is None:
            continue
        tags = el.get("tags", {})
        if tags.get("place") in ("town", "village", "hamlet", "suburb") and tags.get("name"):
            places.append(dict(lat=lat, lon=lon, name=tags["name"], place=tags["place"]))
        else:
            cat = classify(tags)
            if cat in CATEGORIES:
                demand.append(dict(lat=lat, lon=lon, cat=cat, name=tags.get("name", "")))

    cands, excluded = [], []
    direct_wps = [METHERINGHAM, DESTINATION]
    for pl in places:
        c = (pl["lat"], pl["lon"])
        droute = dist_to_route(c, route_wps)
        if metres(c, WADDINGTON) < WADDINGTON_ATZ:
            if dist_to_route(c, direct_wps) <= EXCLUDE_DIST:
                excluded.append(pl["name"])    # village inside the hard no-fly zone → cannot site here
            continue
        if droute > CORRIDOR_DIST:
            continue
        score = 0.0
        served = {}
        for p in demand:
            d = metres(c, (p["lat"], p["lon"]))
            if d < RADIUS:
                score += CATEGORIES[p["cat"]]["weight"] * (1 - d / RADIUS)
                served[p["cat"]] = served.get(p["cat"], 0) + 1
        if score < MIN_SCORE:
            continue                            # settlement with no mapped demand → skip
        cands.append(dict(lat=pl["lat"], lon=pl["lon"], name=pl["name"], place=pl["place"],
                          score=round(score, 1), served=served, dist=round(droute)))

    # spacing: keep the higher-demand village where two are close together
    cands.sort(key=lambda x: -x["score"])
    kept = []
    for c in cands:
        cc = (c["lat"], c["lon"])
        if all(metres(cc, (k["lat"], k["lon"])) >= MIN_SEP for k in kept):
            kept.append(c)
    # order south->north along the corridor and number them
    kept.sort(key=lambda x: x["lat"])
    for i, k in enumerate(kept, 1):
        k["id"] = f"C{i}"
    return kept, sorted(set(excluded))

def build_route(emergency_osm, corridor_osm):
    avoid_r = WADDINGTON_ATZ + ATZ_MARGIN   # stay this far from the ATZ centre

    # 1) the naive direct line — kept to SHOW it is blocked
    direct_len, direct_clear = route_metrics([METHERINGHAM, DESTINATION])
    routes_out = [dict(
        id="direct", name="Direct line (shortest)", kind="blocked", color="#e74c3c",
        note="Shortest A→B, but it enters Waddington's ATZ → rejected by the data filter before planning.",
        coords=[[METHERINGHAM[0], METHERINGHAM[1]], [DESTINATION[0], DESTINATION[1]]],
        length_km=round(direct_len / 1000, 1),
        clearance_m=round(direct_clear),
        breaches_atz=direct_clear < WADDINGTON_ATZ,
    )]

    # 2) algorithm: shortest paths that hug the ATZ disc (two ways round)
    det = tangent_detour(METHERINGHAM, DESTINATION, WADDINGTON, avoid_r)
    meta_by_name = {
        "ccw": dict(side="east"), "cw": dict(side="west"), "clear": dict(side="direct"),
    }
    kinds = ["primary", "backup"]
    colors = {"primary": "#16a34a", "backup": "#0984e3"}
    for i, (name, latlon) in enumerate(det["routes"]):
        length, clear = route_metrics(latlon)
        kind = kinds[i] if i < len(kinds) else "alt"
        side = meta_by_name.get(name, {}).get("side", "")
        label = {"primary": "Tangent detour (primary)",
                 "backup": "Tangent detour (backup, pre-loaded)"}.get(kind, "Route")
        note = ("Shortest legal path: flies tangent to the ATZ edge, hugs the rim, "
                "tangent out — computed, not drawn. This is the main route."
                if kind == "primary" else
                "The other way round the ATZ (longer). Pre-loaded on board so it can "
                "activate instantly if the primary corridor closes mid-flight (scenario B).")
        routes_out.append(dict(
            id=name, name=f"{label} — {side} side", kind=kind, color=colors.get(kind, "#888"),
            note=note,
            coords=[[lat, lon] for (lat, lon) in latlon],
            length_km=round(length / 1000, 1),
            clearance_m=round(clear),
            breaches_atz=clear < WADDINGTON_ATZ,
        ))

    # emergency-landing candidates within the corridor of the PRIMARY route
    primary_ll = next(([ (c[0], c[1]) for c in r["coords"] ]
                       for r in routes_out if r["kind"] == "primary"), [METHERINGHAM, DESTINATION])
    emg = emergency_sites(emergency_osm, primary_ll)
    emergency_fc = fc([
        point_feature(e["lat"], e["lon"],
                      dict(name=e["name"] or "(unnamed open space)",
                           kind=e["kind"], dist=e["dist"]))
        for e in emg
    ])

    # intermediate vertiports at real villages along the primary route
    cvs, cv_excluded = corridor_vertiports(corridor_osm, primary_ll)
    vertiport_fc = fc([
        point_feature(v["lat"], v["lon"],
                      dict(id=v["id"], name=v["name"], place=v["place"],
                           score=v["score"], served=v["served"], dist=v["dist"]))
        for v in cvs
    ])
    return dict(
        start=dict(lat=METHERINGHAM[0], lon=METHERINGHAM[1], name="Metheringham — village pickup pad"),
        end=dict(lat=DESTINATION[0], lon=DESTINATION[1], name="Bailgate pad — Castle View Restaurant, Lincoln"),
        waddington=dict(lat=WADDINGTON[0], lon=WADDINGTON[1], name="RAF Waddington",
                        atz=WADDINGTON_ATZ, matz=WADDINGTON_MATZ),
        cathedral=dict(lat=CATHEDRAL[0], lon=CATHEDRAL[1], name="Lincoln Cathedral", radius=400),
        routes=routes_out,
        emergency=emergency_fc,
        vertiports=vertiport_fc,
        vertiports_excluded=cv_excluded,
    ), emg, cvs, cv_excluded

def main():
    osm = fetch_overpass()
    points = to_points(osm)
    counts = {}
    for p in points:
        counts[p["cat"]] = counts.get(p["cat"], 0) + 1
    print("[data] real OSM features by category:", counts, file=sys.stderr)

    candidates, cells = suitability(points)

    print("[route] fetching emergency-landing surfaces along corridor ...", file=sys.stderr)
    emergency_osm = fetch_emergency()
    print("[route] fetching corridor settlements + demand for intermediate vertiports ...", file=sys.stderr)
    corridor_osm = fetch_corridor()
    route_data, emg, cvs, cv_excluded = build_route(emergency_osm, corridor_osm)

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
                           coverage=k.get("coverage"),
                           served=k["served"], anchors=k["anchors"]))
        for k in candidates
    ]
    final_cover = candidates[-1].get("coverage") if candidates else 0

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
        n_sites=len(cand_features), coverage=final_cover,
        method=("Vertiport COUNT is coverage-driven (not a fixed cap): keep adding "
                "spaced (700 m) local maxima of weighted real-OSM demand until 85% of "
                "weighted demand is within 900 m of a site, or the next site scores "
                "<5% of the best. Exclusions: Cathedral/Castle 400 m no-fly, Waddington 5 km FRZ."),
    )

    payload = dict(
        meta=meta,
        demand=fc(demand_features),
        heat=heat,
        candidates=fc(cand_features),
        obstacles=obstacles,
        airspace=airspace,
        route=route_data,
    )

    with open(DATA_JS, "w") as f:
        f.write("// AUTO-GENERATED by scripts/fetch_and_analyze.py — real OpenStreetMap data.\n")
        f.write("window.LINCOLN_DATA = ")
        json.dump(payload, f, ensure_ascii=False)
        f.write(";\n")
    print(f"[write] {DATA_JS}", file=sys.stderr)
    print(f"[result] {len(demand_features)} demand POIs -> "
          f"{len(cand_features)} vertiports (coverage-driven), "
          f"final demand coverage {final_cover:.0%}.", file=sys.stderr)
    for k in candidates:
        print(f"   {k['id']}  score={k['score']:>6}  cover={k.get('coverage'):.0%}  "
              f"open={k['open']}  anchors={k['anchors']}", file=sys.stderr)
    print(f"[route] Metheringham -> Lincoln, {len(emg)} emergency-landing sites along corridor:", file=sys.stderr)
    for r in route_data["routes"]:
        flag = "BREACHES ATZ" if r["breaches_atz"] else f"clears ATZ ({r['clearance_m']} m)"
        print(f"   {r['id']:<7} {r['length_km']:>4} km  closest Waddington {r['clearance_m']:>5} m  -> {flag}",
              file=sys.stderr)
    print(f"[route] {len(cvs)} intermediate vertiports derived along the corridor:", file=sys.stderr)
    for v in cvs:
        print(f"   {v['id']:<4} {v['name']:<22} score={v['score']:>5}  {v['dist']:>4} m off-route", file=sys.stderr)
    if cv_excluded:
        print(f"   excluded (inside ATZ): {', '.join(cv_excluded)}", file=sys.stderr)

if __name__ == "__main__":
    main()
