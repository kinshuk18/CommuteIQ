# CommuteIQ — Implementation Progress Tracker

## Project Overview
CommuteIQ is a hybrid-work commute copilot for Bengaluru combining BMTC bus + Namma Metro GTFS routing, agentic RAG over verified transit policy documents with strict context tiering (VERIFIED vs UNVERIFIED), traditional ML runtime prediction with MLflow, and an event-driven architecture with Spring Boot 3, FastAPI, Kafka, Redis, and React.

---

## Phase Status Summary
- [x] **Phase 1: Project Scaffolding & Real Data Acquisition** (Completed)
- [x] **Phase 2: PostgreSQL Schema (Flyway) & GTFS / OSM Ingestion** (Completed)
- [ ] **Phase 3: AI Service Core (LLM Providers, Custom Router, ML Regressor + MLflow)**
- [ ] **Phase 4: Agentic RAG (LlamaIndex + 3 Vector Backends, ContextBuilder, LangGraph Agent)**
- [ ] **Phase 5: Gateway Service (Spring Boot 3 REST, GraphQL, Redis Cache & Rate Limiting, Kafka, Resilience4j)**
- [ ] **Phase 6: Kafka Consumer, Feature Drift Monitoring & End-to-End Smoke Test**
- [ ] **Phase 7: Web UI (Vite + React + TS + Leaflet Multimodal Viewer & Chat)**
- [ ] **Phase 8: Production Deployment (K8s Manifests, Multi-Stage Dockerfiles, GitHub Actions CI, Docs)**
- [ ] **Phase 9: Quantitative Evaluation (EVAL.md with real measured numbers) & Optional Fine-Tuning**
- [ ] **Phase 10: Final Audit & Deliverable Verification**

---

## Phase 1 Completed Deliverables
- Project skeleton initialized with `.gitignore`, `.env.example`, `Makefile`, and documentation stubs.
- BMTC bus GTFS: 4,433 stops, 4,271 routes, 15,170 trips, 15,017 stop times downloaded and verified.
- BMRCL Namma Metro GTFS: 488 stops, 3 routes, 3,279 trips, 88,906 stop times downloaded and verified.
- OpenStreetMap POIs: 284 real commercial offices and IT tech parks in Bengaluru extracted via Overpass API.
- RAG Policy Corpus: 10 VERIFIED official government documents (MoRTH 2025, BMRCL, BMTC, Karnataka Transport Dept) and 7 UNVERIFIED news/explainer articles acquired and cleaned.
- Checksums computed and recorded in `data/checksums.json`. Complete attribution and row counts logged in `docs/DATA.md`.

---

## Phase 2 Completed Deliverables
- **Docker Compose**: `deploy/compose.yml` — postgres:16.6-alpine (host port 5434), redis:7.4.1-alpine, kafka KRaft, ai, gateway, web, weaviate profile; healthchecks and named volumes.
- **Flyway migrations** (owned by gateway):
  - `V1__create_gtfs_schema.sql` — stop, route, trip, stop_time, office, saved_commute, feedback + pg_trgm indexes
  - `V2__indexes_and_popularity.sql` — composite lat/lon/agency index + route_popularity table
- **ETL loader**: `data/scripts/load_gtfs.py` — psycopg3 COPY; BMTC + BMRCL GTFS from extracted directories; OSM offices from pre-processed offices.json; idempotent (ON CONFLICT DO NOTHING for stops/routes/trips).
- **Verified DB row counts** (measured 2026-10-30):
  - stop: 4,921 (BMTC 4,433 + BMRCL 488)
  - route: 4,274 (BMTC 4,271 + BMRCL 3)
  - trip: 18,449 (BMTC 15,170 + BMRCL 3,279)
  - stop_time: 103,923 (BMTC 15,017 + BMRCL 88,906)
  - office: 284
- **Gateway skeleton**: `pom.xml` (Spring Boot 3.3.4, Java 21; Flyway, JPA, GraphQL, Redis, Kafka, Resilience4j, Actuator, springdoc), `application.yml`, `GatewayApplication.java`.
- Committed: `feat(p2): flyway migrations V1+V2, GTFS+OSM ETL loader, docker compose with postgres/redis/kafka`

---

## Current Step Details (Phase 3)
- **Status:** Building FastAPI ai-service skeleton with `/health`, `/metrics`, custom GTFS router (Dijkstra/RAPTOR-lite), ML regressor + MLflow.
- **Blockers:** None.
- **Next Command to Resume:**
  ```
  cd "/home/kinshuk-gupta/KINSHUK GUPTA/Mini Project/CommuteIQ"
  # Phase 3 execution — ai service core
  ```
