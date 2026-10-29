"""
ml_model.py — Gradient-boosting regressor predicting scheduled inter-stop running time.

What it models
──────────────
The model predicts the *scheduled* running time (seconds) between consecutive
stop_time rows in the same trip, as recorded in the GTFS feed.  It does NOT
predict live/real-time times.  This distinction is documented in the API response
and in ARCHITECTURE.md.

Features
────────
  - haversine_m   : great-circle distance between consecutive stops (metres)
  - hour           : hour-of-day of the departure (0–23)
  - route_type     : 1 = metro, 3 = bus (GTFS codes)
  - stop_seq_pos   : stop_sequence / total_stops  (normalised position in trip)
  - route_len      : total number of stops in route (proxy for route complexity)

Target
──────
  running_time_sec : departure_sec[n+1] - departure_sec[n]   (positive, < 3600 s)

Split
─────
Time-based: records with departure_sec < SPLIT_BOUNDARY go to train,
the rest to test.  Avoids data leakage from sequential ordering.
SPLIT_BOUNDARY = 6 * 3600  (trips departing before 06:00 → train;
                             06:00+ → test — approximates an early/late split
                             across both agencies).

Baseline
────────
baseline_predicted = haversine_m / BASELINE_SPEED_MPS
where BASELINE_SPEED_MPS is calibrated as the mean speed over the training set.
"""

import logging
import math
import time
from pathlib import Path
from typing import Any

import mlflow
import mlflow.sklearn
import numpy as np
import psycopg
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, root_mean_squared_error

from app.config import settings
from app.metrics import ML_INFERENCE_LATENCY

logger = logging.getLogger(__name__)

