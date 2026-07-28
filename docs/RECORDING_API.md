# Veha 5 Recording API - Mission Flight Data Management

Complete REST API reference for recording, storing, and replaying mission telemetry.

## Overview

The Recording API enables comprehensive flight data management:
- Real-time telemetry capture during missions
- Compressed JSON storage (60-80% reduction via field abbreviation)
- Mission replay with adjustable playback speeds
- Flight statistics (duration, distance, battery usage)
- Recording management (list, retrieve, delete)

## Base URL

```
http://127.0.0.1:5000/api/recording
```

## Endpoints

### 1. Start Recording

**POST** `/recording/start/{mission_id}`

Begin capturing telemetry for a mission.

```bash
curl -X POST http://127.0.0.1:5000/api/recording/start/mission-001
```

**Path Parameters:**
- `mission_id` (string, required): Unique mission identifier

**Response:**
```json
{
  "success": true,
  "message": "Recording started for mission mission-001",
  "mission_id": "mission-001"
}
```

### 2. Stop Recording

**POST** `/recording/stop/{mission_id}`

Stop recording and save to database.

```bash
curl -X POST http://127.0.0.1:5000/api/recording/stop/mission-001
```

**Path Parameters:**
- `mission_id` (string, required): Unique mission identifier

**Response:**
```json
{
  "success": true,
  "message": "Recording stopped for mission mission-001",
  "mission_id": "mission-001",
  "recording_id": "550e8400-e29b-41d4-a716-446655440000",
  "statistics": {
    "mission_id": "mission-001",
    "frame_count": 305,
    "duration_seconds": 30.5,
    "distance_meters": 2450.75,
    "max_altitude": 100.5,
    "battery": {
      "start": 100.0,
      "end": 87.5,
      "min": 87.0,
      "max": 100.0
    },
    "start_time": 1721938284.123,
    "end_time": 1721938314.623
  }
}
```

### 3. Get Recording Details

**GET** `/recording/get/{mission_id}`

Retrieve information about a recorded mission.

```bash
curl http://127.0.0.1:5000/api/recording/get/mission-001
```

**Path Parameters:**
- `mission_id` (string, required): Unique mission identifier

**Response:**
```json
{
  "success": true,
  "recording_id": "550e8400-e29b-41d4-a716-446655440000",
  "mission_id": "mission-001",
  "statistics": {
    "mission_id": "mission-001",
    "frame_count": 305,
    "duration_seconds": 30.5,
    "distance_meters": 2450.75,
    "max_altitude": 100.5,
    "battery": {
      "start": 100.0,
      "end": 87.5,
      "min": 87.0,
      "max": 100.0
    }
  },
  "frame_count": 305
}
```

### 4. List Recordings

**GET** `/recording/list`

Get all recorded missions with pagination.

```bash
curl http://127.0.0.1:5000/api/recording/list?limit=50
```

**Query Parameters:**
- `limit` (integer, optional): Maximum recordings to return (default: 50)

**Response:**
```json
{
  "success": true,
  "count": 3,
  "recordings": [
    {
      "recording_id": "550e8400-e29b-41d4-a716-446655440000",
      "mission_id": "mission-001",
      "duration_seconds": 30.5,
      "distance_meters": 2450.75,
      "max_altitude": 100.5,
      "battery_start": 100.0,
      "battery_end": 87.5,
      "created_at": "2026-07-25T14:31:24Z"
    },
    {
      "recording_id": "660e8400-e29b-41d4-a716-446655440001",
      "mission_id": "mission-002",
      "duration_seconds": 45.2,
      "distance_meters": 3650.25,
      "max_altitude": 150.0,
      "battery_start": 100.0,
      "battery_end": 82.0,
      "created_at": "2026-07-25T13:45:12Z"
    }
  ]
}
```

### 5. Get Playback Timeline

**GET** `/recording/playback/{mission_id}`

Retrieve telemetry timeline for replay with adjustable speed.

```bash
curl http://127.0.0.1:5000/api/recording/playback/mission-001?speed=1.0
```

**Path Parameters:**
- `mission_id` (string, required): Unique mission identifier

**Query Parameters:**
- `speed` (float, optional): Playback speed multiplier (default: 1.0)
  - 0.5 = half speed (2x slower)
  - 1.0 = normal speed
  - 2.0 = double speed
  - 4.0 = 4x speed

