# Veha 5: Multi-Drone & Production Ready

**Milestone**: July 28-August 4, 2026  
**Status**: Planning & Implementation  
**Focus**: Multi-drone coordination, persistence, monitoring, deployment

---

## 🎯 Objectives

### Primary Goals
1. **Multi-Drone Support** - Manage multiple drones simultaneously
2. **Data Persistence** - Store flights, missions, telemetry in database
3. **Production Deployment** - Docker-compose full stack
4. **Monitoring & Observability** - Prometheus metrics, health dashboards
5. **Advanced Failsafe** - Geofence breach, interference detection
6. **Performance** - Load testing, optimization, benchmarks

### Success Criteria
- [ ] Support 5+ concurrent drones
- [ ] All flight data persisted to database
- [ ] Production docker-compose deployment
- [ ] Prometheus metrics for all systems
- [ ] Advanced geofence visualization on map
- [ ] Mission recording with playback
- [ ] <100ms p99 latency under load
- [ ] Automatic failsafe on geofence breach

---

## 🏗️ Architecture Changes

### Database Layer (SQLAlchemy + PostgreSQL)

```python
# Models to implement:
- Drone (id, name, host, port, status, battery, location)
- Mission (id, drone_id, waypoints, status, created_at, completed_at)
- TelemetryRecord (timestamp, drone_id, lat, lon, alt, battery, ...)
- FailsafeEvent (timestamp, drone_id, reason, action_taken)
- NoFlyZone (name, polygon, altitude_min, altitude_max, active)
- User (username, email, permissions, created_at)
```

### Multi-Drone Service Layer

```python
class DroneManager:
    """Manages multiple drone instances."""
    
    def __init__(self):
        self.drones: Dict[str, DroneService] = {}
    
    async def add_drone(self, drone_id: str, host: str, port: int)
    async def remove_drone(self, drone_id: str)
    async def get_drone(self, drone_id: str)
    async def list_drones(self) -> List[DroneStatus]
    async def broadcast_command(self, command: str, data: dict)
```

### Updated REST API

```
# Drone endpoints now require drone_id
POST   /api/drones                      - List all drones
POST   /api/drones/{drone_id}/arm       - Arm specific drone
GET    /api/drones/{drone_id}/status    - Get drone status

# Missions per drone
POST   /api/drones/{drone_id}/missions/upload
GET    /api/drones/{drone_id}/missions/progress
POST   /api/drones/{drone_id}/missions/records  - Get flight records

# Global coordination
GET    /api/coordination/status         - All drones status
POST   /api/coordination/emergency      - Emergency stop all
GET    /api/coordination/geofences      - All NFZ zones
```

---

## 💾 Database Schema

### PostgreSQL Tables

```sql
-- Drones registry
CREATE TABLE drones (
    id UUID PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    host VARCHAR(255),
    port INTEGER,
    status VARCHAR(20),  -- connected/disconnected/error
    battery_percent FLOAT,
    last_heartbeat TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Missions
CREATE TABLE missions (
    id UUID PRIMARY KEY,
    drone_id UUID REFERENCES drones(id),
    waypoints JSONB,  -- Array of waypoints
    status VARCHAR(20),  -- planned/uploaded/running/completed/aborted
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Telemetry records (time-series)
CREATE TABLE telemetry_records (
    timestamp TIMESTAMP NOT NULL,
    drone_id UUID NOT NULL REFERENCES drones(id),
    lat FLOAT,
    lon FLOAT,
    altitude FLOAT,
    vx FLOAT, vy FLOAT, vz FLOAT,
    battery_percent FLOAT,
    satellites INTEGER,
    flight_mode VARCHAR(20),
    armed BOOLEAN,
    PRIMARY KEY (drone_id, timestamp)
) PARTITION BY RANGE (timestamp);

-- Failsafe events
CREATE TABLE failsafe_events (
    id UUID PRIMARY KEY,
    drone_id UUID REFERENCES drones(id),
    timestamp TIMESTAMP,
    reason VARCHAR(50),  -- battery_low, link_loss, geofence_breach, etc
    action_taken VARCHAR(100),
    battery_percent FLOAT,
    altitude FLOAT
);

-- No-Fly Zones
CREATE TABLE noflyZones (
    id UUID PRIMARY KEY,
    name VARCHAR(255),
    polygon GEOMETRY,  -- PostGIS polygon
    altitude_min FLOAT,
    altitude_max FLOAT,
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP
);

-- Mission recordings (for playback)
CREATE TABLE mission_recordings (
    id UUID PRIMARY KEY,
    mission_id UUID REFERENCES missions(id),
    telemetry_data JSONB,  -- Compressed telemetry
    duration_seconds FLOAT,
    distance_meters FLOAT,
    max_altitude FLOAT,
    battery_start FLOAT,
    battery_end FLOAT,
    created_at TIMESTAMP
);
```

---

## 📡 Multi-Drone Coordination

### Drone Manager Pattern

