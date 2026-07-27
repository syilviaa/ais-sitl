<template>
  <div class="video-wrap">
    <img
      v-show="useRealVideo && !videoError && hasLiveFrame"
      ref="videoImg"
      class="video-real"
      alt="Камера Gazebo"
      @load="onVideoLoad"
      @error="onVideoError"
    />
    <canvas
      v-show="!useRealVideo || videoError || !hasLiveFrame"
      ref="canvas"
      class="video-canvas"
      width="640"
      height="360"
    />
    <div v-if="!active" class="video-overlay idle">
      <p>Нет видеопотока</p>
      <small>{{ idleHint }}</small>
    </div>
    <div v-else-if="useRealVideo && !hasLiveFrame && !videoError" class="video-overlay waiting">
      Ожидание камеры Gazebo… · синтетический FPV
    </div>
    <div v-else-if="active" class="video-overlay live">
      <span class="live-dot" /> ЭФИР · {{ sourceLabel }}
    </div>
    <div v-if="active && useRealVideo && hasLiveFrame && !videoError" class="video-hud">
      <span>ВЫС {{ hudAlt }} м</span>
      <span>СКР {{ hudSpeed }} м/с</span>
      <span>КУР {{ hudYaw }}°</span>
    </div>
  </div>
</template>

<script>
export default {
  name: 'VideoStream',
  props: {
    telemetry: { type: Object, default: () => ({}) },
    active: { type: Boolean, default: false },
    apiBase: { type: String, default: '/api' },
  },
  data() {
    return {
      rafId: null,
      useRealVideo: false,
      videoError: false,
      gazeboAvailable: false,
      hasLiveFrame: false,
      statusPoll: null,
      framePoll: null,
      objectUrl: null,
    }
  },
  computed: {
    snapshotBase() {
      const base = this.apiBase.replace(/\/api\/?$/, '')
      return `${base}/api/video/snapshot`
    },
    sourceLabel() {
      if (this.useRealVideo && !this.videoError && this.hasLiveFrame) return 'Gazebo'
      if (this.useRealVideo && !this.videoError) return 'Gazebo · ожидание'
      return 'SIH синт.'
    },
    idleHint() {
      if (this.gazeboAvailable) {
        return 'Gazebo + backend: ./scripts/start-px4-gazebo.sh и start-backend.sh'
      }
      return 'SIH без камеры — синтетический FPV после подключения SITL'
    },
    hudAlt() {
      return (this.telemetry?.alt ?? 0).toFixed(1)
    },
    hudSpeed() {
      const t = this.telemetry || {}
      const spd = t.speed ?? Math.hypot(t.vx || 0, t.vy || 0, t.vz || 0)
      return spd.toFixed(1)
    },
    hudYaw() {
      return (this.telemetry?.yaw ?? 0).toFixed(0)
    },
  },
  watch: {
    active(val) {
      if (val) {
        this.checkVideoStatus()
        this.startFramePoll()
      } else {
        this.stopSynthetic()
        this.stopFramePoll()
      }
    },
    telemetry: {
      deep: true,
      handler() {
        if (this.active && (!this.useRealVideo || this.videoError)) {
          this.drawFrame()
        }
      },
    },
  },
  mounted() {
    this.checkVideoStatus()
    this.statusPoll = setInterval(this.checkVideoStatus, 3000)
    if (this.active) this.startFramePoll()
    else if (!this.active) this.drawIdle()
  },
  beforeUnmount() {
    this.stopSynthetic()
    this.stopFramePoll()
    if (this.statusPoll) clearInterval(this.statusPoll)
  },
  methods: {
    async checkVideoStatus() {
      try {
        const res = await fetch(`${this.apiBase.replace(/\/$/, '')}/video/status`)
        if (!res.ok) return
        const data = await res.json()
        this.gazeboAvailable = Boolean(data.gstreamer_available)
        this.hasLiveFrame = Boolean(data.has_frame)
        if (data.gstreamer_available) {
          this.useRealVideo = true
          this.videoError = false
          this.stopSynthetic()
          if (this.active) this.startFramePoll()
          return
        }
        if (this.active && !this.useRealVideo) this.startSynthetic()
      } catch {
        if (this.active && !this.useRealVideo) this.startSynthetic()
      }
    },
    startFramePoll() {
      if (this.framePoll || !this.useRealVideo) return
      this.framePoll = setInterval(() => this.fetchSnapshot(), 200)
      this.fetchSnapshot()
    },
    stopFramePoll() {
      if (this.framePoll) clearInterval(this.framePoll)
      this.framePoll = null
      if (this.objectUrl) {
        URL.revokeObjectURL(this.objectUrl)
        this.objectUrl = null
      }
    },
    async fetchSnapshot() {
      if (!this.useRealVideo || !this.active) return
      try {
        const res = await fetch(`${this.snapshotBase}?t=${Date.now()}`)
        if (res.status === 503) {
          // Relay is up, Gazebo has not produced a frame yet — keep polling.
          this.hasLiveFrame = false
          if (!this.rafId) this.startSynthetic()
          return
        }
        if (!res.ok) throw new Error(`snapshot ${res.status}`)
        const blob = await res.blob()
        // Downscaled frames of a flat Gazebo scene compress very small.
        if (blob.size < 400) return
        if (this.objectUrl) URL.revokeObjectURL(this.objectUrl)
        this.objectUrl = URL.createObjectURL(blob)
        const img = this.$refs.videoImg
        if (img) img.src = this.objectUrl
      } catch {
        this.onVideoError()
      }
    },
    onVideoLoad() {
      this.videoError = false
      this.hasLiveFrame = true
      this.stopSynthetic()
    },
    onVideoError() {
      this.videoError = true
      this.stopFramePoll()
      if (this.active) this.startSynthetic()
    },
    startSynthetic() {
      this.stopSynthetic()
      const tick = () => {
        this.drawFrame()
        this.rafId = requestAnimationFrame(tick)
      }
      this.rafId = requestAnimationFrame(tick)
    },
    stopSynthetic() {
      if (this.rafId) cancelAnimationFrame(this.rafId)
      this.rafId = null
    },
    drawIdle() {
      const canvas = this.$refs.canvas
      if (!canvas) return
      const ctx = canvas.getContext('2d')
      const { width: w, height: h } = canvas
      ctx.fillStyle = '#0f172a'
      ctx.fillRect(0, 0, w, h)
      ctx.fillStyle = '#64748b'
      ctx.font = '600 15px system-ui, sans-serif'
      ctx.textAlign = 'center'
      ctx.fillText('Видеопоток', w / 2, h / 2)
    },
    drawFrame() {
      const canvas = this.$refs.canvas
      if (!canvas || !this.active) return
      const ctx = canvas.getContext('2d')
      const { width: w, height: h } = canvas
      const t = this.telemetry || {}
      const pitch = (t.pitch || 0) * (Math.PI / 180)
      const roll = (t.roll || 0) * (Math.PI / 180)
      const yaw = t.yaw || 0
      const alt = t.alt ?? 0
      const spd = t.speed ?? Math.hypot(t.vx || 0, t.vy || 0)

      ctx.save()
      ctx.translate(w / 2, h / 2)
      ctx.rotate(-roll)
      const horizonY = pitch * (h / 2.2)
      ctx.fillStyle = '#1e3a5f'
      ctx.fillRect(-w, -h, w * 2, h + horizonY)
      ctx.fillStyle = '#14532d'
      ctx.fillRect(-w, horizonY, w * 2, h * 2)
      ctx.strokeStyle = 'rgba(255,255,255,0.85)'
      ctx.lineWidth = 2
      ctx.beginPath()
      ctx.moveTo(-w, horizonY)
      ctx.lineTo(w, horizonY)
      ctx.stroke()
      ctx.restore()

      ctx.fillStyle = 'rgba(0,0,0,0.55)'
      ctx.fillRect(8, 8, 168, 72)
      ctx.fillStyle = '#e2e8f0'
      ctx.font = '600 13px monospace'
      ctx.textAlign = 'left'
      ctx.fillText(`ВЫС ${alt.toFixed(1)} м`, 16, 28)
      ctx.fillText(`СКР ${spd.toFixed(1)} м/с`, 16, 46)
      ctx.fillText(`КУР ${yaw.toFixed(0)}°`, 16, 64)
    },
  },
}
</script>

