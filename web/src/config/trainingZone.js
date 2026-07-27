/** Astana Training Field — единая учебная зона (карта, NFZ, SITL, маршрут). */
export const TRAINING_HOME = { lat: 51.1694, lon: 71.4491, altitude: 0 }
export const MAP_CENTER = [TRAINING_HOME.lat, TRAINING_HOME.lon]
export const MAP_ZOOM = 14

/** Безопасный маршрут из 4 точек — обходит Training Restricted Area A */
export const DEFAULT_WAYPOINTS = [
  { lat: 51.1680, lon: 71.4460, altitude: 50 },
  { lat: 51.1688, lon: 71.4475, altitude: 60 },
  { lat: 51.1692, lon: 71.4485, altitude: 60 },
  { lat: 51.1680, lon: 71.4460, altitude: 0 },
]
