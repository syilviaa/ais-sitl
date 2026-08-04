<template>
  <div class="map-container">
    <div id="map"></div>
    <div class="map-toolbar" v-if="planMode">
      <span>Клик — добавить точку · перетащите маркер для перемещения</span>
    </div>
    <div class="map-info" v-if="hasPosition">
      <div class="info-badge">
        <span class="label">Выс:</span>
        <span class="value">{{ (dronePosition.alt || 0).toFixed(1) }}m</span>
      </div>
      <div class="info-badge">
        <span class="label">Скр:</span>
        <span class="value">{{ horizontalSpeed.toFixed(1) }} m/s</span>
      </div>
      <div class="info-badge">
        <span class="label">Бат:</span>
        <span class="value" :class="batteryClass">{{ (dronePosition.battery || 0).toFixed(0) }}%</span>
      </div>
    </div>
  </div>
</template>

<script>
import { MAP_CENTER, MAP_ZOOM, TRAINING_HOME } from '../config/trainingZone.js'

export default {
  name: 'MapComponent',
  props: {
    dronePosition: { type: Object, default: null },
    waypoints: { type: Array, default: () => [] },
    nfzGeoJson: { type: Object, default: null },
    planMode: { type: Boolean, default: false },
  },
  emits: ['waypoint-added', 'waypoint-moved', 'waypoint-removed'],
  data() {
    return {
      map: null,
      droneMarker: null,
      homeMarker: null,
      waypointMarkers: [],
      nfzLayers: [],
      route: null,
      trail: null,
      trailPoints: [],
    }
  },
  computed: {
    hasPosition() {
      const p = this.dronePosition
      return p && p.lat != null && p.lon != null
    },
    horizontalSpeed() {
      if (!this.dronePosition) return 0
      if (this.dronePosition.speed != null) return Number(this.dronePosition.speed)
      const vx = this.dronePosition.vx || 0
      const vy = this.dronePosition.vy || 0
      const vz = this.dronePosition.vz || 0
      return Math.hypot(vx, vy, vz)
    },
    batteryClass() {
      const b = this.dronePosition?.battery || 0
      if (b > 50) return 'good'
      if (b > 20) return 'warning'
      return 'critical'
    },
  },
  mounted() {
    this.initMap()
    if (this.hasPosition) this.updateDronePosition(this.dronePosition)
  },
  methods: {
    createDroneIcon(yaw = 0) {
      return L.divIcon({
        className: 'drone-marker-icon',
        html: `<div class="drone-body" style="transform:rotate(${yaw}deg)"><div class="drone-nose"></div><div class="drone-dot"></div></div>`,
        iconSize: [28, 28],
        iconAnchor: [14, 14],
      })
    },
    initMap() {
      if (typeof L === 'undefined') return

      this.map = L.map('map').setView(MAP_CENTER, MAP_ZOOM)
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap · Astana Training Field',
        maxZoom: 19,
      }).addTo(this.map)

      this.homeMarker = L.marker([TRAINING_HOME.lat, TRAINING_HOME.lon], {
        icon: L.divIcon({ className: 'home-pin', html: '🏠', iconSize: [28, 28] }),
      })
      this.homeMarker.bindPopup('<b>Дом</b><br/>Учебный полигон Астана').addTo(this.map)

      this.droneMarker = L.marker([TRAINING_HOME.lat, TRAINING_HOME.lon], {
        icon: this.createDroneIcon(0),
        zIndexOffset: 2000,
      })
      this.droneMarker.bindPopup('Дрон').addTo(this.map)

      this.trail = L.polyline([], { color: '#2563eb', weight: 3, opacity: 0.75 }).addTo(this.map)

      this.map.on('click', (e) => {
        if (!this.planMode) return
        this.$emit('waypoint-added', {
          lat: e.latlng.lat,
          lon: e.latlng.lng,
          altitude: 50,
        })
      })

      if (this.nfzGeoJson) this.renderNfz(this.nfzGeoJson)
      if (this.waypoints.length) this.syncWaypoints(this.waypoints)
    },
    renderNfz(geojson) {
      if (!this.map || !geojson?.features) return
      this.nfzLayers.forEach((l) => l.remove())
      this.nfzLayers = []

      geojson.features.forEach((feature) => {
        if (feature.properties?.type === 'safe_zone') return
        if (feature.properties?.active === false) return
        const ring = feature.geometry?.coordinates?.[0]
        if (!ring) return
        const latlngs = ring.map(([lon, lat]) => [lat, lon])
        const name = feature.properties?.name || 'NFZ'
        const polygon = L.polygon(latlngs, {
          color: '#dc2626',
          fillColor: '#ef4444',
          fillOpacity: 0.3,
          weight: 2,
        })
        polygon.bindPopup(`<b>${name}</b><br/>${feature.properties?.description || ''}`)
        polygon.bindTooltip(name, { permanent: true, direction: 'center', className: 'nfz-label' })
        polygon.addTo(this.map)
        this.nfzLayers.push(polygon)
      })
    },
    syncWaypoints(waypoints) {
      this.waypointMarkers.forEach((m) => m.remove())
      this.waypointMarkers = []

      waypoints.forEach((wp, idx) => {
        const marker = L.marker([wp.lat, wp.lon], {
          draggable: this.planMode,
          icon: L.divIcon({
            className: 'wp-marker-icon',
            html: `<div class="wp-num">${idx + 1}</div>`,
            iconSize: [26, 26],
            iconAnchor: [13, 13],
          }),
          zIndexOffset: 1500 + idx,
        })
        marker.on('dragend', () => {
          const pos = marker.getLatLng()
          this.$emit('waypoint-moved', { index: idx, lat: pos.lat, lon: pos.lng })
        })
        marker.bindPopup(`WP ${idx + 1}<br/>${wp.lat.toFixed(5)}, ${wp.lon.toFixed(5)}<br/>${wp.altitude}m`)
        marker.addTo(this.map)
        this.waypointMarkers.push(marker)
      })

      if (waypoints.length >= 1) {
        const latlngs = waypoints.map((wp) => [wp.lat, wp.lon])
        if (this.route) this.route.remove()
        if (waypoints.length >= 2) {
          this.route = L.polyline(latlngs, { color: '#f59e0b', weight: 3, dashArray: '8 6' }).addTo(this.map)
        } else {
          this.route = null
        }
      } else if (this.route) {
        this.route.remove()
        this.route = null
      }
    },
    updateDronePosition(position) {
      if (!this.map || !this.droneMarker || position?.lat == null || position?.lon == null) return
      this.droneMarker.setLatLng([position.lat, position.lon])
      this.droneMarker.setIcon(this.createDroneIcon(position.yaw || 0))
      this.trailPoints.push([position.lat, position.lon])
      if (this.trailPoints.length > 300) this.trailPoints.shift()
      this.trail.setLatLngs(this.trailPoints)
    },
    clearTrail() {
      this.trailPoints = []
      if (this.trail) this.trail.setLatLngs([])
    },
    refreshWaypointDraggable() {
      this.waypointMarkers.forEach((m) => {
        if (m.dragging) {
          if (this.planMode) m.dragging.enable()
          else m.dragging.disable()
        }
      })
    },
  },
  watch: {
    dronePosition: {
      deep: true,
      handler(val) {
        if (val) this.updateDronePosition(val)
      },
    },
    waypoints: {
      // In-place edits (drag, splice) keep the same array reference, so a
      // shallow watcher would leave markers and the route line out of sync.
      deep: true,
      handler(val) {
        this.syncWaypoints(val || [])
      },
    },
    nfzGeoJson(val) {
      if (val) this.renderNfz(val)
    },
    planMode() {
      this.syncWaypoints(this.waypoints)
    },
  },
}
</script>

<style scoped>
.map-container { position: relative; width: 100%; height: 100%; }
#map { width: 100%; height: 100%; }
.map-toolbar {
  position: absolute; top: 12px; left: 50%; transform: translateX(-50%);
  background: rgba(37, 99, 235, 0.92); color: #fff; padding: 6px 14px;
  border-radius: 20px; font-size: 12px; font-weight: 600; z-index: 500;
}
.map-info {
  position: absolute; bottom: 16px; right: 16px; background: #fff;
  border-radius: 8px; padding: 10px 14px; box-shadow: 0 2px 8px rgba(0,0,0,.12);
  display: flex; gap: 14px; font-size: 12px; z-index: 500;
}
.info-badge { display: flex; gap: 4px; align-items: center; }
.label { color: #6b7280; font-weight: 600; }
.value { font-family: monospace; font-weight: 700; }
.value.good { color: #16a34a; }
.value.warning { color: #d97706; }
.value.critical { color: #dc2626; }
:deep(.nfz-label) {
  background: rgba(220, 38, 38, 0.85); color: #fff; border: none;
  font-size: 10px; font-weight: 700; padding: 2px 6px;
}
</style>
