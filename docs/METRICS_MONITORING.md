# Veha 5 Metrics & Monitoring - Prometheus & Grafana

Complete guide for metrics collection, monitoring, and visualization of the AIS SITL platform.

## Overview

The Metrics API provides comprehensive operational monitoring:
- **Prometheus Format** - `/metrics` endpoint for scraping
- **JSON Summary** - `/api/metrics/summary` for quick checks
- **Manual Updates** - `/api/metrics/update` to refresh from services
- **Real-time Monitoring** - 20+ metrics covering fleet, missions, telemetry, and geofence

## Architecture

```
┌─────────────────────┐
│   AIS SITL Backend  │
│  Metrics Service    │
└──────────┬──────────┘
           │
     ┌─────┴─────────┬─────────────┐
     │               │             │
  /metrics    /api/metrics/   /api/metrics/
(Prometheus)  summary (JSON)  update (POST)
     │               │             │
     ▼               ▼             ▼
┌──────────┐  ┌──────────┐  ┌──────────────┐
│Prometheus│  │Dashboard │  │Manual Trigger│
│  Server  │  │(Grafana) │  │via REST API  │
└──────────┘  └──────────┘  └──────────────┘
```

## Metrics Endpoints

### 1. Prometheus Export

**GET** `/metrics`

Export all metrics in Prometheus text format for scraping.

```bash
curl http://127.0.0.1:5000/metrics
```

**Response:**
```
# HELP ais_sitl_fleet_size_total Total number of drones in fleet
# TYPE ais_sitl_fleet_size_total gauge
ais_sitl_fleet_size_total 2

# HELP ais_sitl_fleet_connected_drones Number of connected drones
# TYPE ais_sitl_fleet_connected_drones gauge
ais_sitl_fleet_connected_drones 2

# HELP ais_sitl_missions_total Total number of missions executed
# TYPE ais_sitl_missions_total counter
ais_sitl_missions_total 10

...
```

### 2. JSON Summary

**GET** `/api/metrics/summary`

Get all metrics in structured JSON format.

```bash
curl http://127.0.0.1:5000/api/metrics/summary
```

**Response:**
```json
{
  "success": true,
  "metrics": {
    "uptime_seconds": 3600.5,
    "fleet": {
      "size": 2,
      "connected": 2,
      "battery_avg": 85.5,
      "battery_min": 80.0,
      "battery_max": 91.0
    },
    "missions": {
      "total": 10,
      "completed": 8,
      "failed": 2,
      "success_rate_percent": 80.0,
      "avg_duration_seconds": 60.0,
      "total_distance_meters": 4000.0
    },
    "telemetry": {
      "updates_total": 1000,
      "rate_hz": 9.8
    },
    "geofence": {
      "violations_total": 2,
      "zones_active": 3
    }
  }
}
```

### 3. Manual Metrics Update

**POST** `/api/metrics/update`

Manually trigger metric collection from all services (fleet, telemetry, geofence).

```bash
curl -X POST http://127.0.0.1:5000/api/metrics/update
```

**Response:**
```json
{
  "success": true,
  "message": "Metrics updated",
  "metrics": {...}
}
```

## Metrics Catalog

### Fleet Metrics

| Metric | Type | Unit | Description |
|--------|------|------|-------------|
| `ais_sitl_fleet_size_total` | gauge | count | Total drones in fleet |
| `ais_sitl_fleet_connected_drones` | gauge | count | Connected drone count |
| `ais_sitl_fleet_battery_percent_avg` | gauge | % | Average battery across fleet |
| `ais_sitl_fleet_battery_percent_min` | gauge | % | Minimum battery in fleet |
| `ais_sitl_fleet_battery_percent_max` | gauge | % | Maximum battery in fleet |

### Mission Metrics

| Metric | Type | Unit | Description |
|--------|------|------|-------------|
| `ais_sitl_missions_total` | counter | count | Total missions executed |
| `ais_sitl_missions_completed` | counter | count | Completed missions |
| `ais_sitl_missions_failed` | counter | count | Failed missions |
| `ais_sitl_mission_success_rate_percent` | gauge | % | Success rate |
| `ais_sitl_mission_duration_seconds_total` | counter | seconds | Total flight time |
| `ais_sitl_mission_duration_seconds_avg` | gauge | seconds | Average mission duration |
| `ais_sitl_mission_distance_meters_total` | counter | meters | Total distance flown |
| `ais_sitl_mission_distance_meters_avg` | gauge | meters | Average mission distance |

### Telemetry Metrics

| Metric | Type | Unit | Description |
|--------|------|------|-------------|
| `ais_sitl_telemetry_updates_total` | counter | count | Total telemetry updates |
| `ais_sitl_telemetry_rate_hz` | gauge | Hz | Current update rate |

### Geofence Metrics

| Metric | Type | Unit | Description |
|--------|------|------|-------------|
| `ais_sitl_geofence_violations_total` | counter | count | Total violations |
| `ais_sitl_geofence_zones_active` | gauge | count | Active zones |

### System Metrics

| Metric | Type | Unit | Description |
|--------|------|------|-------------|
| `ais_sitl_uptime_seconds` | gauge | seconds | Application uptime |

