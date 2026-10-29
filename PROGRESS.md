# CommuteIQ — Implementation Progress Tracker

## Project Overview
CommuteIQ is a hybrid-work commute copilot for Bengaluru combining BMTC bus + Namma Metro GTFS routing, agentic RAG over verified transit policy documents with strict context tiering (VERIFIED vs UNVERIFIED), traditional ML runtime prediction with MLflow, and an event-driven architecture with Spring Boot 3, FastAPI, Kafka, Redis, and React.

---

## Phase Status Summary
- [x] **Phase 1: Project Scaffolding & Real Data Acquisition** (Completed)
- [ ] **Phase 2: PostgreSQL Schema (Flyway) & GTFS / OSM Ingestion** (Next)
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

## Current Step Details (Phase 2)
- **Status:** Creating PostgreSQL Flyway migrations and `data/scripts/load_gtfs.py` for database ingestion.
- **Blockers:** None.
- **Next Command to Resume:**
  ```bash
  cd "/home/kinshuk-gupta/KINSHUK GUPTA/Mini Project/CommuteIQ"
  # Phase 2 execution
  ```
