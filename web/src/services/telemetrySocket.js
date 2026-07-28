import { io } from 'socket.io-client'

const UPDATE_INTERVAL_MS = 100

function normalizeTelemetry(payload) {
  return {
    timestamp: payload.timestamp,
    lat: payload.position?.lat,
    lon: payload.position?.lon,
    alt: payload.position?.alt_agl,
    vx: payload.velocity?.vx,
    vy: payload.velocity?.vy,
    vz: payload.velocity?.vz,
    speed: payload.velocity?.speed,
    battery: payload.battery?.percent,
    gps_status: payload.gps?.fix,
    satellites: payload.gps?.satellites,
    mode: payload.state?.flight_mode,
    armed: payload.state?.armed,
    latency_ms: payload.latency_ms,
  }
}

export function createTelemetrySocket({
  url,
  onStatus = () => {},
  onTelemetry = () => {},
  onError = () => {},
}) {
  const socket = io(url, {
    autoConnect: false,
    reconnection: true,
  })

  let closed = false
  let lastUpdateAt = 0
  let pendingTelemetry = null
  let updateTimer = null

  const deliverTelemetry = () => {
    updateTimer = null
    if (closed || !pendingTelemetry) return

    const payload = pendingTelemetry
    pendingTelemetry = null
    lastUpdateAt = Date.now()
    onTelemetry(normalizeTelemetry(payload))
  }

  socket.on('connected', () => {
    onStatus('connected')
    socket.emit('start_telemetry')
  })

  socket.on('telemetry', (payload) => {
    pendingTelemetry = payload
    const remaining = UPDATE_INTERVAL_MS - (Date.now() - lastUpdateAt)

    if (remaining <= 0 && !updateTimer) {
      deliverTelemetry()
    } else if (!updateTimer) {
      updateTimer = setTimeout(deliverTelemetry, remaining)
    }
  })

  socket.on('telemetry_error', (error) => {
    const message = error?.message || 'Telemetry stream error'
    onStatus('error')
    onError(message)
  })

  socket.on('connect_error', (error) => {
    onStatus('error')
    onError(error.message)
  })

  socket.on('disconnect', (reason) => {
    if (!closed && reason !== 'io client disconnect') {
      onStatus('reconnecting')
    }
  })

  socket.io.on('reconnect_attempt', () => {
    if (!closed) onStatus('reconnecting')
  })

  const close = () => {
    if (closed) return
    closed = true

    if (updateTimer) clearTimeout(updateTimer)
    updateTimer = null
    pendingTelemetry = null

    if (socket.connected) socket.emit('stop_telemetry')
    socket.disconnect()
  }

  return {
    connect() {
      if (closed) return
      onStatus('reconnecting')
      socket.connect()
    },
    start() {
      if (!closed && socket.connected) socket.emit('start_telemetry')
    },
    close,
  }
}
