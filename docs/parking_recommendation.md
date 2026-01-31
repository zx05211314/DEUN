# Taipei Xinyi District — Legal Curb Parking Recommendation (B2C PoC)

## Data contract (PostGIS-ready schema)

```sql
CREATE TABLE district_boundary (
  district_name TEXT PRIMARY KEY,
  geom_polygon GEOMETRY(Polygon, 4326),
  source_version TEXT NOT NULL,
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE roads (
  road_id TEXT PRIMARY KEY,
  geom_line GEOMETRY(LineString, 4326),
  road_class TEXT CHECK (road_class IN ('MAJOR', 'SECONDARY', 'ALLEY')),
  is_ramp_or_expressway BOOLEAN DEFAULT false,
  name TEXT,
  source_version TEXT NOT NULL,
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE curb_restrictions (
  restriction_id TEXT PRIMARY KEY,
  geom_line GEOMETRY(LineString, 4326),
  restriction_type TEXT CHECK (restriction_type IN ('RED', 'YELLOW')),
  time_rule_type TEXT CHECK (time_rule_type IN ('ALWAYS', 'WINDOWS', 'UNKNOWN')),
  time_windows JSONB DEFAULT '[]'::jsonb,
  note_raw TEXT,
  confidence_base DOUBLE PRECISION,
  source_version TEXT NOT NULL,
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE bus_stops (
  stop_id TEXT PRIMARY KEY,
  geom_point GEOMETRY(Point, 4326),
  stop_name TEXT,
  confidence_base DOUBLE PRECISION,
  source_version TEXT NOT NULL,
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE fire_assets (
  asset_id TEXT PRIMARY KEY,
  geom_point GEOMETRY(Point, 4326),
  asset_type TEXT CHECK (asset_type IN ('HYDRANT', 'FIRE_ENTRANCE')),
  confidence_base DOUBLE PRECISION,
  source_version TEXT NOT NULL,
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE intersections (
  node_id TEXT PRIMARY KEY,
  geom_point GEOMETRY(Point, 4326),
  degree INTEGER,
  confidence_base DOUBLE PRECISION,
  source_version TEXT NOT NULL,
  updated_at TIMESTAMPTZ DEFAULT now()
);
```

## Required fields per dataset

- **district_boundary**: `district_name`, `geom_polygon`, `source_version`
- **roads**: `road_id`, `geom_line`, `road_class`, `is_ramp_or_expressway`, `source_version` (optional: `name`)
- **curb_restrictions**: `restriction_id`, `geom_line`, `restriction_type`, `time_rule_type`, `time_windows`, `confidence_base`, `source_version` (optional: `note_raw`)
- **bus_stops**: `stop_id`, `geom_point`, `stop_name`, `confidence_base`, `source_version`
- **fire_assets**: `asset_id`, `geom_point`, `asset_type`, `confidence_base`, `source_version`
- **intersections**: `node_id`, `geom_point`, `degree`, `confidence_base`, `source_version`

## Sample GeoJSON features

```json
{
  "type": "Feature",
  "properties": {
    "district_name": "信義區",
    "source_version": "2024-01-01"
  },
  "geometry": {
    "type": "Polygon",
    "coordinates": [[[121.55, 25.02], [121.58, 25.02], [121.58, 25.05], [121.55, 25.05], [121.55, 25.02]]]
  }
}
```

```json
{
  "type": "Feature",
  "properties": {
    "road_id": "r-001",
    "road_class": "SECONDARY",
    "is_ramp_or_expressway": false,
    "name": "松仁路",
    "source_version": "2024-01-01"
  },
  "geometry": {
    "type": "LineString",
    "coordinates": [[121.57, 25.03], [121.575, 25.035]]
  }
}
```

```json
{
  "type": "Feature",
  "properties": {
    "restriction_id": "c-001",
    "restriction_type": "YELLOW",
    "time_rule_type": "WINDOWS",
    "time_windows": [{"start": "07:00", "end": "09:00", "days": "WEEKDAYS"}],
    "note_raw": "School drop-off zone",
    "confidence_base": 1.0,
    "source_version": "2024-01-01"
  },
  "geometry": {
    "type": "LineString",
    "coordinates": [[121.57, 25.03], [121.571, 25.03]]
  }
}
```

