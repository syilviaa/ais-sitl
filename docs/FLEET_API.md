# Veha 5 Fleet API - Multi-Drone Management

Complete REST API reference for multi-drone coordination and fleet management.

## Overview

The Fleet API enables centralized management of multiple drones with:
- Drone registration and removal
- Fleet status aggregation
- Airspace conflict detection (Haversine-based, 100m horizontal / 50m vertical)
- Coordinated flight operations (staggered takeoff, broadcast commands)
- Emergency stop for all drones

## Base URL

```
http://127.0.0.1:5000/api/fleet
```

## Endpoints

### 1. Register Drone

**POST** `/fleet/add-drone`

Register a new drone in the fleet with connection details.

```bash
curl -X POST http://127.0.0.1:5000/api/fleet/add-drone \
  -H "Content-Type: application/json" \
  -d '{
    "name": "drone1",
    "host": "127.0.0.1",
    "port": 14540
  }'
```

**Request Body:**
- `name` (string, required): Unique drone identifier
- `host` (string, optional): MAVSDK connection host (default: "127.0.0.1")
- `port` (integer, optional): MAVSDK connection port (default: 14540)

**Response:**
```json
{
  "success": true,
  "message": "Drone drone1 registered",
  "drone_id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "drone1",
  "host": "127.0.0.1",
  "port": 14540
}
```

### 2. Remove Drone

**DELETE** `/fleet/remove-drone/{drone_id}`

Remove a drone from the fleet and disconnect.

```bash
curl -X DELETE http://127.0.0.1:5000/api/fleet/remove-drone/drone1
```

**Path Parameters:**
- `drone_id`: Drone name or UUID

**Response:**
```json
{
  "success": true,
  "message": "Drone drone1 removed",
  "drone_id": "drone1"
}
```

### 3. Fleet Status

**GET** `/fleet/status`

Get current status and positions of all drones.

```bash
curl http://127.0.0.1:5000/api/fleet/status
```

**Response:**
```json
{
  "success": true,
  "fleet_size": 2,
  "drones": {
    "drone1": {
      "name": "drone1",
      "connected": true,
      "state": "guided",
      "battery_percent": 85.5,
      "position": {
        "lat": 47.3977,
        "lon": 8.5455,
        "altitude": 50.2
      },
      "last_update": 1721938284.123
    },
    "drone2": {
      "name": "drone2",
      "connected": true,
      "state": "armed",
      "battery_percent": 90.0,
      "position": {
        "lat": 47.3980,
        "lon": 8.5458,
        "altitude": 50.5
      },
      "last_update": 1721938284.456
    }
  }
}
```

### 4. Check Airspace Conflicts

**GET** `/fleet/conflicts`

Detect potential collisions between drones (100m horizontal, 50m vertical).

```bash
curl http://127.0.0.1:5000/api/fleet/conflicts
```

**Response (no conflicts):**
```json
{
  "success": true,
  "conflict_count": 0,
  "conflicts": {}
}
```

**Response (conflicts detected):**
```json
{
  "success": true,
  "conflict_count": 1,
  "conflicts": {
    "drone1": ["drone2"],
    "drone2": ["drone1"]
  }
}
```

### 5. Coordinated Takeoff

**POST** `/fleet/coordinated-takeoff`

Execute staggered takeoff sequence with optional delay between drones.

```bash
curl -X POST http://127.0.0.1:5000/api/fleet/coordinated-takeoff \
  -H "Content-Type: application/json" \
  -d '{
    "drones": ["drone1", "drone2", "drone3"],
    "altitude": 50,
    "delay": 2.0
  }'
```

**Request Body:**
- `drones` (array, required): List of drone names to takeoff
- `altitude` (number, optional): Target altitude in meters (default: 50)
- `delay` (number, optional): Delay between takeoffs in seconds (default: 1.0)

**Response:**
```json
{
  "success": true,
  "message": "Coordinated takeoff initiated for 3 drones",
  "drones": ["drone1", "drone2", "drone3"],
  "altitude": 50,
  "delay": 2.0
}
```

### 6. Broadcast Command

**POST** `/fleet/broadcast`

Send a command to all drones in parallel.

