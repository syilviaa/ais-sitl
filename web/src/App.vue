<template>
  <div id="app" class="dashboard">
    <header class="navbar">
      <div class="navbar-brand">
        <h1>🚁 AIS SITL — Astana Training Field</h1>
        <span class="subtitle">Territory Intelligence Dashboard · KZ</span>
      </div>
      <div class="navbar-status">
        <span :class="['status-badge', apiConnected ? 'connected' : 'disconnected']">
          API {{ apiConnected ? 'OK' : 'OFF' }}
        </span>
        <span :class="['status-badge', wsStatusClass]">
          WS {{ wsStatusLabel }}
        </span>
      </div>
    </header>

    <main class="container">
      <section class="map-panel">
        <MapComponent
          ref="mapComponent"
          :dronePosition="telemetry"
          :waypoints="waypoints"
          :nfzGeoJson="nfzGeoJson"
          :planMode="planMode"
          @waypoint-added="addWaypoint"
          @waypoint-moved="moveWaypoint"
          @waypoint-removed="removeWaypoint"
        />
      </section>

      <aside class="control-panel">
        <!-- Flight Control -->
        <section class="panel flight-panel">
          <h2>🎮 Flight Control</h2>
          <div class="flight-actions">
            <button
              @click="initializeDrone"
              class="btn btn-secondary btn-block"
              :disabled="droneReady"
            >
              {{ droneReady ? '✅ Initialized' : '🔌 Initialize SITL' }}
            </button>
            <div class="btn-row">
              <button @click="droneTakeoff" class="btn btn-primary" :disabled="!droneReady">🛫 Takeoff</button>
              <button @click="droneHold" class="btn btn-secondary" :disabled="!droneReady">⏸ Hold</button>
            </div>
            <div class="btn-row">
              <button @click="droneLand" class="btn btn-secondary" :disabled="!droneReady">🛬 Land</button>
              <button @click="droneRtl" class="btn btn-danger" :disabled="!droneReady">🏠 RTL</button>
            </div>
          </div>
        </section>

        <!-- Mission -->
        <section class="panel mission-panel">
          <h2>✈️ Mission</h2>
          <div class="mission-tools">
            <button
              @click="planMode = !planMode"
              :class="['btn', planMode ? 'btn-primary' : 'btn-secondary', 'btn-block']"
            >
              {{ planMode ? '📍 Plan mode — click map' : '🗺️ Enable planning' }}
            </button>
          </div>

          <ul v-if="waypoints.length" class="wp-list">
            <li v-for="(wp, i) in waypoints" :key="i">
              <span>WP{{ i + 1 }} — {{ wp.lat.toFixed(4) }}, {{ wp.lon.toFixed(4) }} · {{ wp.altitude }}m</span>
              <button v-if="planMode" class="btn-icon" @click="removeWaypoint(i)" title="Remove">✕</button>
            </li>
          </ul>
          <button
            v-if="waypoints.length"
            @click="clearWaypoints"
            class="btn btn-secondary btn-block"
          >
            🗑 Clear ({{ waypoints.length }})
          </button>

          <div v-if="missionBlockReason" class="nfz-block">
            ⛔ {{ missionBlockReason }}
          </div>

          <div class="mission-actions-grid">
            <button @click="validateMission" class="btn btn-secondary">✓ Validate</button>
            <button @click="uploadMission" class="btn btn-primary" :disabled="!missionValid">📤 Upload</button>
          </div>
          <button @click="exportPlan" class="btn btn-secondary btn-block">💾 Export .plan</button>

          <div v-if="missionUploaded" class="mission-active">
            <div class="mission-actions-grid four">
              <button @click="startMission" :disabled="missionRunning" class="btn btn-primary">▶ Start</button>
              <button @click="pauseMission" :disabled="!missionRunning" class="btn btn-secondary">⏸ Pause</button>
              <button @click="resumeMission" :disabled="missionRunning" class="btn btn-secondary">▶ Resume</button>
              <button @click="abortMission" class="btn btn-danger">⏹ Abort</button>
            </div>
            <div class="mission-progress" v-if="missionProgress.total > 0">
              <p>Waypoint {{ missionProgress.current }} / {{ missionProgress.total }}</p>
              <div class="progress-bar">
                <div class="progress-fill" :style="{ width: missionProgress.percent + '%' }"></div>
              </div>
              <p>{{ missionProgress.percent.toFixed(0) }}%</p>
            </div>
          </div>
        </section>

        <!-- Safety -->
        <section class="panel safety-panel">
          <h2>🛡 Safety</h2>
          <div class="safety-grid">
            <div class="safety-item">
              <label>Battery</label>
              <span :class="getBatteryClass(telemetry.battery)">{{ (telemetry.battery || 0).toFixed(0) }}%</span>
            </div>
            <div class="safety-item">
              <label>Connection</label>
              <span :class="wsStatusClass">{{ wsStatusLabel }}</span>
            </div>
            <div class="safety-item">
              <label>Armed</label>
              <span :class="telemetry.armed ? 'warn' : 'ok'">{{ telemetry.armed ? 'ARMED' : 'Disarmed' }}</span>
            </div>
            <div class="safety-item">
              <label>Mode</label>
              <span>{{ telemetry.mode || 'UNKNOWN' }}</span>
            </div>
            <div class="safety-item">
              <label>Failsafe</label>
              <span :class="failsafe.running ? 'ok' : 'warn'">{{ failsafe.running ? 'Active' : 'Idle' }}</span>
            </div>
            <div class="safety-item">
              <label>RTL reason</label>
              <span>{{ rtlReason || '—' }}</span>
            </div>
          </div>
        </section>

        <section class="panel video-panel">
          <h2>📹 Видеопоток</h2>
          <VideoStream
            :telemetry="telemetry"
            :active="droneReady && wsStatus === 'connected'"
            :api-base="API_BASE"
          />
        </section>

        <!-- Events -->
        <section class="panel event-panel">
          <h2>📋 Events</h2>
          <div class="event-list">
            <div v-if="events.length === 0" class="empty-state"><small>No events yet</small></div>
            <div
              v-for="(event, idx) in events.slice(-8).reverse()"
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
import VideoStream from './components/VideoStream.vue'
import { onTelemetry, onConnectionStatus, normalizeTelemetry } from './services/telemetryBridge.js'
import { connectTelemetry, disconnectTelemetry, requestTelemetryStart } from './services/telemetrySocket.js'

