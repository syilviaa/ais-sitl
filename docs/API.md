# API Reference

## Python SDK: Drone/Plane Class

### Connection & Initialization

```python
from src.autopilot.plane import Drone

# Connect to SITL autopilot
drone = Drone(host="127.0.0.1", port=14540)

# Check connection
if drone.is_connected():
    print("✅ Connected to PX4 SITL")
else:
    print("❌ Connection failed")
```

### Flight Control Methods

#### arm()
Arm (enable) motors — **must** be called before takeoff.

```python
success = await drone.arm()
if success:
    print("✅ Motors armed")
else:
    print("❌ Arm failed")
```

**MAVLink equivalent:**
```
→ MAV_CMD_COMPONENT_ARM_DISARM (400)
  param1=1.0 (arm), param2=0.0
← COMMAND_ACK with result code
```

---

#### disarm()
Disarm (disable) motors — stops all motor spin.

```python
success = await drone.disarm()
if success:
    print("✅ Motors disarmed")
```

---

#### takeoff(altitude: float)
Automatic takeoff to specified altitude.

```python
# Takeoff to 50 meters
success = await drone.takeoff(altitude=50.0)

# Blocks until:
# 1. Motors arm
# 2. UAV reaches target altitude
# 3. Stabilizes in hover
```

**Behavior:**
- Arm motors automatically
- Climb vertically to `altitude` (m)
- Hold position at altitude
- Returns `True` on success

**Pre-conditions:**
- No active failsafe
- Battery > 15%
- GPS lock (3+ satellites)

---

#### land()
Automatic landing at current location.

```python
success = await drone.land()

# Blocks until:
# 1. Drone descends to ground
# 2. Motors auto-disarm
# 3. Returns to idle state
```

---

#### hold_position()
Hover in place — stop all movement.

```python
await drone.hold_position()

# Used for:
# - Emergency hold during mission
# - Failsafe response to link loss
# - Operator intervention
```

---

#### fly_mission(waypoints: List[Tuple[float, float, float]])
Execute autonomous mission following waypoints.

```python
# Define mission: (latitude, longitude, altitude_m)
waypoints = [
    (47.39770, 8.54550, 50.0),   # Waypoint 1
    (47.39900, 8.55000, 60.0),   # Waypoint 2
    (47.40100, 8.54500, 50.0),   # Waypoint 3
    (47.39770, 8.54550, 0.0),    # Return to origin & land
]

# Validate mission before upload
is_valid = await drone.validate_mission(waypoints)
if not is_valid:
    print("❌ Mission crosses No-Fly Zone")
    return

# Execute mission
success = await drone.fly_mission(waypoints)

if success:
    print("✅ Mission completed successfully")
else:
    print("❌ Mission aborted")
```

**Behavior:**
1. Auto-arm if not already armed
2. Auto-takeoff to first waypoint altitude
3. Navigate to each waypoint (auto-yaw to next)
4. Maintain speed & altitude constraints
5. Land at final waypoint (if altitude=0)
6. Auto-disarm

**Parameters:**
- `speed` — cruise speed (default: 5 m/s)
- `acceptance_radius` — waypoint arrival radius (default: 5 m)

**Exceptions:**
- `MissionValidationError` — crosses NFZ
- `ConnectionError` — link lost during mission
- `BatteryLowError` — triggers RTL before mission completion

---

### Telemetry & Status

#### get_telemetry()
Fetch current drone status (non-blocking, snapshot).

```python
telemetry = await drone.get_telemetry()

print(f"Position: {telemetry['lat']}, {telemetry['lon']}, {telemetry['alt']}")
print(f"Velocity: {telemetry['vx']}, {telemetry['vy']}, {telemetry['vz']}")
print(f"Attitude: Pitch={telemetry['pitch']}, Roll={telemetry['roll']}, Yaw={telemetry['yaw']}")
print(f"Battery: {telemetry['battery']}%")
print(f"Mode: {telemetry['mode']}")
print(f"Armed: {telemetry['armed']}")
```

**Returns Dict:**
```python
{
    "timestamp": 1689603600.123,     # Unix timestamp (seconds)
    "lat": 47.39770,                 # Latitude (degrees)
    "lon": 8.54550,                  # Longitude (degrees)
    "alt": 50.2,                     # Altitude AGL (meters)
    "vx": 5.1, "vy": 0.3, "vz": -0.1,  # Velocities (m/s)
    "pitch": 2.1,                    # Pitch (degrees)
    "roll": -0.5,                    # Roll (degrees)
    "yaw": 142.3,                    # Yaw (degrees)
    "battery": 78.5,                 # Battery charge (%)
    "rssi": -45,                     # Signal strength (dBm)
    "armed": true,                   # Armed state (bool)
    "mode": "AUTO",                  # Flight mode (str)
    "gps_status": "3D",              # GPS fix type
    "satellites": 12,                # Visible satellites
}
```

---

#### subscribe_telemetry(callback: Callable)
Stream telemetry at 10 Hz (event-based).

```python
async def telemetry_callback(data):
    print(f"Altitude: {data['alt']} m")
    print(f"Battery: {data['battery']}%")

# Subscribe to telemetry stream
await drone.subscribe_telemetry(telemetry_callback)

# Stream runs in background until unsubscribe
await drone.unsubscribe_telemetry()
```

---

#### get_mission_progress()
Get current mission execution progress.

```python
progress = await drone.get_mission_progress()

print(f"Current waypoint: {progress['current']}/{progress['total']}")
print(f"Distance to next: {progress['distance_to_next']} m")
print(f"Time to completion: {progress['eta']} seconds")
```

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
