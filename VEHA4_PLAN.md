# Veha 4: Web Dashboard & REST API

## Milestone: July 25-28, 2026

### Overview
Develop a complete web dashboard for real-time drone monitoring and mission control with REST API backend and GIS map frontend.

### Deliverables

#### Backend (Flask REST API)
- [ ] `src/backend/app.py` - Flask application with REST endpoints
- [ ] `src/backend/routes/` - API route handlers:
  - [ ] `drone_routes.py` - Connection, arm/disarm, takeoff/land
  - [ ] `mission_routes.py` - Mission upload, start, pause, abort
  - [ ] `telemetry_routes.py` - Live telemetry streaming (WebSocket)
  - [ ] `status_routes.py` - System health status
  - [ ] `geofence_routes.py` - NFZ management
- [ ] `src/backend/services/` - Business logic:
  - [ ] `drone_service.py` - Wrapper around Drone class
  - [ ] `mission_service.py` - Wrapper around MissionService
  - [ ] `failsafe_service.py` - Wrapper around FailsafeMonitor
  - [ ] `geofence_service.py` - Wrapper around GeofenceValidator
- [ ] WebSocket for real-time telemetry (10 Hz)
- [ ] CORS support for frontend

#### Frontend (Vue.js/React)
- [ ] `web/` - Frontend directory
- [ ] `web/public/index.html` - Main entry point
- [ ] `web/src/components/` - Reusable components:
  - [ ] `MapComponent.vue` - GIS map (Leaflet + OpenStreetMap)
  - [ ] `TelemetryPanel.vue` - Live telemetry display
  - [ ] `MissionPanel.vue` - Mission control
  - [ ] `SystemStatus.vue` - Health indicators
  - [ ] `EventLog.vue` - Failsafe/event history
- [ ] `web/src/pages/` - Pages:
  - [ ] `Dashboard.vue` - Main mission monitor
  - [ ] `MissionPlanner.vue` - Create/edit missions
  - [ ] `Settings.vue` - Configuration
- [ ] Real-time WebSocket connection to backend
- [ ] Map rendering with:
  - Drone position (live)
  - Flight trail
  - Waypoint route
  - No-Fly Zones
  - Home position

#### Docker Updates
- [ ] Update `Dockerfile` to include backend
- [ ] Update `docker-compose.yml` for multi-container setup:
  - PX4 SITL container
  - Gazebo container
  - Backend API container
  - Frontend dev server (or nginx)

### REST API Specification

#### Drone Endpoints
```
POST   /api/drone/connect              - Connect to SITL
POST   /api/drone/disconnect           - Disconnect
POST   /api/drone/arm                  - Arm motors
POST   /api/drone/disarm               - Disarm
POST   /api/drone/takeoff              - {"altitude": 50.0}
POST   /api/drone/land                 - Land at current position
POST   /api/drone/hold-position        - Hover in place
POST   /api/drone/return-to-launch     - RTL with reason
GET    /api/drone/status               - Current state & telemetry
GET    /api/drone/state                - Current flight mode
```

#### Mission Endpoints
```
POST   /api/mission/upload             - {"waypoints": [...]}
POST   /api/mission/start              - Start mission
POST   /api/mission/pause              - Pause mission
POST   /api/mission/resume             - Resume mission
POST   /api/mission/abort              - Abort mission
GET    /api/mission/progress           - Current waypoint info
GET    /api/mission/history            - Previous missions
POST   /api/mission/validate           - Validate before upload
```

#### Geofence Endpoints
```
GET    /api/geofence/zones             - List all NFZ zones
POST   /api/geofence/zones             - Load GeoJSON zones
GET    /api/geofence/zones/:id         - Get specific zone
POST   /api/geofence/check-point       - {"lat": 47.39, "lon": 8.54, "alt": 50}
POST   /api/geofence/check-mission     - Validate mission waypoints
```

#### Telemetry WebSocket
```
ws://localhost:5000/ws/telemetry

Events:
- telemetry          - 10 Hz position, velocity, attitude, battery
- mission_update     - Waypoint progress
- failsafe_triggered - Emergency event
- system_status      - Health indicators
- event_log          - New log entry
```

### Testing

- [ ] `tests/test_backend_routes.py` - API endpoint tests
- [ ] `tests/test_websocket.py` - WebSocket connection tests
- [ ] `web/tests/components.spec.js` - Frontend component tests
- [ ] `tests/test_veha4_integration.py` - End-to-end tests

### Configuration

`config/app.yaml`:
```yaml
app:
  host: "127.0.0.1"
  port: 5000
  debug: true
  
drone:
  sitl_host: "127.0.0.1"
  sitl_port: 14540
  
telemetry:
  rate_hz: 10.0
  history_size: 100
  
geofence:
  zones_file: "config/nfz_zones.geojson"
  enabled: true
  
frontend:
  map_provider: "openstreetmap"
  initial_zoom: 15
  default_center: [47.3977, 8.5455]
```

### Development Workflow

1. **Backend First**:
   ```bash
   python3 src/backend/app.py
   # API available at http://localhost:5000
   ```

2. **Frontend Development**:
   ```bash
   cd web
   npm install
   npm run dev
   # Frontend at http://localhost:3000 (proxies to :5000)
   ```

3. **Testing**:
   ```bash
   python3 -m pytest tests/test_backend_routes.py -v
   cd web && npm test
   ```

4. **Docker Deployment**:
   ```bash
   docker-compose up
   # Everything at http://localhost:5000
   ```

### Success Criteria

✅ **Veha 4 Complete When:**
- [ ] All REST API endpoints functional with actual Drone class
- [ ] WebSocket telemetry streaming at 10 Hz to frontend
- [ ] GIS map displays drone position in real-time
- [ ] Mission upload and execution via UI
- [ ] Failsafe events logged and displayed
- [ ] System health indicators accurate
- [ ] Full docker-compose setup working
- [ ] All tests passing (backend + frontend)
- [ ] Complete API documentation
- [ ] User can plan, upload, and execute missions without CLI

### Dependencies to Add

```
# Backend
flask==3.0.0
flask-cors==4.0.0
flask-socketio==5.3.4
python-socketio==5.9.0
python-engineio==4.7.1
gunicorn==21.2.0

# Frontend
leaflet==1.9.4
axios==1.4.0
vue==3.3.4
```

### Potential Issues & Mitigations

| Issue | Mitigation |
|-------|-----------|
| MAVSDK not available | Use stub mode in backend |
| WebSocket latency | Buffer telemetry on frontend, interpolate between updates |
| Large GeoJSON NFZ files | Implement client-side spatial indexing |
| Multiple drone support | Design API to support drone_id parameter |
| Mission file upload size | Limit to 10MB, validate before processing |

### Post-Veha 4 (Veha 5)

- [ ] Multi-drone coordination UI
- [ ] Mission logging & playback
- [ ] Performance optimization (SPA, caching)
- [ ] Authentication & authorization
- [ ] Advanced failsafe scenarios UI
- [ ] Production deployment guide

---

**Status**: Planning (July 25, 2026)  
**Owner**: Available for assignment  
**Depends On**: feat/integration-veha3 (Veha 3 complete)
