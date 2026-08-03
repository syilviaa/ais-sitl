<template>
  <div class="vision-panel">
    <div
      v-for="row in statusRows"
      :key="row.key"
      :data-testid="`${row.key}-status`"
      :class="['state-row', row.available ? 'available' : 'unavailable']"
    >
      <span class="state-dot" aria-hidden="true"></span>
      <span class="state-name">{{ row.name }}</span>
      <strong>{{ row.label }}</strong>
    </div>

    <div class="vision-metrics">
      <div>
        <small>Model</small>
        <strong>{{ modelName || '—' }}</strong>
      </div>
      <div>
        <small>Throughput</small>
        <strong>{{ formattedFps }}</strong>
      </div>
      <div>
        <small>Latency</small>
        <strong :class="{ warning: latencyMs > 1000 }">{{ formattedLatency }}</strong>
      </div>
    </div>
  </div>
</template>

<script>
const LABELS = {
  camera: {
    connected: 'Connected',
    disconnected: 'Disconnected',
    error: 'Camera error',
  },
  model: {
    ready: 'Ready',
    loading: 'Loading',
    missing: 'Model missing',
    error: 'Model error',
  },
  stream: {
    live: 'Live',
    reconnecting: 'Reconnecting',
    stopped: 'Stopped',
    error: 'Stream error',
  },
}

export default {
  name: 'VisionPanel',
  props: {
    cameraStatus: { type: String, default: 'disconnected' },
    modelStatus: { type: String, default: 'missing' },
    streamStatus: { type: String, default: 'stopped' },
    modelName: { type: String, default: '' },
    fps: { type: Number, default: null },
    latencyMs: { type: Number, default: null },
  },
  computed: {
    statusRows() {
      return [
        this.statusRow('camera', 'Camera', this.cameraStatus, 'connected'),
        this.statusRow('model', 'Detector', this.modelStatus, 'ready'),
        this.statusRow('stream', 'Stream', this.streamStatus, 'live'),
      ]
    },
    formattedFps() {
      return Number.isFinite(this.fps) ? `${this.fps.toFixed(1)} FPS` : '—'
    },
    formattedLatency() {
      return Number.isFinite(this.latencyMs) ? `${Math.round(this.latencyMs)} ms` : '—'
    },
  },
  methods: {
    statusRow(key, name, value, availableValue) {
      return {
        key,
        name,
        label: LABELS[key][value] || 'Unknown',
        available: value === availableValue,
      }
    },
  },
}
</script>

<style scoped>
.vision-panel { display: grid; gap: 8px; }

.state-row {
  display: grid;
  grid-template-columns: 10px 1fr auto;
  align-items: center;
  gap: 8px;
  font-size: 0.78rem;
}

.state-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #ef4444;
}

.state-row.available .state-dot { background: #22c55e; }
.state-name { color: #64748b; }
.state-row.unavailable strong { color: #b91c1c; }

.vision-metrics {
  display: grid;
  grid-template-columns: 1.4fr 1fr 1fr;
  gap: 6px;
  margin-top: 4px;
}

.vision-metrics div {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
  padding: 7px;
  border-radius: 6px;
  background: #f8fafc;
}

.vision-metrics small { color: #64748b; font-size: 0.65rem; }
.vision-metrics strong {
  overflow: hidden;
  font: 700 0.72rem ui-monospace, SFMono-Regular, Menlo, monospace;
  text-overflow: ellipsis;
}
.vision-metrics .warning { color: #b91c1c; }
</style>
