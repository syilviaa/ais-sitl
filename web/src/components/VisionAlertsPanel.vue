<template>
  <section class="panel vision-alerts-panel">
    <div class="panel-head">
      <h2>CV Alerts</h2>
      <span :class="['status-pill', statusClass]">{{ statusLabel }}</span>
    </div>
    <div v-if="lastError" class="cv-error">{{ lastError }}</div>
    <div class="alert-list">
      <div v-if="alerts.length === 0" class="empty-state"><small>No detections</small></div>
      <button
        v-for="alert in alerts"
        :key="alert.event_id"
        type="button"
        class="alert-item"
        @click="openSnapshot(alert)"
      >
        <div class="alert-top">
          <span class="alert-class">{{ alert.class_name }}</span>
          <span class="alert-conf">{{ formatConfidence(alert.confidence) }}</span>
        </div>
        <div class="alert-meta">
          <span>{{ formatUtc(alert.timestamp) }}</span>
          <span>{{ formatCoord(alert.latitude) }}, {{ formatCoord(alert.longitude) }}</span>
        </div>
        <div class="alert-snap">snapshot →</div>
      </button>
    </div>
    <div v-if="snapshotPreview" class="snapshot-modal" @click.self="snapshotPreview = null">
      <div class="snapshot-card">
        <div class="snapshot-head">
          <strong>{{ snapshotPreview.class_name }}</strong>
          <button type="button" class="btn-close" @click="snapshotPreview = null">×</button>
        </div>
        <img v-if="snapshotSrc" :src="snapshotSrc" class="snapshot-img" alt="snapshot" />
        <p v-else class="empty-state">Snapshot unavailable</p>
        <p class="snapshot-id">{{ snapshotPreview.event_id }}</p>
      </div>
    </div>
  </section>
</template>

<script>
import {
  connectVision,
  disconnectVision,
  onVisionAlert,
  onVisionDetection,
  onVisionError,
  onVisionStatus,
} from '../services/visionSocket.js'

const API_BASE = import.meta.env.VITE_API_URL
  ? `${import.meta.env.VITE_API_URL.replace(/\/$/, '')}/api`
  : import.meta.env.DEV
    ? '/api'
    : 'http://127.0.0.1:5001/api'

const MAX_ALERTS = 30

export default {
  name: 'VisionAlertsPanel',
  data() {
    return {
      alerts: [],
      status: 'disconnected',
      lastError: null,
      snapshotPreview: null,
      unsubscribers: [],
    }
  },
  computed: {
    statusLabel() {
      return (
        {
          connected: 'WS ON',
          reconnecting: '…',
          error: 'ERR',
          disconnected: 'OFF',
        }[this.status] || this.status
      )
    },
    statusClass() {
      if (this.status === 'connected') return 'ok'
      if (this.status === 'reconnecting') return 'warn'
      return 'bad'
    },
    snapshotSrc() {
      const a = this.snapshotPreview
      if (!a) return null
      if (a.snapshot_url?.startsWith('http') || a.snapshot_url?.startsWith('data:')) {
        return a.snapshot_url
      }
      return `${API_BASE}/vision/snapshot/${a.event_id}`
    },
  },
  mounted() {
    this.unsubscribers = [
      onVisionStatus((s) => {
        this.status = s
      }),
      onVisionDetection((e) => this.pushAlert(e)),
      onVisionAlert((e) => this.pushAlert(e)),
      onVisionError((msg) => {
        this.lastError = msg
      }),
    ]
    connectVision()
    this.loadLatest()
  },
  beforeUnmount() {
    this.unsubscribers.forEach((u) => u && u())
    disconnectVision()
  },
  methods: {
    async loadLatest() {
      try {
        const res = await fetch(`${API_BASE}/vision/latest?limit=10`)
        if (!res.ok) return
        const data = await res.json()
        if (data.success && Array.isArray(data.events)) {
          this.alerts = data.events.slice(0, MAX_ALERTS)
        }
      } catch {
        /* dashboard stays up if vision API offline */
      }
    },
    pushAlert(event) {
      if (!event?.event_id) return
      if (!Number.isFinite(event.latitude) || !Number.isFinite(event.longitude)) {
        this.lastError = `Rejected event without GPS: ${event.event_id}`
        return
      }
      const idx = this.alerts.findIndex((a) => a.event_id === event.event_id)
      if (idx >= 0) this.alerts.splice(idx, 1, event)
      else {
        this.alerts.unshift(event)
        if (this.alerts.length > MAX_ALERTS) this.alerts.pop()
      }
      this.lastError = null
    },
    openSnapshot(alert) {
      this.snapshotPreview = alert
    },
    formatConfidence(c) {
      if (c == null || Number.isNaN(Number(c))) return '—'
      return `${Math.round(Number(c) * 100)}%`
    },
    formatUtc(ts) {
      if (!ts) return '—'
      try {
        return new Date(ts).toISOString().replace('T', ' ').replace('.000Z', 'Z')
      } catch {
        return String(ts)
      }
    },
    formatCoord(v) {
      if (v == null || Number.isNaN(Number(v))) return '—'
      return Number(v).toFixed(5)
    },
  },
}
</script>

<style scoped>
.vision-alerts-panel { min-height: 0; display: flex; flex-direction: column; overflow: hidden; }
.panel-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.35rem; }
.panel-head h2 { margin: 0; font-size: 0.95rem; }
.status-pill { font-size: 0.65rem; font-weight: 700; padding: 0.15rem 0.4rem; border-radius: 10px; font-family: monospace; }
.status-pill.ok { background: #dcfce7; color: #166534; }
.status-pill.warn { background: #fef3c7; color: #92400e; }
.status-pill.bad { background: #fee2e2; color: #991b1b; }
.cv-error { background: #fef2f2; border: 1px solid #fecaca; color: #b91c1c; padding: 0.25rem 0.4rem; border-radius: 5px; font-size: 0.7rem; margin-bottom: 0.35rem; }
.alert-list { overflow-y: auto; flex: 1; min-height: 0; }
.alert-item { display: block; width: 100%; text-align: left; border: 1px solid #e2e8f0; background: #f8fafc; border-radius: 6px; padding: 0.4rem 0.5rem; margin-bottom: 0.35rem; cursor: pointer; }
.alert-item:hover { border-color: #93c5fd; background: #eff6ff; }
.alert-top { display: flex; justify-content: space-between; font-size: 0.8rem; font-weight: 700; }
.alert-conf { color: #2563eb; font-family: monospace; }
.alert-meta { display: flex; flex-direction: column; gap: 0.1rem; margin-top: 0.2rem; font-size: 0.65rem; color: #64748b; font-family: monospace; }
.alert-snap { margin-top: 0.15rem; font-size: 0.65rem; color: #2563eb; font-weight: 600; }
.empty-state { text-align: center; color: #94a3b8; padding: 0.4rem; }
.snapshot-modal { position: fixed; inset: 0; background: rgba(15, 23, 42, 0.55); display: flex; align-items: center; justify-content: center; z-index: 1000; padding: 1rem; }
.snapshot-card { background: #fff; border-radius: 10px; padding: 0.75rem; max-width: 420px; width: 100%; }
.snapshot-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem; }
.btn-close { border: none; background: #e2e8f0; width: 1.6rem; height: 1.6rem; border-radius: 50%; cursor: pointer; }
.snapshot-img { width: 100%; max-height: 280px; object-fit: contain; background: #0f172a; border-radius: 6px; }
.snapshot-id { margin-top: 0.4rem; font-size: 0.62rem; color: #94a3b8; font-family: monospace; word-break: break-all; }
</style>
