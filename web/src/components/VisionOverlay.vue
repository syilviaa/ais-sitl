<template>
  <div class="vision-overlay">
    <!-- MJPEG (Gazebo relay) uses <img>; file/RTSP preview can use <video> -->
    <img
      v-if="videoSrc && isMjpeg"
      class="vision-video"
      :src="videoSrc"
      alt="CV video"
    />
    <video
      v-else-if="videoSrc"
      class="vision-video"
      :src="videoSrc"
      autoplay
      muted
      playsinline
    ></video>

    <div v-if="streamStatus !== 'live' || !videoSrc" class="stream-placeholder">
      <strong>{{ streamMessage }}</strong>
      <small>{{ videoSrc ? 'Waiting for frames' : 'Video source unavailable' }}</small>
    </div>

    <svg
      class="detection-layer"
      :viewBox="`0 0 ${frameWidth} ${frameHeight}`"
      preserveAspectRatio="xMidYMid slice"
      aria-label="Vision detections"
    >
      <g v-for="detection in validDetections" :key="detection.key">
        <rect
          data-testid="detection-box"
          class="detection-box"
          :x="detection.x"
          :y="detection.y"
          :width="detection.width"
          :height="detection.height"
        />
        <rect
          class="detection-label-bg"
          :x="detection.x"
          :y="detection.labelY - 28"
          :width="detection.labelWidth"
          height="32"
        />
        <text
          class="detection-label"
          :x="detection.x + 7"
          :y="detection.labelY - 5"
        >
          {{ detection.label }}
        </text>
      </g>
    </svg>
  </div>
</template>

<script>
export default {
  name: 'VisionOverlay',
  props: {
    videoSrc: { type: String, default: '' },
    detections: { type: Array, default: () => [] },
    frameWidth: { type: Number, default: 1920 },
    frameHeight: { type: Number, default: 1080 },
    streamStatus: { type: String, default: 'stopped' },
  },
  computed: {
    isMjpeg() {
      const src = (this.videoSrc || '').toLowerCase()
      return src.includes('mjpeg') || src.includes('/api/video/')
    },
    streamMessage() {
      const messages = {
        stopped: 'Stream stopped',
        reconnecting: 'Stream reconnecting',
        error: 'Stream error',
        live: 'Live',
      }
      return messages[this.streamStatus] || 'Stream unavailable'
    },
    validDetections() {
      return this.detections.flatMap((item, index) => {
        if (!Array.isArray(item?.bbox) || item.bbox.length !== 4) return []
        const [rawX1, rawY1, rawX2, rawY2] = item.bbox.map(Number)
        if (![rawX1, rawY1, rawX2, rawY2].every(Number.isFinite)) return []

        const x1 = Math.max(0, Math.min(this.frameWidth, rawX1))
        const y1 = Math.max(0, Math.min(this.frameHeight, rawY1))
        const x2 = Math.max(0, Math.min(this.frameWidth, rawX2))
        const y2 = Math.max(0, Math.min(this.frameHeight, rawY2))
        if (x2 <= x1 || y2 <= y1) return []

        const className = item.class_name || 'Unknown'
        const confidence = Number(item.confidence)
        const percentage = Number.isFinite(confidence)
          ? Math.round(confidence * 100)
          : 0
        const label = `${className} ${percentage}%`

        return [{
          key: item.event_id || `${className}-${index}`,
          x: x1,
          y: y1,
          width: x2 - x1,
          height: y2 - y1,
          label,
          labelY: Math.max(y1, 32),
          labelWidth: Math.max(150, label.length * 22),
        }]
      })
    },
  },
}
</script>

<style scoped>
.vision-overlay {
  position: relative;
  width: 100%;
  height: 100%;
  min-height: 120px;
  overflow: hidden;
  border-radius: 6px;
  background: #0f172a;
}

.vision-video,
.detection-layer,
.stream-placeholder {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}

.vision-video {
  object-fit: cover;
  object-position: center;
  background: #020617;
}
.detection-layer { pointer-events: none; }

.stream-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  color: #cbd5e1;
  background: #0f172a;
  z-index: 1;
}

.stream-placeholder small { color: #64748b; }

.detection-box {
  fill: none;
  stroke: #22c55e;
  stroke-width: 5;
  vector-effect: non-scaling-stroke;
}

.detection-label-bg { fill: rgba(15, 23, 42, 0.88); }
.detection-label {
  fill: #f8fafc;
  font: 700 22px ui-monospace, SFMono-Regular, Menlo, monospace;
}
</style>
