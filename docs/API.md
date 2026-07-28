# API Reference

## Python SDK: Drone/Plane Class

`Drone` controls only a local PX4 SITL UDP endpoint. `Plane` remains a
compatibility alias. Passing a non-local host raises `ConnectionError`.

```python
from src.autopilot.plane import Drone

drone = Drone(host="127.0.0.1", port=14540)
await drone.connect()
await drone.wait_until_ready()  # requires GPS and home position
await drone.arm()
await drone.takeoff(5.0)
await drone.hold_position()
await drone.land()
await drone.disconnect()
```

### State and safety

`DroneState` values are `DISCONNECTED`, `CONNECTED`, `READY`, `ARMED`,
`AIRBORNE`, `HOLDING`, `LANDING`, `RTL`, and `ERROR`. The current value is
available as `drone.state`.

`arm()` is permitted only from `READY`; `takeoff(altitude_m)` only from
`ARMED`; `hold_position()` and `return_to_launch(reason)` only while airborne.
Takeoff altitude must be from 0.5 to 120 metres. Commands wait for real MAVSDK
telemetry confirmation and raise `DroneTimeoutError` if PX4 does not reach the
expected state. Invalid transitions raise `InvalidStateError`.

### Missions

`validate_mission(waypoints)` validates `(lat, lon, relative_altitude_m)` points
through the existing `GeofenceValidator`; it raises `MissionValidationError`
before a hazardous mission can be uploaded. `fly_mission(waypoints)` validates,
builds MAVSDK `MissionItem` objects, uploads a `MissionPlan`, and starts it.
`get_mission_progress()` returns the latest `current`/`total` progress received
from MAVSDK.

### Telemetry

`TelemetrySnapshot` contains `Position`, `Velocity`, and `Attitude` dataclasses.
`get_telemetry()` returns their backwards-compatible flat dictionary with GPS,
absolute and relative altitude (`alt`), NED ground/vertical velocity,
roll/pitch/yaw, battery percentage, armed state, flight mode, and timestamp.
Fields remain `None` until their real MAVSDK stream has produced data.

`subscribe_telemetry(callback)` starts background collection and invokes the
callback at no more than 10 Hz. Call `unsubscribe_telemetry()` to stop it.

### Exceptions

`ConnectionError`, `DroneTimeoutError`, `InvalidStateError`, and
`MissionValidationError` are the primary control exceptions. `BatteryLowError`
and `LinkLossError` remain available for documented compatibility; policy for
failsafe behavior belongs to the dedicated failsafe module.

---

### Geofencing API

#### load_nfz_zones(filepath: str)
Load No-Fly Zone definitions from GeoJSON.

```python
from src.autopilot.geofence import GeofenceValidator

validator = GeofenceValidator()
validator.load_nfz_zones("config/nfz_zones.geojson")
```

**GeoJSON Format:**
```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "properties": {
        "name": "Airport Control Zone",
        "max_altitude": 150.0
      },
      "geometry": {
        "type": "Polygon",
        "coordinates": [[[lat, lon], [lat, lon], ...]]
      }
    }
  ]
}
```

---

#### validate_mission(waypoints: List[Tuple]) → bool
Check if mission violates any NFZ.

```python
waypoints = [(47.39, 8.54, 50), (47.40, 8.55, 50)]
is_valid = validator.validate_mission(waypoints)

if is_valid:
    print("✅ Mission clears all NFZ")
else:
    print("❌ Mission crosses No-Fly Zone")
```

---

#### check_point_in_nfz(lat: float, lon: float, alt: float) → bool
Check single point against NFZ (runtime).

```python
in_nfz = validator.check_point_in_nfz(47.39, 8.54, 50.0)

if in_nfz:
    print("⚠️  Drone entered NFZ!")
    await drone.hold_position()
```

---

### Failsafe API

#### FailsafeMonitor
Automatic monitoring for emergency conditions.

```python
from src.autopilot.failsafe import FailsafeMonitor

monitor = FailsafeMonitor(drone, config="config/sitl.yaml")
await monitor.start()  # Background monitoring

# Automatically handles:
# - Battery low (< 20%) → RTL
# - Link loss (> 3s) → Hold → RTL
# - NFZ breach → Hold position
```

