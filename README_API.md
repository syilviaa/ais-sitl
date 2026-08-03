# AIS SITL Computer Vision MVP - API Documentation

**Merei's responsibility**: Backend API, WebSocket events, GPS-to-pixel conversion, and event management.

## Overview

The Vision API provides real-time object detection events with GPS coordinates. The system integrates:
- Pixel-to-GPS conversion (geo_calculator.py)
- Vision event storage and retrieval
- REST API endpoints
- WebSocket real-time notifications
- Rate limiting (≤10 events/sec)

## JSON Contracts

### Telemetry Snapshot Schema
Location: `schema_telemetry.json`

Drone telemetry with camera orientation for correct geometric transformation.

**Required fields:**
- `timestamp`: ISO 8601 UTC (e.g., `2026-08-03T12:00:00Z`)
- `latitude`, `longitude`: Drone position in decimal degrees
- `altitude_m`: Altitude above ground (50-100m for MVP)
- `drone_yaw_deg`, `camera_pitch_deg`, `camera_yaw_deg`: Drone and camera orientation
- `hfov_deg`, `vfov_deg`: Horizontal and vertical field of view
- `frame_width`: 1920 (1080p)
- `frame_height`: 1080

**Validation:**
```python
telemetry = TelemetrySnapshot.from_dict(json_data)
telemetry.validate()  # Raises jsonschema.ValidationError if invalid
```

### Vision Event Schema
Location: `schema_vision_event.json`

Object detection event with calculated GPS coordinates.

**Required fields:**
- `event_id`: UUID (auto-generated)
- `timestamp`: ISO 8601 UTC (auto-generated)
- `class_name`: One of `["Person", "Car", "Truck_Machinery"]`
- `confidence`: Float 0.0-1.0 (≥0.65 from detector)
- `bbox`: `[x1, y1, x2, y2]` in frame pixels
- `latitude`, `longitude`: Calculated object center GPS
- `snapshot_url`: Path or URL to JPEG crop
- `source_id`: Source identifier (e.g., `"local_file"`, `"rtsp://..."`)

**Optional fields:**
- `processing_latency_ms`: Frame received → alert created
- `track_id`: Internal deduplication ID

**Example:**
```json
{
  "event_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2026-08-03T12:00:00Z",
  "class_name": "Person",
  "confidence": 0.87,
  "bbox": [100, 150, 200, 400],
  "latitude": 37.7749,
  "longitude": -122.4194,
  "snapshot_url": "/snapshots/550e8400-e29b-41d4-a716-446655440000.jpg",
  "source_id": "local_file",
  "processing_latency_ms": 45
}
```

## REST API Endpoints

### GET /api/vision/health
Health check.

**Response:**
```json
{
  "success": true,
  "status": "healthy",
  "timestamp": "2026-08-03T12:00:00Z"
}
```

### GET /api/vision/latest
Get latest N vision events.

**Query params:**
- `limit`: Number of events (default: 10, max: 100)

**Response:**
```json
{
  "success": true,
  "timestamp": "2026-08-03T12:00:00Z",
  "events": [
    { /* VisionEvent */ },
    ...
  ],
  "count": 10
}
```

### GET /api/vision/events
Get all events with optional class filtering.

**Query params:**
- `class`: Optional class name filter (`Person`, `Car`, `Truck_Machinery`)

**Response:**
```json
{
  "success": true,
  "timestamp": "2026-08-03T12:00:00Z",
  "events": [ /* VisionEvents */ ],
  "count": 42
}
```

### GET /api/vision/event/<event_id>
Get specific event by ID.

**Response:**
```json
{
  "success": true,
  "event": { /* VisionEvent */ }
}
```

**Error (404):**
```json
{
  "success": false,
  "error": "Event not found"
}
```

### GET /api/vision/snapshot/<event_id>
Get snapshot for an event.

Returns JPEG file if local path, or JSON with URL.

### GET /api/vision/stats
Get service statistics.

**Response:**
```json
{
  "success": true,
  "timestamp": "2026-08-03T12:00:00Z",
  "stats": {
    "total_events": 127,
    "last_event_time": "2026-08-03T12:34:56Z",
    "events_by_class": {
      "Person": 67,
      "Car": 42,
      "Truck_Machinery": 18
    }
  }
}
```

## WebSocket Events

### Connection
```javascript
const socket = io('http://localhost:5000');

socket.on('connect', () => {
  console.log('Connected');
  socket.emit('subscribe_detections');
});
```

### vision_detection
Real-time detection event.

