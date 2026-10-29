"""
routes/ml.py — /ml/predict-runtime endpoint and training trigger.
"""

import math

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.ml_model import RuntimePredictor, train_and_register
from app.config import settings

router = APIRouter()

EARTH_RADIUS_M = 6_371_000


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


class RuntimeRequest(BaseModel):
    from_lat: float = Field(..., ge=-90, le=90)
    from_lon: float = Field(..., ge=-180, le=180)
    to_lat: float = Field(..., ge=-90, le=90)
    to_lon: float = Field(..., ge=-180, le=180)
    hour: int = Field(..., ge=0, le=23, description="Hour of departure (0–23)")
    route_type: int = Field(..., description="GTFS route_type: 1=metro, 3=bus")
    stop_seq_pos: float = Field(0.5, ge=0, le=1, description="Normalised stop position in trip")
    route_len: int = Field(10, ge=2, description="Total stops in the trip")


class RuntimeResponse(BaseModel):
    predicted_running_time_sec: float
    haversine_m: float
    model_source: str
    note: str


@router.post("/predict-runtime", response_model=RuntimeResponse)
async def predict_runtime(req: RuntimeRequest):
    """
    Predict the *scheduled* running time between two consecutive stops.

    Note: This models the scheduled time as recorded in the GTFS feed,
    not live/real-time travel time.
    """
    dist = _haversine(req.from_lat, req.from_lon, req.to_lat, req.to_lon)
    predicted = RuntimePredictor.predict(
        haversine_m=dist,
        hour=req.hour,
        route_type=req.route_type,
        stop_seq_pos=req.stop_seq_pos,
        route_len=req.route_len,
    )
    model_source = "gbr-registry" if RuntimePredictor._model is not None else "baseline-speed"
    return RuntimeResponse(
        predicted_running_time_sec=round(predicted, 1),
        haversine_m=round(dist, 1),
        model_source=model_source,
        note="Predicted scheduled running time from GTFS data; does not reflect live traffic.",
    )


@router.post("/train", response_model=dict)
async def trigger_training():
    """
    Trigger ML model training from the Postgres GTFS data.
    Logs run to MLflow and registers the model.  Use sparingly.
    """
    try:
        run_id = train_and_register(settings.db_url)
    except Exception as exc:
        raise HTTPException(500, f"Training failed: {exc}") from exc
    RuntimePredictor.load()
    return {"status": "trained", "run_id": run_id}
