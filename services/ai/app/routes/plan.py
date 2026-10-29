"""
routes/plan.py — /plan endpoint: GTFS multimodal route planning.
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.router import get_router

router = APIRouter()


class PlanRequest(BaseModel):
    origin_lat: float = Field(..., ge=-90, le=90)
    origin_lon: float = Field(..., ge=-180, le=180)
    dest_lat: float = Field(..., ge=-90, le=90)
    dest_lon: float = Field(..., ge=-180, le=180)
    departure_sec: int = Field(..., ge=0, description="Seconds since midnight")
    max_walk_m: float = Field(600, ge=0, le=2000)


class PlanResponse(BaseModel):
    origin_stop: dict
    destination_stop: dict
    departure_sec: int
    arrival_sec: int
    total_duration_sec: int
    vehicle_changes: int
    legs: list[dict]


@router.post("", response_model=PlanResponse)
async def plan_route(req: PlanRequest):
    """
    Return the earliest-arrival GTFS route between two lat/lon points.
    Snaps origin and destination to the nearest GTFS stop within max_walk_m.
    """
    rt = get_router()
    graph = rt.graph

    nearby_origin = graph.nearby_stops(req.origin_lat, req.origin_lon, req.max_walk_m)
    nearby_dest = graph.nearby_stops(req.dest_lat, req.dest_lon, req.max_walk_m)

    if not nearby_origin:
        raise HTTPException(404, "No transit stops within max_walk_m of origin")
    if not nearby_dest:
        raise HTTPException(404, "No transit stops within max_walk_m of destination")

    # Round departure to nearest minute boundary for better LRU cache utilisation
    dep_norm = (req.departure_sec // 60) * 60

    # Try the closest origin/dest pair; on failure expand the search
    best = None
    for o in nearby_origin[:3]:
        for d in nearby_dest[:3]:
            result = rt.route(o["id"], d["id"], dep_norm)
            if result and (best is None or result["arrival_sec"] < best["arrival_sec"]):
                best = result

    if best is None:
        raise HTTPException(404, "No route found between these stops in the GTFS graph")

    return PlanResponse(
        origin_stop=best["origin"],
        destination_stop=best["destination"],
        departure_sec=best["departure_sec"],
        arrival_sec=best["arrival_sec"],
        total_duration_sec=best["total_duration_sec"],
        vehicle_changes=best["vehicle_changes"],
        legs=best["legs"],
    )
