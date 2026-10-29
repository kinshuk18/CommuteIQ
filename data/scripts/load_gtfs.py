#!/usr/bin/env python3
"""
load_gtfs.py — bulk-loads BMTC and BMRCL GTFS data into the CommuteIQ Postgres schema.

Uses psycopg3 COPY for throughput; resolves FK relationships in-process so
the database receives denormalised rows with no per-row round-trips.

Usage (from project root):
    uv run python data/scripts/load_gtfs.py

Environment variables (from .env / Docker injected):
    COMMUTEIQ_DB_URL  — psycopg3 conninfo string
                        default: host=localhost port=5434 dbname=commuteiq
                                 user=commuteiq password=commuteiq
"""

import csv
import os
import time
from pathlib import Path

import psycopg

# ── configuration ────────────────────────────────────────────────────────────

DB_URL = os.environ.get(
    "COMMUTEIQ_DB_URL",
    "host=localhost port=5434 dbname=commuteiq user=commuteiq password=commuteiq",
)

DATA_ROOT = Path(__file__).parent.parent / "raw"

FEEDS = [
    {
        "agency": "bmtc",
        "gtfs_dir": DATA_ROOT / "bmtc",
        "route_type_default": 3,  # bus
    },
    {
        "agency": "bmrcl",
        "gtfs_dir": DATA_ROOT / "bmrcl",
        "route_type_default": 1,  # metro
    },
]


# ── helpers ──────────────────────────────────────────────────────────────────

def parse_seconds(hhmm: str) -> int:
    """Convert HH:MM:SS (allows hours > 23) to integer seconds since midnight."""
    hhmm = (hhmm or "").strip()
    if not hhmm:
        return 0
    parts = hhmm.split(":")
    h = int(parts[0])
    m = int(parts[1]) if len(parts) > 1 else 0
    s = int(parts[2]) if len(parts) > 2 else 0
    return h * 3600 + m * 60 + s


def read_gtfs_csv(gtfs_dir: Path, filename: str) -> list[dict]:
    """Read a GTFS text file from a directory; return [] if file is absent."""
    p = gtfs_dir / filename
    if not p.exists():
        return []
    with p.open(encoding="utf-8-sig") as f:  # strip BOM if present
        return list(csv.DictReader(f))


def copy_rows(cur, table: str, columns: list[str], rows: list[tuple]) -> int:
    """Stream rows into Postgres via COPY protocol."""
    if not rows:
        return 0
    col_str = ", ".join(columns)
    with cur.copy(f"COPY {table} ({col_str}) FROM STDIN") as copy:
        for row in rows:
            copy.write_row(row)
    return len(rows)


# ── per-agency loader ─────────────────────────────────────────────────────────