**Response:**
```json
{
  "success": true,
  "mission_id": "mission-001",
  "playback_speed": 1.0,
  "frame_count": 305,
  "duration_seconds": 30.5,
  "timeline": [
    {
      "t": 1721938284.123,
      "lat": 47.3977,
      "lon": 8.5455,
      "alt": 50.0,
      "vx": 0.0,
      "vy": 0.0,
      "vz": 0.0,
      "roll": 0.0,
      "pitch": 0.0,
      "yaw": 0.0,
      "bat": 100.0,
      "sat": 12,
      "arm": true,
      "mode": "GUIDED",
      "playback_time": 0.0
    },
    {
      "t": 1721938284.233,
      "lat": 47.3978,
      "lon": 8.5456,
      "alt": 50.5,
      "vx": 1.0,
      "vy": 0.5,
      "vz": 0.0,
      "roll": 0.1,
      "pitch": 0.05,
      "yaw": 0.0,
      "bat": 99.95,
      "sat": 12,
      "arm": true,
      "mode": "GUIDED",
      "playback_time": 0.1
    }
  ]
}
```

### 6. Delete Recording

**DELETE** `/recording/delete/{mission_id}`

Remove a recorded mission and its telemetry data.

```bash
curl -X DELETE http://127.0.0.1:5000/api/recording/delete/mission-001
```

**Path Parameters:**
- `mission_id` (string, required): Unique mission identifier

**Response:**
```json
{
  "success": true,
  "message": "Recording deleted for mission mission-001"
}
```

## Data Format

### Telemetry Frame Fields

Compressed format uses abbreviated field names to minimize storage:

```json
{
  "t": 1721938284.123,     // timestamp (Unix float)
  "lat": 47.3977,           // latitude (degrees)
  "lon": 8.5455,            // longitude (degrees)
  "alt": 50.0,              // altitude (meters)
  "vx": 0.0,                // velocity x (m/s)
  "vy": 0.0,                // velocity y (m/s)
  "vz": 0.0,                // velocity z (m/s)
  "roll": 0.0,              // roll angle (degrees)
  "pitch": 0.0,             // pitch angle (degrees)
  "yaw": 0.0,               // yaw angle (degrees)
  "bat": 100.0,             // battery percentage (%)
  "sat": 12,                // GPS satellites
  "arm": true,              // armed state
  "mode": "GUIDED"          // flight mode
}
```

## Examples

### Complete Mission Recording Workflow

```bash
# 1. Start recording before mission
curl -X POST http://127.0.0.1:5000/api/recording/start/surveillance-mission-001

# 2. Execute mission via mission API
curl -X POST http://127.0.0.1:5000/api/mission/start

# 3. Stop recording after mission completes
curl -X POST http://127.0.0.1:5000/api/recording/stop/surveillance-mission-001

# 4. View mission statistics
curl http://127.0.0.1:5000/api/recording/get/surveillance-mission-001

# 5. List all recorded missions
curl http://127.0.0.1:5000/api/recording/list?limit=100

# 6. Get playback timeline at 2x speed for analysis
curl http://127.0.0.1:5000/api/recording/playback/surveillance-mission-001?speed=2.0 | jq '.timeline | length'

# 7. Delete recording if needed
curl -X DELETE http://127.0.0.1:5000/api/recording/delete/surveillance-mission-001
```

### Flight Analysis via Playback

```bash
# Get full playback data
curl http://127.0.0.1:5000/api/recording/playback/mission-001?speed=1.0 > flight.json

# Extract just the positions for visualization
cat flight.json | jq '.timeline | map({lat, lon, alt, playback_time})' > positions.json

# Count frames
cat flight.json | jq '.frame_count'

# Get battery drain rate
cat flight.json | jq '.timeline | [.[0].bat, .[-1].bat] | .[0] - .[1]' 
```

## Performance Notes

- **Storage**: Compressed format reduces JSON size by 60-80% via field abbreviation
- **Capture Rate**: Records at 10 Hz (100ms between frames)
- **Database**: PostgreSQL with JSON storage type
- **Playback**: Timeline generation is O(n) where n = frame count
- **Max Mission**: Tested with 1000+ frame missions (~100 seconds at 10 Hz)

## Compression Details

The recorder abbreviates field names for storage efficiency:
- `timestamp` → `t`
- `latitude` → `lat`
- `longitude` → `lon`
- `altitude` → `alt`
- `battery_percent` → `bat`
- `satellites` → `sat`
- `armed` → `arm`
- `mode` → `mode` (unchanged)
- Velocity components: `vx`, `vy`, `vz`
- Attitude angles: `roll`, `pitch`, `yaw`

Example: A 305-frame mission occupies ~45 KB compressed vs ~120 KB uncompressed.

## Veha 5 Integration

Recording API is part of Veha 5 multi-drone platform:
- Phase 2: ✅ Multi-drone REST API
- Phase 3: ✅ Mission recording & playback (this)
- Phase 4: Advanced geofence scenarios
- Phase 5: Prometheus metrics & Grafana monitoring
