/**
 * Vision Socket.IO client — Мерей (CV MVP).
 * Events: vision_detection, vision_alert (≤10/s server-side).
 */
import { io } from 'socket.io-client'

let socketInstance = null
let closed = false

const detectionListeners = new Set()
const alertListeners = new Set()
const statusListeners = new Set()
const errorListeners = new Set()

let connectionStatus = 'disconnected'

function backendUrl(explicit) {
  const raw = explicit || import.meta.env.VITE_API_URL || ''
  if (raw) return raw.replace(/\/api\/?$/, '').replace(/\/$/, '')
  if (import.meta.env.DEV && typeof window !== 'undefined') {
    return window.location.origin
  }
  return 'http://127.0.0.1:5001'
}

function setStatus(status) {
  connectionStatus = status
  statusListeners.forEach((cb) => {
    try {
      cb(status)
    } catch (e) {
      console.error('vision status listener error', e)
    }
  })
}

function notifyError(message) {
  errorListeners.forEach((cb) => {
    try {
      cb(message)
    } catch (e) {
      console.error('vision error listener error', e)
    }
  })
}

function unwrapPayload(payload) {
  if (!payload || typeof payload !== 'object') return payload
  // Server may wrap as { event_type, timestamp, data } or send VisionEvent directly
  if (payload.data && (payload.event_type || payload.data.event_id)) {
    return { ...payload.data, _envelope_ts: payload.timestamp }
  }
  return payload
}

/** Connect and subscribe to vision detections/alerts. */
export function connectVision(url) {
  disconnectVision()

  const urlBase = backendUrl(url)
  closed = false
  setStatus('reconnecting')

  const socket = io(urlBase, {
    autoConnect: true,
    reconnection: true,
    transports: ['websocket', 'polling'],
  })
  socketInstance = socket

  socket.on('connect', () => {
    setStatus('connected')
    socket.emit('subscribe_detections')
    socket.emit('subscribe_alerts')
  })

  socket.on('connected', () => {
    setStatus('connected')
    socket.emit('subscribe_detections')
    socket.emit('subscribe_alerts')
  })

  socket.on('response', (msg) => {
    if (msg?.status === 'subscribed') setStatus('connected')
  })

  socket.on('vision_detection', (payload) => {
    const event = unwrapPayload(payload)
    detectionListeners.forEach((cb) => {
      try {
        cb(event)
      } catch (e) {
        console.error('vision_detection listener error', e)
      }
    })
  })

  socket.on('vision_alert', (payload) => {
    const event = unwrapPayload(payload)
    alertListeners.forEach((cb) => {
      try {
        cb(event)
      } catch (e) {
        console.error('vision_alert listener error', e)
      }
    })
  })

  socket.on('vision_error', (payload) => {
    notifyError(payload?.message || payload?.error || 'Vision error')
  })

  socket.on('connect_error', (error) => {
    setStatus('error')
    notifyError(error.message)
  })

  socket.on('disconnect', (reason) => {
    if (!closed && reason !== 'io client disconnect') {
      setStatus('reconnecting')
    }
  })

  socket.io.on('reconnect_attempt', () => {
    if (!closed) setStatus('reconnecting')
  })

  return socket
}

export function disconnectVision() {
  closed = true
  if (socketInstance) {
    socketInstance.disconnect()
    socketInstance = null
  }
  setStatus('disconnected')
}

export function onVisionDetection(cb) {
  detectionListeners.add(cb)
  return () => detectionListeners.delete(cb)
}

export function onVisionAlert(cb) {
  alertListeners.add(cb)
  return () => alertListeners.delete(cb)
}

export function onVisionStatus(cb) {
  statusListeners.add(cb)
  cb(connectionStatus)
  return () => statusListeners.delete(cb)
}

export function onVisionError(cb) {
  errorListeners.add(cb)
  return () => errorListeners.delete(cb)
}

export function getVisionStatus() {
  return connectionStatus
}

export function getVisionSocket() {
  return socketInstance
}