const API_BASE = import.meta.env.VITE_API_URL
  ? `${import.meta.env.VITE_API_URL.replace(/\/$/, '')}/api`
  : import.meta.env.DEV
    ? '/api'
    : 'http://127.0.0.1:5001/api'

export default {
  name: 'App',
  components: { MapComponent, VideoStream },
  data() {
    return {
      apiConnected: false,
      wsStatus: 'disconnected',
      droneReady: false,
      planMode: false,
      nfzGeoJson: null,
      telemetry: {
        timestamp: null,
        lat: null,
        lon: null,
        alt: 0,
        vx: 0,
        vy: 0,
        vz: 0,
        battery: 100,
        gps_status: 'NO FIX',
        satellites: 0,
        armed: false,
        mode: 'UNKNOWN',
      },
      missionValid: false,
      missionUploaded: false,
      missionRunning: false,
      missionBlockReason: null,
      missionProgress: { current: 0, total: 0, percent: 0 },
      waypoints: [],
      failsafe: { running: false, battery_warning: false, battery_critical: false },
      rtlReason: null,
      events: [],
      unsubTelemetry: null,
      unsubWsStatus: null,
      restFallbackInterval: null,
      failsafeInterval: null,
      progressInterval: null,
    }
  },
  computed: {
    wsStatusLabel() {
      const map = {
        connected: 'LIVE',
        reconnecting: 'RECONN',
        error: 'ERROR',
        disconnected: 'OFF',
      }
      return map[this.wsStatus] || this.wsStatus.toUpperCase()
    },
    wsStatusClass() {
      if (this.wsStatus === 'connected') return 'connected'
      if (this.wsStatus === 'reconnecting') return 'warning'
      if (this.wsStatus === 'error') return 'disconnected'
      return 'disconnected'
    },
  },
  mounted() {
    this.addEvent('system', 'Astana Training Field dashboard loaded')
    this.loadNfzZones()
    this.initializeBackend()
    this.unsubTelemetry = onTelemetry((t) => {
      if (t) this.telemetry = { ...this.telemetry, ...t }
    })
    this.unsubWsStatus = onConnectionStatus((s) => {
      this.wsStatus = s
    })
    connectTelemetry()
    this.startRestFallback()
    this.startFailsafePolling()
  },
  beforeUnmount() {
    if (this.unsubTelemetry) this.unsubTelemetry()
    if (this.unsubWsStatus) this.unsubWsStatus()
    disconnectTelemetry()
    if (this.restFallbackInterval) clearInterval(this.restFallbackInterval)
    if (this.failsafeInterval) clearInterval(this.failsafeInterval)
    if (this.progressInterval) clearInterval(this.progressInterval)
  },
  methods: {
    /** REST fallback when WebSocket is offline */
    startRestFallback() {
      this.restFallbackInterval = setInterval(async () => {
        if (this.wsStatus === 'connected') return
        try {
          const response = await fetch(`${API_BASE}/telemetry/latest`)
          if (response.ok) {
            const data = await response.json()
            if (data) this.telemetry = { ...this.telemetry, ...normalizeTelemetry(data) }
          }
        } catch {
          /* ignore */
        }
      }, 100)
    },
    startFailsafePolling() {
      this.failsafeInterval = setInterval(async () => {
        try {
          const response = await fetch(`${API_BASE}/failsafe/status`)
          if (response.ok) {
            const data = await response.json()
            this.failsafe = data
            const recent = data.recent_events || []
            const rtl = recent.find((e) => e?.type?.includes('rtl') || e?.action === 'rtl')
            if (rtl) this.rtlReason = rtl.reason || rtl.message || 'failsafe'
          }
        } catch {
          /* ignore */
        }
      }, 2000)
    },
    async loadNfzZones() {
      try {
        const response = await fetch(`${API_BASE}/geofence/geojson`)
        if (response.ok) {
          this.nfzGeoJson = await response.json()
          this.addEvent('info', `NFZ zones: ${this.nfzGeoJson.features?.length || 0}`)
        }
      } catch {
        this.addEvent('warning', 'NFZ GeoJSON unavailable — using local config')
        const local = await fetch('/config/nfz_zones.geojson').catch(() => null)
        if (local?.ok) this.nfzGeoJson = await local.json()
      }
    },
    async initializeBackend() {
      try {
        const response = await fetch(`${API_BASE}/health`)
        this.apiConnected = response.ok
        if (response.ok) this.addEvent('success', 'API connected')
      } catch (e) {
        this.addEvent('error', `API: ${e.message}`)
      }
    },
    async initializeDrone() {
      try {
        this.addEvent('info', 'Initializing SITL...')
        let response = await fetch(`${API_BASE}/drone/initialize`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ port: 14540, sitl_port: 14580 }),
        })
        let data = await response.json()
        if (!data.success) {
          this.addEvent(
            'error',
            (data.hint || data.error || 'Init failed') +
              ' — run ./scripts/start-px4-sitl.sh'
          )
          return
        }
        await fetch(`${API_BASE}/drone/wait-ready`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ timeout: 30 }),
        })
        this.droneReady = true
        requestTelemetryStart()
        this.addEvent('success', 'SITL ready — Astana home')
        if (this.$refs.mapComponent) this.$refs.mapComponent.clearTrail()
      } catch (e) {
        this.addEvent('error', `Init: ${e.message}`)
      }
    },
    async droneTakeoff() {
      try {
        const response = await fetch(`${API_BASE}/drone/takeoff`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ altitude: 50 }),
        })
        const data = await response.json().catch(() => ({}))
        if (response.ok) this.addEvent('success', 'Takeoff 50m')
        else this.addEvent('error', data.error || 'Takeoff failed')
      } catch (e) {
        this.addEvent('error', `Takeoff: ${e.message}`)
      }
    },
    async droneHold() {
      try {
        const response = await fetch(`${API_BASE}/drone/hold`, { method: 'POST' })
        const data = await response.json().catch(() => ({}))
        if (response.ok) this.addEvent('info', 'Hold position')
        else this.addEvent('error', data.error || 'Hold failed')
      } catch (e) {
        this.addEvent('error', `Hold: ${e.message}`)
      }
    },
    async droneLand() {
      try {
        const response = await fetch(`${API_BASE}/drone/land`, { method: 'POST' })
        const data = await response.json().catch(() => ({}))
        if (response.ok) this.addEvent('success', 'Landing')
        else this.addEvent('error', data.error || 'Land failed')
      } catch (e) {
        this.addEvent('error', `Land: ${e.message}`)
      }
    },
    async droneRtl() {
      try {
        const response = await fetch(`${API_BASE}/drone/rtl`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ reason: 'operator_request' }),
        })
        const data = await response.json().catch(() => ({}))
        if (response.ok) {
          this.rtlReason = 'operator_request'
          this.addEvent('warning', data.message || 'RTL initiated')
        } else {
          this.addEvent('error', data.error || 'RTL failed')
        }
      } catch (e) {
        this.addEvent('error', `RTL: ${e.message}`)
      }
    },
    addWaypoint(wp) {
      this.waypoints.push({ ...wp, altitude: wp.altitude || 50 })
      this.missionUploaded = false
      this.missionValid = false
      this.missionBlockReason = null
      this.addEvent('info', `WP${this.waypoints.length} added`)
      this.$nextTick(() => {
        if (this.$refs.mapComponent) {
          this.$refs.mapComponent.syncWaypoints(this.waypoints)
        }
      })
    },
    moveWaypoint({ index, lat, lon }) {
      if (this.waypoints[index]) {
        this.waypoints[index] = { ...this.waypoints[index], lat, lon }
        this.missionUploaded = false
        this.missionValid = false
        this.missionBlockReason = null
        this.addEvent('info', `WP${index + 1} moved`)
      }
    },
    removeWaypoint(index) {
      this.waypoints.splice(index, 1)
      this.missionUploaded = false
      this.missionValid = false
      this.missionBlockReason = null
      this.addEvent('info', `WP${index + 1} removed`)
    },
    clearWaypoints() {
      this.waypoints = []
      this.missionUploaded = false
      this.missionValid = false
      this.missionBlockReason = null
      this.addEvent('info', 'Waypoints cleared')
    },
    async validateMission() {
      if (this.waypoints.length < 2) {
        this.missionBlockReason = 'Need at least 2 waypoints'
        this.missionValid = false
        return
      }
      try {
        this.addEvent('info', 'Validating mission (NFZ)...')
        const response = await fetch(`${API_BASE}/mission/validate`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ waypoints: this.waypoints }),
        })
        const data = await response.json()
        if (data.valid) {
          this.missionValid = true
          this.missionBlockReason = null
          this.addEvent('success', `Valid — ${data.waypoints_count} WPs`)
        } else {
          this.missionValid = false
          this.missionBlockReason = data.nfz_blocked
            ? `Blocked by NFZ: ${data.error || 'No-Fly Zone'}`
            : (data.error || 'Validation failed')
          this.addEvent('error', this.missionBlockReason)
        }
      } catch (e) {
        this.missionValid = false
        this.missionBlockReason = e.message
        this.addEvent('error', `Validate: ${e.message}`)
      }
    },
    async uploadMission() {
      if (!this.missionValid) {
        await this.validateMission()
        if (!this.missionValid) return
      }
      try {
        this.addEvent('info', 'Uploading mission...')
        const response = await fetch(`${API_BASE}/mission/upload`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ waypoints: this.waypoints }),
        })
        const data = await response.json()
        if (response.ok && data.success !== false) {
          this.missionUploaded = true
          this.addEvent('success', `Uploaded (${data.mission_id || 'ok'})`)
          if (this.progressInterval) clearInterval(this.progressInterval)
          this.progressInterval = setInterval(this.updateMissionProgress, 1000)
        } else {
          this.addEvent('error', data.error || 'Upload failed')
        }
      } catch (e) {
        this.addEvent('error', `Upload: ${e.message}`)
      }
    },
    async exportPlan() {
      try {
        const response = await fetch(`${API_BASE}/mission/export-plan`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ waypoints: this.waypoints, name: 'Astana Training Mission' }),
        })
        const data = await response.json()
        if (data.success) {
          const blob = new Blob([JSON.stringify(data.plan, null, 2)], { type: 'application/json' })
          const url = URL.createObjectURL(blob)
          const link = document.createElement('a')
          link.href = url
          link.download = 'astana-mission.plan'
          link.click()
          URL.revokeObjectURL(url)
          this.addEvent('success', 'Exported .plan')
        } else {
          this.addEvent('error', data.error || 'Export failed')
        }
      } catch (e) {
        this.addEvent('error', `Export: ${e.message}`)
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
        this.addEvent('error', `Start: ${e.message}`)
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
        this.addEvent('error', `Pause: ${e.message}`)
      }
    },
    async resumeMission() {
      try {
        const response = await fetch(`${API_BASE}/mission/resume`, { method: 'POST' })
        if (response.ok) {
          this.missionRunning = true
          this.addEvent('success', 'Mission resumed')
        }
      } catch (e) {
        this.addEvent('error', `Resume: ${e.message}`)
      }
    },
    async abortMission() {
      try {
        const response = await fetch(`${API_BASE}/mission/abort`, { method: 'POST' })
        if (response.ok) {
          this.missionRunning = false
          this.missionUploaded = false
          this.missionValid = false
          if (this.progressInterval) clearInterval(this.progressInterval)
          this.addEvent('error', 'Mission aborted')
        }
      } catch (e) {
        this.addEvent('error', `Abort: ${e.message}`)
      }
    },
    async updateMissionProgress() {
      try {
        const response = await fetch(`${API_BASE}/mission/progress`)
        if (response.ok) this.missionProgress = await response.json()
      } catch {
        /* ignore */
      }
    },
    getBatteryClass(battery) {
      if (!battery) return 'critical'
      if (battery > 50) return 'good'
      if (battery > 20) return 'warning'
      return 'critical'
    },
    formatTime(timestamp) {
      if (!timestamp) return '--:--'
      return new Date(timestamp * 1000).toLocaleTimeString()
    },
    addEvent(type, message) {
      this.events.push({ type, message, timestamp: Date.now() / 1000 })
      if (this.events.length > 50) this.events.shift()
    },
  },
}
</script>

