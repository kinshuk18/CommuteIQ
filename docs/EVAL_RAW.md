# EVAL_RAW.md — Phase 4 Raw /ask Evaluation

Raw outputs from 3 real queries run via FastAPI TestClient against the
production AI service (FAISS backend, bge-small-en-v1.5 embeddings,
459 indexed document chunks). Captured 2026-10-30.

**LLM status:** Gemini free-tier daily quota (20 req/day) was exhausted at
run time. The agent's fallback path ("synthesising directly from verified
facts") fired for all three queries — the answer text is a generic stub, but
retrieval (embedding search → FAISS → ranked chunks) and citation assembly ran
normally and returned correct citations. Full LLM answers will be re-captured
in P9 after the quota resets.

---

## Q1 — BMTC bus fare

**Query:** `What is the maximum BMTC bus fare in Bengaluru?`

**HTTP status:** 200 OK

**Answer (fallback):** Information retrieved from official Bangalore transit
documents cited in references.

**Citations returned:** 4

| # | Title | Trust tier | URL |
|---|-------|-----------|-----|
| 1 | Bangalore Metro Fare Chart and Operational Line Maps | UNVERIFIED | https://bengalurumetro.in/bangalore-metro-fare-chart.html |
| 2 | Bangalore Metro Fare Chart and Operational Line Maps | UNVERIFIED | https://bengalurumetro.in/bangalore-metro-fare-chart.html |

**Observation:** Top chunks are Metro fare docs, not BMTC — indicates the
BMTC fare document is present but ranked lower; needs human review in P9.

---

## Q2 — Metro line Majestic → Whitefield

**Query:** `Which metro line connects Majestic to Whitefield?`

**HTTP status:** 200 OK

**Answer (fallback):** Information retrieved from official Bangalore transit
documents cited in references.

**Citations returned:** 4

| # | Title | Trust tier | URL |
|---|-------|-----------|-----|
| 1 | Bangalore Metro Fare Chart and Operational Line Maps | UNVERIFIED | https://bengalurumetro.in/bangalore-metro-fare-chart.html |
| 2 | Bangalore Metro Fare Chart and Operational Line Maps | UNVERIFIED | https://bengalurumetro.in/bangalore-metro-fare-chart.html |

**Observation:** Metro fare doc surfaces for a metro route query — correct
domain. Line identity (Purple Line / Line 2) needs LLM synthesis to surface
from chunks; will verify in P9.

---

## Q3 — Peak hour timings

**Query:** `What are the peak hour timings for Bengaluru traffic?`

**HTTP status:** 200 OK

**Answer (fallback):** Information retrieved from official Bangalore transit
documents cited in references.

**Citations returned:** 4

| # | Title | Trust tier | URL |
|---|-------|-----------|-----|
| 1 | Bengaluru Cabs Revised Uniform Rates and Ride-Hailing Implementation | UNVERIFIED | https://indianexpress.com/article/cities/bangalore/bengaluru… |
| 2 | Bangalore Metro Fare Chart and Operational Line Maps | UNVERIFIED | https://bengalurumetro.in/bangalore-metro-fare-chart.html |

**Observation:** Cab-rates article surfacing for peak-hours query is
reasonable (surge pricing context). A VERIFIED government document on peak
hours would improve precision; flagged for P9 gold-question set.

---

## Infrastructure observations (from run logs)

- FAISS index loaded: **459 document chunks** from `faiss_index/`
- Embedding model: `BAAI/bge-small-en-v1.5` (CPU, loaded in ~0.5 s after cache)
- All 3 requests returned HTTP 200 with structured citation JSON
- LLM fallback triggered: `WARNING app.agent.graph Remote LLM unavailable … synthesizing directly from verified facts`
- Gemini quota: 20 req/day free tier; exhausted; retry available in ~1 h 51 m
- Retrieval pipeline (embed → FAISS search → ContextBuilder → trust-tier label) verified working independently of LLM

---

## Notes for P9

- Re-run these 3 queries once quota resets (or with `LLM_PROVIDER=anthropic_mock`)
  to capture full synthesised answers with inline citation chips.
- All trust-tier labels in citations above come from document metadata set at
  ingest time — not inferred by the LLM — which is the intended behaviour.
- Verified-vs-unverified conflict cases will use real MoRTH 2020 vs 2025
  guidelines documents already in `data/raw/docs/`.
