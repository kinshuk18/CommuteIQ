#!/usr/bin/env python3
"""
fetch_gtfs.py — Download and validate real BMTC and BMRCL (Namma Metro) GTFS feeds.
"""

import hashlib
import json
import os
import sys
import urllib.request
import zipfile
from pathlib import Path

# Paths relative to CommuteIQ root
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw"
CHECKSUM_FILE = PROJECT_ROOT / "data" / "checksums.json"

FEEDS = {
    "bmtc": {
        "url": "https://storage.googleapis.com/storage/v1/b/mdb-latest/o/in-karnataka-bangalore-metropolitan-transport-corporation-bmtc-gtfs-2013.zip?alt=media",
        "zip_name": "bmtc_gtfs.zip",
        "extract_to": "bmtc",
        "required_files": ["stops.txt", "routes.txt", "trips.txt", "stop_times.txt"],
    },
    "bmrcl": {
        "url": "https://raw.githubusercontent.com/Vonter/bmrcl-gtfs/main/gtfs/bmrcl.zip",
        "zip_name": "bmrcl_gtfs.zip",
        "extract_to": "bmrcl",
        "required_files": ["stops.txt", "routes.txt", "trips.txt", "stop_times.txt"],
    },
}


def compute_sha256(file_path: Path) -> str:
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(8192):
            hasher.update(chunk)
    return hasher.hexdigest()


def count_lines(file_path: Path) -> int:
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        return sum(1 for _ in f)


def fetch_and_validate():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    checksums = {}
    if CHECKSUM_FILE.exists():
        try:
            with open(CHECKSUM_FILE, "r") as f:
                checksums = json.load(f)
        except Exception:
            checksums = {}

    summary = {}

    for feed_id, config in FEEDS.items():
        zip_path = RAW_DIR / config["zip_name"]
        extract_dir = RAW_DIR / config["extract_to"]

        print(f"[{feed_id.upper()}] Downloading from {config['url']}...")
        req = urllib.request.Request(config["url"], headers={"User-Agent": "CommuteIQ/1.0"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            content = resp.read()
            with open(zip_path, "wb") as f:
                f.write(content)

        file_hash = compute_sha256(zip_path)
        checksums[config["zip_name"]] = {
            "sha256": file_hash,
            "bytes": zip_path.stat().st_size,
        }
        print(f"[{feed_id.upper()}] Downloaded {zip_path.stat().st_size} bytes, SHA256: {file_hash[:12]}...")

        # Extract
        extract_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path, "r") as z:
            z.extractall(extract_dir)

        # Validate required files and count rows
        feed_summary = {}
        for req_file in config["required_files"]:
            file_on_disk = extract_dir / req_file
            if not file_on_disk.exists():
                print(f"ERROR: Missing required file {req_file} in {feed_id} feed!", file=sys.stderr)
                sys.exit(1)
            total_lines = count_lines(file_on_disk)
            # data rows = total lines - 1 header line
            data_rows = max(0, total_lines - 1)
            feed_summary[req_file] = data_rows
            print(f"[{feed_id.upper()}] {req_file}: {data_rows} records (total lines: {total_lines})")

        summary[feed_id] = feed_summary

    # Save checksums
    with open(CHECKSUM_FILE, "w", encoding="utf-8") as f:
        json.dump(checksums, f, indent=2)
    print(f"\nChecksums updated in {CHECKSUM_FILE}")

    # Output JSON summary for docs
    summary_path = RAW_DIR / "gtfs_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"GTFS row count summary saved to {summary_path}")


if __name__ == "__main__":
    fetch_and_validate()
