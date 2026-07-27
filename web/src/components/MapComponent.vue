<template>
  <div class="map-container">
    <div id="map"></div>
    <div class="map-toolbar" v-if="planMode">
      <span>📍 Click map to add waypoint</span>
    </div>
    <div class="map-info" v-if="dronePosition">
      <div class="info-badge">
        <span class="label">Alt:</span>
        <span class="value">{{ (dronePosition.alt || 0).toFixed(1) }}m</span>
      </div>
      <div class="info-badge">
        <span class="label">GPS:</span>
        <span class="value">{{ dronePosition.satellites || 0 }} sats</span>
      </div>
      <div class="info-badge">
        <span class="label">Battery:</span>
        <span class="value" :class="getBatteryClass(dronePosition.battery)">
          {{ (dronePosition.battery || 0).toFixed(1) }}%
        </span>
      </div>
      <div class="info-badge" v-if="dronePosition.latency_ms != null">
        <span class="label">RTT:</span>
        <span class="value" :class="dronePosition.latency_ms < 50 ? 'good' : 'warning'">
          {{ dronePosition.latency_ms.toFixed(0) }}ms
        </span>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'MapComponent',
  props: {
    dronePosition: { type: Object, default: null },
    waypoints: { type: Array, default: () => [] },
    nfzGeoJson: { type: Object, default: null },
    planMode: { type: Boolean, default: false },
  },
  emits: ['waypoint-added'],
  data() {
    return {
      map: null,
      droneMarker: null,
      homeMarker: null,
      waypointMarkers: [],
      route: null,
      trail: null,
      trailPoints: [],
      nfzLayers: [],
    }
  },
  mounted() {
    this.initMap()
  },
  methods: {
    initMap() {
      if (typeof L === 'undefined') {
        console.error('Leaflet not loaded')
        return
      }

      this.map = L.map('map').setView([47.3977, 8.5350], 14)

      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors',
        maxZoom: 19,
      }).addTo(this.map)

      this.homeMarker = L.marker([47.3977, 8.5350], {
        icon: L.divIcon({
          className: 'home-icon',
          html: '🏠',
          iconSize: [24, 24],
        }),
      })
      this.homeMarker.bindPopup('Home Position').addTo(this.map)

      this.droneMarker = L.marker([47.3977, 8.5350], {
        icon: L.divIcon({
          className: 'drone-icon',
          html: '🚁',
          iconSize: [28, 28],
        }),
      })
      this.droneMarker.bindPopup('Drone').addTo(this.map)

      this.trail = L.polyline([], { color: '#667eea', weight: 3, opacity: 0.7 }).addTo(this.map)

      this.map.on('click', (event) => {
        if (!this.planMode) return
        this.$emit('waypoint-added', {
          lat: event.latlng.lat,
          lon: event.latlng.lng,
          altitude: 50,
        })
      })

      if (this.nfzGeoJson) this.renderNfz(this.nfzGeoJson)
      if (this.waypoints.length) this.addWaypoints(this.waypoints)
    },
    renderNfz(geojson) {
      if (!this.map || !geojson?.features) return
      this.nfzLayers.forEach((layer) => layer.remove())
      this.nfzLayers = []

      geojson.features.forEach((feature) => {
        if (!feature.properties?.active && feature.properties?.active !== undefined) return
        if (feature.properties?.type === 'safe_zone') return
        const coords = feature.geometry?.coordinates?.[0]
        if (!coords) return
        const latlngs = coords.map(([lon, lat]) => [lat, lon])
        const layer = L.polygon(latlngs, {
          color: '#ef4444',
          fillColor: '#ef4444',
          fillOpacity: 0.25,
          weight: 2,
        })
        layer.bindPopup(feature.properties?.name || 'NFZ')
        layer.addTo(this.map)
        this.nfzLayers.push(layer)
      })
    },
    updateDronePosition(position) {
      if (!this.map || !this.droneMarker || !position?.lat) return
      const lat = position.lat
      const lon = position.lon
      this.droneMarker.setLatLng([lat, lon])

      this.trailPoints.push([lat, lon])
      if (this.trailPoints.length > 200) this.trailPoints.shift()
      this.trail.setLatLngs(this.trailPoints)

      if (this.map.getZoom() > 12) {
        this.map.panTo([lat, lon], { animate: true })
      }
    },
    addWaypoints(waypoints) {
      this.waypointMarkers.forEach((m) => m.remove())
      this.waypointMarkers = []
      if (!this.map) return

      waypoints.forEach((wp, idx) => {
        const marker = L.marker([wp.lat, wp.lon], {
          icon: L.divIcon({
            className: 'wp-icon',
            html: `<span>${idx + 1}</span>`,
            iconSize: [22, 22],
          }),
        })
        marker.bindPopup(
          `Waypoint ${idx + 1}<br/>${wp.lat.toFixed(5)}, ${wp.lon.toFixed(5)}<br/>Alt: ${wp.altitude || 50}m`
        )
        marker.addTo(this.map)
        this.waypointMarkers.push(marker)
      })

      if (waypoints.length > 1) {
        const latlngs = waypoints.map((wp) => [wp.lat, wp.lon])
        if (this.route) this.route.remove()
        this.route = L.polyline(latlngs, { color: '#f59e0b', weight: 2, dashArray: '6 4' }).addTo(this.map)
      }
    },
    clearTrail() {
      this.trailPoints = []
      if (this.trail) this.trail.setLatLngs([])
    },
    getBatteryClass(battery) {
      if (!battery) return 'critical'
      if (battery > 50) return 'good'
      if (battery > 20) return 'warning'
      return 'critical'
    },
  },
  watch: {
    dronePosition(newVal) {
      if (newVal) this.updateDronePosition(newVal)
    },
    waypoints(newVal) {
      if (newVal?.length) this.addWaypoints(newVal)
    },
    nfzGeoJson(newVal) {
      if (newVal) this.renderNfz(newVal)
    },
  },
}
</script>

<style scoped>
.map-container {
  position: relative;
  width: 100%;
  height: 100%;
  background: #f5f5f5;
}

#map {
  width: 100%;
  height: 100%;
  z-index: 1;
}

.map-toolbar {
  position: absolute;
  top: 12px;
  left: 50%;
  transform: translateX(-50%);
  background: rgba(102, 126, 234, 0.95);
  color: white;
  padding: 6px 14px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 600;
  z-index: 10;
}

.map-info {
  position: absolute;
  bottom: 20px;
  right: 20px;
  background: white;
  border-radius: 8px;
  padding: 12px 16px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  z-index: 10;
  display: flex;
  gap: 16px;
  font-size: 12px;
}

.info-badge {
  display: flex;
  gap: 4px;
  align-items: center;
}

.label {
  color: #6b7280;
  font-weight: 600;
}

.value {
  color: #1f2937;
  font-family: monospace;
  font-weight: 600;
}

.value.good { color: #22c55e; }
.value.warning { color: #f59e0b; }
.value.critical { color: #ef4444; }

:deep(.wp-icon span) {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  background: #f59e0b;
  color: white;
  border-radius: 50%;
  font-size: 11px;
  font-weight: 700;
  border: 2px solid white;
}
</style>
