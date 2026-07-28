# Veha 4 REST API Reference

**Backend**: Flask + Flask-SocketIO  
**URL**: `http://127.0.0.1:5000`  
**WebSocket**: `ws://127.0.0.1:5000/socket.io/`

---

## Quick Start

```bash
# Start backend server
python3 run_backend.py

# In another terminal, test API
curl http://127.0.0.1:5000/api/health
```

---

## Drone Endpoints

### Initialize Connection
```
POST /api/drone/initialize
```

Connects to PX4 SITL and initializes all services.

**Response**:
```json
{
  "success": true,
  "message": "Drone initialized",
  "connected": true
}
```

---

### Get Status
```
GET /api/drone/status
```

Get current drone status snapshot.

**Response**:
```json
{
  "connected": true,
  "state": "ready",
  "telemetry": {
    "timestamp": 1689603600.123,
    "lat": 47.3977,
    "lon": 8.5455,
    "alt": 0.0,
    "vx": 0.0,
    "vy": 0.0,
    "vz": 0.0,
    "roll": 0.0,
    "pitch": 0.0,
    "yaw": 0.0,
    "battery": 100.0,
    "armed": false,
    "mode": "HOLD",
    "gps_status": "3D",
    "satellites": 12
  },
  "error": null
}
```

---

### Wait Until Ready
```
POST /api/drone/wait-ready
```

Wait for GPS lock and home position.

**Request**:
```json
{
  "timeout": 30
}
```

**Response**:
```json
{
  "success": true,
  "message": "Drone ready"
}
```

---

### Arm
```
POST /api/drone/arm
```

Arm motors.

**Response**:
```json
{
  "success": true,
  "message": "Armed"
}
```

---

### Disarm
```
POST /api/drone/disarm
```

Disarm motors.

---

### Takeoff
```
POST /api/drone/takeoff
```

Takeoff to altitude.

**Request**:
```json
{
  "altitude": 50.0
}
```

**Response**:
```json
{
  "success": true,
  "message": "Takeoff to 50.0m",
  "altitude": 50.0
}
```

---

### Land
```
POST /api/drone/land
```

Land at current position.

---

### Hold Position
```
POST /api/drone/hold
```

Hover in place.

---

### Return to Launch (RTL)
```
POST /api/drone/rtl
```

Return to home position.

**Request**:
```json
{
  "reason": "battery_low"
}
```

---

## Mission Endpoints

### Validate Mission
```
POST /api/mission/validate
```

Validate waypoints before upload.

**Request**:
```json
{
  "waypoints": [
    {
      "lat": 47.3977,
      "lon": 8.5455,
      "altitude": 50.0,
      "speed": 5.0,
      "wait_time": 0.0
    },
    {
      "lat": 47.3985,
      "lon": 8.5465,
      "altitude": 60.0,
      "speed": 5.0,
      "wait_time": 2.0
    }
  ]
}
```

**Response**:
```json
{
  "valid": true,
  "waypoints_count": 2,
  "error": null
}
```

---

### Upload Mission
```
POST /api/mission/upload
```

Upload validated mission to drone.

**Request**: Same as validate

**Response**:
```json
{
  "success": true,
  "mission_id": "abc12345",
  "waypoints": 2,
  "error": null
}
```

---

### Start Mission
```
POST /api/mission/start
```

Start mission execution.

**Response**:
```json
{
  "success": true,
  "mission_id": "abc12345",
  "error": null
}
```

---

### Pause Mission
```
POST /api/mission/pause
```

Pause at current waypoint.

---

### Resume Mission
```
POST /api/mission/resume
```

Continue from pause.

---

### Abort Mission
```
POST /api/mission/abort
```

Cancel current mission.

---

### Get Progress
```
GET /api/mission/progress
```

Get current mission progress.

**Response**:
```json
{
  "current": 2,
  "total": 3,
  "percent": 66.67,
  "mission_id": "abc12345"
}
```

---

### Get History
```
GET /api/mission/history
```

Get mission execution history.

**Response**:
```json
{
  "missions": [
    {
      "mission_id": "abc12345",
      "waypoints": 3,
      "status": "running"
    }
  ],
  "total": 1,
  "current_mission_id": "abc12345"
}
```

---

## Telemetry Endpoints

### Get Latest
```
GET /api/telemetry/latest
```

Get latest telemetry snapshot.

**Response**:
```json
{
  "timestamp": 1689603600.123,
  "lat": 47.3977,
  "lon": 8.5455,
  "alt": 50.2,
  "vx": 5.1,
  "vy": 0.3,
  "vz": -0.1,
  "roll": 1.2,
  "pitch": 2.1,
  "yaw": 180.5,
  "battery": 85.0,
  "armed": true,
  "mode": "AUTO",
  "gps_status": "3D",
  "satellites": 12
}
```

---

### Get History
```
GET /api/telemetry/history?count=10
```

Get telemetry history (default: 10 records).

