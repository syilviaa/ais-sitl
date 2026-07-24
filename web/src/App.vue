<template>
  <div id="app" class="dashboard">
    <!-- Header -->
    <header class="navbar">
      <div class="navbar-brand">
        <h1>🚁 AIS SITL Platform - Veha 4</h1>
        <span class="subtitle">Web Dashboard</span>
      </div>
      <div class="navbar-status">
        <span :class="['status-badge', apiConnected ? 'connected' : 'disconnected']">
          {{ apiConnected ? '🟢' : '🔴' }}
          {{ apiConnected ? 'CONNECTED' : 'DISCONNECTED' }}
        </span>
      </div>
    </header>

    <!-- Main Content -->
    <main class="container">
      <!-- Map Panel -->
      <section class="map-panel">
        <MapComponent :dronePosition="telemetry" :waypoints="waypoints" ref="mapComponent" />
      </section>

      <!-- Control Panel -->
      <aside class="control-panel">
        <!-- Telemetry Panel -->
        <section class="panel telemetry-panel">
          <h2>📊 Telemetry (10 Hz)</h2>
          <div class="telemetry-grid">
            <div class="telemetry-item">
              <label>Position</label>
              <code>{{ telemetry.lat?.toFixed(4) || 'N/A' }}<br/>{{ telemetry.lon?.toFixed(4) || 'N/A' }}</code>
            </div>
            <div class="telemetry-item">
              <label>Altitude</label>
              <code>{{ telemetry.alt?.toFixed(1) || 0 }} m</code>
            </div>
            <div class="telemetry-item">
              <label>Speed</label>
              <code>{{ Math.sqrt((telemetry.vx||0)**2 + (telemetry.vy||0)**2).toFixed(1) }} m/s</code>
            </div>
            <div class="telemetry-item">
              <label>Battery</label>
              <code :class="['battery', getBatteryClass(telemetry.battery)]">
                {{ telemetry.battery?.toFixed(1) || 0 }}%
              </code>
            </div>
            <div class="telemetry-item">
              <label>GPS</label>
              <code>{{ telemetry.satellites || 0 }} sats</code>
            </div>
            <div class="telemetry-item">
              <label>Mode</label>
              <code>{{ telemetry.mode || 'UNKNOWN' }}</code>
            </div>
          </div>
        </section>

        <!-- System Status -->
        <section class="panel status-panel">
          <h2>🔧 System Status</h2>
          <div class="status-list">
            <div class="status-item">
              <span class="status-icon" :class="apiConnected ? 'ok' : 'error'">●</span>
              <span>API Connected</span>
            </div>
            <div class="status-item">
              <span class="status-icon" :class="telemetry.gps_status?.includes('3') ? 'ok' : 'warning'">●</span>
              <span>GPS Lock</span>
            </div>
            <div class="status-item">
              <span class="status-icon" :class="getBatteryClass(telemetry.battery) === 'critical' ? 'error' : 'ok'">●</span>
              <span>Battery</span>
            </div>
            <div class="status-item">
              <span class="status-icon" :class="telemetry.armed ? 'warning' : 'ok'">●</span>
              <span>{{ telemetry.armed ? 'ARMED' : 'Disarmed' }}</span>
            </div>
          </div>
        </section>

        <!-- Mission Control -->
        <section class="panel mission-panel">
          <h2>✈️ Mission Control</h2>
          <div v-if="!missionUploaded" class="upload-section">
            <button @click="uploadTestMission" class="btn btn-primary btn-block">📤 Upload Mission</button>
          </div>
          <div v-else class="mission-active">
            <div class="mission-actions">
              <button @click="startMission" :disabled="missionRunning" class="btn btn-primary">▶ Start</button>
              <button @click="pauseMission" :disabled="!missionRunning" class="btn btn-secondary">⏸ Pause</button>
              <button @click="abortMission" class="btn btn-danger">⏹ Abort</button>
            </div>
            <div class="mission-progress" v-if="missionProgress.total > 0">
              <p>Waypoint: {{ missionProgress.current }} / {{ missionProgress.total }}</p>
              <div class="progress-bar">
                <div
                  class="progress-fill"
                  :style="{ width: missionProgress.percent + '%' }"
                ></div>
              </div>
              <p>{{ missionProgress.percent.toFixed(0) }}%</p>
            </div>
          </div>
        </section>

        <!-- Events Log -->
        <section class="panel event-panel">
          <h2>📋 Events (Last 5)</h2>
          <div class="event-list">
            <div v-if="events.length === 0" class="empty-state">
              <small>No events yet</small>
            </div>
            <div
              v-for="(event, idx) in events.slice(-5).reverse()"
              :key="idx"
              class="event-item"
              :class="event.type"
            >
              <span class="event-time">{{ formatTime(event.timestamp) }}</span>
              <span class="event-message">{{ event.message }}</span>
            </div>
          </div>
        </section>
      </aside>
    </main>
  </div>
</template>

<script>
import MapComponent from './components/MapComponent.vue'

