"""
tests/test_ml.py — Unit tests for the scheduled inter-stop runtime ML model.
"""

import numpy as np
import pytest
from app.ml_model import RuntimePredictor, _haversine


def test_haversine_calculation():
    # MG Road to Trinity (approx 1.2 km)
    d = _haversine(12.9756, 77.6066, 12.9727, 77.6170)
    assert 1000 < d < 1500


def test_runtime_predictor_predict_fallback_and_loaded():
    RuntimePredictor.load()
    pred = RuntimePredictor.predict(
        haversine_m=1200.0,
        hour=9,
        route_type=1,
        stop_seq_pos=0.2,
        route_len=20,
    )
    assert pred > 0.0
    assert 30.0 <= pred <= 600.0  # reasonable scheduled time for 1.2km
