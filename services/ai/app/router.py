"""
router.py — Time-dependent shortest-path routing over the GTFS graph.

Algorithm: RAPTOR-lite (Round-based Public Transit Routing) simplified to a
single-pass Dijkstra with per-edge departure-time filtering.  Walking links
between stops within WALK_RADIUS_M are computed once via a geohash spatial
index and cached.

Key design decisions
─────────────────────
- Seconds-since-midnight throughout; handles overnight trips (>86400 s).
- Transfer penalty of TRANSFER_PENALTY_SEC is added for each vehicle change.
- Walking edges use a fixed speed of WALK_SPEED_MPS; maximum walk = WALK_RADIUS_M.
- The spatial index is a hand-written grid bucketed by (lat_bucket, lon_bucket)
  where each bucket spans GRID_STEP degrees (~250 m).
- Results are cached with an LRU keyed by (origin_stop_id, dest_stop_id, dep_sec).
"""

import heapq
import logging
import math
from functools import lru_cache
from typing import Any

import psycopg

from app.config import settings

logger = logging.getLogger(__name__)

# ── constants ─────────────────────────────────────────────────────────────────

WALK_RADIUS_M = 400          # max walking transfer distance
WALK_SPEED_MPS = 1.2         # 1.2 m/s ≈ 4.3 km/h brisk walking
TRANSFER_PENALTY_SEC = 180   # 3-min vehicle-change penalty
GRID_STEP = 0.0025           # ~250 m grid cell for spatial index
EARTH_RADIUS_M = 6_371_000
INF = float("inf")

# ── haversine ─────────────────────────────────────────────────────────────────


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return great-circle distance in metres."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


# ── GTFS graph builder ────────────────────────────────────────────────────────


class GTFSGraph:
    """
    In-memory GTFS transit graph.

    Nodes  : stop DB IDs (int)
    Edges  : list of (departure_sec, arrival_sec, neighbour_stop_id, trip_id, route_id)
             stored per stop in self.transit_edges[stop_id]
    Walking: additional edges computed lazily from spatial index
    """

    def __init__(self) -> None:
        self.stops: dict[int, dict[str, Any]] = {}        # id → {lat, lon, name, agency, stop_id}
        self.transit_edges: dict[int, list[tuple]] = {}   # stop_id → [(dep, arr, to_stop, trip, route)]
        self.walk_edges: dict[int, list[tuple]] = {}      # stop_id → [(walk_sec, to_stop)]
        self._grid: dict[tuple, list[int]] = {}           # (lat_cell, lon_cell) → [stop_id, ...]
        self._loaded = False

    def load(self, db_url: str) -> None:
        """Pull stops + stop_times from Postgres and build the graph."""
        logger.info("GTFSGraph: loading from DB …")
        conn = psycopg.connect(db_url)
        try:
            with conn.cursor() as cur:
                # Load stops
                cur.execute(
                    "SELECT id, stop_id, stop_name, stop_lat, stop_lon, agency FROM stop"
                )
                for row in cur.fetchall():
                    sid, gtfs_id, name, lat, lon, agency = row
                    self.stops[sid] = {
                        "id": sid, "stop_id": gtfs_id, "name": name,
                        "lat": lat, "lon": lon, "agency": agency,
                    }
                    self.transit_edges[sid] = []
                    # Add to grid spatial index
                    cell = (round(lat / GRID_STEP), round(lon / GRID_STEP))
                    self._grid.setdefault(cell, []).append(sid)

                # Load stop_times ordered for efficient edge building
                # Each consecutive pair (seq n, seq n+1) in the same trip is a directed edge.
                cur.execute(
                    """
                    SELECT
                        st.stop_fk,
                        LEAD(st.stop_fk)      OVER w AS next_stop,
                        st.departure_sec,
                        LEAD(st.arrival_sec)  OVER w AS next_arr,
                        t.id                         AS trip_fk,
                        t.route_fk
                    FROM stop_time st
                    JOIN trip t ON t.id = st.trip_fk
                    WINDOW w AS (PARTITION BY st.trip_fk ORDER BY st.stop_sequence)
                    """
                )
                for row in cur.fetchall():
                    from_stop, to_stop, dep, arr, trip_id, route_id = row
                    if to_stop is None or dep is None or arr is None:
                        continue
                    self.transit_edges[from_stop].append(
                        (dep, arr, to_stop, trip_id, route_id)
                    )
        finally:
            conn.close()

        # Build walking edges using grid spatial index
        self._build_walk_edges()
        self._loaded = True
        n_transit = sum(len(v) for v in self.transit_edges.values())
        n_walk = sum(len(v) for v in self.walk_edges.values())
        logger.info(
            "GTFSGraph: %d stops, %d transit edges, %d walk edges loaded",
            len(self.stops), n_transit, n_walk,
        )

    def _build_walk_edges(self) -> None:
        """For each stop, find stops within WALK_RADIUS_M using the grid index."""
        for sid, sdata in self.stops.items():
            lat, lon = sdata["lat"], sdata["lon"]
            nearby: list[tuple] = []
            # Scan the 3×3 grid neighbourhood
            lat_cell = round(lat / GRID_STEP)
            lon_cell = round(lon / GRID_STEP)
            for dl in (-1, 0, 1):
                for dm in (-1, 0, 1):
                    for nid in self._grid.get((lat_cell + dl, lon_cell + dm), []):
                        if nid == sid:
                            continue
                        nd = self.stops[nid]
                        dist = haversine(lat, lon, nd["lat"], nd["lon"])
                        if dist <= WALK_RADIUS_M:
                            walk_sec = int(dist / WALK_SPEED_MPS)
                            nearby.append((walk_sec, nid))
            self.walk_edges[sid] = nearby

    def stop_by_gtfs_id(self, agency: str, gtfs_stop_id: str) -> int | None:
        """Resolve (agency, gtfs_stop_id) → DB id."""
        for sid, s in self.stops.items():
            if s["agency"] == agency and s["stop_id"] == gtfs_stop_id:
                return sid
        return None

    def nearby_stops(self, lat: float, lon: float, radius_m: float = 600) -> list[dict]:
        """Return stops within radius_m sorted by distance."""
        results = []
        lat_cell = round(lat / GRID_STEP)
        lon_cell = round(lon / GRID_STEP)
        cells_needed = math.ceil(radius_m / (GRID_STEP * EARTH_RADIUS_M * math.pi / 180)) + 1
        for dl in range(-cells_needed, cells_needed + 1):
            for dm in range(-cells_needed, cells_needed + 1):
                for sid in self._grid.get((lat_cell + dl, lon_cell + dm), []):
                    s = self.stops[sid]
                    d = haversine(lat, lon, s["lat"], s["lon"])
                    if d <= radius_m:
                        results.append({**s, "distance_m": round(d)})
        results.sort(key=lambda x: x["distance_m"])
        return results


