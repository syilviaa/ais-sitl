<template>
  <section class="vision-alerts">
    <div class="alerts-heading">
      <strong>CV alerts</strong>
      <span :class="['socket-state', status]">{{ status }}</span>
    </div>
    <p v-if="lastError" class="vision-error">{{ lastError }}</p>
    <p v-if="alerts.length === 0" class="empty-alerts">No detections</p>
    <a
      v-for="alert in alerts"
      :key="alert.event_id"
      :href="snapshotUrl(alert)"
      target="_blank"
      rel="noopener"
      class="vision-alert"
    >
      <span class="alert-primary">
        <b>{{ alert.class_name }}</b>
        <b>{{ confidence(alert.confidence) }}</b>
      </span>
      <span>{{ utc(alert.timestamp) }}</span>
      <span>{{ coordinate(alert.latitude) }}, {{ coordinate(alert.longitude) }}</span>
      <span class="snapshot-link">open snapshot →</span>
    </a>
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

export default {
  name: 'VisionAlertsPanel',
  data() {
    return {
      alerts: [],
      status: 'disconnected',
      lastError: null,
      unsubscribers: [],
    }
  },
  mounted() {
    this.unsubscribers = [
      onVisionStatus((status) => { this.status = status }),
      onVisionDetection(this.pushAlert),
      onVisionAlert(this.pushAlert),
      onVisionError((message) => { this.lastError = message }),
    ]
    connectVision()
    this.loadLatest()
  },
  beforeUnmount() {
    this.unsubscribers.forEach((unsubscribe) => unsubscribe())
    disconnectVision()
  },
  methods: {
    async loadLatest() {
      try {
        const response = await fetch(`${API_BASE}/vision/latest?limit=10`)
        if (!response.ok) return
        const payload = await response.json()
        if (Array.isArray(payload.events)) this.alerts = payload.events
      } catch {
        /* Vision API being offline must not break the main dashboard. */
      }
    },
    pushAlert(alert) {
      if (!alert?.event_id) return
      if (!Number.isFinite(alert.latitude) || !Number.isFinite(alert.longitude)) {
        this.lastError = `Rejected event without GPS: ${alert.event_id}`
        return
      }
      this.alerts = [
        alert,
        ...this.alerts.filter((item) => item.event_id !== alert.event_id),
      ].slice(0, 30)
      this.lastError = null
    },
    snapshotUrl(alert) {
      return `${API_BASE}/vision/snapshots/${alert.event_id}.jpg`
    },
    confidence(value) {
      return `${Math.round(Number(value) * 100)}%`
    },
    coordinate(value) {
      return Number(value).toFixed(5)
    },
    utc(value) {
      try {
        return new Date(value).toISOString()
      } catch {
        return String(value || '—')
      }
    },
  },
}
</script>

<style scoped>
.vision-alerts { margin-top: .5rem; border-top: 1px solid #e2e8f0; padding-top: .5rem; }
.alerts-heading, .alert-primary { display: flex; justify-content: space-between; gap: .5rem; }
.alerts-heading { align-items: center; margin-bottom: .35rem; font-size: .72rem; }
.socket-state { padding: .1rem .35rem; border-radius: 8px; background: #fee2e2; color: #991b1b; }
.socket-state.connected { background: #dcfce7; color: #166534; }
.socket-state.reconnecting { background: #fef3c7; color: #92400e; }
.vision-alert { display: flex; flex-direction: column; gap: .1rem; padding: .35rem; margin-top: .25rem; border: 1px solid #e2e8f0; border-radius: 5px; color: #475569; text-decoration: none; font: .62rem monospace; }
.vision-alert:hover { background: #eff6ff; border-color: #93c5fd; }
.alert-primary { color: #0f172a; font-size: .7rem; }
.snapshot-link { color: #2563eb; }
.vision-error { color: #b91c1c; font-size: .62rem; }
.empty-alerts { color: #94a3b8; text-align: center; font-size: .65rem; }
</style>
