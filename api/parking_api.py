from __future__ import annotations

import json
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Query

from modules.parking.engine import ParkingRecommendationEngine
from modules.parking.models import ParkingRecommendationRequest, RiskProfile, SearchMode, SortMode
from modules.parking.repository import InMemoryParkingRepository

router = APIRouter(prefix="/v1/parking", tags=["parking"])
engine = ParkingRecommendationEngine(InMemoryParkingRepository())


def _parse_time(value: Optional[str]) -> datetime:
    tz = ZoneInfo("Asia/Taipei")
    if not value:
        return datetime.now(tz)
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=tz)
    return parsed.astimezone(tz)


@router.get("/recommend")
def recommend(
    mode: SearchMode = Query(SearchMode.NEARBY),
    lat: Optional[float] = Query(None),
    lng: Optional[float] = Query(None),
    radius_m: float = Query(600.0, ge=50, le=3000),
    polygon: Optional[str] = Query(None, description="GeoJSON polygon string"),
    time: Optional[str] = Query(None),
    risk_profile: RiskProfile = Query(RiskProfile.NEUTRAL),
    sort: SortMode = Query(SortMode.NEAR),
    limit: int = Query(30, ge=1, le=100),
):
    if mode == SearchMode.NEARBY and (lat is None or lng is None):
        raise HTTPException(status_code=400, detail="lat/lng required for nearby mode")
    polygon_payload = None
    if mode == SearchMode.AREA:
        if not polygon:
            raise HTTPException(status_code=400, detail="polygon required for area mode")
        polygon_payload = json.loads(polygon)
    request = ParkingRecommendationRequest(
        mode=mode,
        lat=lat,
        lng=lng,
        radius_m=radius_m,
        polygon=polygon_payload,
        time=_parse_time(time),
        risk_profile=risk_profile,
        sort=sort,
        limit=limit,
    )
    return engine.recommend(request)


@router.get("/segment/{segment_id}")
def segment_detail(segment_id: str):
    detail = engine.segment_detail(segment_id)
    if not detail:
        raise HTTPException(status_code=404, detail="segment not found")
    return detail
