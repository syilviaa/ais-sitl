<template>
  <div id="app" class="dashboard">
    <header class="navbar">
      <div class="navbar-brand">
        <h1>AIS SITL — Учебный полигон Астана</h1>
      </div>
      <div class="navbar-telemetry">
        <span class="chip" :class="getBatteryClass(telemetry.battery)">
          Бат {{ (telemetry.battery || 0).toFixed(0) }}%
        </span>
        <span class="chip">{{ modeLabel }}</span>
        <span class="chip" :class="telemetry.armed ? 'warn' : 'ok'">
          {{ telemetry.armed ? 'Моторы ВКЛ' : 'Моторы ВЫКЛ' }}
        </span>
        <span class="chip" :class="failsafe.running ? 'ok' : 'muted'">
          Failsafe {{ failsafe.running ? 'OK' : '—' }}
        </span>
      </div>
      <div class="navbar-status">
        <span :class="['status-badge', apiConnected ? 'connected' : 'disconnected']">
          API {{ apiConnected ? 'ОК' : 'ВЫКЛ' }}
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
        <section class="panel flight-panel">
          <h2>Управление</h2>
          <button
            @click="initializeDrone"
            class="btn btn-secondary btn-block"
            :disabled="droneReady"
          >
            {{ droneReady ? 'Подключено' : 'Подключить SITL' }}
          </button>
          <div class="btn-grid four">
            <button @click="droneTakeoff" class="btn btn-primary" :disabled="!droneReady">Взлёт</button>
            <button @click="droneHold" class="btn btn-secondary" :disabled="!droneReady">Удержание</button>
            <button @click="droneLand" class="btn btn-secondary" :disabled="!droneReady">Посадка</button>
            <button @click="droneRtl" class="btn btn-danger" :disabled="!droneReady">Домой</button>
          </div>
        </section>

        <section class="panel mission-panel">
          <h2>Миссия</h2>
          <div class="mission-row">
            <button
              @click="planMode = !planMode"
              :class="['btn', planMode ? 'btn-primary' : 'btn-secondary']"
            >
              {{ planMode ? 'План: клик на карте' : 'Планирование' }}
            </button>
            <span v-if="waypoints.length" class="wp-summary">{{ waypoints.length }} точек</span>
            <button
              v-if="waypoints.length && planMode"
              @click="clearWaypoints"
              class="btn btn-secondary btn-sm"
            >
              Очистить
            </button>
          </div>
          <div class="speed-row">
            <label for="cruise-speed">Скорость</label>
            <input
              id="cruise-speed"
              v-model.number="cruiseSpeed"
              type="range"
              min="3"
              max="18"
              step="1"
            />
            <span class="speed-value">{{ cruiseSpeed }} м/с</span>
            <button @click="applyFlightSpeed" class="btn btn-secondary btn-sm" :disabled="!droneReady">
              Применить
            </button>
          </div>
          <div class="speed-row">
            <label for="wp-altitude">Высота точек</label>
            <input
              id="wp-altitude"
              v-model.number="waypointAltitude"
              type="range"
              min="10"
              max="120"
              step="5"
            />
            <span class="speed-value">{{ waypointAltitude }} м</span>
          </div>
          <div v-if="missionBlockReason" class="nfz-block">{{ missionBlockReason }}</div>
          <div class="btn-grid three">
            <button @click="validateMission" class="btn btn-secondary">Проверить</button>
            <button @click="uploadMission" class="btn btn-primary" :disabled="!missionValid">Загрузить</button>
            <button @click="exportPlan" class="btn btn-secondary">Экспорт</button>
          </div>
          <div v-if="missionUploaded" class="mission-active">
            <div class="btn-grid four">
              <button @click="startMission" :disabled="missionRunning" class="btn btn-primary">Старт</button>
              <button @click="pauseMission" :disabled="!missionRunning" class="btn btn-secondary">Пауза</button>
              <button @click="resumeMission" :disabled="missionRunning" class="btn btn-secondary">Далее</button>
              <button @click="abortMission" class="btn btn-danger">Стоп</button>
            </div>
            <div class="mission-progress" v-if="missionProgress.total > 0">
              <div class="progress-bar">
                <div class="progress-fill" :style="{ width: missionProgress.percent + '%' }"></div>
              </div>
              <span class="progress-text">
                {{ missionProgress.current }}/{{ missionProgress.total }} · {{ missionProgress.percent.toFixed(0) }}%
              </span>
            </div>
          </div>
        </section>

        <section class="panel video-panel">
          <h2>Видео</h2>
          <div class="cv-runtime">
            <VisionOverlay
              :video-src="visionVideoSrc"
              :detections="vision.detections"
              :frame-width="vision.frameWidth"
              :frame-height="vision.frameHeight"
              :stream-status="vision.streamStatus"
            />
            <VisionPanel
              :camera-status="vision.cameraStatus"
              :model-status="vision.modelStatus"
              :stream-status="vision.streamStatus"
              :model-name="vision.modelName"
              :fps="vision.fps"
              :latency-ms="vision.latencyMs"
            />
            <VisionAlertsPanel />
          </div>
        </section>

        <section class="panel event-panel">
          <h2>Журнал</h2>
          <div class="event-list">
            <div v-if="events.length === 0" class="empty-state"><small>Событий нет</small></div>
            <div
              v-for="(event, idx) in events.slice(-4).reverse()"
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
import VisionOverlay from './components/VisionOverlay.vue'
import VisionPanel from './components/VisionPanel.vue'
import VisionAlertsPanel from './components/VisionAlertsPanel.vue'
import { onTelemetry, onConnectionStatus, normalizeTelemetry } from './services/telemetryBridge.js'
import { connectTelemetry, disconnectTelemetry, requestTelemetryStart } from './services/telemetrySocket.js'
import { onVisionDetection, onVisionAlert } from './services/visionSocket.js'

