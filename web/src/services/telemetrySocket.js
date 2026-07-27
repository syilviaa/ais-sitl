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

/** url без /api — например http://127.0.0.1:5000 */
export function connectTelemetry(url) {
  disconnectTelemetry()

  const backendUrl = url || import.meta.env.VITE_API_URL || 'http://127.0.0.1:5000'
  closed = false
  setConnectionStatus('reconnecting')

  const socket = io(backendUrl, {
    autoConnect: true,
    reconnection: true,
  })
  socketInstance = socket

  socket.on('connected', () => {
    setConnectionStatus('connected')
    socket.emit('start_telemetry')
  })

  socket.on('telemetry', (payload) => {
    pendingTelemetry = payload
    scheduleDelivery()
  })

  socket.on('telemetry_error', (error) => {
    setConnectionStatus('error')
    console.error('telemetry_error', error?.message || error)
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
    start() {
      if (socket.connected) socket.emit('start_telemetry')
    },
    close() {
      statusUnsub?.()
      telemetryUnsub?.()
      disconnectTelemetry()
    },
  }
}