```json
{
  "type": "Feature",
  "properties": {
    "stop_id": "bs-001",
    "stop_name": "市政府站",
    "confidence_base": 1.0,
    "source_version": "2024-01-01"
  },
  "geometry": {
    "type": "Point",
    "coordinates": [121.565, 25.035]
  }
}
```

```json
{
  "type": "Feature",
  "properties": {
    "asset_id": "fa-001",
    "asset_type": "HYDRANT",
    "confidence_base": 0.9,
    "source_version": "2024-01-01"
  },
  "geometry": {
    "type": "Point",
    "coordinates": [121.566, 25.036]
  }
}
```

```json
{
  "type": "Feature",
  "properties": {
    "node_id": "int-001",
    "degree": 3,
    "confidence_base": 0.9,
    "source_version": "2024-01-01"
  },
  "geometry": {
    "type": "Point",
    "coordinates": [121.567, 25.037]
  }
}
```

## Import & standardization plan

1. **District boundary**
   - Source: Taipei administrative boundary (district-level).
   - Filter `district_name = "信義區"` and load into `district_boundary`.

2. **Road centerlines**
   - Source: city road network (centerline).
   - Normalize `road_class` into MAJOR/SECONDARY/ALLEY.
   - Populate `is_ramp_or_expressway` and `name` as available.

3. **Curb restrictions**
   - Source: legal curbline data or digitized curb markings.
   - Normalize to `restriction_type` (RED/YELLOW).
   - Parse time windows into `time_windows` JSONB.
   - Use `time_rule_type = UNKNOWN` if signs are unclear.

4. **Bus stops**
   - Source: official bus stop dataset.
   - Load points with `stop_name`.

5. **Fire assets**
   - Source: hydrant / fire entrance datasets.
   - Store `asset_type` accordingly.

6. **Intersections (derived)**
   - Use `ST_Node`/`ST_Dump` with road network to derive nodes and degree.

7. **Clip to Xinyi**
   - Use `ST_Intersection` with `district_boundary.geom_polygon` for all spatial tables.

## Rules engine summary

- **RED (hard exclusions)**: active redline, active yellowline, within 10m of intersections, within 10m of bus stops, within 5m of hydrants/fire assets.
- **YELLOW (medium risk)**: unknown yellowline, 10–15m from intersections/bus stops, 5–8m from hydrants, major roads, low-confidence data.
- **GREEN**: no RED/YELLOW triggers and outside active restrictions.

## Road filtering & classification

- `road_class` must be supplied in the roads dataset (or derived during ETL) with values `MAJOR`, `SECONDARY`, `ALLEY`.
- Segments where `is_ramp_or_expressway = true` are excluded from candidate generation.

## CRS and distance/buffer strategy

- Input GeoJSON is assumed to be WGS84 (EPSG:4326).
- For meter-accurate buffers (10m/15m/5m/8m), geometries are projected to **TWD97 / TM2 zone 121 (EPSG:3826)**, buffered in meters, and then converted back to WGS84 for output.
- Distance calculations for margins and walk distance are performed in the projected CRS to avoid degree-based inaccuracies.

## API contract

- `GET /v1/parking/recommend`
- `GET /v1/parking/segment/{segment_id}`

See `api/parking_api.py` for the response shape.

## Timezone handling

- The `time` query parameter accepts ISO-8601.
- If `time` includes a timezone offset, it is converted to **Asia/Taipei** for evaluation.
- If `time` is naive (no offset), it is assumed to be **Asia/Taipei**.
- If omitted, the server uses the current time in **Asia/Taipei**.

## Quickstart

### Run the API locally

```bash
pip install -r requirements.txt
uvicorn api.server:app --reload --port 8000
```

### Required input folder layout

```
data/parking/
  district_boundary.geojson
  roads.geojson
  curb_restrictions.geojson
  bus_stops.geojson
  fire_assets.geojson
  intersections.geojson
input/
  parking_qa_points.csv
```

> A tiny sample dataset pack is included in `data/parking/` for end-to-end smoke checks. Replace these files with real Xinyi datasets for production runs.

### Example requests

**Nearby mode**

