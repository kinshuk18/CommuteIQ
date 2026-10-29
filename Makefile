.PHONY: help fetch-data load-db train-ml test-ai test-gateway test-web test up down eval

help:
	@echo "CommuteIQ Development Commands:"
	@echo "  make fetch-data   - Download BMTC/BMRCL GTFS, OSM offices, and policy corpus"
	@echo "  make load-db      - Ingest GTFS schedules and OSM POIs into PostgreSQL"
	@echo "  make train-ml     - Train runtime predictor on real GTFS stop_times with MLflow"
	@echo "  make test-ai      - Run Python unit and integration tests (pytest)"
	@echo "  make test-gateway - Run Java Spring Boot unit & Testcontainers tests"
	@echo "  make test-web     - Typecheck and test React frontend"
	@echo "  make test         - Run all test suites across services"
	@echo "  make up           - Start full container stack (Postgres, Redis, Kafka, AI, Gateway, Web)"
	@echo "  make down         - Stop container stack"
	@echo "  make eval         - Run quantitative evaluation suite (RAG recall, routing accuracy, ML)"

fetch-data:
	python3 data/scripts/fetch_gtfs.py
	python3 data/scripts/fetch_osm.py
	python3 data/scripts/fetch_docs.py

load-db:
	python3 data/scripts/load_gtfs.py

train-ml:
	python3 services/ai/ml/train_runtime_model.py

test-ai:
	cd services/ai && pytest -v

test-gateway:
	cd services/gateway && ./mvnw test

test-web:
	cd web && npm run build

test: test-ai test-gateway test-web

up:
	docker compose -f deploy/compose.yml up -d

down:
	docker compose -f deploy/compose.yml down

eval:
	python3 services/ai/evaluation/run_eval.py
