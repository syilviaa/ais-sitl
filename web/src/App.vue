<template>
  <div id="app" class="dashboard">
    <header class="navbar">
      <div class="navbar-brand">
        <h1>🚁 AIS SITL Platform - Veha 4</h1>
      </div>
      <div class="navbar-status">
        <span :class="['status-badge', connectionStatus]">
          {{ connectionStatus === 'connected' ? '🟢' : '🔴' }}
          {{ connectionStatus.toUpperCase() }}
        </span>
      </div>
    </header>

    <main class="container">
      <section class="map-panel">
        <div id="map" class="map-container">
          <div class="map-placeholder">
            <p>GIS Map Component (Veha 4 - TODO)</p>
          </div>
        </div>
      </section>

      <aside class="control-panel">
        <section class="panel">
          <h2>📊 Telemetry</h2>
          <div class="telemetry-grid">
            <div class="telemetry-item">
              <label>Battery</label>
              <code>{{ telemetry.battery || 0 }}%</code>
            </div>
            <div class="telemetry-item">
              <label>Altitude</label>
              <code>{{ telemetry.altitude || 0 }}m</code>
            </div>
          </div>
        </section>

        <section class="panel">
          <h2>🔧 Status</h2>
          <div class="status-list">
            <div class="status-item">
              <span class="status-icon ok">●</span>
              <span>Connected</span>
            </div>
          </div>
        </section>

        <section class="panel">
          <h2>✈️ Mission</h2>
          <div class="mission-actions">
            <button @click="startMission" class="btn btn-primary">Start</button>
            <button @click="pauseMission" class="btn btn-secondary">Pause</button>
            <button @click="abortMission" class="btn btn-danger">Abort</button>
          </div>
        </section>
      </aside>
    </main>
  </div>
</template>

<script>
export default {
  name: 'App',
  data() {
    return {
      connectionStatus: 'disconnected',
      telemetry: {
        battery: 85,
        altitude: 50,
      },
    }
  },
  methods: {
    startMission() { console.log('Start') },
    pauseMission() { console.log('Pause') },
    abortMission() { console.log('Abort') },
  },
}
</script>

<style scoped>
#app { height: 100vh; display: flex; flex-direction: column; }
.navbar { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 1rem; }
.container { display: flex; flex: 1; gap: 1rem; padding: 1rem; }
.map-panel { flex: 1; background: white; border-radius: 8px; }
.control-panel { width: 300px; display: flex; flex-direction: column; gap: 1rem; }
.panel { background: white; border-radius: 8px; padding: 1rem; }
.btn { padding: 0.5rem; border: none; border-radius: 4px; cursor: pointer; }
.btn-primary { background: #667eea; color: white; }
.btn-secondary { background: #e5e7eb; }
.btn-danger { background: #ef4444; color: white; }
</style>