```bash
curl "http://localhost:8000/v1/parking/recommend?mode=nearby&lat=25.0330&lng=121.5654&radius_m=600&time=2024-05-10T18:00:00+08:00&sort=near&limit=30"
```

**Polygon mode**

```bash
curl --get "http://localhost:8000/v1/parking/recommend" \
  --data-urlencode "mode=area" \
  --data-urlencode "polygon={\"type\":\"Polygon\",\"coordinates\":[[[121.561,25.032],[121.569,25.032],[121.569,25.038],[121.561,25.038],[121.561,25.032]]]}" \
  --data-urlencode "time=2024-05-10T18:00:00+08:00" \
  --data-urlencode "sort=near" \
  --data-urlencode "limit=30"
```

### API smoke tests (expected keys)

After starting the API with `uvicorn`, run:

```bash
curl -s "http://localhost:8000/v1/parking/recommend?mode=nearby&lat=25.0330&lng=121.5654&radius_m=600" | jq 'keys'
curl -s --get "http://localhost:8000/v1/parking/recommend" \
  --data-urlencode "mode=area" \
  --data-urlencode "polygon={\"type\":\"Polygon\",\"coordinates\":[[[121.561,25.032],[121.569,25.032],[121.569,25.038],[121.561,25.038],[121.561,25.032]]]}" | jq '.segments[0] | keys'
```

Expected top-level keys: `meta`, `segments`. For each segment: `segment_id`, `risk_level`, `geometry`, `anchor_point`, `score`, `explanations`, `checklist`.

### Example responses (trimmed)

> Responses below are illustrative examples from the bundled sample dataset; replace the sample data with real inputs for production validation.

**Nearby mode (sample)**

```json
{
  "meta": {
    "district": "信義區",
    "aoi_type": "circle",
    "generated_at": "2024-05-10T18:00:00+08:00",
    "data_versions": {
      "district_boundary": "district_boundary.geojson:1700000000",
      "roads": "roads.geojson:1700000000",
      "curb_restrictions": "curb_restrictions.geojson:1700000000",
      "bus_stops": "bus_stops.geojson:1700000000",
      "fire_assets": "fire_assets.geojson:1700000000",
      "intersections": "intersections.geojson:1700000000"
    }
  },
  "segments": [
    {
      "segment_id": "sample-segment-id",
      "risk_level": "GREEN",
      "geometry": {"type": "LineString", "coordinates": [[121.564, 25.033], [121.565, 25.034]]},
      "anchor_point": {"lat": 25.0335, "lng": 121.5645},
      "score": 0.0,
      "explanations": [{"reason_tag": "CLEAR_OF_RESTRICTIONS", "value": ""}],
      "checklist": []
    }
  ]
}
```

**Polygon mode (sample)**

```json
{
  "meta": {
    "district": "信義區",
    "aoi_type": "polygon",
    "generated_at": "2024-05-10T18:00:00+08:00",
    "data_versions": {
      "district_boundary": "district_boundary.geojson:1700000000",
      "roads": "roads.geojson:1700000000",
      "curb_restrictions": "curb_restrictions.geojson:1700000000",
      "bus_stops": "bus_stops.geojson:1700000000",
      "fire_assets": "fire_assets.geojson:1700000000",
      "intersections": "intersections.geojson:1700000000"
    }
  },
  "segments": [
    {
      "segment_id": "sample-segment-id",
      "risk_level": "GREEN",
      "geometry": {"type": "LineString", "coordinates": [[121.569, 25.036], [121.57, 25.037]]},
      "anchor_point": {"lat": 25.0365, "lng": 121.5695},
      "score": 0.0,
      "explanations": [{"reason_tag": "CLEAR_OF_RESTRICTIONS", "value": ""}],
      "checklist": []
    }
  ]
}
```

## QA / validation plan

- Maintain 30–60 curated test points across Xinyi:
  - dense commercial areas, residential alleys, MRT exits, bus-stop clusters.
- For each point: record expected level, photo/Street View reference, and notes.
- Acceptance: GREEN false positives should be extremely low.
- QA harness outputs reports to `reports/parking_qa_report.json` and `reports/parking_qa_report.csv`.
- Full QA evaluation requires `shapely` and `pyproj` to be installed; the fallback mode is a last resort and may reduce spatial accuracy.
