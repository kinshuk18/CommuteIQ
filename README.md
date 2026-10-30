# CommuteIQ

**CommuteIQ** is an enterprise hybrid-work commute copilot designed for the Bengaluru tech corridor (Outer Ring Road, Whitefield, Electronic City). It combines multimodal transit routing (BMTC bus + Namma Metro), ML runtime prediction, policy-grounded RAG, and an agentic assistant into a production-grade microservices architecture.

## Architecture

- **AI Service (`services/ai`)**: Python 3.11, FastAPI, spatial GTFS router with k-d tree and LRU cache, MLflow runtime regressor, LangGraph multi-node agent, LlamaIndex RAG with verified vs. unverified citation splits, and pluggable FAISS/Pinecone/Weaviate vector backends.
- **Gateway (`services/gateway`)**: Java 21, Spring Boot 3.3, REST & GraphQL endpoints, Flyway migrations, Redis token-bucket rate limiting via Lua, Resilience4j circuit breakers, shared secret auth, and Kafka event producers.
- **Data & Storage**: PostgreSQL 16 on port 5434 (GTFS transit schedules & OSM tech park POIs), Redis 7 (caching & rate limits), Apache Kafka 3.7 (feedback event streaming).
- **Web (`web`)**: React 18, Vite 4, TypeScript, Leaflet map with route polylines and verified citation chip badges.

## Real Data Corpus

CommuteIQ uses real Bengaluru transit schedules, OSM spatial extracts, and official transit policy documents:
- **Transit Stops**: 4,921 total (4,433 BMTC bus stops + 488 BMRCL metro nodes)
- **Routes & Trips**: 4,274 routes, 18,449 scheduled trips, and 103,923 stop times
- **Offices / POIs**: 284 deduplicated tech parks and IT campuses
- **Policy Corpus**: 6 official documents (MoRTH shared mobility guidelines, BMRCL smart-card rules, BMTC fare charts, Karnataka draft transport policies).

## Quick Start & Make Targets

```bash
make test-gateway   # Run Spring Boot JUnit tests with mocked deps
make test-ai        # Run pytest test suite for router, ML & RAG agent
make build-gateway  # Package Spring Boot jar for container runtime
make test-web       # Build React TypeScript frontend
make test           # Run all unit test suites
make up             # Start Docker Compose stack
make down           # Stop Docker Compose stack
make eval           # Execute quantitative evaluation benchmark
```

## Current Status

- **Done**: P1 (real GTFS/OSM/PDF data fetch), P2 (PostgreSQL V1/V2 Flyway & loader), P3 (spatial router & MLflow regression), P4 (multi-provider LLM strategy, RAG with citations, LangGraph agent), P5 (Spring Boot 3 gateway, GraphQL, Redis rate limiting, Kafka producers).
- **In Progress**: P6 (containerization & Docker Compose orchestration), P7 (React UI), P8 (K8s & CI), P9 (eval benchmark).

## Limitations

- **Scheduled Times**: ETA calculations utilize static GTFS timetables enhanced with GBR regression; live telemetry feeds (GPS vehicle positions) are not incorporated.
- **Partial BMTC Coverage**: GTFS data covers primary arterial routes; feeder routes outside main corridors may be incomplete.
- **Free-Tier LLM Quotas**: Tested against free-tier Gemini and Groq API endpoints; an on-disk cache and extractive fallback prevent quota exhaustion.

---
*Built with AI assistance (Antigravity; Gemini and Claude models); design, review and verification by me.*