```python
# Single source of truth for all drones
class DroneCoordinator:
    def __init__(self, db_session):
        self.db = db_session
        self.drones = {}
        self.locks = {}  # Per-drone locking
    
    async def initialize_fleet(self):
        """Load all drones from database."""
        drones = await self.db.query(Drone).all()
        for drone_config in drones:
            await self.add_drone(drone_config)
    
    async def add_drone(self, config):
        """Add new drone to fleet."""
        service = DroneService()
        await service.initialize(config.host, config.port)
        self.drones[config.id] = service
    
    async def execute_coordinated_mission(self, mission_plan):
        """
        Execute mission across multiple drones.
        mission_plan: {
            'drones': ['drone1', 'drone2', 'drone3'],
            'start_delay': 5.0,  # Seconds between starts
            'sync_points': [
                {'waypoint_index': 5, 'drones': ['drone1', 'drone2']},
            ]
        }
        """
        # Implementation
```

### Conflict Resolution

```python
# Prevent two drones from occupying same space
class AirspaceManager:
    async def reserve_airspace(self, drone_id, lat, lon, radius_m, duration_s):
        """Reserve cylindrical airspace."""
        
    async def check_conflict(self, drone_id, lat, lon, alt):
        """Check if position conflicts with other drone routes."""
        
    async def get_avoidance_waypoint(self, drone_id, current_pos, target_pos):
        """Calculate alternate waypoint to avoid collision."""
```

---

## 🎬 Mission Recording & Playback

### Mission Recorder

```python
class MissionRecorder:
    """Records telemetry and mission events for playback."""
    
    async def start_recording(self, mission_id: str):
        self.recording_buffer = deque(maxlen=100)  # Memory-efficient
    
    async def on_telemetry(self, snapshot):
        self.recording_buffer.append({
            'timestamp': snapshot.timestamp,
            'lat': snapshot.lat,
            'lon': snapshot.lon,
            'alt': snapshot.altitude_m,
            'battery': snapshot.battery_percent,
        })
    
    async def save_recording(self, mission_id: str):
        """Compress and save to database."""
        compressed = gzip.compress(json.dumps(self.recording_buffer).encode())
        await db.create_mission_recording(
            mission_id=mission_id,
            telemetry_data=compressed,
            duration=calculated_duration,
        )
```

### Mission Playback API

```
GET    /api/missions/{mission_id}/recording        - Get recorded flight
GET    /api/missions/{mission_id}/playback?speed=1.5  - Stream playback
POST   /api/missions/{mission_id}/replay           - Re-fly same mission
```

---

## 🔴 Advanced Failsafe Scenarios

### Geofence Breach Handler

```python
class GeofenceFailsafe:
    """Advanced geofence breach response."""
    
    async def on_geofence_breach(self, drone_id, position, nfz):
        """
        Response levels:
        1. HOLD - Stop and hover
        2. RTL - Return to launch
        3. DIVERT - Fly to safe waypoint
        4. LAND - Emergency land
        """
        threat_level = self.assess_threat(position, nfz)
        
        if threat_level == "CRITICAL":
            # Emergency land immediately
            await self.drone.land()
        elif threat_level == "SEVERE":
            # Return to launch
            await self.drone.return_to_launch()
        elif threat_level == "MODERATE":
            # Divert to safe waypoint
            safe_point = await self.airspace_manager.get_safe_waypoint()
            await self.drone.fly_to(safe_point)
        else:
            # Just hold
            await self.drone.hold_position()
```

### Interference Detection

```python
class InterferenceDetector:
    """Detect signal loss, RF interference, GPS jamming."""
    
    async def check_signal_health(self, telemetry):
        # Monitor RSSI, GPS accuracy degradation
        
    async def on_interference(self, drone_id, type: str):
        # GPS_JAMMING, LINK_INTERFERENCE, SIGNAL_LOSS
        # Trigger alternative control method or RTL
```

---

## 📊 Monitoring & Observability

### Prometheus Metrics

```python
# Metrics to expose:
- drone_battery_percent (gauge per drone)
- drone_altitude_meters (gauge per drone)
- drone_connection_status (gauge)
- mission_duration_seconds (histogram)
- failsafe_events_total (counter)
- api_request_duration (histogram)
- database_query_time (histogram)
- websocket_clients_connected (gauge)
```

### Health Dashboard

```
GET    /api/health/system                - Overall system health
GET    /api/health/drones               - Per-drone health
GET    /api/health/database             - DB connection pool
GET    /api/metrics                     - Prometheus format
```

---

## 🐳 Docker Deployment

### docker-compose.yml

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: ais_sitl
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    # Caching & telemetry buffering

  backend:
    build: .
    environment:
      DATABASE_URL: postgresql://postgres:${DB_PASSWORD}@postgres/ais_sitl
      REDIS_URL: redis://redis:6379
    ports:
      - "5000:5000"
    depends_on:
      - postgres
      - redis

  frontend:
    build: web/
    ports:
      - "3000:3000"
    depends_on:
      - backend

  prometheus:
    image: prom/prometheus
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    ports:
      - "9090:9090"

  grafana:
    image: grafana/grafana
    ports:
      - "3001:3000"
    depends_on:
      - prometheus
    volumes:
      - grafana_data:/var/lib/grafana

