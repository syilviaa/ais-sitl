# AIS National Territory Intelligence & Security Platform

**Sprint №1: MVP Development with PX4 SITL Simulation**

[📅 Timeline: July 14 - July 28, 2026]

---

## 📋 Overview

This repository contains the **Milestone 1 (Infrastructure & SITL Setup)** for the AIS platform — a territorial surveillance system using PX4 autopilot drones in Software-In-The-Loop (SITL) simulation.

### Architecture Stack (Sprint 1 MVP)

```
┌─────────────────────────────────────────────────────┐
│  Frontend: Web Dashboard (GIS Map + Mission Control) │  [Veha 4-5]
└────────────────┬────────────────────────────────────┘
                 │ WebSocket (MAVLink telemetry)
┌────────────────▼────────────────────────────────────┐
│  Backend: Python API Server + MAVSDK/pymavlink      │  [Veha 2-4]
└────────────────┬────────────────────────────────────┘
                 │ MAVLink Protocol (UDP)
┌────────────────▼────────────────────────────────────┐
│  Autopilot: PX4 SITL + Gazebo Simulation            │  [Veha 1 ✅]
│  • Flight control (Arm/Disarm/Takeoff/Land)         │
│  • Telemetry polling (10 Hz)                        │
│  • Geofencing (No-Fly Zones)                        │
│  • Failsafe (RTL on battery low / link loss)        │
└─────────────────────────────────────────────────────┘
```

---

## 🎯 Veha 1 (Infrastructure) — COMPLETED CHECKLIST

- [x] PX4 SITL + Gazebo Docker image built
- [x] CI/CD pipeline (GitHub Actions) configured
- [x] Local macOS development environment setup
- [x] Docker validation tests passing
- [ ] Team onboarded on local development

---

## 🚀 Quick Start

### Option A: macOS (Recommended for dev team)

```bash
# 1. Clone repository
git clone <repo-url> ais-sitl-platform
cd ais-sitl-platform

# 2. Run setup (installs Docker, builds image)
make install

# 3. Start SITL simulation
make docker-run
```

**Requirements:**
- macOS 11+
- Homebrew
- Docker Desktop (installed via `make install`)
- ~5-10 GB disk space

### Option B: Docker Only (Headless / CI)

```bash
# Build image
docker build -t ais-sitl:latest -f Dockerfile .

# Validate build
docker run --rm ais-sitl:latest test

# Run SITL (without GUI)
docker run --rm ais-sitl:latest gazebo
```

### Option C: CI/CD Pipeline

Push to `main` or `develop` branch — GitHub Actions automatically:
1. Builds Docker image
2. Validates SITL build
3. Runs security scans
4. Checks documentation

---

## 📁 Repository Structure

```
ais-sitl-platform/
├── Dockerfile                 # PX4 SITL + Gazebo container
├── entrypoint.sh             # Container startup script
├── install_macos.sh          # macOS local setup
├── Makefile                  # Development commands
├── README.md                 # This file
├── .github/
│   └── workflows/
│       └── sitl-ci.yml       # GitHub Actions CI pipeline
├── src/
│   ├── autopilot/           # [Veha 2-3] PX4 flight code
│   │   ├── plane.py         # Plane/Drone class
│   │   ├── geofence.py      # NFZ geofencing
│   │   └── failsafe.py      # RTL failsafe handling
│   └── backend/             # [Veha 4] MAVLink server
│       ├── mavlink_server.py
│       └── telemetry_handler.py
├── web/                      # [Veha 4-5] Frontend Dashboard
│   ├── index.html
│   ├── map.js
│   └── mission-control.js
├── tests/                    # Unit & integration tests
│   ├── test_plane.py
│   ├── test_geofence.py
│   └── test_mavlink.py
└── docs/
    ├── ARCHITECTURE.md       # Detailed architecture
    ├── API.md               # MAVSDK/pymavlink API reference
    └── DEPLOYMENT.md        # Production deployment guide
```

---

## 🛠️ Development Workflow

### Local Testing

```bash
# Build Docker image
make docker-build

# Run SITL in Docker
make docker-run

# Run validation tests
make docker-test

# Interactive shell in container
make docker-shell
```

### Code Quality

```bash
# Lint Python code
flake8 src/ --max-line-length=120

# Format code
black src/

# Type checking
mypy src/
```

### Testing

```bash
# Run unit tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html
```

---

## 📡 MAVLink Communication

All drone-to-server communication uses **MAVLink 2.0** protocol over UDP:

- **Default port:** 14540 (SITL)
- **Telemetry rate:** 10 Hz
- **Latency target:** < 50 ms RTT
- **Libraries:** MAVSDK (Python) + pymavlink

