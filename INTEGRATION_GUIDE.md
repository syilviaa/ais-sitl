# Integration Guide: Veha 3 (Drone + Telemetry + Mission + Failsafe)

This branch integrates two complementary implementations:
- **Жанель's PX4 SITL Drone class** (`src/autopilot/plane.py`): Low-level flight control with state machine
- **Мерей's modular systems** (`src/telemetry.py`, `src/mission.py`, `src/failsafe.py`): High-level mission and health monitoring

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Application Layer (Your Code)                              │
│  - Mission planning & execution                             │
│  - Real-time monitoring                                     │
│  - Emergency response                                       │
└──────────────────────┬──────────────────────────────────────┘
                       │
        ┌──────────────┼──────────────┐
        │              │              │
    ┌───▼──────┐  ┌───▼──────┐  ┌───▼──────┐
    │ Telemetry│  │ Mission  │  │ Failsafe │
    │Collector │  │ Service  │  │ Monitor  │
    └───┬──────┘  └───┬──────┘  └───┬──────┘
        │              │              │
        └──────────────┼──────────────┘
                       │
                  ┌────▼─────┐
                  │  Drone   │
                  │  Class   │
                  │ (Жанель) │
                  └────┬─────┘
                       │
         ┌─────────────┼──────────────┐
         │             │              │
    ┌────▼────┐  ┌────▼────┐   ┌────▼────┐
    │ Geofence│  │ MAVSDK  │   │  PX4    │
    │Validator│  │ System  │   │  SITL   │
    └─────────┘  └─────────┘   └─────────┘
```

## Components

### 1. Core Flight Control (src/autopilot/plane.py)
**Жанель's implementation**: Complete drone control with MAVSDK

```python
from src.autopilot.plane import Drone, DroneState

drone = Drone(host="127.0.0.1", port=14540)
await drone.connect()
await drone.wait_until_ready()
await drone.arm()
await drone.takeoff(50.0)
```

**Key methods:**
- `connect()`, `disconnect()` - Connection lifecycle
- `arm()`, `disarm()` - Motor control
- `takeoff(altitude)`, `land()` - Flight control
- `hold_position()`, `return_to_launch(reason)` - Safety
- `fly_mission(waypoints)` - Autonomous missions
- `subscribe_telemetry(callback)` - 10 Hz updates

### 2. Telemetry Collection (src/telemetry.py)
**Мерей's modular system**: 10 Hz background polling

```python
from src.telemetry import TelemetryCollector
from src.models import TelemetrySnapshot

collector = TelemetryCollector(
    system=drone._system,  # Use drone's MAVSDK system
    rate_hz=10.0,
)
await collector.start()

# Get latest snapshot
snapshot: TelemetrySnapshot = collector.get_latest()
print(f"Battery: {snapshot.battery_percent}%")

# Or subscribe to updates
async def on_telemetry(snapshot):
    print(f"Alt: {snapshot.altitude_m}m")

collector.on_telemetry(on_telemetry)
```

**Key features:**
- Separate telemetry collection thread
- Full history tracking (configurable)
- Async/sync callback support
- Statistics tracking

### 3. Mission Management (src/mission.py)
**Мерей's modular system**: Waypoint-based flight planning

```python
from src.mission import MissionService
from src.models import Waypoint

service = MissionService(system=drone._system)

waypoints = [
    Waypoint(47.39, 8.54, 50.0),
    Waypoint(47.40, 8.55, 50.0),
    Waypoint(47.39, 8.54, 0.0),  # Return to start & land
]

await service.upload_mission(waypoints)
await service.start_mission()

# Monitor progress
while True:
    progress = service.get_progress()
    print(f"Waypoint {progress.current}/{progress.total}")
    if progress.is_mission_finished:
        break
    await asyncio.sleep(1.0)
```

**Key features:**
- Mission validation
- Real-time progress tracking
- Geofence integration
- Flexible waypoint definition

### 4. Failsafe Monitoring (src/failsafe.py)
**Мерей's modular system**: Emergency protection

```python
from src.failsafe import FailsafeMonitor
from src.models import FailsafeReason

monitor = FailsafeMonitor(
    drone=drone,
    telemetry_collector=collector,
    battery_warning_percent=20.0,
    battery_critical_percent=5.0,
    link_loss_timeout_sec=3.0,
)

async def on_failsafe(reason: FailsafeReason):
    print(f"🚨 FAILSAFE: {reason.value}")

monitor.on_failsafe(on_failsafe)
await monitor.start()
```

**Protection triggers:**
- Battery < 20%: RTL warning
- Battery < 5%: Critical landing
- No telemetry > 3s: Link loss RTL
- Geofence breach: Hold position

### 5. Geofencing (src/autopilot/geofence.py)
**Жанель's implementation**: No-Fly Zone validation

```python
from src.autopilot.geofence import GeofenceValidator

validator = GeofenceValidator()
validator.load_nfz_zones("config/nfz_zones.geojson")

# Validate missions before upload
is_valid = validator.validate_mission([
    (47.39, 8.54, 50),
    (47.40, 8.55, 50),
])

