# Veha 5 Testing Guide

Complete testing procedures for all 5 phases of the AIS SITL multi-drone platform.

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Unit Testing](#unit-testing)
3. [Integration Testing](#integration-testing)
4. [Manual Testing with cURL](#manual-testing-with-curl)
5. [Full System Testing with Docker](#full-system-testing-with-docker)
6. [Phase-Specific Testing](#phase-specific-testing)
7. [Performance & Load Testing](#performance--load-testing)
8. [Troubleshooting](#troubleshooting)

---

## Quick Start

### Prerequisites

```bash
# Install Python 3.11+
python3 --version

# Install dependencies
pip3 install -r requirements.txt

# Verify pytest
python3 -m pytest --version
```

### Run All Tests (30 seconds)

```bash
# Run full test suite
python3 -m pytest tests/ -v

# Run with coverage report
python3 -m pytest tests/ --cov=src --cov-report=html
```

### Expected Output

```
tests/test_fleet_service.py::TestFleetServiceBasics::test_add_drone PASSED
tests/test_fleet_api.py::TestFleetAddDrone::test_add_drone_success PASSED
tests/test_recording_service.py::TestMissionRecorderBasics::test_start_recording PASSED
tests/test_geofence_service.py::TestGeofenceMonitor::test_altitude_below_minimum PASSED
tests/test_metrics_service.py::TestMetricsFleet::test_update_fleet_metrics PASSED

======================== 154 passed in 8.23s ========================
```

---

## Unit Testing

Test individual services in isolation without database or HTTP.

### Phase 2: Fleet Service

```bash
# Run fleet service tests
python3 -m pytest tests/test_fleet_service.py -v

# Specific test
python3 -m pytest tests/test_fleet_service.py::TestFleetServiceBasics::test_add_drone -v

# With output
python3 -m pytest tests/test_fleet_service.py -v -s
```

**What's Tested:**
- ✅ Adding drones to fleet
- ✅ Removing drones from fleet
- ✅ Fleet status aggregation
- ✅ Airspace conflict detection
- ✅ Coordinated takeoff
- ✅ Broadcast commands
- ✅ Emergency stop

### Phase 3: Recording Service

```bash
# Run mission recorder tests
python3 -m pytest tests/test_mission_recorder.py -v

# Run recording service tests
python3 -m pytest tests/test_recording_service.py -v --tb=short

# All recording tests
python3 -m pytest tests/test_recording*.py -v
```

**What's Tested:**
- ✅ Telemetry snapshot creation
- ✅ Recording start/stop
- ✅ Snapshot addition during recording
- ✅ Duration calculation
- ✅ Distance calculation (Haversine)
- ✅ Max altitude tracking
- ✅ Battery range tracking
- ✅ Compression/decompression
- ✅ Playback timeline generation

### Phase 4: Geofence Service

```bash
# Run geofence monitor tests
python3 -m pytest tests/test_geofence_service.py::TestGeofenceMonitor -v

# Run geofence service tests
python3 -m pytest tests/test_geofence_service.py::TestGeofenceServiceCRUD -v

# Test polygon detection
python3 -m pytest tests/test_geofence_service.py::TestGeofenceMonitor::test_point_in_polygon_inside -v
```

**What's Tested:**
- ✅ Altitude violations (below/above)
- ✅ Boundary violations (point-in-polygon)
- ✅ Zone CRUD operations
- ✅ Mission validation
- ✅ Position checking
- ✅ Violation tracking

### Phase 5: Metrics Service

```bash
# Run metrics tests
python3 -m pytest tests/test_metrics_service.py -v

# Test Prometheus export
python3 -m pytest tests/test_metrics_service.py::TestMetricsExport -v
```

**What's Tested:**
- ✅ Fleet metric updates
- ✅ Mission metric tracking
- ✅ Telemetry metrics
- ✅ Geofence metrics
- ✅ Success rate calculation
- ✅ Prometheus format export
- ✅ JSON summary generation

---

## Integration Testing

Test REST API endpoints with mocked services.

### Phase 2: Fleet API

```bash
# Run fleet API tests
python3 -m pytest tests/test_fleet_api.py -v

# Test add drone endpoint
python3 -m pytest tests/test_fleet_api.py::TestFleetAddDrone -v

# Test status endpoint
python3 -m pytest tests/test_fleet_api.py::TestFleetStatus -v
```

### Phase 3: Recording API

```bash
# Run recording API tests
python3 -m pytest tests/test_recording_api.py -v

# Test recording lifecycle
python3 -m pytest tests/test_recording_api.py::TestRecordingStart -v
python3 -m pytest tests/test_recording_api.py::TestRecordingStop -v
python3 -m pytest tests/test_recording_api.py::TestRecordingPlayback -v
```

### Phase 4: Geofence API

```bash
# Run geofence API tests
python3 -m pytest tests/test_geofence_api.py -v

# Test zone management
python3 -m pytest tests/test_geofence_api.py::TestGeofenceCreate -v
python3 -m pytest tests/test_geofence_api.py::TestGeofenceUpdate -v

# Test validation
python3 -m pytest tests/test_geofence_api.py::TestGeofenceMissionValidation -v
```

### Phase 5: Metrics API

```bash
# Run metrics API tests
python3 -m pytest tests/test_metrics_api.py -v

# Test Prometheus export
python3 -m pytest tests/test_metrics_api.py::TestMetricsPrometheus -v

# Test JSON summary
python3 -m pytest tests/test_metrics_api.py::TestMetricsSummary -v
```

---

## Manual Testing with cURL

Test endpoints manually against a running backend.

### Prerequisites

```bash
# Terminal 1: Start backend
cd ais-sitl-platform
python3 run_backend.py

# Terminal 2: Run cURL commands
```

### Phase 2: Fleet Management

```bash
# 1. Add drone
curl -X POST http://127.0.0.1:5000/api/fleet/add-drone \
  -H "Content-Type: application/json" \
  -d '{
    "name": "drone1",
    "host": "127.0.0.1",
    "port": 14540
  }'

# Expected: {"success": true, "name": "drone1", ...}

# 2. List fleet status
curl http://127.0.0.1:5000/api/fleet/status

# Expected: {"success": true, "fleet_size": 1, "drones": {...}}

# 3. Check conflicts
curl http://127.0.0.1:5000/api/fleet/conflicts

# Expected: {"success": true, "conflict_count": 0, "conflicts": {}}

# 4. Broadcast command (arm all)
curl -X POST http://127.0.0.1:5000/api/fleet/broadcast \
  -H "Content-Type: application/json" \
  -d '{"command": "arm"}'

# 5. Remove drone
curl -X DELETE http://127.0.0.1:5000/api/fleet/remove-drone/drone1
```

### Phase 3: Mission Recording

```bash
# 1. Start recording
curl -X POST http://127.0.0.1:5000/api/recording/start/mission-001

# Expected: {"success": true, "message": "Recording started..."}

# 2. Simulate telemetry (in Python)
import requests
for i in range(10):
    requests.post('http://127.0.0.1:5000/api/recording/update/mission-001', json={
        'lat': 47.35 + i*0.001,
        'lon': 8.55 + i*0.001,
        'altitude': 50 + i,
        'battery': 100 - i*2
    })

# 3. Stop recording
curl -X POST http://127.0.0.1:5000/api/recording/stop/mission-001

# 4. Get recording details
curl http://127.0.0.1:5000/api/recording/get/mission-001

# 5. List all recordings
curl http://127.0.0.1:5000/api/recording/list

# 6. Get playback timeline
curl "http://127.0.0.1:5000/api/recording/playback/mission-001?speed=1.0"
```

### Phase 4: Geofence Management

```bash
# 1. Create zone
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

# 2. List zones
curl http://127.0.0.1:5000/api/geofence/list

# 3. Validate mission waypoints
curl -X POST http://127.0.0.1:5000/api/geofence/validate-mission \
  -H "Content-Type: application/json" \
  -d '{
    "waypoints": [
      {"lat": 47.35, "lon": 8.55, "altitude": 50.0},
      {"lat": 47.36, "lon": 8.56, "altitude": 75.0}
    ]
  }'

# Expected: {"valid": true, "violation_count": 0}

# 4. Check position
curl -X POST http://127.0.0.1:5000/api/geofence/check-position \
  -H "Content-Type: application/json" \
  -d '{
    "drone_id": "drone1",
    "position": {"lat": 47.3509, "lon": 8.5509, "altitude": 48.5}
  }'

# 5. Get violation history
curl http://127.0.0.1:5000/api/geofence/violations/airfield
```

### Phase 5: Metrics & Monitoring

```bash
# 1. Export Prometheus metrics
curl http://127.0.0.1:5000/metrics

# Expected: Prometheus format with metrics

# 2. Get JSON summary
curl http://127.0.0.1:5000/api/metrics/summary | jq '.metrics'

# 3. Manually update metrics
curl -X POST http://127.0.0.1:5000/api/metrics/update

# 4. Check specific metrics
curl http://127.0.0.1:5000/api/metrics/summary | jq '.metrics.fleet'
curl http://127.0.0.1:5000/api/metrics/summary | jq '.metrics.missions'
```

---

## Full System Testing with Docker

Test all services together in isolated containers.

### Prerequisites

```bash
# Build images
docker-compose build

# Start all services
docker-compose up -d

# Verify services
docker-compose ps

# Expected: All services in "Up" state
```

### Health Checks

```bash
# Backend health
curl http://localhost:5000/api/health

# Expected: {"status": "ok", "version": "0.1.0", "drone_connected": false}

# Frontend (Vue.js)
curl http://localhost:3000

# Prometheus health
curl http://localhost:9090/-/healthy

# Grafana health
curl http://localhost:3001/api/health

# PostgreSQL
docker exec ais_sitl_db pg_isready

# Redis
docker exec ais_sitl_cache redis-cli ping
```

### Full Workflow Test

```bash
# 1. Check backend is healthy
curl http://127.0.0.1:5000/api/health

# 2. Add drone to fleet
curl -X POST http://127.0.0.1:5000/api/fleet/add-drone \
  -H "Content-Type: application/json" \
  -d '{"name": "drone1", "host": "127.0.0.1", "port": 14540}'

# 3. Create geofence zone
curl -X POST http://127.0.0.1:5000/api/geofence/create \
  -H "Content-Type: application/json" \
  -d '{
    "name": "zone1",
    "polygon": {"type": "Polygon", "coordinates": [[[8.5, 47.3], [8.6, 47.3], [8.6, 47.4], [8.5, 47.4], [8.5, 47.3]]]},
    "altitude_min": 0, "altitude_max": 100
  }'

# 4. Start recording
curl -X POST http://127.0.0.1:5000/api/recording/start/test-mission-1

# 5. Check fleet status
curl http://127.0.0.1:5000/api/fleet/status

# 6. Stop recording
curl -X POST http://127.0.0.1:5000/api/recording/stop/test-mission-1

# 7. Get metrics
curl http://127.0.0.1:5000/api/metrics/summary | jq

# 8. View in Grafana
# http://localhost:3001 (admin/admin)
```

### Docker Debugging

```bash
# View backend logs
docker-compose logs -f backend

# View PostgreSQL logs
docker-compose logs -f postgres

# Execute command in container
docker exec ais_sitl_backend python3 -c "import requests; print(requests.get('http://localhost:5000/api/health').json())"

# Stop all services
docker-compose down

# Clean up volumes
docker-compose down -v
```

---

## Phase-Specific Testing

### Phase 2: Fleet Management Testing

**Test Scenario 1: Multi-Drone Registration**

```python
# test_fleet_workflow.py
import asyncio
from src.backend.services.fleet_service import FleetService

async def test_multi_drone_workflow():
    service = FleetService()
    
    # Register 3 drones
    for i in range(1, 4):
        result = await service.add_drone(
            f"drone{i}",
            "127.0.0.1",
            14540 + i
        )
        assert result["success"] is True
        print(f"✅ Registered drone{i}")
    
    # Check fleet size
    size = service.get_fleet_size()
    assert size == 3
    print(f"✅ Fleet size: {size}")
    
    # Get fleet status
    status = await service.get_fleet_status()
    assert status["fleet_size"] == 3
    print(f"✅ Fleet status retrieved")

# Run: python3 -c "import asyncio; from test_fleet_workflow import test_multi_drone_workflow; asyncio.run(test_multi_drone_workflow())"
```

**Test Scenario 2: Conflict Detection**

```python
async def test_conflict_detection():
    service = FleetService()
    
    # Manually set positions that would conflict
    # (In real scenario, positions come from telemetry)
    
    # Check conflicts
    conflicts = await service.check_conflicts()
    print(f"Conflicts: {conflicts}")
```

### Phase 3: Recording Testing

**Test Scenario: Record and Playback**

```python
# test_recording_workflow.py
import asyncio
from src.backend.services.mission_recorder import MissionRecorder, TelemetrySnapshot

async def test_record_and_playback():
    recorder = MissionRecorder("mission-001")
    
    # Start recording
    await recorder.start()
    print("✅ Recording started")
    
    # Add telemetry snapshots
    positions = [
        (47.35, 8.55, 50.0),
        (47.36, 8.56, 60.0),
        (47.37, 8.57, 55.0),
    ]
    
    for i, (lat, lon, alt) in enumerate(positions):
        snapshot = TelemetrySnapshot(
            timestamp=1721938284.0 + i,
            lat=lat,
            lon=lon,
            altitude=alt,
            battery=100 - i*5,
        )
        await recorder.add_snapshot(snapshot)
    
    # Stop recording
    await recorder.stop()
    print("✅ Recording stopped")
    
    # Get statistics
    stats = recorder.get_statistics()
    print(f"✅ Stats: {stats}")
    
    # Generate playback timeline
    timeline = recorder.playback_timeline(playback_speed=2.0)
    print(f"✅ Playback timeline: {len(timeline)} frames at 2x speed")
```

### Phase 4: Geofence Testing

**Test Scenario: Geofence Validation**

```python
# test_geofence_workflow.py
import asyncio
from src.backend.services.geofence_service import GeofenceService

async def test_geofence_workflow():
    service = GeofenceService()
    
    # Create zone
    result = await service.create_zone(
        "test_zone",
        {
            "type": "Polygon",
            "coordinates": [[[8.5, 47.3], [8.6, 47.3], [8.6, 47.4], [8.5, 47.4], [8.5, 47.3]]]
        },
        altitude_min=0.0,
        altitude_max=100.0
    )
    assert result["success"] is True
    print("✅ Zone created")
    
    # Validate mission - valid waypoints
    valid_mission = await service.validate_mission([
        {"lat": 47.35, "lon": 8.55, "altitude": 50.0},
        {"lat": 47.36, "lon": 8.56, "altitude": 60.0},
    ])
    assert valid_mission["valid"] is True
    print("✅ Valid mission passed")
    
    # Validate mission - altitude violation
    invalid_mission = await service.validate_mission([
        {"lat": 47.35, "lon": 8.55, "altitude": 150.0},  # Above max
    ])
    assert invalid_mission["valid"] is False
    print(f"✅ Invalid mission detected: {invalid_mission['violations']}")
```

### Phase 5: Metrics Testing

**Test Scenario: Metrics Collection**

```python
# test_metrics_workflow.py
from src.backend.services.metrics_service import MetricsService

def test_metrics_workflow():
    service = MetricsService()
    
    # Update fleet metrics
    service.update_fleet_metrics({
        "drones": {
            "drone1": {"connected": True, "battery_percent": 85.0},
            "drone2": {"connected": True, "battery_percent": 90.0},
        }
    })
    print("✅ Fleet metrics updated")
    
    # Record missions
    service.record_mission_completion(duration_seconds=60.0, distance_meters=500.0, success=True)
    service.record_mission_completion(duration_seconds=30.0, distance_meters=250.0, success=False)
    print("✅ Mission metrics recorded")
    
    # Get summary
    summary = service.get_metrics_summary()
    print(f"Success rate: {summary['missions']['success_rate_percent']}%")
    
    # Export Prometheus format
    prometheus = service.get_prometheus_metrics()
    assert "ais_sitl_fleet_size_total" in prometheus
    print("✅ Prometheus metrics exported")
```

---

## Performance & Load Testing

### Benchmark Fleet Size

```bash
# Test with 5 drones
python3 -c "
import asyncio
import time
from src.backend.services.fleet_service import FleetService

async def benchmark():
    service = FleetService()
    
    # Add 5 drones
    start = time.time()
    for i in range(5):
        await service.add_drone(f'drone{i}', '127.0.0.1', 14540+i)
    elapsed = time.time() - start
    print(f'Added 5 drones in {elapsed:.3f}s')
    
    # Get fleet status
    start = time.time()
    for _ in range(100):
        await service.get_fleet_status()
    elapsed = time.time() - start
    print(f'Fleet status queries: {elapsed:.3f}s (100x)')
    
    # Check conflicts
    start = time.time()
    for _ in range(100):
        await service.check_conflicts()
    elapsed = time.time() - start
    print(f'Conflict checks: {elapsed:.3f}s (100x)')

asyncio.run(benchmark())
"
```

### Load Test Telemetry Recording

```bash
# Simulate 1000 telemetry snapshots
python3 -c "
import asyncio
import time
from src.backend.services.mission_recorder import MissionRecorder, TelemetrySnapshot

async def load_test():
    recorder = MissionRecorder('test')
    await recorder.start()
    
    start = time.time()
    for i in range(1000):
        snapshot = TelemetrySnapshot(
            timestamp=1721938284.0 + i/10,
            lat=47.35 + (i % 100) * 0.0001,
            lon=8.55 + (i % 100) * 0.0001,
            altitude=50 + (i % 50),
            battery=100 - (i % 100),
        )
        await recorder.add_snapshot(snapshot)
    
    await recorder.stop()
    elapsed = time.time() - start
    
    print(f'Recorded 1000 snapshots in {elapsed:.3f}s')
    print(f'Rate: {1000/elapsed:.0f} snapshots/sec')
    
    stats = recorder.get_statistics()
    print(f'Statistics: {stats}')

asyncio.run(load_test())
"
```

---

## Troubleshooting

### Test Failures

**pytest: module not found**
```bash
# Solution: Install in development mode
pip3 install -e .
pip3 install -r requirements.txt
```

**ImportError: No module named 'src'**
```bash
# Solution: Run from repository root
cd ais-sitl-platform
python3 -m pytest tests/
```

**async test failures**
```bash
# Add pytest.ini
[pytest]
asyncio_mode = auto

# Or use: pytest tests/ --asyncio-mode=auto
```

**Database connection errors in tests**
```bash
# Use SQLite for tests:
# In conftest.py:
@pytest.fixture
def app():
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    return app
```

### Backend Issues

**Port 5000 already in use**
```bash
# Kill process on port 5000
lsof -ti:5000 | xargs kill -9

# Or use different port
python3 run_backend.py --port 5001
```

**PostgreSQL connection refused**
```bash
# Start PostgreSQL
docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=postgres postgres:15

# Or use SQLite for testing
export DATABASE_URL="sqlite:///test.db"
```

**Redis connection refused**
```bash
# Start Redis
docker run -d -p 6379:6379 redis:7

# Or disable Redis caching for tests
app.config['REDIS_URL'] = None
```

### Docker Issues

**Container won't start**
```bash
# Check logs
docker-compose logs backend

# Rebuild
docker-compose build --no-cache

# Start fresh
docker-compose down -v
docker-compose up
```

**Services can't communicate**
```bash
# Check network
docker network ls

# Verify DNS
docker exec ais_sitl_backend ping postgres

# Use container name, not localhost
DATABASE_URL=postgresql://user:pass@postgres:5432/db
```

---

## Test Checklist

### Before Deploying

- [ ] All unit tests pass (`pytest tests/ -v`)
- [ ] Coverage >80% (`pytest --cov=src`)
- [ ] No linting errors (`flake8 src/`)
- [ ] All integration tests pass
- [ ] Docker build succeeds (`docker-compose build`)
- [ ] All services start (`docker-compose up -d`)
- [ ] Health checks pass
- [ ] Manual cURL tests work
- [ ] Grafana dashboards display data
- [ ] No database migrations pending

### Regression Testing

- [ ] Veha 4 endpoints still work (drone, mission, telemetry, failsafe)
- [ ] WebSocket telemetry streaming works
- [ ] Vue.js frontend loads
- [ ] Geofence validation doesn't break missions
- [ ] Metrics export doesn't impact performance

---

## Continuous Integration

Example GitHub Actions workflow:

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: postgres
      redis:
        image: redis:7

    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.11'
      
      - run: pip install -r requirements.txt
      - run: pytest tests/ --cov=src
```

---

**Last Updated:** 2026-07-25  
**Test Suite:** 154+ test cases  
**Coverage:** >85%  
**Avg Runtime:** 8-10 seconds