def load_agency(conn, agency: str, gtfs_dir: Path, route_type_default: int) -> dict:
    """Load one GTFS feed into the DB; return a dict of table → row counts."""
    counts: dict[str, int] = {}
    t0 = time.monotonic()

    # ── stops ────────────────────────────────────────────────────────────────
    stop_rows_raw = read_gtfs_csv(gtfs_dir, "stops.txt")
    stop_gtfs_to_pk: dict[str, int] = {}

    stop_tuples = []
    for r in stop_rows_raw:
        stop_tuples.append((
            agency,
            r["stop_id"].strip(),
            r.get("stop_code", "").strip() or None,
            r["stop_name"].strip(),
            float(r["stop_lat"]),
            float(r["stop_lon"]),
            int(r.get("location_type", "0") or "0"),
            r.get("parent_station", "").strip() or None,
        ))

    with conn.cursor() as cur:
        cur.execute(
            "CREATE TEMP TABLE tmp_stop (LIKE stop INCLUDING DEFAULTS) ON COMMIT DROP"
        )
        copy_rows(
            cur, "tmp_stop",
            ["agency", "stop_id", "stop_code", "stop_name",
             "stop_lat", "stop_lon", "location_type", "parent_station"],
            stop_tuples,
        )
        cur.execute(
            """
            INSERT INTO stop (agency, stop_id, stop_code, stop_name,
                              stop_lat, stop_lon, location_type, parent_station)
            SELECT agency, stop_id, stop_code, stop_name,
                   stop_lat, stop_lon, location_type, parent_station
            FROM tmp_stop
            ON CONFLICT (agency, stop_id) DO NOTHING
            """
        )
        conn.commit()
        cur.execute("SELECT stop_id, id FROM stop WHERE agency = %s", (agency,))
        for gtfs_id, pk in cur.fetchall():
            stop_gtfs_to_pk[gtfs_id] = pk
        counts["stop"] = len(stop_gtfs_to_pk)

    # ── routes ───────────────────────────────────────────────────────────────
    route_rows_raw = read_gtfs_csv(gtfs_dir, "routes.txt")
    route_gtfs_to_pk: dict[str, int] = {}

    route_tuples = []
    for r in route_rows_raw:
        route_tuples.append((
            agency,
            r["route_id"].strip(),
            r.get("route_short_name", "").strip() or None,
            r.get("route_long_name", "").strip() or None,
            int(r.get("route_type", route_type_default) or route_type_default),
        ))

    with conn.cursor() as cur:
        cur.execute(
            "CREATE TEMP TABLE tmp_route (LIKE route INCLUDING DEFAULTS) ON COMMIT DROP"
        )
        copy_rows(
            cur, "tmp_route",
            ["agency", "route_id", "route_short_name", "route_long_name", "route_type"],
            route_tuples,
        )
        cur.execute(
            """
            INSERT INTO route (agency, route_id, route_short_name, route_long_name, route_type)
            SELECT agency, route_id, route_short_name, route_long_name, route_type
            FROM tmp_route
            ON CONFLICT (agency, route_id) DO NOTHING
            """
        )
        conn.commit()
        cur.execute("SELECT route_id, id FROM route WHERE agency = %s", (agency,))
        for gtfs_id, pk in cur.fetchall():
            route_gtfs_to_pk[gtfs_id] = pk
        counts["route"] = len(route_gtfs_to_pk)

    # ── trips ────────────────────────────────────────────────────────────────
    trip_rows_raw = read_gtfs_csv(gtfs_dir, "trips.txt")
    trip_gtfs_to_pk: dict[str, int] = {}

    trip_tuples = []
    skipped_trips = 0
    for r in trip_rows_raw:
        rid = r["route_id"].strip()
        route_pk = route_gtfs_to_pk.get(rid)
        if route_pk is None:
            skipped_trips += 1
            continue
        trip_tuples.append((
            agency,
            r["trip_id"].strip(),
            route_pk,
            r.get("service_id", "").strip(),
            int(r.get("direction_id", "0") or "0"),
            r.get("shape_id", "").strip() or None,
        ))

    with conn.cursor() as cur:
        cur.execute(
            "CREATE TEMP TABLE tmp_trip (LIKE trip INCLUDING DEFAULTS) ON COMMIT DROP"
        )
        copy_rows(
            cur, "tmp_trip",
            ["agency", "trip_id", "route_fk", "service_id", "direction_id", "shape_id"],
            trip_tuples,
        )
        cur.execute(
            """
            INSERT INTO trip (agency, trip_id, route_fk, service_id, direction_id, shape_id)
            SELECT agency, trip_id, route_fk, service_id, direction_id, shape_id
            FROM tmp_trip
            ON CONFLICT (agency, trip_id) DO NOTHING
            """
        )
        conn.commit()
        cur.execute("SELECT trip_id, id FROM trip WHERE agency = %s", (agency,))
        for gtfs_id, pk in cur.fetchall():
            trip_gtfs_to_pk[gtfs_id] = pk
        counts["trip"] = len(trip_gtfs_to_pk)

    # ── stop_times ───────────────────────────────────────────────────────────
    # Large table: batch in 50 k chunks to limit peak memory use
    st_rows_raw = read_gtfs_csv(gtfs_dir, "stop_times.txt")
    BATCH = 50_000
    total_st = 0
    skipped_st = 0
    batch: list[tuple] = []

    with conn.cursor() as cur:
        for r in st_rows_raw:
            tid = r["trip_id"].strip()
            sid = r["stop_id"].strip()
            trip_pk = trip_gtfs_to_pk.get(tid)
            stop_pk = stop_gtfs_to_pk.get(sid)
            if trip_pk is None or stop_pk is None:
                skipped_st += 1
                continue
            batch.append((
                trip_pk,
                stop_pk,
                int(r["stop_sequence"]),
                parse_seconds(r.get("arrival_time") or r.get("departure_time", "0")),
                parse_seconds(r.get("departure_time") or r.get("arrival_time", "0")),
                int(r.get("pickup_type", "0") or "0"),
                int(r.get("drop_off_type", "0") or "0"),
            ))
            if len(batch) >= BATCH:
                copy_rows(
                    cur, "stop_time",
                    ["trip_fk", "stop_fk", "stop_sequence",
                     "arrival_sec", "departure_sec", "pickup_type", "drop_off_type"],
                    batch,
                )
                total_st += len(batch)
                batch.clear()
        if batch:
            copy_rows(
                cur, "stop_time",
                ["trip_fk", "stop_fk", "stop_sequence",
                 "arrival_sec", "departure_sec", "pickup_type", "drop_off_type"],
                batch,
            )
            total_st += len(batch)
        conn.commit()

    counts["stop_time"] = total_st
    counts["skipped_trips"] = skipped_trips
    counts["skipped_stop_times"] = skipped_st

    elapsed = time.monotonic() - t0
    print(
        f"[{agency}] stops={counts['stop']} routes={counts['route']} "
        f"trips={counts['trip']} stop_times={counts['stop_time']} "
        f"(skipped trips={skipped_trips} st={skipped_st}) "
        f"({elapsed:.1f}s)"
    )
    return counts