## Prometheus Configuration

Add to `prometheus.yml`:

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'ais_sitl'
    static_configs:
      - targets: ['localhost:5000']
    metrics_path: '/metrics'
    scrape_interval: 10s
```

## Grafana Dashboard Setup

### 1. Add Prometheus Data Source

```
Configuration → Data Sources → Add
Name: AIS SITL
Type: Prometheus
URL: http://prometheus:9090
```

### 2. Dashboard JSON

See `monitoring/grafana/dashboard.json` for complete dashboard configuration including:

- **Fleet Status Panel**
  - Connected drones gauge
  - Average battery percentage
  - Fleet size time series

- **Mission Performance Panel**
  - Success rate gauge
  - Completed vs failed counter
  - Mission duration trends

- **Telemetry Quality Panel**
  - Update rate gauge (Hz)
  - Updates over time

- **Geofence Status Panel**
  - Active zones gauge
  - Violations counter
  - Violations over time

### 3. Example Queries

```promql
# Connected drones over time
ais_sitl_fleet_connected_drones

# Mission success rate with 5m moving average
avg_over_time(ais_sitl_mission_success_rate_percent[5m])

# Battery trend
rate(ais_sitl_fleet_battery_percent_avg[1m])

# Telemetry lag
1000 / ais_sitl_telemetry_rate_hz

# Total mission time
increase(ais_sitl_mission_duration_seconds_total[1h])
```

## Alert Rules

Example `prometheus/alert_rules.yml`:

```yaml
groups:
  - name: ais_sitl_alerts
    rules:
      - alert: LowBattery
        expr: ais_sitl_fleet_battery_percent_min < 20
        for: 2m
        annotations:
          summary: "Low battery in fleet"

      - alert: DroneDisconnected
        expr: ais_sitl_fleet_connected_drones < ais_sitl_fleet_size_total
        for: 1m
        annotations:
          summary: "Drone disconnected from fleet"

      - alert: MissionFailureRate
        expr: (ais_sitl_missions_failed / ais_sitl_missions_total) > 0.2
        for: 5m
        annotations:
          summary: "High mission failure rate"

      - alert: TelemetryLoss
        expr: ais_sitl_telemetry_rate_hz < 5
        for: 30s
        annotations:
          summary: "Telemetry rate below 5 Hz"

      - alert: GeofenceViolation
        expr: increase(ais_sitl_geofence_violations_total[5m]) > 0
        annotations:
          summary: "Geofence violation detected"
```

## Docker Integration

The docker-compose.yml already includes:

```yaml
prometheus:
  image: prom/prometheus:latest
  volumes:
    - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml:ro
  ports:
    - "9090:9090"

grafana:
  image: grafana/grafana:latest
  ports:
    - "3001:3000"
  environment:
    GF_SECURITY_ADMIN_PASSWORD: admin
```

Start the full monitoring stack:

```bash
docker-compose up -d
```

Then access:
- **Prometheus**: http://localhost:9090
- **Grafana**: http://localhost:3001 (admin/admin)

## Quick Start

### 1. Verify Metrics Export

```bash
curl http://127.0.0.1:5000/metrics | head -20
```

### 2. Check JSON Summary

```bash
curl http://127.0.0.1:5000/api/metrics/summary | jq '.metrics.fleet'
```

### 3. Update Metrics Manually

```bash
curl -X POST http://127.0.0.1:5000/api/metrics/update
```

### 4. Query in Prometheus

```
http://localhost:9090
Query: ais_sitl_missions_total
```

### 5. View in Grafana

```
http://localhost:3001
Dashboard: AIS SITL Multi-Drone Platform
```

## Performance Considerations

- **Metric Collection**: O(1) in-memory operations
- **Prometheus Scrape**: 10-15 second intervals recommended
- **Grafana Refresh**: 30 second intervals for dashboards
- **Minimal Overhead**: <1% CPU impact
- **Storage**: ~50KB per day on Prometheus TSDB

## Troubleshooting

### Prometheus Can't Scrape Backend

```bash
# Check if metrics endpoint is accessible
curl http://127.0.0.1:5000/metrics

# Check docker network (if using containers)
docker exec ais_sitl_prometheus curl http://backend:5000/metrics
```

### Missing Metrics

```bash
# Metrics are only populated when services are active
# Trigger manual update
curl -X POST http://127.0.0.1:5000/api/metrics/update

# Check if services are initialized
curl http://127.0.0.1:5000/api/metrics/summary
```

### Grafana Dashboard Not Updating

```bash
# Verify Prometheus data source
Configuration → Data Sources → Test

# Check query execution time
http://localhost:9090/graph

# Increase Grafana refresh interval
Panel Settings → Refresh
```

## Veha 5 Integration

Metrics API is part of Veha 5 multi-drone platform:
- Phase 2: ✅ Multi-drone REST API
- Phase 3: ✅ Mission recording & playback
- Phase 4: ✅ Advanced geofence failsafe
- Phase 5: ✅ Prometheus metrics & Grafana monitoring (this)

## Related Documentation

- FLEET_API.md - Multi-drone fleet operations
- RECORDING_API.md - Mission recording and playback
- GEOFENCE_API.md - Airspace boundary enforcement
