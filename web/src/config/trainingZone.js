/** Almaty Training Field — единая учебная зона (карта, NFZ, SITL, маршрут). */
export const TRAINING_HOME = { lat: 43.2220, lon: 76.8512, altitude: 0 }
export const MAP_CENTER = [TRAINING_HOME.lat, TRAINING_HOME.lon]
export const MAP_ZOOM = 14

/** Безопасный маршрут из 4 точек — обходит Training Restricted Area A */
export const DEFAULT_WAYPOINTS = [
  { lat: 43.2200, lon: 76.8480, altitude: 50 },
  { lat: 43.2210, lon: 76.8495, altitude: 60 },
  { lat: 43.2215, lon: 76.8505, altitude: 60 },
  { lat: 43.2200, lon: 76.8480, altitude: 0 },
]