# ── router ────────────────────────────────────────────────────────────────────


class GTFSRouter:
    """
    Time-dependent Dijkstra on the GTFS + walking graph.

    State: (earliest_arrival_sec, current_stop_id, vehicle_changes)
    Priority queue key: earliest_arrival_sec

    Walking edges have no departure constraint (can be taken any time).
    Transit edges require boarding at departure_sec >= current_time.
    """

    def __init__(self, graph: GTFSGraph) -> None:
        self.graph = graph

    @lru_cache(maxsize=4096)
    def route(
        self,
        origin_stop_db_id: int,
        dest_stop_db_id: int,
        departure_sec: int,
    ) -> dict | None:
        """
        Find the earliest-arrival path from origin to dest departing ≥ departure_sec.
        Returns a path dict or None if unreachable.

        LRU cache key: (origin, dest, departure_sec rounded to nearest 60s)
        — callers should normalise departure_sec to minute boundaries.
        """
        if origin_stop_db_id not in self.graph.stops:
            return None
        if dest_stop_db_id not in self.graph.stops:
            return None

        # dist[stop_id] = earliest arrival at that stop
        dist: dict[int, float] = {origin_stop_db_id: float(departure_sec)}
        # prev[stop_id] = (prev_stop_id, edge_info)
        prev: dict[int, tuple] = {}
        # vehicle_changes[stop_id]
        changes: dict[int, int] = {origin_stop_db_id: 0}

        # heap: (arrival_sec, stop_id, last_trip_id)
        heap: list[tuple] = [(departure_sec, origin_stop_db_id, -1)]

        while heap:
            arr_sec, u, last_trip = heapq.heappop(heap)
            if arr_sec > dist.get(u, INF):
                continue
            if u == dest_stop_db_id:
                break

            # Transit edges: pick the next available departure from this stop
            for edge in self.graph.transit_edges.get(u, []):
                dep, next_arr, v, trip_id, route_id = edge
                if dep < arr_sec:
                    continue   # already departed
                # Transfer penalty when switching vehicles
                penalty = TRANSFER_PENALTY_SEC if (last_trip != -1 and trip_id != last_trip) else 0
                new_arr = next_arr + penalty
                if new_arr < dist.get(v, INF):
                    dist[v] = new_arr
                    prev[v] = (u, {"type": "transit", "trip_id": trip_id,
                                   "route_id": route_id, "dep": dep, "arr": next_arr})
                    changes[v] = changes.get(u, 0) + (1 if penalty else 0)
                    heapq.heappush(heap, (new_arr, v, trip_id))

            # Walking edges (no departure constraint)
            for walk_sec, v in self.graph.walk_edges.get(u, []):
                new_arr = arr_sec + walk_sec
                if new_arr < dist.get(v, INF):
                    dist[v] = new_arr
                    prev[v] = (u, {"type": "walk", "walk_sec": walk_sec})
                    changes[v] = changes.get(u, 0)
                    heapq.heappush(heap, (new_arr, v, -1))

        if dest_stop_db_id not in dist or dist[dest_stop_db_id] == INF:
            return None

        # Reconstruct path
        path_stops = []
        node = dest_stop_db_id
        while node in prev:
            path_stops.append(node)
            node, _ = prev[node]
        path_stops.append(origin_stop_db_id)
        path_stops.reverse()

        legs = []
        node = dest_stop_db_id
        while node in prev:
            p, edge_info = prev[node]
            legs.append({**edge_info, "from_stop": p, "to_stop": node})
            node = p
        legs.reverse()

        origin_s = self.graph.stops[origin_stop_db_id]
        dest_s = self.graph.stops[dest_stop_db_id]
        total_sec = int(dist[dest_stop_db_id]) - departure_sec

        return {
            "origin": origin_s,
            "destination": dest_s,
            "departure_sec": departure_sec,
            "arrival_sec": int(dist[dest_stop_db_id]),
            "total_duration_sec": total_sec,
            "vehicle_changes": changes.get(dest_stop_db_id, 0),
            "legs": legs,
            "stop_sequence": path_stops,
        }


# ── module-level singleton (initialised at startup) ────────────────────────────

_graph: GTFSGraph | None = None
_router: GTFSRouter | None = None


def get_router() -> GTFSRouter:
    global _graph, _router
    if _router is None:
        raise RuntimeError("GTFSRouter not initialised — call init_router() at startup")
    return _router


def init_router(db_url: str | None = None) -> GTFSRouter:
    """Load graph from DB and return the router singleton."""
    global _graph, _router
    _graph = GTFSGraph()
    _graph.load(db_url or settings.db_url)
    _router = GTFSRouter(_graph)
    return _router