### Telemetry Packet Format

```python
{
    "timestamp": 1689603600.123,      # Unix timestamp (ms precision)
    "lat": 47.3977,                   # GPS latitude
    "lon": 8.5455,                    # GPS longitude
    "alt": 45.2,                      # Altitude (meters)
    "vx": 5.1, "vy": 2.3, "vz": -0.5, # Velocities (m/s)
    "pitch": 2.1, "roll": -1.3, "yaw": 142.5,  # Attitude (degrees)
    "battery": 78.5,                  # Battery % (0-100)
    "armed": true,                    # Armed state
    "mode": "AUTO"                    # Flight mode
}
```

---

## 🗺️ Geofencing (No-Fly Zones)

NFZ polygon validation before mission upload:

```python
from autopilot.geofence import GeofenceValidator

validator = GeofenceValidator()
validator.load_nfz_zones("config/nfz_zones.geojson")

waypoints = [(47.39, 8.54, 50), (47.40, 8.55, 50), ...]
is_valid = validator.validate_mission(waypoints)

if not is_valid:
    print("❌ Mission crosses NFZ!")
```

---

## ⚠️ Failsafe Scenarios

| Trigger | Action | Details |
|---------|--------|---------|
| Battery < 20% | RTL (Return to Launch) | Auto-land at origin |
| Link loss > 3s | Hold position → RTL (30s) | Hover then return |
| Physical NFZ entry | Hold position | Operator can override |

---

## 📊 Definition of Done (DoD) — Veha 1

- [x] **Code Conformance:** Dockerfile + scripts follow best practices (no linting errors)
- [x] **Peer Review:** CI/CD files reviewed and tested
- [x] **Documentation:** README + API docs complete
- [x] **CI Integration:** GitHub Actions pipeline validates build
- [x] **Reproducibility:** Setup works on clean macOS machine in < 20 minutes

### Acceptance Criteria (Sprint Completion)

✅ **Veha 1 Acceptance Test:**
```bash
# On any team member's macOS:
make install              # Should complete in ~10 min
make docker-test          # Should print "✅ SITL validation passed"
docker run ... gazebo     # Should launch Gazebo without errors
```

---

## 🔄 GitHub Actions CI Pipeline

**Triggers:** Push to `main`, `develop`, or Pull Requests

**Jobs:**
1. **build-docker** — Build & push Docker image to GHCR
2. **validate-sitl** — Run SITL build validation
3. **code-quality** — Lint Python code (flake8)
4. **security-scan** — Trivy security scanning
5. **documentation** — Verify README exists

**Status badge:** [![CI/CD Pipeline](../../actions/workflows/sitl-ci.yml/badge.svg)](../../actions)

---

## 🔗 Next Steps (Veha 2 — Day 7)

- Implement `src/autopilot/plane.py` class with:
  - `arm()` / `disarm()`
  - `takeoff(altitude)` / `land()`
  - `hold_position()`
  - `fly_mission(waypoints)`
  - Telemetry polling (10 Hz)

**Dependency:** This Veha 1 (SITL infrastructure) must be complete ✅

---

## 📚 Documentation

- [Architecture Design](docs/ARCHITECTURE.md) — System overview
- [API Reference](docs/API.md) — MAVSDK/pymavlink methods
- [Deployment Guide](docs/DEPLOYMENT.md) — Production setup
- [Troubleshooting](docs/TROUBLESHOOTING.md) — Common issues

---

## 🤝 Contributing

1. Create feature branch: `git checkout -b feature/your-feature`
2. Make changes, commit: `git commit -am "feat: description"`
3. Push: `git push origin feature/your-feature`
4. Open Pull Request → CI validates automatically
5. After review & approval, merge to `main`

### Commit Message Format

```
<type>(<scope>): <subject>

<body>

Closes #<issue-number>
```

**Types:** `feat`, `fix`, `docs`, `test`, `refactor`, `ci`

---

## 📞 Support & Issues

- **Technical questions:** Check [Troubleshooting](docs/TROUBLESHOOTING.md)
- **Bug reports:** Open GitHub Issue with reproduction steps
- **Architecture questions:** Contact system architect
- **CI/CD issues:** Check GitHub Actions workflow logs

---

## 📋 References from TZ

- [51, 744] — SITL and Gazebo
- [242, 245] — MAVSDK & pymavlink
- [32, 246] — Mission planning & geofencing
- [34, 727] — Failsafe scenarios
- [108, 118] — CI/CD integration

---

**Status:** ✅ Veha 1 (Infrastructure) — COMPLETE

**Maintainers:** DevOps Team

**Last Updated:** 2026-07-17
