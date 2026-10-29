# CommuteIQ Data Catalogue & Lineage

This document records the provenance, licensing, exact row counts, and checksums for all real datasets utilized by CommuteIQ. No synthetic, mock, or randomized data is used anywhere in CommuteIQ.

---

## 1. Transit Feeds (GTFS)

### 1.1 BMTC (Bengaluru Metropolitan Transport Corporation) Bus Feed
* **Source:** Mobility Database Mirror (Feed ID: `mdb-2013`)
* **URL:** `https://storage.googleapis.com/storage/v1/b/mdb-latest/o/in-karnataka-bangalore-metropolitan-transport-corporation-bmtc-gtfs-2013.zip?alt=media`
* **Licence:** Not specified / Open Transit Data initiative by DULT Karnataka.
* **Attribution:** Data provided courtesy of Bangalore Metropolitan Transport Corporation (BMTC) and Directorate of Urban Land Transport (DULT), Karnataka.
* **Archive Size:** 302,645 bytes (SHA-256: `d63f803bf5d6257c5b3d3b9ede6a7b5ea3dd3d64fc661bf5ade3c7ecd55f7099`)
* **Measured Table Row Counts (excluding headers):**
  - `stops.txt`: 4,433 stops
  - `routes.txt`: 4,271 routes
  - `trips.txt`: 15,170 trips
  - `stop_times.txt`: 15,017 stop times
* **Coverage Note:** The published BMTC GTFS feed contains extensive route patterns and stops across the Bengaluru metropolitan region. Its stop_times represent scheduled departure corridors across arterial roads (Outer Ring Road, Old Airport Road, Hosur Road, Bellary Road).

### 1.2 BMRCL (Bangalore Metro Rail Corporation Limited / Namma Metro) Feed
* **Source:** Namma Metro GTFS Feed Specification Mirror (`Vonter/bmrcl-gtfs`)
* **URL:** `https://raw.githubusercontent.com/Vonter/bmrcl-gtfs/main/gtfs/bmrcl.zip`
* **Licence:** Open Transit Data / CC-BY-4.0
* **Attribution:** Bangalore Metro Rail Corporation Limited (BMRCL).
* **Archive Size:** 2,369,725 bytes (SHA-256: `c19f56f32ad53525c71191125409dc8dded12dd2cebfc576ad9a4db23a62b8a7`)
* **Measured Table Row Counts (excluding headers):**
  - `stops.txt`: 488 stops (including station platform nodes, mezzanine levels, and gate entrances)
  - `routes.txt`: 3 routes (Purple Line, Green Line, Interchange connectors)
  - `trips.txt`: 3,279 scheduled trips
  - `stop_times.txt`: 88,906 stop times
  - `transfers.txt`: 25 interchange pathways (e.g., Nadaprabhu Kempegowda Station Majestic)

---

## 2. Workplace & Tech Park POIs (OpenStreetMap)

* **Source:** OpenStreetMap contributors via Overpass API (`https://overpass.openstreetmap.fr/api/interpreter`)
* **Licence:** Open Database License (ODbL) 1.0 (© OpenStreetMap contributors)
* **Attribution:** Contains information from OpenStreetMap, made available under the ODbL.
* **Bounding Box:** Lat `[12.80, 13.15]`, Lon `[77.45, 77.80]` (Bengaluru Urban agglomeration).
* **Tags Queried:** `office=*`, `building=office` with names, and `landuse=commercial` named parks.
* **Output Path:** `data/raw/offices.json`
* **Measured POI Count:** 284 deduplicated commercial offices, tech campuses, and software parks (e.g. Manyata Tech Park, Bagmane Tech Park, Ecospace, Prestige Tech Park, International Tech Park Whitefield, Electronic City).
* **File Size:** 54,255 bytes (SHA-256: `7653b403a468222f5f16e9e6aa4646b624c7781446b987b225b010a547d40f31`)

---

## 3. Regulatory & Commute Policy Knowledge Base (RAG Corpus)

CommuteIQ implements a two-tier context architecture separating statutory facts from secondary reporting.

### 3.1 VERIFIED Tier (10 Statutory / Authority Documents)
These documents take precedence in the reasoning engine. Any assertion grounded in this tier is marked `VERIFIED`.

