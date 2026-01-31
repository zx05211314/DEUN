from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import List, Optional


class RoadClass(str, Enum):
    MAJOR = "MAJOR"
    SECONDARY = "SECONDARY"
    ALLEY = "ALLEY"


class RestrictionType(str, Enum):
    RED = "RED"
    YELLOW = "YELLOW"


class TimeRuleType(str, Enum):
    ALWAYS = "ALWAYS"
    WINDOWS = "WINDOWS"
    UNKNOWN = "UNKNOWN"


class RiskLevel(str, Enum):
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    RED = "RED"


class SearchMode(str, Enum):
    NEARBY = "nearby"
    AREA = "area"


class SortMode(str, Enum):
    NEAR = "near"
    STABLE = "stable"


class RiskProfile(str, Enum):
    NEUTRAL = "neutral"


@dataclass(frozen=True)
class TimeWindow:
    start: str
    end: str
    days: str


@dataclass(frozen=True)
class DistrictBoundary:
    name: str
    geom: object
    source_version: str


@dataclass(frozen=True)
class RoadRecord:
    road_id: str
    geom: object
    road_class: RoadClass
    is_ramp_or_expressway: bool
    name: Optional[str]
    source_version: str


@dataclass(frozen=True)
class RestrictionRecord:
    restriction_id: str
    geom: object
    restriction_type: RestrictionType
    time_rule_type: TimeRuleType
    time_windows: List[TimeWindow]
    note_raw: Optional[str]
    confidence_base: float
    source_version: str


@dataclass(frozen=True)
class StopRecord:
    stop_id: str
    geom: object
    stop_name: str
    confidence_base: float
    source_version: str


@dataclass(frozen=True)
class FireAssetRecord:
    asset_id: str
    geom: object
    asset_type: str
    confidence_base: float
    source_version: str


@dataclass(frozen=True)
class IntersectionRecord:
    node_id: str
    geom: object
    degree: int
    confidence_base: float
    source_version: str


@dataclass
class ParkingRecommendationRequest:
    mode: SearchMode
    lat: Optional[float]
    lng: Optional[float]
    radius_m: float
    polygon: Optional[dict]
    time: datetime
    risk_profile: RiskProfile
    sort: SortMode
    limit: int


@dataclass
class CandidateSegment:
    segment_id: str
    road_id: str
    geom: object
    road_class: RoadClass
    reasons: List[str]
    reason_values: dict
    checklist: List[str]
    risk_level: RiskLevel
    margin_distance_m: float
    walk_distance_m: float
    anchor_point: object
    score: float
