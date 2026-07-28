# AIS SITL Platform - Web Frontend

## Veha 4: Web Dashboard

Vue.js frontend for real-time drone monitoring and mission control.

### Features (Planned)

- 🗺️ **GIS Map** - Live drone position, flight trail, waypoints, No-Fly Zones
- 📊 **Telemetry** - Real-time position, velocity, attitude, battery, GPS
- ✈️ **Mission Control** - Upload, start, pause, abort missions
- 🔧 **System Status** - Health indicators, connection status, failsafe state
- 📋 **Event Log** - Failsafe events, mission updates, system alerts
- 🌐 **WebSocket** - 10 Hz telemetry streaming from backend

### Architecture

```
web/
├── public/
│   └── index.html          # Main HTML
├── src/
│   ├── main.js             # Vue entry point
│   ├── App.vue             # Root component
│   ├── components/         # Reusable components
│   │   ├── MapComponent.vue        # GIS map (Leaflet)
│   │   ├── TelemetryPanel.vue      # Live telemetry
│   │   ├── MissionPanel.vue        # Mission control
│   │   ├── SystemStatus.vue        # Health indicators
│   │   └── EventLog.vue            # Event history
│   ├── pages/              # Page components
│   │   ├── Dashboard.vue           # Main mission monitor
│   │   ├── MissionPlanner.vue      # Create/edit missions
│   │   └── Settings.vue            # Configuration
│   ├── services/           # API integration
│   │   ├── api.js                  # REST API client
│   │   ├── websocket.js            # WebSocket manager
│   │   └── mapService.js           # Map utilities
│   └── assets/             # Static assets
└── package.json            # Dependencies
```

### Development Setup

```bash
# Install dependencies
npm install

# Development server (localhost:3000, proxies to :5000)
npm run dev

# Production build
npm build

# Run tests
npm test

# Lint & format
npm run lint
npm run format
```

### Dependencies

```json
{
  "dependencies": {
    "vue": "^3.3.4",
    "vue-router": "^4.2.4",
    "leaflet": "^1.9.4",
    "axios": "^1.4.0",
    "socket.io-client": "^4.6.1"
  },
  "devDependencies": {
    "@vitejs/plugin-vue": "^4.2.3",
    "vite": "^4.3.9",
    "vitest": "^0.34.0"
  }
}
```

### WebSocket Events

```javascript
// Connect to backend
const socket = io('http://localhost:5000');

// Receive telemetry (10 Hz)
socket.on('telemetry', (data) => {
  console.log(`Altitude: ${data.altitude}m`);
  console.log(`Battery: ${data.battery}%`);
});

// Mission progress
socket.on('mission_update', (progress) => {
  console.log(`Waypoint ${progress.current}/${progress.total}`);
});

// Failsafe events
socket.on('failsafe', (event) => {
  console.log(`⚠️ ${event.reason}`);
});

// System status
socket.on('system_status', (status) => {
  console.log(`GPS: ${status.gps_ok ? 'OK' : 'LOST'}`);
});
```

### REST API Integration

```javascript
import axios from 'axios';

const API_BASE = 'http://localhost:5000/api';

// Drone Control
await axios.post(`${API_BASE}/drone/arm`);
await axios.post(`${API_BASE}/drone/takeoff`, { altitude: 50.0 });

// Mission Control
await axios.post(`${API_BASE}/mission/upload`, { waypoints: [...] });
await axios.post(`${API_BASE}/mission/start`);

// Telemetry
const status = await axios.get(`${API_BASE}/drone/status`);
```

### Components Status

| Component | Status | Owner |
|-----------|--------|-------|
| MapComponent | ⏳ TODO | Veha 4 |
| TelemetryPanel | ⏳ TODO | Veha 4 |
| MissionPanel | ⏳ TODO | Veha 4 |
| SystemStatus | ⏳ TODO | Veha 4 |
| EventLog | ⏳ TODO | Veha 4 |
| Dashboard | ⏳ TODO | Veha 4 |
| API Client | ⏳ TODO | Veha 4 |
| WebSocket Manager | ⏳ TODO | Veha 4 |

### Testing

```bash
# Unit tests (components)
npm run test:unit

# Integration tests (API)
npm run test:integration

# E2E tests (full workflow)
npm run test:e2e

# Coverage report
npm run test:coverage
```

### Deployment

See [../DEPLOYMENT.md](../DEPLOYMENT.md) for production setup.

---

**Status**: Planning (Veha 4 - July 25-28, 2026)  
**Technology**: Vue 3 + Vite + Leaflet + Socket.io  
**Depends On**: Backend API (src/backend/app.py)