const API_BASE = 'http://127.0.0.1:5000/api'

export default {
  name: 'App',
  components: {
    MapComponent,
  },
  data() {
    return {
      apiConnected: false,
      telemetry: {
        timestamp: null,
        lat: null,
        lon: null,
        alt: 0,
        vx: 0,
        vy: 0,
        vz: 0,
        battery: 0,
        gps_status: 'NO FIX',
        satellites: 0,
        armed: false,
        mode: 'UNKNOWN',
      },
      missionUploaded: false,
      missionRunning: false,
      missionProgress: {
        current: 0,
        total: 0,
        percent: 0,
      },
      waypoints: [
        { lat: 47.3977, lon: 8.5455, altitude: 50 },
        { lat: 47.3985, lon: 8.5465, altitude: 60 },
        { lat: 47.3977, lon: 8.5455, altitude: 0 },
      ],
      events: [],
      telemetryInterval: null,
      progressInterval: null,
    }
  },
  mounted() {
    this.addEvent('system', 'Dashboard loaded')
    this.initializeBackend()
    this.startTelemetryPolling()
  },
  beforeUnmount() {
    if (this.telemetryInterval) clearInterval(this.telemetryInterval)
    if (this.progressInterval) clearInterval(this.progressInterval)
  },
  methods: {
    async initializeBackend() {
      try {
        const response = await fetch(`${API_BASE}/health`)
        if (response.ok) {
          this.apiConnected = true
          this.addEvent('success', 'Connected to API')
        }
      } catch (e) {
        this.addEvent('error', `API error: ${e.message}`)
      }
    },
    async startTelemetryPolling() {
      this.telemetryInterval = setInterval(async () => {
        try {
          const response = await fetch(`${API_BASE}/telemetry/latest`)
          if (response.ok) {
            const data = await response.json()
            if (data) {
              this.telemetry = { ...this.telemetry, ...data }
              if (this.$refs.mapComponent) {
                this.$refs.mapComponent.updateDronePosition(this.telemetry)
              }
            }
          }
        } catch (e) {
          console.error('Telemetry error:', e)
        }
      }, 100) // 10 Hz
    },
    async uploadTestMission() {
      try {
        this.addEvent('info', 'Validating mission...')

        // Validate
        const validateResp = await fetch(`${API_BASE}/mission/validate`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ waypoints: this.waypoints }),
        })

        if (!validateResp.ok) {
          this.addEvent('error', 'Mission validation failed')
          return
        }

        this.addEvent('success', 'Mission validated')

        // Upload
        this.addEvent('info', 'Uploading mission...')
        const uploadResp = await fetch(`${API_BASE}/mission/upload`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ waypoints: this.waypoints }),
        })

        if (uploadResp.ok) {
          const data = await uploadResp.json()
          this.missionUploaded = true
          this.addEvent('success', `Mission uploaded (ID: ${data.mission_id})`)

          // Add waypoints to map
          if (this.$refs.mapComponent) {
            this.$refs.mapComponent.addWaypoints(this.waypoints)
          }

          // Start progress polling
          if (this.progressInterval) clearInterval(this.progressInterval)
          this.progressInterval = setInterval(this.updateMissionProgress, 1000)
        } else {
          this.addEvent('error', 'Upload failed')
        }
      } catch (e) {
        this.addEvent('error', `Upload error: ${e.message}`)
      }
    },
    async startMission() {
      try {
        const response = await fetch(`${API_BASE}/mission/start`, { method: 'POST' })
        if (response.ok) {
          this.missionRunning = true
          this.addEvent('success', 'Mission started')
        }
      } catch (e) {
        this.addEvent('error', `Start error: ${e.message}`)
      }
    },
    async pauseMission() {
      try {
        const response = await fetch(`${API_BASE}/mission/pause`, { method: 'POST' })
        if (response.ok) {
          this.missionRunning = false
          this.addEvent('warning', 'Mission paused')
        }
      } catch (e) {
        this.addEvent('error', `Pause error: ${e.message}`)
      }
    },
    async abortMission() {
      try {
        const response = await fetch(`${API_BASE}/mission/abort`, { method: 'POST' })
        if (response.ok) {
          this.missionRunning = false
          this.missionUploaded = false
          this.addEvent('error', 'Mission aborted')
          if (this.progressInterval) clearInterval(this.progressInterval)
        }
      } catch (e) {
        this.addEvent('error', `Abort error: ${e.message}`)
      }
    },
    async updateMissionProgress() {
      try {
        const response = await fetch(`${API_BASE}/mission/progress`)
        if (response.ok) {
          const data = await response.json()
          this.missionProgress = data
        }
      } catch (e) {
        console.error('Progress error:', e)
      }
    },
    getBatteryClass(battery) {
      if (!battery) return 'critical'
      if (battery > 50) return 'good'
      if (battery > 20) return 'warning'
      return 'critical'
    },
    formatTime(timestamp) {
      if (!timestamp) return '--:--:--'
      const date = new Date(timestamp * 1000)
      return date.toLocaleTimeString()
    },
    addEvent(type, message) {
      this.events.push({
        type,
        message,
        timestamp: Date.now() / 1000,
      })
      if (this.events.length > 50) this.events.shift()
    },
  },
}
</script>

