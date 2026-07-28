# Veha 5 Geofence API - Airspace Boundary Enforcement

Complete REST API reference for geofence zone management and real-time boundary monitoring.

## Overview

The Geofence API provides comprehensive airspace restrictions:
- Polygon boundary enforcement (ray-casting point-in-polygon)
- Altitude ceiling per zone (min/max altitude constraints)
- Pre-flight mission validation against NFZ
- Real-time position monitoring with violation alerts
- Violation history tracking and analysis

## Base URL

```
http://127.0.0.1:5000/api/geofence
```

## Endpoints

### 1. Create Geofence Zone

**POST** `/geofence/create`

Define a new No-Fly Zone (NFZ) with boundary polygon and altitude constraints.

```bash
curl -X POST http://127.0.0.1:5000/api/geofence/create \
  -H "Content-Type: application/json" \
  -d '{
    "name": "restricted_airspace",
    "polygon": {
      "type": "Polygon",
      "coordinates": [[[8.5, 47.3], [8.6, 47.3], [8.6, 47.4], [8.5, 47.4], [8.5, 47.3]]]
    },
    "altitude_min": 0.0,
    "altitude_max": 100.0
  }'
```

**Request Body:**
- `name` (string, required): Unique zone identifier
- `polygon` (GeoJSON, required): Boundary polygon with exterior ring
- `altitude_min` (float, optional): Minimum altitude in meters (default: 0)
- `altitude_max` (float, optional): Maximum altitude in meters (default: ∞)

**Response:**
```json
{
  "success": true,
  "message": "Zone restricted_airspace created",
  "zone_id": "550e8400-e29b-41d4-a716-446655440000",
  "zone": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "restricted_airspace",
    "polygon": {...},
    "altitude_min": 0.0,
    "altitude_max": 100.0,
    "active": true
  }
}
```

### 2. Get Zone Details

**GET** `/geofence/get/{zone_name}`

Retrieve information about a geofence zone.

```bash
curl http://127.0.0.1:5000/api/geofence/get/restricted_airspace
```

**Path Parameters:**
- `zone_name` (string, required): Zone identifier

**Response:**
```json
{
  "success": true,
  "zone": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "restricted_airspace",
    "polygon": {...},
    "altitude_min": 0.0,
    "altitude_max": 100.0,
    "active": true
  }
}
```

### 3. List All Zones

**GET** `/geofence/list`

Get all geofence zones with optional active filter.

```bash
curl http://127.0.0.1:5000/api/geofence/list?active=true
```

**Query Parameters:**
- `active` (boolean, optional): Filter by active status (default: true)

**Response:**
```json
{
  "success": true,
  "count": 3,
  "zones": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "name": "restricted_airspace",
      "altitude_min": 0.0,
      "altitude_max": 100.0,
      "active": true
    }
  ]
}
```

### 4. Update Zone

**POST** `/geofence/update/{zone_name}`

Modify zone parameters (boundary, altitude limits, status).

```bash
curl -X POST http://127.0.0.1:5000/api/geofence/update/restricted_airspace \
  -H "Content-Type: application/json" \
  -d '{
    "altitude_max": 150.0,
    "active": true
  }'
```

**Path Parameters:**
- `zone_name` (string, required): Zone identifier

**Request Body:**
- `polygon` (GeoJSON, optional): Updated boundary
- `altitude_min` (float, optional): New minimum altitude
- `altitude_max` (float, optional): New maximum altitude
- `active` (boolean, optional): Enable/disable zone

**Response:**
```json
{
  "success": true,
  "message": "Zone restricted_airspace updated",
  "zone": {...}
}
```

### 5. Delete Zone

**DELETE** `/geofence/delete/{zone_name}`

Remove a geofence zone.

```bash
curl -X DELETE http://127.0.0.1:5000/api/geofence/delete/restricted_airspace
```

**Path Parameters:**
- `zone_name` (string, required): Zone identifier

**Response:**
```json
{
  "success": true,
  "message": "Zone restricted_airspace deleted"
}
```

### 6. Validate Mission Waypoints

**POST** `/geofence/validate-mission`

