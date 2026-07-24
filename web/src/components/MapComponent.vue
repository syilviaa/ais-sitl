<template>
  <div class="map-container">
    <div id="map"></div>
    <div class="map-info" v-if="dronePosition">
      <div class="info-badge">
        <span class="label">Alt:</span>
        <span class="value">{{ dronePosition.alt.toFixed(1) }}m</span>
      </div>
      <div class="info-badge">
        <span class="label">GPS:</span>
        <span class="value">{{ dronePosition.satellites || 0 }} sats</span>
      </div>
      <div class="info-badge">
        <span class="label">Battery:</span>
        <span class="value" :class="getBatteryClass(dronePosition.battery)">
          {{ dronePosition.battery.toFixed(1) }}%
        </span>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'MapComponent',
  props: {
    dronePosition: {
      type: Object,
      default: null,
    },
    waypoints: {
      type: Array,
      default: () => [],
    },
  },
  data() {
    return {
      map: null,
      droneMarker: null,
      homeMarker: null,
      waypointMarkers: [],
      route: null,
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

      this.map = L.map('map').setView([47.3977, 8.5455], 13)

      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors',
        maxZoom: 19,
      }).addTo(this.map)

      // Home marker
      this.homeMarker = L.marker([47.3977, 8.5455], {
        icon: L.icon({
          iconUrl: 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9IiMyMmM1NWUiIHN0cm9rZS13aWR0aD0iMiI+PHBhdGggZD0iTTMgOWwzLTMgMy0zIDMgMyAzIDMgMyAzSzMgOXoiLz48L3N2Zz4=',
          iconSize: [24, 24],
        }),
      })
      this.homeMarker.bindPopup('Home Position').addTo(this.map)

      // Drone marker
      this.droneMarker = L.marker([47.3977, 8.5455], {
        icon: L.icon({
          iconUrl: 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNiIgaGVpZ2h0PSIyNiIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9IiM2NjdlZWEiIHN0cm9rZS13aWR0aD0iMiI+PGNpcmNsZSBjeD0iMTIiIGN5PSIxMiIgcj0iNiIvPjwvc3ZnPg==',
          iconSize: [26, 26],
        }),
      })
      this.droneMarker.bindPopup('Drone').addTo(this.map)
    },
    updateDronePosition(position) {
      if (!this.map || !this.droneMarker) return

      const lat = position.lat
      const lon = position.lon
      this.droneMarker.setLatLng([lat, lon])

      // Keep map centered on drone
      if (this.map.getZoom() > 12) {
        this.map.panTo([lat, lon], { animate: true })
      }
    },
    addWaypoints(waypoints) {
      // Clear existing markers
      this.waypointMarkers.forEach(m => m.remove())
      this.waypointMarkers = []

      if (!this.map) return

      // Add waypoint markers
      waypoints.forEach((wp, idx) => {
        const marker = L.marker([wp.lat, wp.lon], {
          icon: L.icon({
            iconUrl: `data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9IiNmNTlFMGIiIHN0cm9rZS13aWR0aD0iMiI+PGNpcmNsZSBjeD0iMTIiIGN5PSIxMiIgcj0iNCIvPjwvc3ZnPg==`,
            iconSize: [24, 24],
          }),
        })
        marker.bindPopup(`Waypoint ${idx + 1}<br/>${wp.lat.toFixed(4)}, ${wp.lon.toFixed(4)}<br/>Alt: ${wp.altitude || 0}m`)
        marker.addTo(this.map)
        this.waypointMarkers.push(marker)
      })

      // Draw route
      if (waypoints.length > 1) {
        const latlngs = waypoints.map(wp => [wp.lat, wp.lon])
        if (this.route) this.route.remove()
        this.route = L.polyline(latlngs, { color: '#f59e0b', weight: 2 }).addTo(this.map)
      }
    },
    getBatteryClass(battery) {
      if (battery > 50) return 'good'
      if (battery > 20) return 'warning'
      return 'critical'
    },
  },
  watch: {
    dronePosition(newVal) {
      if (newVal) {
        this.updateDronePosition(newVal)
      }
    },
    waypoints(newVal) {
      if (newVal && newVal.length > 0) {
        this.addWaypoints(newVal)
      }
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

.value.good {
  color: #22c55e;
}

.value.warning {
  color: #f59e0b;
}

.value.critical {
  color: #ef4444;
}
</style>
