"""
tests/test_api.py — Integration tests for FastAPI endpoints.
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_endpoint():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "service": "commuteiq-ai"}


def test_metrics_endpoint():
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert b"commuteiq_requests_total" in resp.content or b"request_latency" in resp.content or b"process_virtual_memory_bytes" in resp.content


def test_predict_runtime_endpoint():
    payload = {
        "from_lat": 12.9756,
        "from_lon": 77.6066,
        "to_lat": 12.9727,
        "to_lon": 77.6170,
        "hour": 9,
        "route_type": 1,
        "stop_seq_pos": 0.25,
        "route_len": 24,
    }
    resp = client.post("/ml/predict-runtime", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "predicted_running_time_sec" in data
    assert data["predicted_running_time_sec"] > 0
    assert "haversine_m" in data
    assert "model_source" in data