<style scoped>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

#app {
  height: 100vh;
  display: flex;
  flex-direction: column;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background: #f5f5f5;
}

/* Header */
.navbar {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 1rem 2rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.navbar-brand h1 {
  font-size: 1.5rem;
  font-weight: 600;
}

.subtitle {
  font-size: 0.75rem;
  opacity: 0.8;
  margin-left: 1rem;
}

.status-badge {
  padding: 0.5rem 1rem;
  border-radius: 20px;
  font-weight: 600;
  font-size: 0.9rem;
}

.status-badge.connected {
  background: rgba(34, 197, 94, 0.2);
  color: #22c55e;
}

.status-badge.disconnected {
  background: rgba(239, 68, 68, 0.2);
  color: #ef4444;
}

/* Container */
.container {
  display: flex;
  flex: 1;
  gap: 1rem;
  padding: 1rem;
  overflow: hidden;
}

.map-panel {
  flex: 1;
  background: white;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

/* Control Panel */
.control-panel {
  width: 320px;
  display: flex;
  flex-direction: column;
  gap: 1rem;
  overflow-y: auto;
  overflow-x: hidden;
  padding-right: 0.5rem;
}

.control-panel::-webkit-scrollbar {
  width: 6px;
}

.control-panel::-webkit-scrollbar-track {
  background: transparent;
}

.control-panel::-webkit-scrollbar-thumb {
  background: #cbd5e1;
  border-radius: 3px;
}

/* Panels */
.panel {
  background: white;
  border-radius: 8px;
  padding: 1.5rem;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.panel h2 {
  font-size: 1.1rem;
  margin-bottom: 1rem;
  font-weight: 600;
  color: #1f2937;
}

/* Telemetry */
.telemetry-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
  font-size: 0.9rem;
}

.telemetry-item {
  display: flex;
  flex-direction: column;
}

.telemetry-item label {
  font-weight: 600;
  color: #6b7280;
  font-size: 0.8rem;
  margin-bottom: 0.25rem;
}

.telemetry-item code {
  font-family: 'Monaco', monospace;
  font-size: 0.85rem;
  background: #f3f4f6;
  padding: 0.35rem 0.5rem;
  border-radius: 4px;
  word-break: break-all;
  font-weight: 500;
}

.battery.good { color: #22c55e; }
.battery.warning { color: #f59e0b; }
.battery.critical { color: #ef4444; }

/* Status */
.status-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.status-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  font-size: 0.95rem;
}

.status-icon {
  font-size: 1.2rem;
  font-weight: bold;
}

.status-icon.ok { color: #22c55e; }
.status-icon.warning { color: #f59e0b; }
.status-icon.error { color: #ef4444; }

/* Mission */
.upload-section {
  display: flex;
  gap: 0.5rem;
}

.mission-active .mission-actions {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 0.5rem;
  margin-bottom: 1rem;
}

.mission-progress {
  font-size: 0.9rem;
}

.mission-progress p {
  margin-bottom: 0.5rem;
  color: #6b7280;
}

.progress-bar {
  width: 100%;
  height: 8px;
  background: #e5e7eb;
  border-radius: 4px;
  overflow: hidden;
  margin-bottom: 0.5rem;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
  transition: width 0.3s ease;
}

/* Buttons */
.btn {
  padding: 0.5rem;
  border: none;
  border-radius: 4px;
  font-weight: 600;
  cursor: pointer;
  font-size: 0.85rem;
  transition: all 0.2s;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-primary {
  background: #667eea;
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background: #5568d3;
}

.btn-secondary {
  background: #e5e7eb;
  color: #1f2937;
}

.btn-secondary:hover:not(:disabled) {
  background: #d1d5db;
}

.btn-danger {
  background: #ef4444;
  color: white;
}

.btn-danger:hover:not(:disabled) {
  background: #dc2626;
}

.btn-block {
  width: 100%;
}

/* Events */
.event-list {
  font-size: 0.85rem;
  max-height: 200px;
  overflow-y: auto;
}

.event-item {
  padding: 0.5rem;
  margin-bottom: 0.5rem;
  border-left: 3px solid #e5e7eb;
  background: #f9fafb;
  border-radius: 2px;
}

.event-item.error { border-left-color: #ef4444; }
.event-item.warning { border-left-color: #f59e0b; }
.event-item.info { border-left-color: #667eea; }
.event-item.success { border-left-color: #22c55e; }
.event-item.system { border-left-color: #6b7280; }

.event-time {
  font-family: monospace;
  color: #9ca3af;
  font-size: 0.75rem;
  margin-right: 0.5rem;
}

.event-message {
  color: #374151;
}

.empty-state {
  text-align: center;
  color: #9ca3af;
  padding: 2rem 1rem;
}
</style>
