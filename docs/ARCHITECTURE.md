# AIS Platform Architecture

## System Overview

The AIS (Territorial Intelligence & Security Platform) is a multi-tier drone management system combining:

1. **Autopilot Layer** — PX4 SITL for flight control
2. **Communication Layer** — MAVLink protocol (UDP)
3. **Backend Layer** — Python API server with MAVSDK
4. **Frontend Layer** — Web-based GIS dashboard

---

## Layer 1: Autopilot (PX4 SITL)

### Components

- **PX4 Firmware** — Running in SITL mode (no hardware)
- **Gazebo Simulator** — 3D physics engine for drone motion
- **MAVLink Interface** — UDP socket (127.0.0.1:14540 by default)

### Flight Modes

| Mode | Description | Trigger |
|------|-------------|---------|
| MANUAL | Operator controls all axes | User command |
| ALTCTL | Altitude hold | User command |
| POSCTL | Position hold + altitude | User command |
| AUTO | Mission following | Mission upload |
| RTL | Return to Launch | Failsafe / User command |

### Failsafe Triggers

1. **Battery Low** (< 20%) → RTL
2. **Battery Critical** (< 5%) → Immediate land
3. **RC/Link Loss** (> 3s) → Hold position → RTL (after 30s)

---

## Layer 2: MAVLink Protocol

### Message Flow

```
Dashboard → Backend (Python) → PX4 SITL
   ↓            ↓                ↓
 JSON      MAVLink 2.0 (UDP)   Simulator
   ↓            ↓                ↓
WebSocket  127.0.0.1:14540    Gazebo Physics
```

### Key Messages

**Outbound (Dashboard → Autopilot):**
- `MAV_CMD_COMPONENT_ARM_DISARM` — Arm/Disarm motors
- `MAV_CMD_NAV_TAKEOFF` — Takeoff to altitude
- `MAV_CMD_NAV_LAND` — Land at current position
- `MAV_CMD_NAV_WAYPOINT` — Mission waypoint
- `MAV_CMD_DO_SET_MODE` — Change flight mode

**Inbound (Autopilot → Dashboard):**
- `HEARTBEAT` — Alive signal (1 Hz)
- `GLOBAL_POSITION_INT` — GPS + altitude (10 Hz)
- `ATTITUDE` — Roll/Pitch/Yaw (10 Hz)
- `VFR_HUD` — Speed + altitude (10 Hz)
- `BATTERY_STATUS` — Battery level (1 Hz)
- `STATUSTEXT` — Text messages (async)

---

## Layer 3: Backend (Python API)

### Dependencies

- **MAVSDK** — High-level drone API
- **pymavlink** — Low-level MAVLink protocol
- **Flask** — REST API framework
- **Flask-SocketIO** — Real-time telemetry streaming

### Key Components

#### autopilot/plane.py
```python
class Drone:
    def __init__(self, host: str = "127.0.0.1", port: int = 14540)
    def arm(self) → bool
    def disarm(self) → bool
    def takeoff(altitude: float) → bool
    def land(self) → bool
    def hold_position(self) → bool
    def fly_mission(waypoints: List[Tuple]) → bool
    def get_telemetry(self) → dict
```

#### autopilot/geofence.py
```python
class GeofenceValidator:
    def load_nfz_zones(filepath: str) → None
    def validate_mission(waypoints: List[Tuple]) → bool
    def check_point_in_nfz(lat, lon, alt) → bool
```

#### autopilot/failsafe.py
```python
class FailsafeMonitor:
    def check_battery(self) → None      # Triggers RTL if low
    def check_link_health(self) → None  # Detects connection loss
    def trigger_rtl(self) → None        # Forces RTL mode
```

---

## Layer 4: Frontend (Dashboard)

### Components

1. **GIS Map** — Leaflet.js map for visualization
2. **Mission Planner** — Click-to-waypoint interface
3. **Telemetry Panel** — Live drone status
4. **Mission Control** — Arm/Disarm/Takeoff buttons
5. **Video Stream** — Camera feed window

### Telemetry Update Cycle

```
Gazebo Physics (100 Hz)
    ↓
  PX4 SITL (10 Hz publish)
    ↓
  MAVLink → Python Backend (UDP listener)
    ↓
  WebSocket → Browser (GIS update)
    ↓
  Dashboard Map Refresh (5 Hz minimum)
```

---

## Data Flow Example: Mission Upload

### Sequence Diagram

```
Dashboard User          Backend Server          PX4 SITL
     │                       │                    │
     │─── Click waypoints ──→ │                    │
     │                       │                    │
     │                  NFZ Validation             │
     │                       │                    │
     │                  Create mission plan        │
     │                       │                    │
     │  ← Validation OK ──────│                    │
     │                       │                    │
     │─── Upload mission ────→ │                   │
     │                       │                    │
     │                       │─ MAV_CMD_NAV_* ───→ │
     │                       │                    │
     │                       │ ← Ack (HEARTBEAT) ─│
     │                       │                    │
     │ ← Mission Uploaded ────│                    │
     │                       │                    │
```

---

## Geofencing Implementation

### No-Fly Zone (NFZ) Validation

**Before Mission Upload:**
1. Parse GeoJSON NFZ zones from `config/nfz_zones.geojson`
2. For each waypoint-to-waypoint segment:
   - Check if line crosses any NFZ boundary
   - If YES: Reject mission → Notify dashboard
3. If all segments valid: Upload mission

**Runtime Monitoring:**
1. PX4 autopilot periodically reports position
2. Backend checks current position against NFZ
3. If breach detected:
   - Trigger `hold_position()` mode
   - Alert operator
   - Prevent further waypoint updates

### Implementation

```python
from shapely.geometry import Point, Polygon, LineString
import geojson

# Load zones
zones = geojson.load(open("config/nfz_zones.geojson"))

# Check if waypoint crosses NFZ
for zone in zones["features"]:
    poly = Polygon(zone["geometry"]["coordinates"][0])
    segment = LineString([waypoint1, waypoint2])
    if poly.intersects(segment):
        return False  # Mission invalid
```

---

## Failsafe Scenarios

### Scenario 1: Low Battery

```
Timeline:
T+240s → Battery reaches 20% threshold
       → Trigger RTL mode
       → Hold altitude 50m
       → Navigate to origin via GPS
       → Land at origin
       → Dashboard shows "Flight Complete"
```

### Scenario 2: Link Loss

```
Timeline:
T+0s   → Last MAVLink received
T+3s   → No heartbeat → PX4 triggers RTL
       → Hover at current altitude
T+30s  → Still no link → Auto-land (safety)
T+45s  → Landed, motors disarmed
```

---

## Performance Requirements

| Metric | Target | Method |
|--------|--------|--------|
| Telemetry latency | < 50 ms | MAVLink timestamp |
| GIS map update | 5 Hz | WebSocket broadcast |
| Geofence check | < 10 ms | Local calculation |
| Mission planning | < 200 ms | Backend processing |
| System uptime | 99.9% | Heartbeat monitoring |

---

## Testing Strategy

### Unit Tests
- Geofence polygon intersection
- Waypoint validation
- MAVLink message parsing

### Integration Tests
- Full mission upload → flight → landing
- NFZ breach detection
- Failsafe triggers

### System Tests (SITL)
- 4-point mission in Gazebo
- RTL recovery from failsafe
- GIS map synchronization

---

## References

- [PX4 Flight Stack](https://px4.io)
- [MAVLink Protocol](https://mavlink.io)
- [MAVSDK Documentation](https://mavsdk.io)
- [Gazebo Simulator](http://gazebosim.org)