const API_BASE = import.meta.env.VITE_API_URL
  ? `${import.meta.env.VITE_API_URL.replace(/\/$/, '')}/api`
  : import.meta.env.DEV
    ? '/api'
    : 'http://127.0.0.1:5001/api'

export default {
  name: 'App',
  components: {
    MapComponent,
    VisionOverlay,
    VisionPanel,
    VisionAlertsPanel,
  },
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
      cruiseSpeed: 15,
      waypointAltitude: 50,
      missionRunning: false,
      missionBlockReason: null,
      missionProgress: { current: 0, total: 0, percent: 0 },
      waypoints: [],
      failsafe: { running: false, battery_warning: false, battery_critical: false },
      rtlReason: null,
      events: [],
      vision: {
        videoSrc: import.meta.env.VITE_VISION_STREAM_URL || '',
        detections: [],
        frameWidth: 1920,
        frameHeight: 1080,
        cameraStatus: 'disconnected',
        modelStatus: 'missing',
        streamStatus: 'stopped',
        modelName: '',
        fps: null,
        latencyMs: null,
        useMjpeg: false,
      },
      unsubTelemetry: null,
      unsubWsStatus: null,
      unsubVisionDet: null,
      unsubVisionAlert: null,
      restFallbackInterval: null,
      failsafeInterval: null,
      progressInterval: null,
      visionPollInterval: null,
    }
  },
  computed: {
    visionVideoSrc() {
      if (this.vision.videoSrc) return this.vision.videoSrc
      if (this.vision.useMjpeg && this.droneReady) {
        return `${API_BASE}/video/mjpeg`
      }
      return ''
    },
    wsStatusLabel() {
      const map = {
        connected: 'ЭФИР',
        reconnecting: 'ПОДКЛ',
        error: 'ОШИБКА',
        disconnected: 'ВЫКЛ',
      }
      return map[this.wsStatus] || this.wsStatus.toUpperCase()
    },
    modeLabel() {
      const modes = {
        hold: 'Удержание',
        manual: 'Ручной',
        auto: 'Авто',
        rtl: 'Домой',
        land: 'Посадка',
        takeoff: 'Взлёт',
        UNKNOWN: '—',
      }
      const m = (this.telemetry.mode || 'UNKNOWN').toLowerCase()
      return modes[m] || this.telemetry.mode || '—'
    },
    rtlReasonLabel() {
      if (!this.rtlReason) return '—'
      const map = {
        operator_request: 'Команда оператора',
        battery_low: 'Низкий заряд',
        link_loss: 'Потеря связи',
        nfz_breach: 'Зона NFZ',
      }
      return map[this.rtlReason] || this.rtlReason
    },
    wsStatusClass() {
      if (this.wsStatus === 'connected') return 'connected'
      if (this.wsStatus === 'reconnecting') return 'warning'
      if (this.wsStatus === 'error') return 'disconnected'
      return 'disconnected'
    },
  },
  mounted() {
    this.addEvent('system', 'Панель загружена — полигон Астана')
    this.loadNfzZones()
    this.initializeBackend()
    this.unsubTelemetry = onTelemetry((t) => {
      if (t) this.telemetry = { ...this.telemetry, ...t }
    })
    this.unsubWsStatus = onConnectionStatus((s) => {
      this.wsStatus = s
    })
    this.unsubVisionDet = onVisionDetection((event) => this.onVisionEvent(event))
    this.unsubVisionAlert = onVisionAlert((event) => this.onVisionEvent(event))
    connectTelemetry()
    this.startRestFallback()
    this.startFailsafePolling()
    this.startVisionPolling()
  },
  beforeUnmount() {
    if (this.unsubTelemetry) this.unsubTelemetry()
    if (this.unsubWsStatus) this.unsubWsStatus()
    if (this.unsubVisionDet) this.unsubVisionDet()
    if (this.unsubVisionAlert) this.unsubVisionAlert()
    disconnectTelemetry()
    if (this.restFallbackInterval) clearInterval(this.restFallbackInterval)
    if (this.failsafeInterval) clearInterval(this.failsafeInterval)
    if (this.progressInterval) clearInterval(this.progressInterval)
    if (this.visionPollInterval) clearInterval(this.visionPollInterval)
  },
  methods: {
    onVisionEvent(event) {
      if (!event?.event_id) return
      this.vision.modelStatus = 'ready'
      this.vision.cameraStatus = 'connected'
      this.vision.streamStatus = 'live'
      if (!this.vision.modelName) this.vision.modelName = 'yolov8n'
      const next = [event, ...this.vision.detections.filter((d) => d.event_id !== event.event_id)]
      this.vision.detections = next.slice(0, 12)
      if (event.processing_latency_ms != null) {
        this.vision.latencyMs = Number(event.processing_latency_ms)
      }
    },
    startVisionPolling() {
      const tick = async () => {
        try {
          const health = await fetch(`${API_BASE}/vision/health`)
          if (!health.ok) {
            this.vision.modelStatus = this.vision.modelStatus === 'ready' ? 'ready' : 'missing'
            return
          }
          const videoStatus = await fetch(`${API_BASE}/video/status`).catch(() => null)
          if (videoStatus?.ok) {
            const vs = await videoStatus.json()
            const live = Boolean(vs.running || vs.clients > 0 || vs.gstreamer_available)
            this.vision.useMjpeg = Boolean(vs.gstreamer_available)
            if (live && this.droneReady) {
              this.vision.cameraStatus = 'connected'
              this.vision.streamStatus = 'live'
            }
          }
          const latest = await fetch(`${API_BASE}/vision/latest?limit=8`)
          if (latest.ok) {
            const payload = await latest.json()
            if (Array.isArray(payload.events) && payload.events.length) {
              this.vision.detections = payload.events
              this.vision.modelStatus = 'ready'
              if (!this.vision.modelName) this.vision.modelName = 'yolov8n'
            }
          }
        } catch {
          /* vision offline must not break dashboard */
        }
      }
      tick()
      this.visionPollInterval = setInterval(tick, 2000)
    },
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
          this.addEvent('info', `Зоны NFZ: ${this.nfzGeoJson.features?.length || 0}`)
        }
      } catch {
        this.addEvent('warning', 'NFZ недоступен — локальный config')
        const local = await fetch('/config/nfz_zones.geojson').catch(() => null)
        if (local?.ok) this.nfzGeoJson = await local.json()
      }
    },
    async initializeBackend() {
      try {
        const response = await fetch(`${API_BASE}/health`)
        this.apiConnected = response.ok
        if (response.ok) this.addEvent('success', 'API подключён')
      } catch (e) {
        this.addEvent('error', `API: ${e.message}`)
      }
    },
    async initializeDrone() {
      try {
        this.addEvent('info', 'Подключение к SITL...')
        const response = await fetch(`${API_BASE}/drone/initialize`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ port: 14540, sitl_port: 14580 }),
        })
        const data = await response.json()
        if (data.success) {
          const readyRes = await fetch(`${API_BASE}/drone/wait-ready`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ timeout: 45 }),
          })
          const ready = await readyRes.json().catch(() => ({}))
          this.droneReady = true
          requestTelemetryStart()
          if (ready.success) {
            this.addEvent('success', 'SITL готов — дом Astana')
          } else {
            this.addEvent('warning', `SITL подключён, но не готов: ${ready.error || 'GPS/home'}`)
          }
          if (this.$refs.mapComponent) this.$refs.mapComponent.clearTrail()
        } else {
          this.addEvent('error', (data.hint || data.error || 'Ошибка подключения') + ' — ./scripts/start-px4-sitl.sh')
        }
      } catch (e) {
        this.addEvent('error', `Подключение: ${e.message}`)
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
        if (response.ok) this.addEvent('success', 'Взлёт 50 м')
        else this.addEvent('error', data.error || 'Взлёт не выполнен')
      } catch (e) {
        this.addEvent('error', `Взлёт: ${e.message}`)
      }
    },
    async droneHold() {
      try {
        const response = await fetch(`${API_BASE}/drone/hold`, { method: 'POST' })
        const data = await response.json().catch(() => ({}))
        if (response.ok) this.addEvent('info', 'Удержание позиции')
        else this.addEvent('error', data.error || 'Удержание не выполнено')
      } catch (e) {
        this.addEvent('error', `Удержание: ${e.message}`)
      }
    },
    async droneLand() {
      try {
        const response = await fetch(`${API_BASE}/drone/land`, { method: 'POST' })
        const data = await response.json().catch(() => ({}))
        if (response.ok) this.addEvent('success', 'Посадка')
        else this.addEvent('error', data.error || 'Посадка не выполнена')
      } catch (e) {
        this.addEvent('error', `Посадка: ${e.message}`)
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
          this.addEvent('warning', data.message || 'RTL — возврат домой')
        } else {
          this.addEvent('error', data.error || 'RTL не выполнен')
        }
      } catch (e) {
        this.addEvent('error', `RTL: ${e.message}`)
      }
    },
    addWaypoint(wp) {
      this.waypoints.push({ ...wp, altitude: this.waypointAltitude })
      this.missionUploaded = false
      this.missionValid = false
      this.missionBlockReason = null
      this.addEvent('info', `Точка ${this.waypoints.length} добавлена`)
    },
    moveWaypoint({ index, lat, lon }) {
      if (this.waypoints[index]) {
        this.waypoints[index] = { ...this.waypoints[index], lat, lon }
        this.missionUploaded = false
        this.missionValid = false
        this.missionBlockReason = null
        this.addEvent('info', `Точка ${index + 1} перемещена`)
      }
    },
    removeWaypoint(index) {
      this.waypoints.splice(index, 1)
      this.missionUploaded = false
      this.missionValid = false
      this.missionBlockReason = null
      this.addEvent('info', `Точка ${index + 1} удалена`)
    },
    clearWaypoints() {
      this.waypoints = []
      this.missionUploaded = false
      this.missionValid = false
      this.missionBlockReason = null
      this.addEvent('info', 'Маршрут очищен')
    },
    async validateMission() {
      if (this.waypoints.length < 2) {
        this.missionBlockReason = 'Нужно минимум 2 точки'
        this.missionValid = false
        return
      }
      try {
        this.addEvent('info', 'Проверка маршрута (NFZ)...')
        const response = await fetch(`${API_BASE}/mission/validate`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ waypoints: this.waypoints }),
        })
        const data = await response.json()
        if (data.valid) {
          this.missionValid = true
          this.missionBlockReason = null
          this.addEvent('success', `OK — ${data.waypoints_count} точек`)
        } else {
          this.missionValid = false
          this.missionBlockReason = data.nfz_blocked
            ? `Заблокировано NFZ: ${data.error || 'запретная зона'}`
            : (data.error || 'Ошибка проверки')
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
        this.addEvent('info', 'Загрузка маршрута...')
        const response = await fetch(`${API_BASE}/mission/upload`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ waypoints: this.waypoints, speed: this.cruiseSpeed }),
        })
        const data = await response.json()
        if (response.ok && data.success !== false) {
          this.missionUploaded = true
          this.addEvent('success', `Загружено (${data.mission_id || 'ok'})`)
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
          link.download = 'almaty-mission.plan'
          link.click()
          URL.revokeObjectURL(url)
          this.addEvent('success', 'Экспорт .plan')
        } else {
          this.addEvent('error', data.error || 'Export failed')
        }
      } catch (e) {
        this.addEvent('error', `Export: ${e.message}`)
      }
    },
    async applyFlightSpeed() {
      try {
        const response = await fetch(`${API_BASE}/drone/flight-speed`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ cruise_m_s: this.cruiseSpeed }),
        })
        const data = await response.json()
        if (response.ok && data.success) {
          this.addEvent('success', `Скорость ${this.cruiseSpeed} м/с применена`)
        } else {
          this.addEvent('error', `Скорость: ${data.error || 'ошибка'}`)
        }
      } catch (e) {
        this.addEvent('error', `Скорость: ${e.message}`)
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
  overflow: hidden;
}

