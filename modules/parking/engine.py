from __future__ import annotations

import hashlib
import importlib
import math
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Dict, Iterable, List, Optional, Tuple
from shapely.geometry import LineString, MultiLineString, Point, Polygon, shape
from shapely.ops import substring, transform, unary_union

from modules.parking.models import (
    CandidateSegment,
    ParkingRecommendationRequest,
    RestrictionRecord,
    RestrictionType,
    RiskLevel,
    RoadClass,
    SortMode,
    TimeRuleType,
)
from modules.parking.repository import ParkingRepository

@dataclass(frozen=True)
class RuleConfig:
    buffer_redline_m: float = 0.6
    buffer_yellow_unknown_m: float = 0.6
    buffer_intersection_red_m: float = 10.0
    buffer_intersection_yellow_m: float = 15.0
    buffer_bus_red_m: float = 10.0
    buffer_bus_yellow_m: float = 15.0
    buffer_hydrant_red_m: float = 5.0
    buffer_hydrant_yellow_m: float = 8.0
    min_segment_m: float = 8.0
    split_segment_m: float = 30.0


WGS84 = "EPSG:4326"
TWD97_TM2 = "EPSG:3826"
WEB_MERCATOR = "EPSG:3857"


def _web_mercator_forward(x: float, y: float) -> tuple[float, float]:
    origin_shift = 2 * math.pi * 6378137 / 2.0
    mx = x * origin_shift / 180.0
    my = math.log(math.tan((90 + y) * math.pi / 360.0)) / (math.pi / 180.0)
    my = my * origin_shift / 180.0
    return mx, my


def _web_mercator_inverse(x: float, y: float) -> tuple[float, float]:
    origin_shift = 2 * math.pi * 6378137 / 2.0
    lon = (x / origin_shift) * 180.0
    lat = (y / origin_shift) * 180.0
    lat = 180 / math.pi * (2 * math.atan(math.exp(lat * math.pi / 180.0)) - math.pi / 2.0)
    return lon, lat


def _load_transformers() -> tuple[Callable, Callable]:
    spec = importlib.util.find_spec("pyproj")
    if spec:
        pyproj = importlib.import_module("pyproj")
        transformer = pyproj.Transformer.from_crs(WGS84, TWD97_TM2, always_xy=True)
        reverse = pyproj.Transformer.from_crs(TWD97_TM2, WGS84, always_xy=True)
        return transformer.transform, reverse.transform
    return _web_mercator_forward, _web_mercator_inverse


TO_METERS, TO_WGS84 = _load_transformers()


def project_to_meters(geom):
    return transform(TO_METERS, geom)


def project_to_wgs84(geom):
    return transform(TO_WGS84, geom)


def line_length_m(line: LineString) -> float:
    return line.length


def split_line(line: LineString, split_m: float) -> List[LineString]:
    length = line_length_m(line)
    if length <= split_m:
        return [line]
    segments: List[LineString] = []
    start_m = 0.0
    while start_m < length:
        end_m = min(start_m + split_m, length)
        start_dist = start_m / length
        end_dist = end_m / length
        piece = substring(line, start_dist, end_dist, normalized=True)
        if isinstance(piece, LineString):
            segments.append(piece)
        start_m = end_m
    return segments


def _time_window_active(window: dict, current: datetime) -> bool:
    start = datetime.strptime(window["start"], "%H:%M").time()
    end = datetime.strptime(window["end"], "%H:%M").time()
    day = current.strftime("%A").upper()
    day = day[:3]
    days = window.get("days", "").upper()
    if days == "WEEKDAYS" and day in {"SAT", "SUN"}:
        return False
    if days == "WEEKENDS" and day not in {"SAT", "SUN"}:
        return False
    if days not in {"", "WEEKDAYS", "WEEKENDS"} and day not in days:
        return False
    if start <= end:
        return start <= current.time() <= end
    return current.time() >= start or current.time() <= end


def restriction_active(restriction: RestrictionRecord, current: datetime) -> bool:
    if restriction.time_rule_type == TimeRuleType.ALWAYS:
        return True
    if restriction.time_rule_type != TimeRuleType.WINDOWS:
        return False
    if not restriction.time_windows:
        return False
    return any(_time_window_active(window.__dict__, current) for window in restriction.time_windows)