**Response**:
```json
{
  "count": 10,
  "data": [
    {...},
    {...}
  ]
}
```

---

### Get Statistics
```
GET /api/telemetry/stats
```

Get collection statistics.

**Response**:
```json
{
  "update_count": 1234,
  "target_rate_hz": 10.0,
  "actual_rate_hz": 9.95,
  "history_size": 100
}
```

---

## Failsafe Endpoints

### Get Status
```
GET /api/failsafe/status
```

Get failsafe monitoring status.

**Response**:
```json
{
  "running": true,
  "battery_warning": 20.0,
  "battery_critical": 5.0,
  "link_loss_timeout": 3.0,
  "events_total": 0,
  "recent_events": []
}
```

---

### Get Events
```
GET /api/failsafe/events?limit=50
```

Get failsafe event history.

**Response**:
```json
{
  "total": 1,
  "events": [
    {
      "type": "failsafe",
      "reason": "battery_low",
      "timestamp": 1689603700.123
    }
  ]
}
```

---

## WebSocket Events

### Connect
```javascript
const socket = io('http://127.0.0.1:5000');

socket.on('connect', () => {
  console.log('Connected to server');
});

socket.on('connected', (data) => {
  console.log('Client ID:', data.client_id);
});
```

---

### Start Telemetry Stream
```javascript
// Request 10 Hz telemetry stream
socket.emit('start_telemetry');

// Receive telemetry updates
socket.on('telemetry', (data) => {
  console.log('Altitude:', data.alt);
  console.log('Battery:', data.battery);
});
```

---

### Stop Telemetry Stream
```javascript
socket.emit('stop_telemetry');
```

---

### Failsafe Events
```javascript
socket.on('failsafe', (event) => {
  console.log('Failsafe:', event.reason);
});
```

---

### Mission Updates
```javascript
socket.on('mission_update', (progress) => {
  console.log(`Waypoint ${progress.current}/${progress.total}`);
});
```

---

## Error Responses

### 400 Bad Request
```json
{
  "error": "Invalid request",
  "success": false
}
```

### 404 Not Found
```json
{
  "error": "Not found",
  "success": false
}
```

### 500 Internal Server Error
```json
{
  "error": "Internal server error",
  "success": false
}
```

---

## Testing with curl

```bash
# Health check
curl http://127.0.0.1:5000/api/health

# Initialize drone
curl -X POST http://127.0.0.1:5000/api/drone/initialize

# Get status
curl http://127.0.0.1:5000/api/drone/status

# Arm
curl -X POST http://127.0.0.1:5000/api/drone/arm

# Takeoff to 50m
curl -X POST http://127.0.0.1:5000/api/drone/takeoff \
  -H "Content-Type: application/json" \
  -d '{"altitude": 50}'

# Validate mission
curl -X POST http://127.0.0.1:5000/api/mission/validate \
  -H "Content-Type: application/json" \
  -d '{
    "waypoints": [
      {"lat": 47.39, "lon": 8.54, "altitude": 50},
      {"lat": 47.40, "lon": 8.55, "altitude": 60}
    ]
  }'

# Upload mission
curl -X POST http://127.0.0.1:5000/api/mission/upload \
  -H "Content-Type: application/json" \
  -d '{
    "waypoints": [
      {"lat": 47.39, "lon": 8.54, "altitude": 50},
      {"lat": 47.40, "lon": 8.55, "altitude": 60}
    ]
  }'

# Start mission
curl -X POST http://127.0.0.1:5000/api/mission/start

# Get progress
curl http://127.0.0.1:5000/api/mission/progress

# Land
curl -X POST http://127.0.0.1:5000/api/drone/land
```

---

## Testing with Python

```python
import requests

BASE_URL = "http://127.0.0.1:5000"

# Initialize
requests.post(f"{BASE_URL}/api/drone/initialize")

# Get status
status = requests.get(f"{BASE_URL}/api/drone/status").json()
print(status)

# Validate mission
mission = {
    "waypoints": [
        {"lat": 47.39, "lon": 8.54, "altitude": 50},
        {"lat": 47.40, "lon": 8.55, "altitude": 60},
    ]
}
requests.post(f"{BASE_URL}/api/mission/validate", json=mission)

# Upload mission
requests.post(f"{BASE_URL}/api/mission/upload", json=mission)

# Start
requests.post(f"{BASE_URL}/api/mission/start")

# Monitor progress
progress = requests.get(f"{BASE_URL}/api/mission/progress").json()
print(progress)
```

---

## Performance

- **Telemetry Rate**: 10 Hz (100ms interval)
- **Response Time**: <100ms
- **WebSocket Latency**: <50ms
- **Concurrent Clients**: 100+

---

## Status Codes

| Code | Meaning |
|------|---------|
| 200 | Success |
| 400 | Bad Request |
| 404 | Not Found |
| 500 | Server Error |

---

**Veha 4 Backend - REST API & WebSocket**  
Status: In Development  
Timeline: July 25-28, 2026