.navbar {
  background: linear-gradient(135deg, #1e40af 0%, #0369a1 100%);
  color: white;
  padding: 0.45rem 1rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.75rem;
  box-shadow: 0 2px 6px rgba(0,0,0,.12);
  flex-shrink: 0;
}

.navbar-brand h1 { font-size: 1.05rem; font-weight: 700; white-space: nowrap; }

.navbar-telemetry {
  display: flex;
  gap: 0.35rem;
  flex-wrap: wrap;
  justify-content: center;
  flex: 1;
}

.chip {
  padding: 0.2rem 0.5rem;
  border-radius: 12px;
  font-size: 0.68rem;
  font-weight: 700;
  background: rgba(255,255,255,.15);
  font-family: monospace;
}

.chip.good { background: rgba(34,197,94,.3); }
.chip.warning { background: rgba(245,158,11,.35); }
.chip.critical { background: rgba(239,68,68,.35); }
.chip.ok { background: rgba(34,197,94,.25); }
.chip.warn { background: rgba(245,158,11,.35); }
.chip.muted { opacity: 0.7; }

.navbar-status { display: flex; gap: 0.35rem; flex-shrink: 0; }

.status-badge {
  padding: 0.25rem 0.55rem;
  border-radius: 12px;
  font-weight: 700;
  font-size: 0.68rem;
  letter-spacing: 0.03em;
}

.status-badge.connected { background: rgba(34,197,94,.25); color: #bbf7d0; }
.status-badge.disconnected { background: rgba(239,68,68,.25); color: #fecaca; }
.status-badge.warning { background: rgba(245,158,11,.25); color: #fde68a; }

.container {
  display: flex;
  flex: 1;
  gap: 0.5rem;
  padding: 0.5rem;
  overflow: hidden;
  min-height: 0;
}

.map-panel {
  flex: 1;
  min-width: 0;
  background: #fff;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 1px 4px rgba(0,0,0,.08);
}

.control-panel {
  width: 400px;
  flex-shrink: 0;
  display: grid;
  grid-template-rows: auto auto minmax(160px, 1.2fr) auto;
  gap: 0.4rem;
  overflow: hidden;
  min-height: 0;
}

.panel {
  background: #fff;
  border-radius: 8px;
  padding: 0.55rem 0.65rem;
  box-shadow: 0 1px 4px rgba(0,0,0,.08);
}

.panel h2 {
  font-size: 0.78rem;
  margin-bottom: 0.4rem;
  font-weight: 700;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.btn-grid {
  display: grid;
  gap: 0.3rem;
  margin-top: 0.35rem;
}

.btn-grid.four { grid-template-columns: repeat(4, 1fr); }
.btn-grid.three { grid-template-columns: repeat(3, 1fr); }

.btn {
  padding: 0.35rem 0.4rem;
  border: none;
  border-radius: 5px;
  font-weight: 600;
  cursor: pointer;
  font-size: 0.72rem;
  transition: opacity 0.15s;
}

.btn-sm { padding: 0.25rem 0.45rem; font-size: 0.68rem; }

.btn:disabled { opacity: 0.45; cursor: not-allowed; }
.btn-primary { background: #2563eb; color: #fff; }
.btn-secondary { background: #e2e8f0; color: #1e293b; }
.btn-danger { background: #dc2626; color: #fff; }
.btn-block { width: 100%; margin-top: 0.3rem; }

.mission-row {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  flex-wrap: wrap;
}

.mission-row .btn { flex: 1; min-width: 0; }

.speed-row {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  margin-top: 0.45rem;
  font-size: 0.68rem;
  color: var(--text-dim, #8fa3bf);
}

.speed-row input[type='range'] {
  flex: 1;
  min-width: 0;
  accent-color: var(--accent, #3ea6ff);
}

.speed-value {
  min-width: 3.6rem;
  text-align: right;
  font-variant-numeric: tabular-nums;
  color: var(--text, #e6edf6);
}

.wp-summary {
  font-size: 0.68rem;
  color: #64748b;
  font-weight: 600;
  white-space: nowrap;
}

.nfz-block {
  background: #fef2f2;
  border: 1px solid #fecaca;
  color: #b91c1c;
  padding: 0.3rem 0.45rem;
  border-radius: 5px;
  font-size: 0.68rem;
  margin-top: 0.35rem;
}

.mission-active { margin-top: 0.35rem; }

.mission-progress {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  margin-top: 0.3rem;
}

.progress-bar {
  flex: 1;
  height: 5px;
  background: #e2e8f0;
  border-radius: 3px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #2563eb, #0369a1);
  transition: width 0.3s;
}

.progress-text {
  font-size: 0.65rem;
  color: #64748b;
  white-space: nowrap;
  font-family: monospace;
}

.video-panel {
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.cv-runtime {
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
  min-height: 0;
}

.cv-runtime :deep(.vision-overlay) {
  min-height: 110px;
  max-height: 180px;
}

.cv-runtime :deep(.vision-alerts) {
  max-height: 110px;
  overflow-y: auto;
  border-top: 1px solid #e2e8f0;
  padding-top: 0.35rem;
}

.event-panel {
  min-height: 0;
  overflow: hidden;
}

.event-list {
  font-size: 0.68rem;
  overflow: hidden;
}

.event-item {
  padding: 0.2rem 0.35rem;
  margin-bottom: 0.2rem;
  border-left: 2px solid #e2e8f0;
  background: #f8fafc;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.event-item.error { border-left-color: #dc2626; }
.event-item.warning { border-left-color: #d97706; }
.event-item.info { border-left-color: #2563eb; }
.event-item.success { border-left-color: #16a34a; }
.event-item.system { border-left-color: #64748b; }

.event-time { font-family: monospace; color: #94a3b8; font-size: 0.62rem; margin-right: 0.3rem; }
.empty-state { text-align: center; color: #94a3b8; padding: 0.35rem; }
</style>