volumes:
  postgres_data:
  prometheus_data:
  grafana_data:
```

### One-Command Deployment

```bash
docker-compose up --build
# Everything available at localhost:
# - Backend API: :5000
# - Frontend Dashboard: :3000
# - Prometheus: :9090
# - Grafana: :3001
```

---

## 🎯 Implementation Phases

### Phase 1: Database & Multi-Drone (Days 1-2)
- [ ] Set up PostgreSQL with schema
- [ ] Implement SQLAlchemy ORM models
- [ ] Create DroneManager/DroneCoordinator
- [ ] Update REST API for multi-drone
- [ ] Database migration scripts

### Phase 2: Recording & Playback (Days 2-3)
- [ ] Implement MissionRecorder
- [ ] Playback endpoints & UI
- [ ] Telemetry compression/decompression
- [ ] Mission replay functionality
- [ ] Frontend: Recording viewer

### Phase 3: Advanced Failsafe (Day 3)
- [ ] GeofenceFailsafe integration
- [ ] InterferenceDetector
- [ ] Multi-level response strategies
- [ ] Testing & validation
- [ ] Frontend: Threat visualization

### Phase 4: Monitoring & Docker (Days 3-4)
- [ ] Prometheus metrics export
- [ ] Health check endpoints
- [ ] docker-compose setup
- [ ] Grafana dashboards
- [ ] Load testing & benchmarks

### Phase 5: Polish & Documentation (Day 4)
- [ ] Performance optimization
- [ ] Complete test coverage
- [ ] API documentation updates
- [ ] Deployment guide
- [ ] Migration guide from Veha 4

---

## 📈 Load Testing Targets

```
Scenario: 5 drones, 100 concurrent clients, 10 Hz telemetry

Targets:
- API p99 latency: <100ms
- Database queries: <50ms
- WebSocket broadcast: <20ms
- Memory usage: <2GB
- CPU usage: <60%

Tools:
- locust - HTTP load testing
- wrk - WebSocket benchmark
- k6 - Scenario testing
```

---

## 🗂️ File Structure

```
src/
├── backend/
│   ├── models/              # SQLAlchemy ORM models
│   │   ├── drone.py
│   │   ├── mission.py
│   │   ├── telemetry.py
│   │   └── noflyzone.py
│   ├── services/            # Updated services
│   │   ├── drone_coordinator.py
│   │   ├── mission_recorder.py
│   │   └── geofence_failsafe.py
│   ├── routes/              # Multi-drone routes
│   │   ├── drones.py
│   │   ├── missions.py
│   │   ├── coordination.py
│   │   └── health.py
│   ├── database.py          # DB initialization
│   ├── config.py            # Configuration
│   └── app.py               # Updated Flask app
│
├── migrations/              # Alembic migrations
│
├── tests/
│   ├── test_multidrone.py
│   ├── test_recording.py
│   ├── test_failsafe_advanced.py
│   └── test_load.py
│
├── docker-compose.yml
├── Dockerfile
├── prometheus.yml
└── grafana-dashboards/
```

---

## 🚀 Success Metrics

### Functionality
- [x] Single-drone support (Veha 1-4)
- [ ] Multi-drone coordination
- [ ] Mission recording/playback
- [ ] Advanced geofence
- [ ] Database persistence
- [ ] Monitoring dashboard

### Performance
- [ ] <100ms p99 API latency
- [ ] 1000+ messages/sec throughput
- [ ] <2GB memory for 5 drones
- [ ] <60% CPU utilization

### Reliability
- [ ] 99.9% uptime target
- [ ] Graceful degradation
- [ ] Database recovery
- [ ] Drone reconnection

### Documentation
- [ ] API docs updated
- [ ] Deployment guide
- [ ] Migration guide
- [ ] Operations manual

---

## 📅 Timeline

```
July 28  | Phase 1: Database & Multi-Drone
July 29  | Phase 2: Recording & Playback
July 30  | Phase 3: Advanced Failsafe
July 31  | Phase 4: Monitoring & Docker
Aug 1    | Phase 5: Polish & Testing
Aug 2-4  | Load testing, optimization, docs
```

---

## 🎓 References

- **SQLAlchemy**: https://docs.sqlalchemy.org/
- **Prometheus**: https://prometheus.io/
- **Grafana**: https://grafana.com/
- **PostGIS**: https://postgis.net/ (for geo queries)
- **locust**: https://locust.io/ (load testing)

---

**Veha 5**: Production-ready multi-drone AIS SITL platform  
**Next Phase**: Veha 5 Implementation (July 28 - August 4, 2026)