```bash
curl -X POST http://127.0.0.1:5000/api/fleet/broadcast \
  -H "Content-Type: application/json" \
  -d '{
    "command": "arm"
  }'
```

**Supported Commands:**
- `arm`: Arm all drone motors
- `disarm`: Disarm all drone motors
- `takeoff`: Takeoff to altitude (requires `altitude` in data)
- `land`: Land all drones
- `hold`: Hold position on all drones
- `rtl`: Return to launch on all drones

**Request Body:**
- `command` (string, required): Command to execute
- Additional fields for command-specific parameters (e.g., `altitude` for takeoff)

**Response:**
```json
{
  "success": true,
  "command": "arm",
  "results": {
    "drone1": {
      "success": true,
      "message": "Armed"
    },
    "drone2": {
      "success": true,
      "message": "Armed"
    }
  }
}
```

### 7. Emergency Stop

**POST** `/fleet/emergency-stop`

Immediately land all drones (emergency failsafe).

```bash
curl -X POST http://127.0.0.1:5000/api/fleet/emergency-stop
```

**Response:**
```json
{
  "success": true,
  "message": "Emergency stop initiated for all drones"
}
```

## WebSocket Events

### Fleet Status Updates

Connect to WebSocket and emit `start_fleet_monitoring` to receive periodic fleet status.

```javascript
const socket = io('http://127.0.0.1:5000');

socket.emit('start_fleet_monitoring');

socket.on('fleet_status', (data) => {
  console.log('Fleet status:', data);
  // {
  //   "success": true,
  //   "fleet_size": 2,
  //   "drones": { ... }
  // }
});
```

### Fleet Status on Demand

```javascript
socket.emit('fleet_status');

socket.on('fleet_status', (data) => {
  console.log('Fleet status:', data);
});
```

## Error Handling

All endpoints return errors with `success: false` and an error message.

**400 Bad Request:**
```json
{
  "error": "Drone name required",
  "success": false
}
```

**500 Internal Server Error:**
```json
{
  "error": "Connection refused",
  "success": false
}
```

## Examples

### Multi-Drone Surveillance Mission

```bash
# 1. Register drones
curl -X POST http://127.0.0.1:5000/api/fleet/add-drone \
  -H "Content-Type: application/json" \
  -d '{"name": "drone1", "host": "127.0.0.1", "port": 14540}'

curl -X POST http://127.0.0.1:5000/api/fleet/add-drone \
  -H "Content-Type: application/json" \
  -d '{"name": "drone2", "host": "127.0.0.1", "port": 14541}'

# 2. Check fleet status
curl http://127.0.0.1:5000/api/fleet/status

# 3. Arm all drones
curl -X POST http://127.0.0.1:5000/api/fleet/broadcast \
  -H "Content-Type: application/json" \
  -d '{"command": "arm"}'

# 4. Coordinated takeoff (2 second stagger)
curl -X POST http://127.0.0.1:5000/api/fleet/coordinated-takeoff \
  -H "Content-Type: application/json" \
  -d '{
    "drones": ["drone1", "drone2"],
    "altitude": 100,
    "delay": 2.0
  }'

# 5. Monitor for conflicts
curl http://127.0.0.1:5000/api/fleet/conflicts

# 6. Land all drones
curl -X POST http://127.0.0.1:5000/api/fleet/broadcast \
  -H "Content-Type: application/json" \
  -d '{"command": "land"}'

# 7. Remove drones
curl -X DELETE http://127.0.0.1:5000/api/fleet/remove-drone/drone1
curl -X DELETE http://127.0.0.1:5000/api/fleet/remove-drone/drone2
```

## Performance Notes

- Fleet status queries run in parallel (no sequential blocking)
- Conflict detection uses Haversine algorithm: O(n²) where n = fleet size
- WebSocket broadcasts occur every 1 second (configurable)
- Per-drone async locking prevents race conditions
- Recommended fleet size: 2-10 drones per backend instance

## Veha 5 Integration

Fleet API is part of Veha 5 multi-drone platform:
- Phase 2: Multi-drone REST API (completed)
- Phase 3: Mission recording & playback
- Phase 4: Advanced geofence scenarios
- Phase 5: Prometheus metrics & Grafana monitoring