class ParkingRecommendationEngine:
    def __init__(self, repository: ParkingRepository, config: RuleConfig | None = None) -> None:
        self.repository = repository
        self.config = config or RuleConfig()
        self._segment_cache: Dict[str, dict] = {}

    def recommend(self, request: ParkingRecommendationRequest) -> dict:
        district = self.repository.district_boundary()
        aoi = self._build_aoi(request, district)

        roads = [
            road
            for road in self.repository.roads()
            if not road.is_ramp_or_expressway and road.geom.intersects(aoi)
        ]
        if not roads:
            return self._build_response(request, [], aoi)

        hard_mask, yellow_unknown_lines, inactive_yellow_lines, intersections, bus_stops, fire_assets = (
            self._build_masks(request, aoi)
        )
        segments = self._build_segments(request, roads, hard_mask)
        candidates = self._classify_segments(
            request,
            segments,
            yellow_unknown_lines,
            inactive_yellow_lines,
            intersections,
            bus_stops,
            fire_assets,
        )
        ranked = self._rank_segments(request, candidates)
        limited = ranked[: request.limit]
        response = self._build_response(request, limited, aoi)
        self._segment_cache = {segment["segment_id"]: segment for segment in limited}
        return response

    def segment_detail(self, segment_id: str) -> Optional[dict]:
        return self._segment_cache.get(segment_id)

    def _build_aoi(self, request: ParkingRecommendationRequest, district) -> Polygon:
        if request.mode.value == "area" and request.polygon:
            if request.polygon.get("type") == "Feature":
                aoi = shape(request.polygon["geometry"])
            else:
                aoi = shape(request.polygon)
        else:
            point = Point(request.lng or 0.0, request.lat or 0.0)
            point_m = project_to_meters(point)
            aoi = project_to_wgs84(point_m.buffer(request.radius_m))
        if district and district.geom:
            return aoi.intersection(district.geom)
        return aoi

    def _build_masks(
        self, request: ParkingRecommendationRequest, aoi: Polygon
    ) -> Tuple[Polygon, list, list, list, list, list]:
        active_red = []
        active_yellow = []
        yellow_unknown = []
        inactive_yellow = []
        for restriction in self.repository.curb_restrictions():
            if not restriction.geom.intersects(aoi):
                continue
            if restriction.restriction_type == RestrictionType.RED and restriction_active(restriction, request.time):
                active_red.append(restriction)
            elif restriction.restriction_type == RestrictionType.YELLOW:
                if restriction_active(restriction, request.time):
                    active_yellow.append(restriction)
                elif restriction.time_rule_type == TimeRuleType.WINDOWS:
                    inactive_yellow.append(restriction)
                elif restriction.time_rule_type == TimeRuleType.UNKNOWN:
                    yellow_unknown.append(restriction)

        hard_masks = []
        hard_masks.extend(project_to_meters(r.geom).buffer(self.config.buffer_redline_m) for r in active_red)
        hard_masks.extend(project_to_meters(r.geom).buffer(self.config.buffer_redline_m) for r in active_yellow)

        intersections = [node for node in self.repository.intersections() if node.geom.intersects(aoi)]
        bus_stops = [stop for stop in self.repository.bus_stops() if stop.geom.intersects(aoi)]
        fire_assets = [asset for asset in self.repository.fire_assets() if asset.geom.intersects(aoi)]

        hard_masks.extend(
            project_to_meters(node.geom).buffer(self.config.buffer_intersection_red_m) for node in intersections
        )
        hard_masks.extend(project_to_meters(stop.geom).buffer(self.config.buffer_bus_red_m) for stop in bus_stops)
        hard_masks.extend(
            project_to_meters(asset.geom).buffer(self.config.buffer_hydrant_red_m) for asset in fire_assets
        )

        hard_union = unary_union(hard_masks) if hard_masks else Polygon()
        yellow_unknown_lines = [(record, project_to_meters(record.geom)) for record in yellow_unknown]
        inactive_yellow_lines = [(record, project_to_meters(record.geom)) for record in inactive_yellow]
        intersection_points = [(record, project_to_meters(record.geom)) for record in intersections]
        bus_points = [(record, project_to_meters(record.geom)) for record in bus_stops]
        fire_points = [(record, project_to_meters(record.geom)) for record in fire_assets]
        return (
            hard_union,
            yellow_unknown_lines,
            inactive_yellow_lines,
            intersection_points,
            bus_points,
            fire_points,
        )

    def _build_segments(
        self,
        request: ParkingRecommendationRequest,
        roads: Iterable,
        hard_mask: Polygon,
    ) -> List[CandidateSegment]:
        segments: List[CandidateSegment] = []
        for road in roads:
            road_geom_m = project_to_meters(road.geom)
            cleaned = road_geom_m.difference(hard_mask) if not hard_mask.is_empty else road_geom_m
            lines: List[LineString] = []
            if isinstance(cleaned, LineString):
                lines = [cleaned]
            elif isinstance(cleaned, MultiLineString):
                lines = list(cleaned.geoms)
            for line in lines:
                if line_length_m(line) < self.config.min_segment_m:
                    continue
                for piece in split_line(line, self.config.split_segment_m):
                    if line_length_m(piece) < self.config.min_segment_m:
                        continue
                    anchor_m = piece.interpolate(0.5, normalized=True)
                    anchor = project_to_wgs84(anchor_m)
                    piece_wgs = project_to_wgs84(piece)
                    segment_id = self._segment_id(road.road_id, piece)
                    segments.append(
                        CandidateSegment(
                            segment_id=segment_id,
                            road_id=road.road_id,
                            geom=piece_wgs,
                            road_class=road.road_class,
                            reasons=[],
                            reason_values={},
                            checklist=[],
                            risk_level=RiskLevel.GREEN,
                            margin_distance_m=self._margin_distance(piece, hard_mask),
                            walk_distance_m=0.0,
                            anchor_point=anchor,
                            score=0.0,
                        )
                    )
        return segments

    def _margin_distance(self, line: LineString, hard_mask: Polygon) -> float:
        if hard_mask.is_empty:
            return 999.0
        return line.distance(hard_mask)

    def _classify_segments(
        self,
        request: ParkingRecommendationRequest,
        segments: List[CandidateSegment],
        yellow_unknown: list,
        inactive_yellow: list,
        intersections: list,
        bus_stops: list,
        fire_assets: list,
    ) -> List[CandidateSegment]:
        low_confidence = []
        for record, _geom in intersections + bus_stops + fire_assets:
            if getattr(record, "confidence_base", 1.0) < 0.7:
                low_confidence.append((record, _geom))
        low_confidence.extend([(r, geom) for r, geom in yellow_unknown if r.confidence_base < 0.7])
        for segment in segments:
            reasons = []
            checklist = []
            segment_m = project_to_meters(segment.geom)
            intersection_distance = self._min_distance(segment_m, intersections)
            if (
                intersection_distance
                and self.config.buffer_intersection_red_m
                < intersection_distance
                <= self.config.buffer_intersection_yellow_m
            ):
                reasons.append("NEAR_INTERSECTION_MARGIN")
                segment.reason_values["NEAR_INTERSECTION_MARGIN"] = round(intersection_distance, 2)
                checklist.append("CONFIRM_CORNER_CLEARANCE")

            bus_distance = self._min_distance(segment_m, bus_stops)
            if (
                bus_distance
                and self.config.buffer_bus_red_m
                < bus_distance
                <= self.config.buffer_bus_yellow_m
            ):
                reasons.append("NEAR_BUSSTOP_MARGIN")
                segment.reason_values["NEAR_BUSSTOP_MARGIN"] = round(bus_distance, 2)
                checklist.append("CONFIRM_BUSSTOP_ZONE")

            fire_distance = self._min_distance(segment_m, fire_assets)
            if (
                fire_distance
                and self.config.buffer_hydrant_red_m
                < fire_distance
                <= self.config.buffer_hydrant_yellow_m
            ):
                reasons.append("NEAR_HYDRANT_MARGIN")
                segment.reason_values["NEAR_HYDRANT_MARGIN"] = round(fire_distance, 2)
                checklist.append("CONFIRM_HYDRANT_VISIBILITY")

            if segment.road_class == RoadClass.MAJOR:
                reasons.append("ROAD_CLASS_RISK")
                checklist.extend(["CONFIRM_NOT_BLOCKING_TRAFFIC", "CONFIRM_NO_ADDITIONAL_SIGNS"])
            if any(geom.intersects(segment_m) for _record, geom in yellow_unknown):
                reasons.append("YELLOWLINE_TIME_UNKNOWN")
                checklist.extend(["CONFIRM_TIME_SIGN", "CONFIRM_CURB_COLOR"])
            inactive_yellow_hit = any(geom.intersects(segment_m) for _record, geom in inactive_yellow)
            low_confidence_distance = self._min_distance(segment_m, low_confidence, max_distance_m=15.0)
            if low_confidence and low_confidence_distance:
                reasons.append("LOW_CONFIDENCE_DATA")
                segment.reason_values["LOW_CONFIDENCE_DATA"] = round(low_confidence_distance, 2)
                checklist.append("CONFIRM_ON_SITE_SIGNS")

            if reasons:
                segment.risk_level = RiskLevel.YELLOW
                segment.reasons = reasons[:3]
                segment.checklist = list(dict.fromkeys(checklist))
            else:
                segment.reasons = ["YELLOWLINE_INACTIVE"] if inactive_yellow_hit else ["CLEAR_OF_RESTRICTIONS"]
        return segments

    def _min_distance(self, line: LineString, records: list, max_distance_m: Optional[float] = None) -> Optional[float]:
        if not records:
            return None
        min_m = min(line.distance(geom) for _record, geom in records)
        distance_m = min_m
        if max_distance_m is not None and distance_m > max_distance_m:
            return None
        return distance_m

    def _rank_segments(
        self, request: ParkingRecommendationRequest, segments: List[CandidateSegment]
    ) -> List[CandidateSegment]:
        user_point = None
        if request.lat is not None and request.lng is not None:
            user_point = project_to_meters(Point(request.lng, request.lat))

        for segment in segments:
            if user_point is not None:
                segment_point = project_to_meters(segment.anchor_point)
                segment.walk_distance_m = segment_point.distance(user_point)

        def score(segment: CandidateSegment) -> Tuple[int, float, float]:
            risk_weight = 0 if segment.risk_level == RiskLevel.GREEN else 1
            if request.sort == SortMode.STABLE:
                return (risk_weight, -segment.margin_distance_m, segment.walk_distance_m)
            return (risk_weight, segment.walk_distance_m, -segment.margin_distance_m)

        sorted_segments = sorted(segments, key=score)
        return sorted_segments

    def _build_response(self, request: ParkingRecommendationRequest, segments: List[CandidateSegment], aoi: Polygon) -> dict:
        data_versions = self.repository.data_versions()
        response_segments = []
        for segment in segments:
            response_segments.append(
                {
                    "segment_id": segment.segment_id,
                    "risk_level": segment.risk_level.value,
                    "geometry": segment.geom.__geo_interface__,
                    "anchor_point": {
                        "lat": segment.anchor_point.y,
                        "lng": segment.anchor_point.x,
                    },
                    "score": segment.score,
                    "explanations": [
                        {
                            "reason_tag": reason,
                            "value": segment.reason_values.get(reason, ""),
                        }
                        for reason in segment.reasons[:3]
                    ],
                    "checklist": segment.checklist if segment.risk_level == RiskLevel.YELLOW else [],
                }
            )
        return {
            "meta": {
                "district": "信義區",
                "aoi_type": "polygon" if request.mode.value == "area" else "circle",
                "generated_at": request.time.isoformat(),
                "data_versions": data_versions,
            },
            "segments": response_segments,
        }

    def _segment_id(self, road_id: str, segment_m: LineString) -> str:
        coords = [f"{round(x, 2)}:{round(y, 2)}" for x, y in segment_m.coords]
        payload = f"{road_id}|{'|'.join(coords)}"
        return hashlib.sha1(payload.encode("utf-8")).hexdigest()
