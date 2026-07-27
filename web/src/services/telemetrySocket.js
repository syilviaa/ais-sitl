/**
 * WebSocket transport — Жанель.
 * Данные в UI через telemetryBridge.js (Мерей).
 */
import { io } from 'socket.io-client'
import {
  pushTelemetry,
  setConnectionStatus,
  onConnectionStatus,
  onTelemetry,
} from './telemetryBridge.js'

const UPDATE_INTERVAL_MS = 100

let socketInstance = null
let closed = false
let lastUpdateAt = 0
let pendingTelemetry = null
let updateTimer = null

function backendUrl(explicit) {
  const raw = explicit || import.meta.env.VITE_API_URL || ''
  if (raw) return raw.replace(/\/api\/?$/, '').replace(/\/$/, '')
  // Vite dev: use proxy on same origin
  if (import.meta.env.DEV && typeof window !== 'undefined') {
    return window.location.origin
  }
  return 'http://127.0.0.1:5001'
}

function deliverTelemetry() {
  updateTimer = null
  if (closed || !pendingTelemetry) return
  const payload = pendingTelemetry
  pendingTelemetry = null
  lastUpdateAt = Date.now()
  pushTelemetry(payload)
}

function scheduleDelivery() {
  const remaining = UPDATE_INTERVAL_MS - (Date.now() - lastUpdateAt)
  if (remaining <= 0 && !updateTimer) {
    deliverTelemetry()
  } else if (!updateTimer) {
    updateTimer = setTimeout(deliverTelemetry, remaining)
  }
}

function requestTelemetryStart() {
  if (socketInstance?.connected) {
    socketInstance.emit('start_telemetry')
  }
}

/** Подключить Socket.IO. url без /api — например http://127.0.0.1:5000 */
export function connectTelemetry(url) {
  disconnectTelemetry()

  const urlBase = backendUrl(url)
  closed = false
  setConnectionStatus('reconnecting')

  const socket = io(urlBase, {
    autoConnect: true,
    reconnection: true,
    transports: ['websocket', 'polling'],
  })
  socketInstance = socket

  // Transport-level connect (Socket.IO)
  socket.on('connect', () => {
    setConnectionStatus('connected')
    socket.emit('start_telemetry')
  })

  // Backend handshake event (after connect)
  socket.on('connected', () => {
    setConnectionStatus('connected')
    socket.emit('start_telemetry')
  })

  socket.on('telemetry_started', (info) => {
    setConnectionStatus('connected')
    if (info?.pending) {
      console.info('telemetry pending:', info.message)
    }
  })

  socket.on('telemetry', (payload) => {
    pendingTelemetry = payload
    scheduleDelivery()
  })

  socket.on('telemetry_error', (error) => {
    const msg = error?.message || ''
    if (msg.toLowerCase().includes('not initialized')) {
      setConnectionStatus('connected')
      return
    }
    setConnectionStatus('error')
    console.error('telemetry_error', msg || error)
  })

  socket.on('connect_error', (error) => {
    setConnectionStatus('error')
    console.error('connect_error', error.message)
  })

  socket.on('disconnect', (reason) => {
    if (!closed && reason !== 'io client disconnect') {
      setConnectionStatus('reconnecting')
    }
  })

  socket.io.on('reconnect_attempt', () => {
    if (!closed) setConnectionStatus('reconnecting')
  })

  return socket
}

export function disconnectTelemetry() {
  closed = true
  if (updateTimer) clearTimeout(updateTimer)
  updateTimer = null
  pendingTelemetry = null

  if (socketInstance) {
    if (socketInstance.connected) socketInstance.emit('stop_telemetry')
    socketInstance.disconnect()
    socketInstance = null
  }
  setConnectionStatus('disconnected')
}

export { requestTelemetryStart }

/** Совместимость с App.vue ветки feat/dashboard-websocket-client */
export function createTelemetrySocket({ url, onStatus, onTelemetry: onTelemetryCb, onError }) {
  const statusUnsub = onStatus ? onConnectionStatus(onStatus) : null
  const telemetryUnsub = onTelemetryCb ? onTelemetry(onTelemetryCb) : null

  const socket = connectTelemetry(url)

  if (onError) {
    socket.on('connect_error', (e) => onError(e.message))
    socket.on('telemetry_error', (e) => onError(e?.message || 'Telemetry error'))
  }

  return {
    connect() {
      if (!socket.connected) socket.connect()
    },
    start: requestTelemetryStart,
    close() {
      statusUnsub?.()
      telemetryUnsub?.()
      disconnectTelemetry()
    },
  }
}
