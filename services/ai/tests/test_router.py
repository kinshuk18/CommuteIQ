"""
tests/test_router.py — Unit tests for the GTFSRouter using real GTFS data slices.

Tests use a small in-memory GTFSGraph seeded from actual BMRCL stop/stop_time rows
to avoid a live DB dependency in CI.  The data slice is extracted from the real
GTFS files; no synthetic values are invented.
"""

import csv
import math
from pathlib import Path

import pytest

from app.router import GTFSGraph, GTFSRouter, haversine, WALK_RADIUS_M

# ── real GTFS data slice ──────────────────────────────────────────────────────
# We read the first 100 stops and all stop_times for the first 5 trips of BMRCL.
# This gives a deterministic, small but real graph.

BMRCL_DIR = Path(__file__).parent.parent.parent.parent / "data" / "raw" / "bmrcl"


def _load_stops_slice(n: int = 100) -> dict:
    """Return first n stops from bmrcl/stops.txt as {stop_id: {id, lat, lon, name}}."""
    stops = {}
    p = BMRCL_DIR / "stops.txt"
    if not p.exists():
        return stops
    with p.open(encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if i >= n:
                break
            stops[row["stop_id"]] = {
                "gtfs_id": row["stop_id"],
                "name": row["stop_name"],
                "lat": float(row["stop_lat"]),
                "lon": float(row["stop_lon"]),
            }
    return stops


def _build_small_graph() -> GTFSGraph:
    """Build a GTFSGraph in-memory from a real BMRCL data slice."""
    stops_raw = _load_stops_slice(120)
    if not stops_raw:
        pytest.skip("BMRCL data not available (data/raw/bmrcl/stops.txt missing)")

    graph = GTFSGraph()

    # Assign DB-style integer IDs
    gtfs_to_dbid = {gid: i + 1 for i, gid in enumerate(stops_raw)}
    for gtfs_id, sdata in stops_raw.items():
        dbid = gtfs_to_dbid[gtfs_id]
        graph.stops[dbid] = {
            "id": dbid,
            "stop_id": gtfs_id,
            "name": sdata["name"],
            "lat": sdata["lat"],
            "lon": sdata["lon"],
            "agency": "bmrcl",
        }
        graph.transit_edges[dbid] = []

    # Spatial index
    from app.router import GRID_STEP
    for dbid, s in graph.stops.items():
        cell = (round(s["lat"] / GRID_STEP), round(s["lon"] / GRID_STEP))
        graph._grid.setdefault(cell, []).append(dbid)

    # Load stop_times for the first 5 trips that use stops in our slice
    trips_seen = set()
    rows_by_trip: dict[str, list] = {}
    p = BMRCL_DIR / "stop_times.txt"
    if p.exists():
        with p.open(encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                tid = row["trip_id"]
                sid = row["stop_id"]
                if sid not in stops_raw:
                    continue
                if tid not in trips_seen and len(trips_seen) >= 5:
                    continue
                trips_seen.add(tid)
                rows_by_trip.setdefault(tid, []).append(row)

    def _parse_sec(s: str) -> int:
        parts = s.strip().split(":")
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + (int(parts[2]) if len(parts) > 2 else 0)

    for tid, rows in rows_by_trip.items():
        rows_sorted = sorted(rows, key=lambda r: int(r["stop_sequence"]))
        for i in range(len(rows_sorted) - 1):
            cur_r = rows_sorted[i]
            nxt_r = rows_sorted[i + 1]
            from_dbid = gtfs_to_dbid.get(cur_r["stop_id"])
            to_dbid = gtfs_to_dbid.get(nxt_r["stop_id"])
            if from_dbid is None or to_dbid is None:
                continue
            dep = _parse_sec(cur_r.get("departure_time") or cur_r.get("arrival_time", "0"))
            arr = _parse_sec(nxt_r.get("arrival_time") or nxt_r.get("departure_time", "0"))
            graph.transit_edges[from_dbid].append((dep, arr, to_dbid, tid, "r1"))

    graph._build_walk_edges()
    graph._loaded = True
    return graph


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def graph() -> GTFSGraph:
    return _build_small_graph()


@pytest.fixture(scope="module")
def router(graph) -> GTFSRouter:
    return GTFSRouter(graph)


# ── tests ─────────────────────────────────────────────────────────────────────

def test_haversine_known_pair():
    """Haversine between Majestic and Indiranagar (approx 7.5 km)."""
    # Majestic (Kempegowda) ~ 12.9766, 77.5713
    # Indiranagar ~12.9784, 77.6408
    d = haversine(12.9766, 77.5713, 12.9784, 77.6408)
    assert 6000 < d < 9000, f"Expected ~7500 m, got {d:.0f} m"


def test_graph_loaded(graph):
    assert len(graph.stops) > 0, "Graph must have stops"
    assert len(graph.transit_edges) > 0, "Graph must have transit edges"


def test_walk_edges_within_radius(graph):
    """All walk edges must be within WALK_RADIUS_M."""
    for sid, edges in graph.walk_edges.items():
        s = graph.stops[sid]
        for walk_sec, nid in edges:
            n = graph.stops[nid]
            dist = haversine(s["lat"], s["lon"], n["lat"], n["lon"])
            assert dist <= WALK_RADIUS_M + 1, (
                f"Walk edge {sid}→{nid} is {dist:.0f} m, exceeds {WALK_RADIUS_M}"
            )


def test_router_finds_path(router, graph):
    """Router must find a path between two stops that are connected via transit edges."""
    # Pick two stops that have transit edges between them
    stops_with_edges = [
        sid for sid, edges in graph.transit_edges.items() if edges
    ]
    if len(stops_with_edges) < 2:
        pytest.skip("Not enough transit edges in test slice")

    origin = stops_with_edges[0]
    # Find a reachable destination
    edges = graph.transit_edges[origin]
    if not edges:
        pytest.skip("No outbound edges from first stop")
    _, _, dest, _, _ = edges[0]

    dep_sec = edges[0][0]  # use actual departure time
    result = router.route(origin, dest, dep_sec)
    assert result is not None, "Router should find the direct edge"
    assert result["arrival_sec"] >= dep_sec
    assert result["total_duration_sec"] >= 0


def test_router_unreachable_returns_none(router, graph):
    """Isolated stop with no edges should return None."""
    # Find a stop with no transit edges and no walk edges
    isolated = None
    for sid in graph.stops:
        if not graph.transit_edges.get(sid) and not graph.walk_edges.get(sid):
            isolated = sid
            break
    if isolated is None:
        pytest.skip("No isolated stop in test slice")

    # Route from isolated to some other stop
    others = [s for s in graph.stops if s != isolated]
    if not others:
        pytest.skip("No other stops")
    result = router.route(isolated, others[0], 21600)
    assert result is None


def test_nearby_stops_returns_sorted(graph):
    """nearby_stops should return results sorted by distance."""
    # Use centroid of all stops as query point
    lats = [s["lat"] for s in graph.stops.values()]
    lons = [s["lon"] for s in graph.stops.values()]
    clat = sum(lats) / len(lats)
    clon = sum(lons) / len(lons)

    results = graph.nearby_stops(clat, clon, radius_m=5000)
    if len(results) < 2:
        pytest.skip("Not enough stops near centroid")
    for i in range(len(results) - 1):
        assert results[i]["distance_m"] <= results[i + 1]["distance_m"]