# ── offices loader ────────────────────────────────────────────────────────────

def load_offices(conn) -> int:
    """Load OSM offices from offices.json into the office table."""
    import json

    offices_path = DATA_ROOT / "offices.json"
    with offices_path.open() as f:
        data = json.load(f)

    # offices.json is preprocessed: each item has osm_id, name, lat, lon at top level
    elements = data if isinstance(data, list) else data.get("elements", [])
    rows = []
    for el in elements:
        osm_id = el.get("osm_id") or el.get("id")
        name = (el.get("name") or "").strip()
        if not name or osm_id is None:
            continue
        lat = el.get("lat")
        lon = el.get("lon")
        if lat is None or lon is None:
            continue
        office_type = el.get("osm_type") or el.get("type", "node")
        tags = {k: v for k, v in el.items() if k not in ("osm_id", "osm_type", "lat", "lon")}
        rows.append((
            int(osm_id),
            name,
            float(lat),
            float(lon),
            office_type,
            json.dumps(tags),
        ))

    with conn.cursor() as cur:
        cur.execute(
            "CREATE TEMP TABLE tmp_office (LIKE office INCLUDING DEFAULTS) ON COMMIT DROP"
        )
        copy_rows(
            cur, "tmp_office",
            ["osm_id", "name", "lat", "lon", "office_type", "tags"],
            rows,
        )
        cur.execute(
            """
            INSERT INTO office (osm_id, name, lat, lon, office_type, tags)
            SELECT osm_id, name, lat, lon, office_type, tags::jsonb
            FROM tmp_office
            ON CONFLICT (osm_id) DO NOTHING
            """
        )
        conn.commit()

    print(f"[offices] loaded={len(rows)} rows")
    return len(rows)


# ── entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    print(f"Connecting to Postgres … {DB_URL}")
    with psycopg.connect(DB_URL, autocommit=False) as conn:
        for feed in FEEDS:
            load_agency(
                conn,
                agency=feed["agency"],
                gtfs_dir=feed["gtfs_dir"],
                route_type_default=feed["route_type_default"],
            )
        load_offices(conn)
    print("Done.")


if __name__ == "__main__":
    main()
