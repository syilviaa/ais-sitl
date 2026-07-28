# Veha 4 Frontend - Vue.js Dashboard

**Technology**: Vue 3 + Leaflet + Socket.io  
**Status**: Core components complete  
**URL**: `http://127.0.0.1:3000` (dev) or `:5000` (production)

---

## Features Implemented

✅ **Map Component** (MapComponent.vue)
- Leaflet-based GIS map
- Live drone position marker
- Home position marker
- Waypoint markers with numbering
- Flight route visualization
- Real-time position updates
- Telemetry info badges (alt, GPS sats, battery)

✅ **Dashboard** (App.vue)
- Real-time telemetry display (10 Hz)
- System status indicators
- Mission control (upload, start, pause, abort)
- Event logging (last 50 events)
- API connection status
- Responsive layout

✅ **Telemetry Panel**
- Position (lat, lon)
- Altitude
- Speed (calculated from vx, vy)
- Battery percentage with color coding
- GPS satellites & status
- Flight mode

✅ **System Status Panel**
- API connection status
- GPS lock indicator
- Battery health
- Armed/Disarmed status

✅ **Mission Control Panel**
- Mission upload button
- Start/Pause/Abort controls
- Progress bar with percentage
- Current waypoint display

✅ **Event Log Panel**
- Last 5 events displayed
- Color-coded by type (error/warning/info/success/system)
- Timestamp for each event
- Auto-scrolling

---

## Project Structure

```
web/
├── public/
│   └── index.html              # Main HTML with Leaflet CDN
├── src/
│   ├── main.js                 # Vue entry point
│   ├── App.vue                 # Root component (dashboard)
│   ├── components/
│   │   └── MapComponent.vue    # GIS map component
│   └── assets/                 # (TODO) Static files
├── package.json                # Dependencies & scripts
└── README.md                   # Frontend documentation
```

---

## Running Frontend

### Development Server

```bash
cd web
npm install
npm run dev
```

Opens at: `http://localhost:3000`  
Proxies API calls to backend at `:5000`

### Production Build

```bash
npm run build
npm run preview
```

---

## Components

### App.vue (Root)
- Dashboard layout with header, map, and control panels
- API connection management
- Telemetry polling (10 Hz)
- Mission state management
- Event logging system

**Data**:
```javascript
{
  apiConnected: boolean,
  telemetry: {
    lat, lon, alt, vx, vy, vz,
    battery, satellites, armed, mode, ...
  },
  missionProgress: { current, total, percent },
  waypoints: Array,
  events: Array,
}
```

**Methods**:
- `initializeBackend()` - Check API connection
- `startTelemetryPolling()` - 10 Hz updates
- `uploadTestMission()` - Upload 3-waypoint mission
- `startMission()`, `pauseMission()`, `abortMission()`
- `updateMissionProgress()` - Poll progress
- `addEvent(type, message)` - Log event

### MapComponent.vue
- Leaflet map initialization
- Drone position tracking
- Waypoint visualization
- Route polyline drawing
- Real-time position updates

**Props**:
- `dronePosition` - Current telemetry snapshot
- `waypoints` - Array of mission waypoints

**Methods**:
- `initMap()` - Initialize Leaflet map
- `updateDronePosition(pos)` - Update drone marker
- `addWaypoints(waypoints)` - Draw mission route

---

## API Integration

### Telemetry Polling (Every 100ms)

```javascript
const response = await fetch('http://127.0.0.1:5000/api/telemetry/latest')
const data = await response.json()
// Update telemetry display and map
```

### Mission Upload

```javascript
await fetch('/api/mission/upload', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ waypoints: [...] }),
})
```

### Mission Start/Pause/Abort

```javascript
await fetch('/api/mission/start', { method: 'POST' })
await fetch('/api/mission/pause', { method: 'POST' })
await fetch('/api/mission/abort', { method: 'POST' })
```

### Mission Progress

```javascript
const response = await fetch('/api/mission/progress')
const { current, total, percent } = await response.json()
```

---

## Styling

### Color Scheme
- Primary: `#667eea` (purple)
- Secondary: `#764ba2` (dark purple)
- Success: `#22c55e` (green)
- Warning: `#f59e0b` (orange)
- Error: `#ef4444` (red)
- Gray: `#6b7280` (text), `#e5e7eb` (borders)

### Responsive Layout
- Main: Header (full width) + Container (flex)
- Container: Map (flex: 1) + Control Panel (320px fixed)
- Control Panel: Scrollable, 5 panels stacked

### Components
- Panels: White background, 8px radius, shadow
- Buttons: 4px radius, transitions, hover states
- Grids: 2-column for telemetry, 1-column for status
- Progress bar: Linear gradient background

---

## Event Types

```javascript
addEvent(type, message)
```

**Types**:
- `'system'` - System events (dashboard loaded)
- `'success'` - Successful operations (mission uploaded)
- `'error'` - Errors (upload failed)
- `'warning'` - Warnings (paused, battery low)
- `'info'` - Information (validating, uploading)

---

## Testing

### Manual Testing
1. Open `http://127.0.0.1:3000` in browser
2. Verify "Connected to API" in events
3. Click "Upload Mission" button
4. Verify 3 waypoints appear on map
5. Click "Start" to begin mission
6. Monitor telemetry updates
7. Check progress bar increments

### Component Testing (TODO)
```bash
npm run test:unit
npm run test:e2e
```

---

## Future Enhancements

- [ ] WebSocket real-time telemetry (replace polling)
- [ ] Geofence zone visualization on map
- [ ] Failsafe event notifications
- [ ] Custom mission waypoint drawing
- [ ] Telemetry graph history
- [ ] Multi-drone support
- [ ] Settings panel
- [ ] Dark mode
- [ ] Mobile responsive design
- [ ] Recording/playback missions

---

## Troubleshooting

### Map not showing
- Check Leaflet CDN is loaded (browser console)
- Verify map container has height/width

### No telemetry data
- Check backend is running: `python3 run_backend.py`
- Verify API connection in events log
- Check CORS headers

### Mission upload fails
- Ensure waypoints are valid (lat: ±90, lon: ±180)
- Check backend mission validation
- Verify geofence zones are loaded

### Buttons not responding
- Check browser console for errors
- Verify backend endpoint is accessible
- Check network tab for failed requests

---

**Status**: Core Dashboard Complete ✅  
**Timeline**: July 25-28, 2026  
**Next**: WebSocket streaming, geofence visualization