SPLIT_BOUNDARY = 6 * 3600   # seconds since midnight
MIN_SEC = 10                 # discard unrealistically short scheduled gaps
MAX_SEC = 3600               # discard gaps > 1 hour (data quality guard)
EARTH_RADIUS_M = 6_371_000


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def _load_training_data(db_url: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Query Postgres for consecutive stop-time pairs and return (X_train, y_train, X_test, y_test).
    Uses a single SQL query with LAG/LEAD to avoid Python-side groupby.
    """
    sql = """
    WITH ordered AS (
        SELECT
            st.trip_fk,
            st.stop_sequence,
            st.departure_sec,
            s.stop_lat  AS lat,
            s.stop_lon  AS lon,
            r.route_type,
            LEAD(st.departure_sec) OVER w AS next_dep,
            LEAD(s.stop_lat)       OVER w AS next_lat,
            LEAD(s.stop_lon)       OVER w AS next_lon,
            COUNT(*) OVER (PARTITION BY st.trip_fk) AS trip_len,
            t.route_fk
        FROM stop_time st
        JOIN stop  s ON s.id  = st.stop_fk
        JOIN trip  t ON t.id  = st.trip_fk
        JOIN route r ON r.id  = t.route_fk
        WINDOW w AS (PARTITION BY st.trip_fk ORDER BY st.stop_sequence)
    )
    SELECT
        departure_sec,
        lat, lon,
        next_lat, next_lon,
        route_type,
        stop_sequence,
        trip_len,
        (next_dep - departure_sec) AS running_time_sec
    FROM ordered
    WHERE next_dep IS NOT NULL
      AND (next_dep - departure_sec) BETWEEN %(min_sec)s AND %(max_sec)s
    """
    logger.info("Loading training data from Postgres …")
    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, {"min_sec": MIN_SEC, "max_sec": MAX_SEC})
            rows = cur.fetchall()

    logger.info("Loaded %d inter-stop records", len(rows))

    X_rows, y_rows = [], []
    for (dep_sec, lat, lon, nlat, nlon, rtype, seq, tlen, rt_sec) in rows:
        dist = _haversine(lat, lon, nlat, nlon)
        hour = (dep_sec % 86400) // 3600
        seq_pos = seq / max(tlen - 1, 1)
        X_rows.append([dist, hour, rtype, seq_pos, tlen])
        y_rows.append(rt_sec)

    X = np.array(X_rows, dtype=np.float32)
    y = np.array(y_rows, dtype=np.float32)

    # Time-based split: early departures → train, later → test
    mask_train = X[:, 1] < (SPLIT_BOUNDARY // 3600)  # col 1 = hour
    X_train, y_train = X[mask_train], y[mask_train]
    X_test, y_test = X[~mask_train], y[~mask_train]
    logger.info(
        "Split: train=%d, test=%d (boundary hour=%d)",
        len(X_train), len(X_test), SPLIT_BOUNDARY // 3600,
    )
    return X_train, y_train, X_test, y_test


def train_and_register(db_url: str | None = None) -> str:
    """
    Train the regressor, compare with baseline, log to MLflow, register the model.
    Returns the MLflow run_id.
    """
    db_url = db_url or settings.db_url
    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    mlflow.set_experiment(settings.mlflow_experiment_name)

    X_train, y_train, X_test, y_test = _load_training_data(db_url)

    with mlflow.start_run() as run:
        run_id = run.info.run_id
        feature_names = ["haversine_m", "hour", "route_type", "stop_seq_pos", "route_len"]
        mlflow.log_params({
            "features": ",".join(feature_names),
            "split": f"hour<{SPLIT_BOUNDARY // 3600}",
            "train_rows": len(X_train),
            "test_rows": len(X_test),
            "min_sec_filter": MIN_SEC,
            "max_sec_filter": MAX_SEC,
        })

        # ── Gradient Boosting regressor ────────────────────────────────────
        gbr = GradientBoostingRegressor(
            n_estimators=200,
            max_depth=4,
            learning_rate=0.08,
            subsample=0.8,
            min_samples_leaf=10,
            random_state=42,
        )
        gbr.fit(X_train, y_train)
        preds = gbr.predict(X_test)

        mae = mean_absolute_error(y_test, preds)
        rmse = root_mean_squared_error(y_test, preds)
        mlflow.log_metrics({"gbr_mae_sec": round(mae, 2), "gbr_rmse_sec": round(rmse, 2)})
        logger.info("GBR  MAE=%.1f s  RMSE=%.1f s", mae, rmse)

        # ── Baseline: distance / mean_speed ───────────────────────────────
        # Compute mean speed from training set distances and times
        train_dists = X_train[:, 0]
        train_dists_pos = train_dists[train_dists > 0]
        train_times_pos = y_train[train_dists > 0]
        mean_speed = float(np.mean(train_dists_pos / train_times_pos))  # m/s
        baseline_preds = X_test[:, 0] / max(mean_speed, 0.1)
        b_mae = mean_absolute_error(y_test, baseline_preds)
        b_rmse = root_mean_squared_error(y_test, baseline_preds)
        mlflow.log_metrics({
            "baseline_mae_sec": round(b_mae, 2),
            "baseline_rmse_sec": round(b_rmse, 2),
            "baseline_mean_speed_mps": round(mean_speed, 3),
        })
        logger.info(
            "Baseline (speed=%.2f m/s)  MAE=%.1f s  RMSE=%.1f s",
            mean_speed, b_mae, b_rmse,
        )

        # ── Register model ─────────────────────────────────────────────────
        mlflow.sklearn.log_model(
            gbr,
            name="model",
            registered_model_name="runtime-regressor",
            input_example=X_train[:1],
            serialization_format="cloudpickle",
        )
        mlflow.log_param("mean_speed_baseline_mps", round(mean_speed, 3))

    return run_id


# ── inference wrapper ─────────────────────────────────────────────────────────

class RuntimePredictor:
    """Loads the latest registered MLflow model and serves predictions."""

    _model: Any = None
    _mean_speed: float = 7.0  # fallback until model is loaded

    @classmethod
    def load(cls) -> None:
        mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
        try:
            cls._model = mlflow.sklearn.load_model("models:/runtime-regressor/latest")
            logger.info("RuntimePredictor: model loaded from MLflow registry")
        except Exception as exc:
            logger.warning("RuntimePredictor: no model in registry yet (%s)", exc)
            cls._model = None

    @classmethod
    def predict(
        cls,
        haversine_m: float,
        hour: int,
        route_type: int,
        stop_seq_pos: float,
        route_len: int,
    ) -> float:
        """Return predicted scheduled running time in seconds."""
        t0 = time.perf_counter()
        if cls._model is not None:
            X = np.array([[haversine_m, hour, route_type, stop_seq_pos, route_len]], dtype=np.float32)
            result = float(cls._model.predict(X)[0])
        else:
            # Fallback baseline: haversine / mean_speed
            result = haversine_m / max(cls._mean_speed, 0.1)
        elapsed = time.perf_counter() - t0
        ML_INFERENCE_LATENCY.observe(elapsed)
        return max(result, 1.0)  # always positive