Pre-flight check: validate all waypoints against active geofence zones.

```bash
curl -X POST http://127.0.0.1:5000/api/geofence/validate-mission \
  -H "Content-Type: application/json" \
  -d '{
    "waypoints": [
      {"lat": 47.35, "lon": 8.55, "altitude": 50.0},
      {"lat": 47.36, "lon": 8.56, "altitude": 60.0},
      {"lat": 47.37, "lon": 8.57, "altitude": 55.0}
    ]
  }'
```

**Request Body:**
- `waypoints` (array, required): List of waypoint objects with lat/lon/altitude

**Response (Valid Mission):**
```json
{
  "success": true,
  "valid": true,
  "violation_count": 0,
  "violations": []
}
```

**Response (Invalid Mission):**
```json
{
  "success": true,
  "valid": false,
  "violation_count": 2,
  "violations": [
    {
      "waypoint_index": 1,
      "waypoint": {"lat": 47.36, "lon": 8.56, "altitude": 150.0},
      "zone": "restricted_airspace",
      "violation_type": "altitude",
      "message": "Above maximum altitude (150m > 100m)"
    },
    {
      "waypoint_index": 2,
      "waypoint": {"lat": 47.37, "lon": 8.57, "altitude": 55.0},
      "zone": "restricted_airspace",
      "violation_type": "boundary",
      "message": "Outside geofence boundary (47.37, 8.57)"
    }
  ]
}
```

### 7. Check Real-Time Position

**POST** `/geofence/check-position`

Real-time monitoring: validate drone position against all active zones.

```bash
curl -X POST http://127.0.0.1:5000/api/geofence/check-position \
  -H "Content-Type: application/json" \
  -d '{
    "drone_id": "drone1",
    "position": {
      "lat": 47.3977,
      "lon": 8.5455,
      "altitude": 50.0
    }
  }'
```

**Request Body:**
- `drone_id` (string, required): Drone identifier
- `position` (object, required): Current position with lat/lon/altitude

**Response (Safe):**
```json
{
  "success": true,
  "safe": true,
  "violation_count": 0,
  "violations": []
}
```

**Response (Violation):**
```json
{
  "success": true,
  "safe": false,
  "violation_count": 1,
  "violations": [
    {
      "type": "altitude",
      "zone": "restricted_airspace",
      "message": "Above maximum altitude (120m > 100m)",
      "action": "hold"
    }
  ]
}
```

### 8. Get Violation History

**GET** `/geofence/violations/{zone_name}`

Retrieve past violations for a geofence zone.

```bash
curl http://127.0.0.1:5000/api/geofence/violations/restricted_airspace?limit=50
```

**Path Parameters:**
- `zone_name` (string, required): Zone identifier

**Query Parameters:**
- `limit` (integer, optional): Maximum violations to return (default: 100)

**Response:**
```json
{
  "success": true,
  "zone": "restricted_airspace",
  "violation_count": 2,
  "violations": [
    {
      "violation_type": "altitude",
      "drone_id": "drone1",
      "timestamp": 1721938284.123,
      "position": {
        "lat": 47.3977,
        "lon": 8.5455,
        "alt": 120.5
      },
      "action_taken": "hold",
      "message": "Above maximum altitude"
    },
    {
      "violation_type": "boundary",
      "drone_id": "drone2",
      "timestamp": 1721938290.456,
      "position": {
        "lat": 47.4100,
        "lon": 8.5600,
        "alt": 50.0
      },
      "action_taken": "rtl",
      "message": "Outside geofence boundary"
    }
  ]
}
```

## GeoJSON Polygon Format

### Simple Rectangle

```json
{
  "type": "Polygon",
  "coordinates": [
    [
      [8.5, 47.3],
      [8.6, 47.3],
      [8.6, 47.4],
      [8.5, 47.4],
      [8.5, 47.3]
    ]
  ]
}
```

### Complex Boundary with Hole

