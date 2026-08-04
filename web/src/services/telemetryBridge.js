/**
 * UI telemetry bridge — Мерей.
 */

const listeners = new Set()
let connectionStatus = 'disconnected'
let statusListeners = new Set()

export function onTelemetry(callback) {
  listeners.add(callback)
  return () => listeners.delete(callback)
}
export function pushTelemetry(payload) {
  listeners.forEach((cb) => {
    try {
      cb(normalizeTelemetry(payload))
    } catch (err) {
      console.error('telemetryBridge listener error', err)
    }
  })
}

export function setConnectionStatus(status) {
  connectionStatus = status
  statusListeners.forEach((cb) => cb(status))
}

export function onConnectionStatus(callback) {
  statusListeners.add(callback)
  callback(connectionStatus)
  return () => statusListeners.delete(callback)
}

export function getConnectionStatus() {
  return connectionStatus
}

function normalizeBattery(raw) {
  if (raw == null || Number.isNaN(Number(raw))) return 100
  const value = Number(raw)
  if (value > 100) return Math.min(100, value / 100)
  return Math.max(0, Math.min(100, value))
}

function groundSpeed(raw, vel) {
  const vx = Number(vel.vx ?? raw.vx ?? 0)
  const vy = Number(vel.vy ?? raw.vy ?? 0)
  const vz = Number(vel.vz ?? raw.vz ?? 0)
  if (raw.ground_speed_m_s != null && !Number.isNaN(Number(raw.ground_speed_m_s))) {
    return Number(raw.ground_speed_m_s)
  }
  if (vel.ground_speed_m_s != null && !Number.isNaN(Number(vel.ground_speed_m_s))) {
    return Number(vel.ground_speed_m_s)
  }
  if (raw.speed != null && !Number.isNaN(Number(raw.speed))) {
    return Number(raw.speed)
  }
  if (raw.speed_m_s != null && !Number.isNaN(Number(raw.speed_m_s))) {
    return Number(raw.speed_m_s)
  }
  if (vel.speed != null && !Number.isNaN(Number(vel.speed))) {
    return Number(vel.speed)
  }
  return Math.hypot(vx, vy, vz)
}

export function normalizeTelemetry(raw) {
  if (!raw) return null
  if (raw.lat != null) {
    return {
      ...raw,
      battery: normalizeBattery(raw.battery),
      speed: groundSpeed(raw, {}),
    }
  }

  const pos = raw.position || {}
  const vel = raw.velocity || {}
  const att = raw.attitude || {}
  const bat = raw.battery || {}
  const gps = raw.gps || {}
  const state = raw.state || {}

  return {
    timestamp: raw.timestamp,
    lat: pos.lat ?? raw.lat,
    lon: pos.lon ?? raw.lon,
    alt: pos.alt_agl ?? pos.alt ?? raw.alt ?? 0,
    vx: vel.vx ?? raw.vx ?? 0,
    vy: vel.vy ?? raw.vy ?? 0,
    vz: vel.vz ?? raw.vz ?? 0,
    speed: groundSpeed(raw, vel),
    roll: att.roll ?? raw.roll ?? 0,
    pitch: att.pitch ?? raw.pitch ?? 0,
    yaw: att.yaw ?? raw.yaw ?? 0,
    battery: normalizeBattery(bat.percent ?? raw.battery ?? raw.battery_percent),
    gps_status: gps.fix ?? raw.gps_status ?? 'no_fix',
    satellites: gps.satellites ?? raw.satellites ?? 0,
    armed: state.armed ?? raw.armed ?? false,
    mode: state.flight_mode ?? raw.mode ?? 'UNKNOWN',
    latency_ms: raw.latency_ms,
  }
}
