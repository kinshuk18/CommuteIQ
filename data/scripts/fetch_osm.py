#!/usr/bin/env python3
"""
fetch_osm.py — Fetch real Bengaluru tech parks, IT campuses, and commercial offices via OpenStreetMap.
"""

import hashlib
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw"
CHECKSUM_FILE = PROJECT_ROOT / "data" / "checksums.json"
OUTPUT_FILE = RAW_DIR / "offices.json"

OVERPASS_SERVERS = [
    "https://overpass.openstreetmap.fr/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]

# Bengaluru bounding box: lat 12.80 to 13.15, lon 77.45 to 77.80
QUERY = """
[out:json][timeout:30];
(
  node["office"]["name"](12.80,77.45,13.15,77.80);
  way["office"]["name"](12.80,77.45,13.15,77.80);
  way["building"="office"]["name"](12.80,77.45,13.15,77.80);
  way["landuse"="commercial"]["name"](12.80,77.45,13.15,77.80);
);
out center 300;
"""

NOMINATIM_SEEDS = [
    "Manyata Tech Park Bengaluru",
    "Bagmane Tech Park CV Raman Nagar Bengaluru",
    "Bagmane Constellation Business Park Bengaluru",
    "Ecospace Business Park Bellandur Bengaluru",
    "Prestige Tech Park Marathahalli Bengaluru",
    "International Tech Park Bengaluru Whitefield",
    "ETV Embassy TechVillage Bengaluru",
    "RMZ Ecoworld Bellandur Bengaluru",
    "Global Village Tech Park Rajarajeshwari Nagar Bengaluru",
    "Cessna Business Park Bengaluru",
    "Kalyani Magnum Tech Park JP Nagar Bengaluru",
    "Electronic City Phase 1 Bengaluru",
    "Electronic City Phase 2 Bengaluru",
    "Divyasree Technopolis Yemalur Bengaluru",
    "RMZ Infinity Old Madras Road Bengaluru",
    "Prestige Shantiniketan Whitefield Bengaluru",
    "Brigade Tech Gardens Brookefield Bengaluru",
    "Salarpuria Sattva Knowledge Court Whitefield Bengaluru",
    "Velankani Tech Park Electronic City Bengaluru",
    "Embassy GolfLinks Business Park Domlur Bengaluru",
]


def compute_sha256(file_path: Path) -> str:
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(8192):
            hasher.update(chunk)
    return hasher.hexdigest()


def fetch_from_overpass() -> list:
    encoded = urllib.parse.urlencode({"data": QUERY}).encode()
    for ep in OVERPASS_SERVERS:
        print(f"[OSM] Querying Overpass endpoint: {ep}...")
        req = urllib.request.Request(
            ep,
            data=encoded,
            headers={"User-Agent": "CommuteIQ-Academic/1.0 (contact: student-project)"},
        )
        try:
            with urllib.request.urlopen(req, timeout=35) as resp:
                data = json.loads(resp.read().decode())
                elements = data.get("elements", [])
                if elements:
                    print(f"[OSM] Successfully fetched {len(elements)} raw elements from {ep}")
                    return elements
        except Exception as e:
            print(f"[OSM] Endpoint {ep} failed: {e}")
    return []


def fetch_from_nominatim() -> list:
    print("[OSM] Overpass unavailable, fetching seed tech parks via Nominatim...")
    results = []
    for seed in NOMINATIM_SEEDS:
        url = f"https://nominatim.openstreetmap.org/search?q={urllib.parse.quote(seed)}&format=json&limit=1"
        req = urllib.request.Request(url, headers={"User-Agent": "CommuteIQ-Academic/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
                if data:
                    item = data[0]
                    results.append({
                        "id": int(item.get("osm_id", 0)),
                        "type": item.get("osm_type", "node"),
                        "lat": float(item["lat"]),
                        "lon": float(item["lon"]),
                        "tags": {
                            "name": seed.replace(" Bengaluru", ""),
                            "office": "commercial",
                            "display_name": item.get("display_name", ""),
                        },
                    })
                    print(f"  + Seed: {seed} -> ({item['lat']}, {item['lon']})")
        except Exception as e:
            print(f"  - Failed seed {seed}: {e}")
    return results


def process_and_save():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    elements = fetch_from_overpass()
    if not elements:
        elements = fetch_from_nominatim()

    if not elements:
        print("ERROR: Failed to fetch OSM data from both Overpass and Nominatim!", file=sys.stderr)
        sys.exit(1)

    offices = []
    seen_names = set()

    for el in elements:
        tags = el.get("tags", {})
        name = tags.get("name", "").strip()
        if not name:
            continue
        norm_name = name.lower()
        if norm_name in seen_names:
            continue

        lat = el.get("lat")
        lon = el.get("lon")
        if lat is None or lon is None:
            center = el.get("center", {})
            lat = center.get("lat")
            lon = center.get("lon")

        if lat is None or lon is None:
            continue

        seen_names.add(norm_name)
        office_type = tags.get("office") or tags.get("building") or tags.get("landuse") or "office"
        suburb = tags.get("addr:suburb") or tags.get("addr:district") or tags.get("addr:street") or ""

        offices.append({
            "osm_id": el.get("id"),
            "osm_type": el.get("type"),
            "name": name,
            "category": office_type,
            "suburb": suburb,
            "lat": round(float(lat), 7),
            "lon": round(float(lon), 7),
        })

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(offices, f, indent=2)

    file_hash = compute_sha256(OUTPUT_FILE)
    print(f"\n[OSM] Saved {len(offices)} real offices/tech parks to {OUTPUT_FILE}")
    print(f"[OSM] SHA256: {file_hash}")

    # Update checksums
    checksums = {}
    if CHECKSUM_FILE.exists():
        try:
            with open(CHECKSUM_FILE, "r") as f:
                checksums = json.load(f)
        except Exception:
            checksums = {}
    checksums["offices.json"] = {
        "sha256": file_hash,
        "bytes": OUTPUT_FILE.stat().st_size,
        "count": len(offices),
    }
    with open(CHECKSUM_FILE, "w", encoding="utf-8") as f:
        json.dump(checksums, f, indent=2)


if __name__ == "__main__":
    process_and_save()