```json
{
  "type": "Polygon",
  "coordinates": [
    [
      [8.5, 47.3],
      [8.7, 47.3],
      [8.7, 47.5],
      [8.5, 47.5],
      [8.5, 47.3]
    ],
    [
      [8.55, 47.35],
      [8.65, 47.35],
      [8.65, 47.45],
      [8.55, 47.45],
      [8.55, 47.35]
    ]
  ]
}
```

## Examples

### Complete Geofence Workflow

```bash
# 1. Create restricted airspace zone
curl -X POST http://127.0.0.1:5000/api/geofence/create \
  -H "Content-Type: application/json" \
  -d '{
    "name": "airfield",
    "polygon": {
      "type": "Polygon",
      "coordinates": [[[8.5, 47.3], [8.6, 47.3], [8.6, 47.4], [8.5, 47.4], [8.5, 47.3]]]
    },
    "altitude_min": 0.0,
    "altitude_max": 100.0
  }'

# 2. List all active zones
curl http://127.0.0.1:5000/api/geofence/list?active=true

# 3. Pre-flight mission validation
curl -X POST http://127.0.0.1:5000/api/geofence/validate-mission \
  -H "Content-Type: application/json" \
  -d '{
    "waypoints": [
      {"lat": 47.35, "lon": 8.55, "altitude": 50.0},
      {"lat": 47.36, "lon": 8.56, "altitude": 75.0},
      {"lat": 47.35, "lon": 8.55, "altitude": 50.0}
    ]
  }'

# 4. During flight: check drone position
curl -X POST http://127.0.0.1:5000/api/geofence/check-position \
  -H "Content-Type: application/json" \
  -d '{
    "drone_id": "drone1",
    "position": {"lat": 47.3509, "lon": 8.5509, "altitude": 48.5}
  }'

# 5. Update zone (emergency increase altitude limit)
curl -X POST http://127.0.0.1:5000/api/geofence/update/airfield \
  -H "Content-Type: application/json" \
  -d '{"altitude_max": 150.0}'

# 6. Post-flight: retrieve violation history
curl http://127.0.0.1:5000/api/geofence/violations/airfield?limit=100

# 7. Disable zone temporarily
curl -X POST http://127.0.0.1:5000/api/geofence/update/airfield \
  -H "Content-Type: application/json" \
  -d '{"active": false}'

# 8. Delete zone when no longer needed
curl -X DELETE http://127.0.0.1:5000/api/geofence/delete/airfield
```

## Violation Types

| Type | Description | Action | Example |
|------|-------------|--------|---------|
| `altitude` | Altitude outside min/max range | hold, land | Drone at 120m with max 100m |
| `boundary` | Position outside polygon | hold, rtl | Drone outside NFZ perimeter |
| `return_home` | Automatic RTL triggered | rtl | Combined violations trigger RTL |

## Performance Notes

- **Polygon Checking:** O(n) ray-casting where n = polygon vertices
- **Zone Queries:** Constant time (in-memory cache)
- **Multi-Zone Validation:** O(z × w × n) where z = zones, w = waypoints, n = polygon vertices
- **Recommended Max:** 50 zones per backend, 10 vertices per polygon

## Integration with Failsafe

Geofence violations can trigger automatic failsafe actions:

```python
# Register callback for RTL on boundary breach
coordinator.geofence.register_violation_callback(
    drone_id="drone1",
    zone_name="restricted_airspace",
    callback=on_violation  # Triggered on boundary violation
)

async def on_violation(violation):
    if violation.violation_type == "boundary":
        await drone_service.return_to_launch(reason="geofence_breach")
```

## Database Schema

Zones stored in `noflyZones` table:
- `id` (UUID): Primary key
- `name` (string): Unique zone identifier
- `polygon` (JSON): GeoJSON polygon geometry
- `altitude_min` (float): Minimum altitude
- `altitude_max` (float): Maximum altitude
- `active` (boolean): Zone status
- `created_at`, `updated_at` (timestamps)

## Veha 5 Integration

Geofence API is part of Veha 5 multi-drone platform:
- Phase 2: ✅ Multi-drone REST API
- Phase 3: ✅ Mission recording & playback
- Phase 4: ✅ Advanced geofence failsafe (this)
- Phase 5: Prometheus metrics & Grafana monitoring
