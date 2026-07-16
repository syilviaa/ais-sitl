# Troubleshooting Guide

## Common Issues & Solutions

### Issue: Docker build fails on macOS

**Error:**
```
ERROR: buildx: error loading build config for docker-container driver: ...
```

**Solution:**
1. Ensure Docker Desktop is running
2. Rebuild buildx: `docker buildx create --use`
3. Retry: `make docker-build`

---

### Issue: `make install` hangs on Docker Desktop installation

**Symptom:** Script pauses after "Installing Docker Desktop..."

**Solution:**
1. Docker Desktop needs to be started manually after Homebrew install
2. Open Applications → Docker.app
3. Wait for Docker to fully launch (~1-2 minutes)
4. Re-run: `./install_macos.sh`

---

### Issue: Gazebo window doesn't appear (headless macOS)

**Problem:** Docker on macOS cannot display GUI without X11 forwarding

**Solutions:**

**Option A: Install XQuartz (Recommended)**
```bash
brew install xquartz

# Then add to ~/.zshrc:
export DISPLAY=:0

# Run with X11 forwarding:
docker run -it --rm \
  -e DISPLAY=host.docker.internal:0 \
  -v /tmp/.X11-unix:/tmp/.X11-unix \
  ais-sitl:latest gazebo
```

**Option B: Skip GUI, run headless**
```bash
# Validation only (no visualization)
docker run --rm ais-sitl:latest test

# Run SITL without Gazebo GUI
docker run --rm ais-sitl:latest shell
# Then inside container:
# cd /root/px4
# make px4_sitl gazebo_headless
```

---

### Issue: Port 14540 already in use

**Error:**
```
Error: Could not bind to port 14540
```

**Solution:**
1. Find process using port:
   ```bash
   lsof -i :14540
   ```

2. Kill it:
   ```bash
   kill -9 <PID>
   ```

3. Or use different port in Docker:
   ```bash
   docker run -p 14541:14540 ais-sitl:latest
   ```

---

### Issue: `pytest` not found or import errors

**Error:**
```
ModuleNotFoundError: No module named 'pytest'
```

**Solution:**
```bash
# Install test dependencies
pip install -r requirements.txt

# Or run via Docker
docker run --rm ais-sitl:latest test
```

---

### Issue: Shapely geometry errors in geofence tests

**Error:**
```
OSError: Could not find lib c or LoadLibrary failed
```

**Solution:**
```bash
# Reinstall Shapely with system dependencies
pip install --no-cache-dir shapely>=2.0.1

# Or use conda
conda install -c conda-forge shapely
```

---

### Issue: CI/CD pipeline fails on GitHub

**Symptom:** GitHub Actions workflow shows red X

**Debugging:**
1. Click Actions tab on GitHub repo
2. Select failed workflow run
3. Expand job logs
4. Common causes:
   - Docker build timeout (increase to 3600s in workflow)
   - Insufficient disk space in CI runner
   - Network timeout downloading dependencies

**Fix:**
```yaml
# In .github/workflows/sitl-ci.yml, increase timeout:
- name: Build Docker image
  timeout-minutes: 60  # Increased from default 360
```

---

### Issue: MAVLink connection fails in Python scripts

**Error:**
```
ConnectionError: Could not connect to autopilot at 127.0.0.1:14540
```

**Solutions:**
1. Ensure PX4 SITL is running:
   ```bash
   docker run -it --rm ais-sitl:latest gazebo
   ```

2. Check MAVLink listening:
   ```bash
   nc -zv 127.0.0.1 14540
   ```

3. Verify MAVSDK installation:
   ```bash
   python3 -c "import mavsdk; print(mavsdk.__version__)"
   ```

4. If using Docker container, ensure network is shared:
   ```bash
   docker run --network host ais-sitl:latest
   ```

---

### Issue: Git configuration errors

**Error:**
```
Your name and email address are not configured
```

**Solution:**
```bash
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"
```

---

### Issue: Makefile commands not found

**Symptom:** `Command not found: make`

**Solution (macOS):**
```bash
# Install GNU Make via Homebrew
brew install make

# Or use built-in BSD make
bmake  # BSD make (usually available by default)
```

---

## Performance & Optimization

### Gazebo simulation is slow

**Causes:**
- Simulation speed > 1.0× (SITL_SPEEDFACTOR)
- Physics engine too strict
- Insufficient CPU cores

**Solutions:**
```bash
# Check simulation speed in config/sitl.yaml
simulation_speed: 1.0  # 1.0 = realtime

# Reduce update rate for faster simulation
update_rate: 50  # Instead of 100 Hz

# Use faster physics engine
physics_engine: "bullet"  # Instead of ODE
```

---

### CI builds take too long

**Solution:** Enable build caching

```yaml
# In GitHub Actions workflow:
- name: Set up Docker buildx
  uses: docker/setup-buildx-action@v3
  
# Cache layers between builds
cache-from: type=gha
cache-to: type=gha,mode=max
```

---

## Logging & Debugging

### Enable debug logging

```bash
# In Python code:
import logging
logging.basicConfig(level=logging.DEBUG)

# Or set environment variable:
export LOG_LEVEL=DEBUG
python main.py

# View Docker logs:
docker logs <container_id>
```

### Capture MAVLink messages

```bash
# Using pymavlink mavlogdump:
python3 -m pymavlink.tools.mavlogdump sitl.log

# Or tcpdump (low-level):
tcpdump -i lo -A port 14540
```

---

## System Requirements Check

```bash
# Verify Docker installation
docker --version

# Check available disk space
df -h /var/lib/docker

# Test Docker daemon
docker run hello-world

# Verify Python
python3 --version

# Check network connectivity
ping google.com

# List open ports
lsof -i -P -n | grep LISTEN
```

---

## Getting Help

1. **Check logs:** `make logs` or `docker logs`
2. **GitHub Issues:** Report bug with:
   - Error message (full traceback)
   - Your OS/Docker version
   - Steps to reproduce
3. **Contact team:** See README.md Support section
4. **Documentation:** Check docs/ folder for architecture details

---

## Emergency Procedures

### Hard reset (last resort)

```bash
# Stop all containers
docker stop $(docker ps -aq)

# Remove Docker image
docker rmi ais-sitl:latest

# Clean project
make clean

# Start fresh
make install
```

### Reset Git repository

```bash
# Undo all local changes
git reset --hard HEAD

# Or reset to specific commit
git reset --hard <commit-hash>
```

---

**Last Updated:** 2026-07-17

**Maintained By:** DevOps Team
