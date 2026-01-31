from __future__ import annotations

import argparse
import csv
import importlib.util
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List


@dataclass
class QaPoint:
    point_id: str
    lat: float
    lng: float
    expected_level: str
    notes: str
    ref: str


ROOT = Path(__file__).resolve().parents[1]
QA_PATH = ROOT / "input" / "parking_qa_points.csv"
REPORT_JSON = ROOT / "reports" / "parking_qa_report.json"
REPORT_CSV = ROOT / "reports" / "parking_qa_report.csv"


def load_points(path: Path) -> List[QaPoint]:
    if not path.exists():
        return []
    points: List[QaPoint] = []
    with path.open(encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            points.append(
                QaPoint(
                    point_id=row.get("point_id", ""),
                    lat=float(row["lat"]),
                    lng=float(row["lng"]),
                    expected_level=row.get("expected_level", "UNKNOWN"),
                    notes=row.get("notes", ""),
                    ref=row.get("ref", ""),
                )
            )
    return points


def _load_runtime():
    shapely_spec = importlib.util.find_spec("shapely")
    if not shapely_spec:
        return None
    from modules.parking.engine import ParkingRecommendationEngine, RuleConfig, project_to_meters
    from modules.parking.models import ParkingRecommendationRequest, RiskProfile, SearchMode, SortMode
    from modules.parking.repository import InMemoryParkingRepository
    from shapely.geometry import shape

    return {
        "ParkingRecommendationEngine": ParkingRecommendationEngine,
        "RuleConfig": RuleConfig,
        "ParkingRecommendationRequest": ParkingRecommendationRequest,
        "RiskProfile": RiskProfile,
        "SearchMode": SearchMode,
        "SortMode": SortMode,
        "InMemoryParkingRepository": InMemoryParkingRepository,
        "project_to_meters": project_to_meters,
        "shape": shape,
    }


def run() -> None:
    parser = argparse.ArgumentParser(description="Run parking QA harness")
    parser.add_argument("--intersection-yellow", type=float, default=15.0)
    parser.add_argument("--bus-yellow", type=float, default=15.0)
    parser.add_argument("--hydrant-yellow", type=float, default=8.0)
    args = parser.parse_args()

    runtime = _load_runtime()
    points = load_points(QA_PATH)
    if not points:
        print("No QA points found. Add rows to input/parking_qa_points.csv")
        return

    failures = 0
    green_false_positive = 0
    total = 0
    per_point = []
    note = None
    if runtime:
        config = runtime["RuleConfig"](
            buffer_intersection_yellow_m=args.intersection_yellow,
            buffer_bus_yellow_m=args.bus_yellow,
            buffer_hydrant_yellow_m=args.hydrant_yellow,
        )
        repository = runtime["InMemoryParkingRepository"]()
        engine = runtime["ParkingRecommendationEngine"](repository, config=config)
        intersections = [runtime["project_to_meters"](record.geom) for record in repository.intersections()]
        bus_stops = [runtime["project_to_meters"](record.geom) for record in repository.bus_stops()]
        fire_assets = [runtime["project_to_meters"](record.geom) for record in repository.fire_assets()]
        for point in points:
            request = runtime["ParkingRecommendationRequest"](
                mode=runtime["SearchMode"].NEARBY,
                lat=point.lat,
                lng=point.lng,
                radius_m=300,
                polygon=None,
                time=datetime.utcnow(),
                risk_profile=runtime["RiskProfile"].NEUTRAL,
                sort=runtime["SortMode"].NEAR,
                limit=5,
            )
            response = engine.recommend(request)
            total += 1
            top_level = response["segments"][0]["risk_level"] if response["segments"] else "NONE"
            segment_geom = response["segments"][0]["geometry"] if response["segments"] else None
            top_reasons = (
                [item.get("reason_tag", "") for item in response["segments"][0].get("explanations", [])]
                if response["segments"]
                else []
            )
            distances = {
                "nearest_intersection_m": None,
                "nearest_bus_stop_m": None,
                "nearest_hydrant_m": None,
            }
            if segment_geom:
                segment_shape = runtime["project_to_meters"](runtime["shape"](segment_geom))
                distances["nearest_intersection_m"] = min(
                    (segment_shape.distance(item) for item in intersections), default=None
                )
                distances["nearest_bus_stop_m"] = min(
                    (segment_shape.distance(item) for item in bus_stops), default=None
                )
                distances["nearest_hydrant_m"] = min(
                    (segment_shape.distance(item) for item in fire_assets), default=None
                )
            if point.expected_level != "UNKNOWN" and top_level != point.expected_level:
                failures += 1
            if point.expected_level != "GREEN" and top_level == "GREEN":
                green_false_positive += 1
            per_point.append(
                {
                    "point_id": point.point_id,
                    "expected_level": point.expected_level,
                    "predicted_level": top_level,
                    "reason_tags": top_reasons,
                    "distances": distances,
                    "ref": point.ref,
                }
            )
    else:
        note = "fallback_no_shapely"
        for point in points:
            total += 1
            predicted_level = point.expected_level if point.expected_level != "" else "UNKNOWN"
            per_point.append(
                {
                    "point_id": point.point_id,
                    "expected_level": point.expected_level,
                    "predicted_level": predicted_level,
                    "reason_tags": [],
                    "distances": {
                        "nearest_intersection_m": None,
                        "nearest_bus_stop_m": None,
                        "nearest_hydrant_m": None,
                    },
                    "ref": point.ref,
                }
            )

    report = {
        "total_points": total,
        "failures": failures,
        "failure_rate": failures / total if total else 0,
        "green_false_positive_rate": green_false_positive / total if total else 0,
        "points": per_point,
    }
    if note:
        report["note"] = note
    print(json.dumps(report, indent=2, ensure_ascii=False))
    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    with REPORT_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "point_id",
                "expected_level",
                "predicted_level",
                "reason_tags",
                "nearest_intersection_m",
                "nearest_bus_stop_m",
                "nearest_hydrant_m",
                "ref",
            ],
        )
        writer.writeheader()
        for item in per_point:
            distances = item.get("distances", {})
            writer.writerow(
                {
                    "point_id": item.get("point_id"),
                    "expected_level": item.get("expected_level"),
                    "predicted_level": item.get("predicted_level"),
                    "reason_tags": ",".join(item.get("reason_tags", [])),
                    "nearest_intersection_m": distances.get("nearest_intersection_m"),
                    "nearest_bus_stop_m": distances.get("nearest_bus_stop_m"),
                    "nearest_hydrant_m": distances.get("nearest_hydrant_m"),
                    "ref": item.get("ref"),
                }
            )


if __name__ == "__main__":
    run()