---

## REST API (Backend Server)

### Endpoints

#### GET /api/drone/status
Current drone status snapshot.

```bash
curl http://localhost:5000/api/drone/status
```

**Response:**
```json
{
  "connected": true,
  "armed": true,
  "mode": "AUTO",
  "position": {
    "lat": 47.39770,
    "lon": 8.54550,
    "alt": 50.2
  },
  "velocity": {
    "x": 5.1,
    "y": 0.3,
    "z": -0.1
  },
  "battery": 78.5,
  "timestamp": 1689603600.123
}
```

---

#### POST /api/drone/arm
Arm motors.

```bash
curl -X POST http://localhost:5000/api/drone/arm
```

---

#### POST /api/drone/disarm
Disarm motors.

```bash
curl -X POST http://localhost:5000/api/drone/disarm
```

---

#### POST /api/drone/takeoff
Takeoff to altitude.

```bash
curl -X POST http://localhost:5000/api/drone/takeoff \
  -H "Content-Type: application/json" \
  -d '{"altitude": 50.0}'
```

---

#### POST /api/drone/land
Land at current position.

```bash
curl -X POST http://localhost:5000/api/drone/land
```

---

#### POST /api/mission/upload
Upload and execute mission.

```bash
curl -X POST http://localhost:5000/api/mission/upload \
  -H "Content-Type: application/json" \
  -d '{
    "waypoints": [
      [47.39770, 8.54550, 50.0],
      [47.39900, 8.55000, 60.0],
      [47.39770, 8.54550, 0.0]
    ]
  }'
```

**Response:**
```json
{
  "success": true,
  "message": "Mission uploaded",
  "mission_id": "abc123"
}
```

---

#### GET /api/mission/progress
Mission execution progress.

```bash
curl http://localhost:5000/api/mission/progress
```

---

#### POST /api/mission/abort
Abort current mission.

```bash
curl -X POST http://localhost:5000/api/mission/abort
```

---

## WebSocket Events

Real-time telemetry streaming.

```javascript
const socket = io('http://localhost:5000');

socket.on('telemetry', (data) => {
  console.log(`Altitude: ${data.alt} m`);
  console.log(`Battery: ${data.battery}%`);
});

socket.on('mission_update', (progress) => {
  console.log(`Waypoint ${progress.current}/${progress.total}`);
});

socket.on('failsafe', (event) => {
  console.log(`⚠️ Failsafe triggered: ${event.reason}`);
});
```

---

## Error Handling

### Common Exceptions

```python
from src.autopilot.plane import (
    ConnectionError,
    MissionValidationError,
    BatteryLowError,
    LinkLossError,
)

try:
    await drone.fly_mission(waypoints)
except MissionValidationError as e:
    print(f"❌ Mission invalid: {e}")
except BatteryLowError as e:
    print(f"⚠️ Battery low, triggering RTL")
except ConnectionError as e:
    print(f"❌ Connection lost")
```

---

## Code Examples

### Complete Mission Example

```python
import asyncio
from src.autopilot.plane import Drone
from src.autopilot.geofence import GeofenceValidator

async def main():
    # Initialize
    drone = Drone()
    validator = GeofenceValidator()
    validator.load_nfz_zones("config/nfz_zones.geojson")

    # Check connection
    if not drone.is_connected():
        print("❌ Cannot connect to drone")
        return

    # Plan mission
    waypoints = [
        (47.39770, 8.54550, 50.0),
        (47.39900, 8.55000, 50.0),
        (47.40100, 8.54500, 50.0),
        (47.39770, 8.54550, 0.0),  # Land
    ]

    # Validate
    if not validator.validate_mission(waypoints):
        print("❌ Mission crosses NFZ")
        return

    # Execute
    print("🚀 Starting mission...")
    success = await drone.fly_mission(waypoints)

    if success:
        print("✅ Mission completed")
    else:
        print("❌ Mission aborted")

asyncio.run(main())
```

---

## References

- MAVSDK: https://mavsdk.io/docs
- MAVLink: https://mavlink.io/messages
- PX4 Commander: https://px4.io/community/code