<style scoped>
* { margin: 0; padding: 0; box-sizing: border-box; }

#app {
  height: 100vh;
  display: flex;
  flex-direction: column;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background: #f0f4f8;
}

.navbar {
  background: linear-gradient(135deg, #1e40af 0%, #0369a1 100%);
  color: white;
  padding: 0.75rem 1.5rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
  box-shadow: 0 2px 6px rgba(0,0,0,.12);
}

.navbar-brand h1 { font-size: 1.25rem; font-weight: 700; }
.subtitle { font-size: 0.72rem; opacity: 0.85; margin-left: 0.5rem; }

.navbar-status { display: flex; gap: 0.5rem; }

.status-badge {
  padding: 0.35rem 0.75rem;
  border-radius: 16px;
  font-weight: 700;
  font-size: 0.75rem;
  letter-spacing: 0.03em;
}

.status-badge.connected { background: rgba(34,197,94,.25); color: #bbf7d0; }
.status-badge.disconnected { background: rgba(239,68,68,.25); color: #fecaca; }
.status-badge.warning { background: rgba(245,158,11,.25); color: #fde68a; }

.container {
  display: flex;
  flex: 1;
  gap: 0.75rem;
  padding: 0.75rem;
  overflow: hidden;
}

.map-panel {
  flex: 1;
  background: #fff;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 1px 4px rgba(0,0,0,.08);
}

.control-panel {
  width: 340px;
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
  overflow-y: auto;
  padding-right: 4px;
}

.panel {
  background: #fff;
  border-radius: 8px;
  padding: 1rem;
  box-shadow: 0 1px 4px rgba(0,0,0,.08);
}

.panel h2 {
  font-size: 0.95rem;
  margin-bottom: 0.75rem;
  font-weight: 700;
  color: #1e293b;
}

.flight-actions { display: flex; flex-direction: column; gap: 0.45rem; }

.btn-row { display: flex; gap: 0.4rem; }
.btn-row .btn { flex: 1; font-size: 0.78rem; }

.btn {
  padding: 0.45rem 0.6rem;
  border: none;
  border-radius: 6px;
  font-weight: 600;
  cursor: pointer;
  font-size: 0.82rem;
  transition: opacity 0.15s;
}

.btn:disabled { opacity: 0.45; cursor: not-allowed; }
.btn-primary { background: #2563eb; color: #fff; }
.btn-secondary { background: #e2e8f0; color: #1e293b; }
.btn-danger { background: #dc2626; color: #fff; }
.btn-block { width: 100%; margin-top: 0.35rem; }

.mission-tools { margin-bottom: 0.5rem; }

.wp-list {
  list-style: none;
  font-size: 0.72rem;
  margin: 0.5rem 0;
  max-height: 100px;
  overflow-y: auto;
}

.wp-list li {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 3px 0;
  border-bottom: 1px solid #f1f5f9;
  font-family: monospace;
}

.btn-icon {
  background: none;
  border: none;
  color: #dc2626;
  cursor: pointer;
  font-size: 0.85rem;
  padding: 0 4px;
}

.nfz-block {
  background: #fef2f2;
  border: 1px solid #fecaca;
  color: #b91c1c;
  padding: 0.5rem;
  border-radius: 6px;
  font-size: 0.78rem;
  margin: 0.5rem 0;
}

.mission-actions-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.4rem;
  margin-top: 0.5rem;
}

.mission-actions-grid.four { grid-template-columns: 1fr 1fr; }

.mission-progress { font-size: 0.82rem; margin-top: 0.5rem; color: #64748b; }
.mission-progress p { margin-bottom: 0.3rem; }

.progress-bar {
  height: 6px;
  background: #e2e8f0;
  border-radius: 3px;
  overflow: hidden;
  margin-bottom: 0.3rem;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #2563eb, #0369a1);
  transition: width 0.3s;
}

.safety-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.5rem;
  font-size: 0.82rem;
}

.safety-item { display: flex; flex-direction: column; gap: 2px; }
.safety-item label { font-size: 0.7rem; color: #64748b; font-weight: 600; text-transform: uppercase; }
.safety-item span { font-weight: 700; font-family: monospace; }
.safety-item .ok { color: #16a34a; }
.safety-item .warn { color: #d97706; }
.safety-item .good { color: #16a34a; }
.safety-item .warning { color: #d97706; }
.safety-item .critical { color: #dc2626; }

.video-placeholder {
  background: #0f172a;
  height: 100px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #64748b;
  border-radius: 6px;
}

.video-placeholder p { color: #94a3b8; font-weight: 600; font-size: 0.9rem; }
.video-placeholder small { font-size: 0.72rem; margin-top: 4px; }

.event-list { font-size: 0.78rem; max-height: 160px; overflow-y: auto; }

.event-item {
  padding: 0.35rem 0.5rem;
  margin-bottom: 0.35rem;
  border-left: 3px solid #e2e8f0;
  background: #f8fafc;
}

.event-item.error { border-left-color: #dc2626; }
.event-item.warning { border-left-color: #d97706; }
.event-item.info { border-left-color: #2563eb; }
.event-item.success { border-left-color: #16a34a; }
.event-item.system { border-left-color: #64748b; }

.event-time { font-family: monospace; color: #94a3b8; font-size: 0.68rem; margin-right: 0.4rem; }
.empty-state { text-align: center; color: #94a3b8; padding: 1rem; }
</style>