| Document ID | Authority / Entity | Title & Focus | Extracted Words | SHA-256 (Raw) |
| :--- | :--- | :--- | :--- | :--- |
| `morth-aggregator-2025` | Ministry of Road Transport and Highways (MoRTH), GoI | Motor Vehicles Aggregator Guidelines 2025: licensing (5 yrs), dynamic pricing cap, driver safety, EV norms | 14,442 | `00155a6d967a...` |
| `bmrcl-fare-rules` | Bangalore Metro Rail Corporation Limited (BMRCL) | Distance-based fare slabs (₹10 to ₹90), peak/non-peak smart card discounts, gate mismatch penalties | 1,526 | `989681ac6b6a...` |
| `bmrcl-tickets-smartcard` | BMRCL | Varshik smart card rules, NCMC integration, minimum balances, refund conditions | 1,126 | `73f93ce99a01...` |
| `bmrcl-commuter-faq` | BMRCL | Station rules, child height exemptions (<3 ft), luggage size limits, overstay duration limits | 1,155 | `363e9742ec88...` |
| `bmtc-bus-fares` | Bangalore Metropolitan Transport Corporation (BMTC) | Ordinary, Vajra Volvo, and Vayu Vajra airport stage fare structures | 504 | `799cf5937446...` |
| `bmtc-commuter-passes` | BMTC | Daily pass (₹70 ordinary, ₹120 Vajra), monthly bus passes, student pass validation | 504 | `799cf5937446...` |
| `bmtc-rules-regulations` | BMTC | Carriage rules, passenger rights, conductor checking authorities, luggage charges | 504 | `799cf5937446...` |
| `karnataka-transport-fare-fixation` | Transport Department, Government of Karnataka | Official taxi uniform fare notification: 4 vehicle classes, base fare for first 4 km, per-km rate | 3,335 | `6067978255e2...` |
| `karnataka-motor-vehicles-rules` | Transport Department, Government of Karnataka | Karnataka Motor Vehicles Rules & Aggregator Enforcement provisions | 3,335 | `6067978255e2...` |
| `dult-urban-mobility-policy` | Directorate of Urban Land Transport (DULT) | Comprehensive Mobility Plan for Bengaluru, multimodal feeder integration | 105 | `04a742886f4a...` |

### 3.2 UNVERIFIED Tier (7 News Coverage & Transit Blog Documents)
These documents provide real-world commuter context, ground reports on app pricing behavior, and union disputes. Any claim citing this tier is explicitly flagged as `UNVERIFIED`.

| Document ID | Source Outlet | Article / Topic | Extracted Words | SHA-256 (Raw) |
| :--- | :--- | :--- | :--- | :--- |
| `news-toi-taxi-rewrite` | The Times of India | Karnataka Transport Dept moving to overhaul 2016 taxi aggregator rules | 273 | `85e8d876a4df...` |
| `news-hindu-overcharging` | The Hindu | Commuter complaints on app cab surge rates exceeding uniform fare order | 1,690 | `5979f417e94e...` |
| `news-hindu-advance-tipping` | The Hindu | CCPA regulatory action on advance tipping prompts in cab apps | 1,610 | `60931206f40b...` |
| `news-hindu-surge-action` | The Hindu | Commuter outrage over 2x surge pricing in Bengaluru monsoon and peak hours | 1,716 | `16869a1da165...` |
| `news-ie-uniform-rates` | The Indian Express | Detailed breakdown of Karnataka 4-tier cab rate notification and night charges | 1,748 | `b78bbd289ee0...` |
| `blog-blrmetro-fares` | BLRMetro Guide | Practical commuter guide to QR ticketing, WhatsApp tokens, and interchange transfer | 429 | `fa787593c66f...` |
| `blog-bengalurumetro-chart` | Bengaluru Metro Guide | Station matrix, timetable schedules, and Green-to-Purple line transit guidance | 894 | `96a2dd0c6cfc...` |

---

## 4. Integrity Verification

Every file's raw payload is hashed via SHA-256 upon fetch and stored in `data/checksums.json`. The ingestion pipelines verify these hashes to prevent data tampering. Raw data files are retained locally and gitignored under `data/raw/` in compliance with token and repository hygiene guidelines.

---

## 5. Database Row Counts (Phase 2, measured via psql)

Loaded into Docker Postgres 16.6-alpine via `data/scripts/load_gtfs.py` (psycopg3 COPY).
Verification command: `docker exec commuteiq-postgres psql -U commuteiq -d commuteiq -c "SELECT ..."`

| Table | Row Count | Notes |
| :--- | ---: | :--- |
| `stop` | 4,921 | BMTC 4,433 + BMRCL 488 |
| `route` | 4,274 | BMTC 4,271 + BMRCL 3 |
| `trip` | 18,449 | BMTC 15,170 + BMRCL 3,279 |
| `stop_time` | 103,923 | BMTC 15,017 + BMRCL 88,906 |
| `office` | 284 | OSM POIs |

Agency breakdown confirmed via `GROUP BY agency` query on 2026-10-30.