**Payload:**
```json
{
  "event_type": "vision_detection",
  "timestamp": "2026-08-03T12:00:00Z",
  "data": { /* VisionEvent */ }
}
```

### vision_alert
Alert event (same structure as detection, but separate channel for UI filtering).

**Payload:**
```json
{
  "event_type": "vision_alert",
  "timestamp": "2026-08-03T12:00:00Z",
  "data": { /* VisionEvent */ }
}
```

### Rate Limiting
- Maximum 10 events/sec broadcasted on WebSocket
- Excess events are silently dropped (no buffering)
- REST API `/latest` endpoint has no rate limit

## Geo Calculation

### Pixel-to-GPS Conversion

**Module:** `backend/geo/geo_calculator.py`

The GeoCalculator uses a flat-earth model suitable for small areas (MVP scope).

```python
from backend.geo.geo_calculator import GeoCalculator
from backend.vision_contracts import TelemetrySnapshot

calculator = GeoCalculator()

# Calculate GPS from pixel coordinates
lat, lon = calculator.pixel_to_gps(
    bbox_center=(pixel_x, pixel_y),
    telemetry=telemetry_snapshot
)
```

**Assumptions:**
- Flat earth model (valid for small areas)
- Pinhole camera model
- Camera orientation relative to drone is fixed

**Accuracy:**
- Target: 5-10m error in demo scenarios
- Varies with altitude, FOV, and camera pitch
- Best accuracy at nadir (90° pitch)

**Validation:**
Use control points to verify accuracy:

```python
from backend.geo.geo_validation import GeoValidator

validator = GeoValidator()
control_points = validator.get_control_points()

for point in control_points:
    lat, lon = calculator.pixel_to_gps(
        bbox_center=(point.pixel_x, point.pixel_y),
        telemetry=telemetry_at_altitude(point.altitude_m)
    )
    error_m = validator.calculate_error_m(
        lat, lon,
        point.expected_lat, point.expected_lon
    )
    assert error_m <= 10.0  # MVP requirement
```

## Error Handling

### Telemetry Validation Errors
If telemetry is invalid (missing fields, out of range altitude):
- Logged but doesn't crash Vision Service
- GPS coordinates are not calculated
- No VisionEvent is created

### Rate Limiting
- WebSocket: Events beyond 10/sec are dropped silently
- REST API: No rate limit, returns all stored events

### Missing Resources
- Snapshot not found → return 404
- Event not found → return 404
- Invalid event_id → return 400

## Testing

### Unit Tests
```bash
pytest tests/unit/test_geo_calculator.py -v
pytest tests/unit/test_vision_service.py -v
pytest tests/unit/test_vision_contracts.py -v
```

### Test Fixtures
- `fixtures/telemetry_valid.json`: Valid telemetry example
- `fixtures/telemetry_invalid.json`: Invalid cases (out of range altitude, missing fields)
- `fixtures/vision_event_valid.json`: Valid vision event example

### Control Points
Synthetic control points at altitudes 50m, 75m, 100m for validation:
- Frame center
- Frame edges (left, right)

Expected error: ≤10 meters in demo scenarios.

## Performance Metrics

| Metric | Target | How to Measure |
|--------|--------|----------------|
| WebSocket throughput | ≤10 events/sec | `VisionSocketHandler._check_rate_limit()` |
| Event storage latency | <100ms | REST API response time |
| Geo accuracy | 5-10m | `GeoValidator.calculate_error_m()` |
| API response time | <500ms | Benchmark `/api/vision/latest` |

## Limitations

1. **Flat-Earth Model**: Not suitable for areas >50km diameter
2. **No Inter-Frame Tracking**: Deduplication (track_id) not in MVP
3. **No Thermal/IR**: RGB-only for MVP
4. **Stateless Cameras**: Camera parameters must be constant per run
5. **Rate Limiting**: Events beyond 10/sec are dropped (no queue)

## Integration Points

### From Detector (Zhanel)
- DetectorResult: class, confidence, bbox
- TelemetrySnapshot: drone position, camera orientation
- Frame: RGB image

### To Dashboard (UI)
- VisionEvent via REST API: `/api/vision/latest`
- Real-time updates via WebSocket: `vision_detection`, `vision_alert`
- Snapshot URLs for display

## Development Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Run tests
pytest tests/unit/ -v

# Start API server
python app.py

# Check health
curl http://localhost:5000/api/vision/health
```

## Future Improvements (Beyond MVP)

- [ ] DeepSORT inter-frame tracking
- [ ] Thermal/IR support
- [ ] TensorRT optimization
- [ ] Event persistence (database backend)
- [ ] Advanced rate limiting (queue + notify on drop)