<style scoped>
.video-wrap {
  position: relative;
  border-radius: 8px;
  overflow: hidden;
  background: #0f172a;
  aspect-ratio: 16 / 9;
}
.video-real,
.video-canvas {
  width: 100%;
  height: 100%;
  display: block;
  object-fit: cover;
}
.video-overlay {
  position: absolute;
  pointer-events: none;
}
.video-overlay.idle {
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-end;
  padding-bottom: 12px;
  background: linear-gradient(transparent 40%, rgba(0, 0, 0, 0.75));
}
.video-overlay.idle p {
  color: #94a3b8;
  font-weight: 600;
  font-size: 0.85rem;
  margin: 0;
}
.video-overlay.idle small {
  color: #cbd5e1;
  font-size: 0.68rem;
  text-align: center;
  max-width: 90%;
  margin-top: 4px;
}
.video-overlay.waiting {
  top: 8px;
  right: 8px;
  background: rgba(15, 23, 42, 0.85);
  color: #cbd5e1;
  font-size: 0.68rem;
  font-weight: 600;
  padding: 3px 8px;
  border-radius: 4px;
}
.video-overlay.live {
  top: 8px;
  right: 8px;
  background: rgba(220, 38, 38, 0.85);
  color: #fff;
  font-size: 0.7rem;
  font-weight: 700;
  padding: 3px 8px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  gap: 5px;
}
.live-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #fff;
  animation: pulse 1s infinite;
}
@keyframes pulse {
  50% { opacity: 0.4; }
}
.video-hud {
  position: absolute;
  left: 8px;
  bottom: 8px;
  display: flex;
  flex-direction: column;
  gap: 2px;
  background: rgba(0, 0, 0, 0.55);
  color: #e2e8f0;
  font: 600 12px monospace;
  padding: 6px 10px;
  border-radius: 4px;
  pointer-events: none;
}
</style>
