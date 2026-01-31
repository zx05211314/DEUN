from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from shapely.geometry import shape

from modules.parking.models import (
    DistrictBoundary,
    FireAssetRecord,
    IntersectionRecord,
    RestrictionRecord,
    RestrictionType,
    RoadClass,
    RoadRecord,
    StopRecord,
    TimeRuleType,
    TimeWindow,
)

ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = ROOT / "data" / "parking"


def _load_geojson(path: Path) -> List[dict]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("type") != "FeatureCollection":
        return []
    return payload.get("features", [])


def _feature_version(path: Path) -> str:
    if not path.exists():
        return "missing"
    mtime = path.stat().st_mtime
    return f"{path.name}:{int(mtime)}"


class ParkingRepository:
    def district_boundary(self) -> Optional[DistrictBoundary]:
        raise NotImplementedError

    def roads(self) -> List[RoadRecord]:
        raise NotImplementedError

    def curb_restrictions(self) -> List[RestrictionRecord]:
        raise NotImplementedError

    def bus_stops(self) -> List[StopRecord]:
        raise NotImplementedError

    def fire_assets(self) -> List[FireAssetRecord]:
        raise NotImplementedError

    def intersections(self) -> List[IntersectionRecord]:
        raise NotImplementedError

    def data_versions(self) -> Dict[str, str]:
        raise NotImplementedError


class InMemoryParkingRepository(ParkingRepository):
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or DATA_ROOT
        self._district_path = self.root / "district_boundary.geojson"
        self._roads_path = self.root / "roads.geojson"
        self._curb_path = self.root / "curb_restrictions.geojson"
        self._bus_path = self.root / "bus_stops.geojson"
        self._fire_path = self.root / "fire_assets.geojson"
        self._intersection_path = self.root / "intersections.geojson"
        self._cache = {}

    def district_boundary(self) -> Optional[DistrictBoundary]:
        if "district" in self._cache:
            return self._cache["district"]
        features = _load_geojson(self._district_path)
        boundary = None
        for feature in features:
            props = feature.get("properties", {})
            if props.get("district_name") == "信義區":
                boundary = DistrictBoundary(
                    name=props.get("district_name", "信義區"),
                    geom=shape(feature["geometry"]),
                    source_version=_feature_version(self._district_path),
                )
                break
        self._cache["district"] = boundary
        return boundary

    def roads(self) -> List[RoadRecord]:
        if "roads" in self._cache:
            return self._cache["roads"]
        records: List[RoadRecord] = []
        for feature in _load_geojson(self._roads_path):
            props = feature.get("properties", {})
            road_class = RoadClass(props.get("road_class", "SECONDARY"))
            records.append(
                RoadRecord(
                    road_id=str(props.get("road_id")),
                    geom=shape(feature["geometry"]),
                    road_class=road_class,
                    is_ramp_or_expressway=bool(props.get("is_ramp_or_expressway", False)),
                    name=props.get("name"),
                    source_version=_feature_version(self._roads_path),
                )
            )
        self._cache["roads"] = records
        return records

    def curb_restrictions(self) -> List[RestrictionRecord]:
        if "curb" in self._cache:
            return self._cache["curb"]
        records: List[RestrictionRecord] = []
        for feature in _load_geojson(self._curb_path):
            props = feature.get("properties", {})
            windows = [
                TimeWindow(**window) for window in props.get("time_windows", []) if isinstance(window, dict)
            ]
            records.append(
                RestrictionRecord(
                    restriction_id=str(props.get("restriction_id")),
                    geom=shape(feature["geometry"]),
                    restriction_type=RestrictionType(props.get("restriction_type", "RED")),
                    time_rule_type=TimeRuleType(props.get("time_rule_type", "ALWAYS")),
                    time_windows=windows,
                    note_raw=props.get("note_raw"),
                    confidence_base=float(props.get("confidence_base", 1.0)),
                    source_version=_feature_version(self._curb_path),
                )
            )
        self._cache["curb"] = records
        return records

    def bus_stops(self) -> List[StopRecord]:
        if "bus" in self._cache:
            return self._cache["bus"]
        records: List[StopRecord] = []
        for feature in _load_geojson(self._bus_path):
            props = feature.get("properties", {})
            records.append(
                StopRecord(
                    stop_id=str(props.get("stop_id")),
                    geom=shape(feature["geometry"]),
                    stop_name=str(props.get("stop_name", "")),
                    confidence_base=float(props.get("confidence_base", 1.0)),
                    source_version=_feature_version(self._bus_path),
                )
            )
        self._cache["bus"] = records
        return records

    def fire_assets(self) -> List[FireAssetRecord]:
        if "fire" in self._cache:
            return self._cache["fire"]
        records: List[FireAssetRecord] = []
        for feature in _load_geojson(self._fire_path):
            props = feature.get("properties", {})
            records.append(
                FireAssetRecord(
                    asset_id=str(props.get("asset_id")),
                    geom=shape(feature["geometry"]),
                    asset_type=str(props.get("asset_type", "HYDRANT")),
                    confidence_base=float(props.get("confidence_base", 1.0)),
                    source_version=_feature_version(self._fire_path),
                )
            )
        self._cache["fire"] = records
        return records

    def intersections(self) -> List[IntersectionRecord]:
        if "intersections" in self._cache:
            return self._cache["intersections"]
        records: List[IntersectionRecord] = []
        for feature in _load_geojson(self._intersection_path):
            props = feature.get("properties", {})
            records.append(
                IntersectionRecord(
                    node_id=str(props.get("node_id")),
                    geom=shape(feature["geometry"]),
                    degree=int(props.get("degree", 0)),
                    confidence_base=float(props.get("confidence_base", 0.9)),
                    source_version=_feature_version(self._intersection_path),
                )
            )
        self._cache["intersections"] = records
        return records

    def data_versions(self) -> Dict[str, str]:
        return {
            "district_boundary": _feature_version(self._district_path),
            "roads": _feature_version(self._roads_path),
            "curb_restrictions": _feature_version(self._curb_path),
            "bus_stops": _feature_version(self._bus_path),
            "fire_assets": _feature_version(self._fire_path),
            "intersections": _feature_version(self._intersection_path),
        }

    def with_versions(self, record: RestrictionRecord, version: str) -> RestrictionRecord:
        return replace(record, source_version=version)