# Check single points at runtime
in_nfz = validator.check_point_in_nfz(47.39, 8.54, 50.0)
```

## Complete Example (Veha 3 Flight)

```python
import asyncio
from src.autopilot.plane import Drone
from src.telemetry import TelemetryCollector
from src.mission import MissionService
from src.failsafe import FailsafeMonitor
from src.models import Waypoint, FailsafeReason

async def main():
    # Initialize drone
    drone = Drone(host="127.0.0.1", port=14540)
    await drone.connect()
    await drone.wait_until_ready()
    
    # Start telemetry collection
    collector = TelemetryCollector(system=drone._system)
    await collector.start()
    
    # Start failsafe monitoring
    failsafe = FailsafeMonitor(
        drone=drone,
        telemetry_collector=collector,
    )
    
    async def on_failsafe_triggered(reason):
        print(f"⚠️ Failsafe: {reason.value}")
    
    failsafe.on_failsafe(on_failsafe_triggered)
    failsafe_task = asyncio.create_task(failsafe.start())
    
    # Plan and execute mission
    mission_service = MissionService(system=drone._system)
    waypoints = [
        Waypoint(47.39, 8.54, 50.0),  # Climb to 50m
        Waypoint(47.40, 8.55, 60.0),  # Climb to 60m and move
        Waypoint(47.39, 8.54, 0.0),   # Return and land
    ]
    
    await mission_service.upload_mission(waypoints)
    await mission_service.start_mission()
    
    # Monitor mission
    while True:
        progress = mission_service.get_progress()
        telemetry = collector.get_latest()
        
        print(f"Waypoint: {progress.current}/{progress.total}")
        print(f"Altitude: {telemetry.altitude_m:.1f}m")
        print(f"Battery: {telemetry.battery_percent:.1f}%")
        
        if progress.is_mission_finished:
            break
        
        await asyncio.sleep(1.0)
    
    # Cleanup
    await failsafe.stop()
    failsafe_task.cancel()
    await collector.stop()
    await drone.disconnect()
    
    print("✅ Mission complete")

if __name__ == "__main__":
    asyncio.run(main())
```

## Data Models (src/models.py)

All systems share data models from `src.models`:

- **TelemetrySnapshot**: Complete telemetry state (timestamp, position, velocity, attitude, battery, GPS, etc.)
- **Waypoint**: Mission waypoint with optional gimbal/camera control
- **MissionItem**: MAVSDK-compatible mission item
- **MissionProgress**: Current mission status
- **NoFlyZone**: Geofence zone definition
- **FailsafeReason**: Enumeration of emergency triggers
- **FailsafeEvent**: Logged failsafe incident

## Integration Points

### Drone → Telemetry
```python
# Option 1: Use drone's built-in telemetry (simpler, but less control)
await drone.subscribe_telemetry(my_callback)

# Option 2: Use TelemetryCollector for more control
collector = TelemetryCollector(system=drone._system)
```

### Drone → Mission
```python
# MissionService wraps MAVSDK directly
service = MissionService(system=drone._system)
# Then call drone.fly_mission() or use service directly
```

### Drone → Failsafe
```python
# FailsafeMonitor calls these drone methods:
await drone.hold_position()        # On emergency
await drone.return_to_launch(reason)  # For RTL
```

### Geofence Integration
Both the Drone class and MissionService validate missions:
```python
# Drone.fly_mission() validates internally
# MissionService doesn't validate (use GeofenceValidator separately)
```

## Testing

### Unit Tests
- `tests/test_plane.py` - Drone class (state machine, safety)
- `tests/test_telemetry.py` - TelemetryCollector (polling, history)
- `tests/test_mission.py` - MissionService (validation, progress)
- `tests/test_failsafe.py` - FailsafeMonitor (battery, link loss)
- `tests/test_geofence.py` - GeofenceValidator (NFZ detection)

### Running Tests
```bash
python3 -m pytest tests/ -v
python3 -m pytest tests/test_plane.py -v  # Specific test file
```

## Known Limitations

1. **MAVSDK Availability**: Some features require MAVSDK; in stub mode, telemetry is simulated
2. **Thread Safety**: TelemetryCollector uses asyncio, not thread-safe
3. **Mission Validation**: GeofenceValidator must be called separately from Drone.fly_mission()
4. **Real-time Performance**: 10 Hz telemetry may miss fast transients

## Future Work (Veha 4+)

- [ ] Web dashboard with real-time telemetry (WebSocket)
- [ ] REST API for mission upload/monitoring
- [ ] Advanced failsafe modes (geofence breach response)
- [ ] Multi-drone coordination
- [ ] Flight data recording and playback
- [ ] Autonomous geofence learning

## Questions?

See:
- `src/README_INTEGRATION.md` - Detailed system documentation
- `docs/API.md` - Complete API reference
- Test files for usage examples

---

**Status**: Veha 3 (July 22-25, 2026)  
**Contributors**: Жанель (Drone), Мерей (Telemetry/Mission/Failsafe)  
**Integration**: Claude Code
