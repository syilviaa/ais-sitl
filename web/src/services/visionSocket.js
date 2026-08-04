/** Socket.IO client for vision_detection and vision_alert events. */
import { io } from 'socket.io-client'

let socket = null
const listeners = {
  alert: new Set(),
  detection: new Set(),
  status: new Set(),
  error: new Set(),
}

function notify(type, value) {
  listeners[type].forEach((callback) => callback(value))
}

function backendUrl() {
  const configured = import.meta.env.VITE_API_URL || ''
  if (configured) return configured.replace(/\/api\/?$/, '').replace(/\/$/, '')
  return import.meta.env.DEV ? window.location.origin : 'http://127.0.0.1:5001'
}

export function connectVision() {
  disconnectVision()
  notify('status', 'reconnecting')
  socket = io(backendUrl(), {
    transports: ['websocket', 'polling'],
    reconnection: true,
  })
  socket.on('connect', () => {
    notify('status', 'connected')
    socket.emit('subscribe_detections')
    socket.emit('subscribe_alerts')
  })
  socket.on('vision_detection', (event) => notify('detection', event?.data || event))
  socket.on('vision_alert', (event) => notify('alert', event?.data || event))
  socket.on('vision_error', (error) => notify('error', error?.message || 'Vision error'))
  socket.on('connect_error', (error) => {
    notify('status', 'error')
    notify('error', error.message)
  })
  socket.on('disconnect', () => notify('status', 'disconnected'))
  return socket
}

export function disconnectVision() {
  if (socket) socket.disconnect()
  socket = null
  notify('status', 'disconnected')
}

export function onVisionAlert(callback) {
  listeners.alert.add(callback)
  return () => listeners.alert.delete(callback)
}

export function onVisionDetection(callback) {
  listeners.detection.add(callback)
  return () => listeners.detection.delete(callback)
}

export function onVisionStatus(callback) {
  listeners.status.add(callback)
  return () => listeners.status.delete(callback)
}

export function onVisionError(callback) {
  listeners.error.add(callback)
  return () => listeners.error.delete(callback)
}
