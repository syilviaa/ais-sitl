# Veha 5 Deployment to Render.com

**Complete guide for deploying the AIS SITL multi-drone platform to Render.com**

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Render.com Setup](#rendercom-setup)
3. [Database Configuration](#database-configuration)
4. [Backend Deployment](#backend-deployment)
5. [Frontend Deployment](#frontend-deployment)
6. [Environment Variables](#environment-variables)
7. [Verification & Testing](#verification--testing)
8. [Monitoring & Logs](#monitoring--logs)
9. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required Accounts & Tools
- ✅ Render.com account (free tier available)
- ✅ GitHub account (for code repository)
- ✅ Git installed locally
- ✅ Docker installed (for local testing)

### Repository Requirements
- ✅ Code pushed to GitHub: `feat/veha5-multidrone` branch
- ✅ `Dockerfile.backend` configured
- ✅ `requirements.txt` up to date
- ✅ `docker-compose.yml` for local testing

---

## Render.com Setup

### Step 1: Create Render Account

1. Go to [https://render.com](https://render.com)
2. Click **Sign Up**
3. Connect GitHub account
4. Authorize Render to access repositories

### Step 2: Create PostgreSQL Database

**In Render Dashboard:**

1. Click **+ New** → **PostgreSQL**
2. Configure:
   - **Name:** `ais-sitl-db`
   - **Database:** `ais_sitl`
   - **User:** `postgres`
   - **Region:** Choose closest to you (e.g., `oregon` for US West)
   - **Plan:** Starter (free tier, 256MB)

3. Click **Create Database**
4. **Save the connection string** (you'll need it):
   ```
   postgresql://[user]:[password]@[host]:[port]/[database]
   ```

### Step 3: Create Backend Web Service

**In Render Dashboard:**

1. Click **+ New** → **Web Service**
2. Connect GitHub repository:
   - Select `ais-sitl` repository
   - Select branch: `feat/veha5-multidrone`
   - Click **Connect**

3. Configure service:
   - **Name:** `ais-sitl-backend`
   - **Environment:** `Docker`
   - **Region:** `oregon` (match database)
   - **Branch:** `feat/veha5-multidrone`
   - **Dockerfile path:** `Dockerfile.backend`
   - **Plan:** Free tier

4. Click **Create Web Service**

**⚠️ Don't start deployment yet** - we need to set environment variables first

---

## Database Configuration

### PostgreSQL Connection String

From the PostgreSQL database page, copy the **Internal Database URL** (for services within Render):

```
postgresql://[user]:[password]@[internal-host]:5432/ais_sitl
```

This will be used for the backend service.

---

## Backend Deployment

### Step 1: Set Environment Variables

In Render Dashboard → Backend Service → **Environment**:

Add the following variables:

```bash
# Database
DATABASE_URL=postgresql://[user]:[password]@[internal-host]:5432/ais_sitl

# Flask Configuration
FLASK_ENV=production
FLASK_DEBUG=False
SECRET_KEY=generate-random-secret-key-here

# Redis (optional - can use in-memory cache for free tier)
REDIS_URL=

# Logging
LOG_LEVEL=INFO

# API Configuration
API_HOST=0.0.0.0
API_PORT=10000

# CORS Settings
CORS_ORIGINS=*
```

**Generate SECRET_KEY:**
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

### Step 2: Configure Build Settings

In the Web Service settings:

- **Build Command:** 
  ```
  pip install -r requirements.txt
  ```

- **Start Command:**
  ```
  gunicorn --workers 3 --threads 2 --worker-class gthread --bind 0.0.0.0:10000 run_backend:app
  ```

**Note:** If using Flask-SocketIO, use:
  ```
  gunicorn --workers 1 --worker-class geventwebsocket.gunicorn.workers.GeventWebSocketWorker --bind 0.0.0.0:10000 run_backend:app
  ```

### Step 3: Update Dockerfile.backend for Render

The Dockerfile needs a few adjustments for Render:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY src/ ./src/
COPY run_backend.py .

# Create logs directory
RUN mkdir -p logs

# Expose port
EXPOSE 10000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:10000/api/health')"

# Run with gunicorn
CMD ["gunicorn", "--workers", "3", "--threads", "2", "--worker-class", "gthread", "--bind", "0.0.0.0:10000", "run_backend:app"]
```

### Step 4: Update run_backend.py

Ensure it creates the app factory properly:

```python
import os
from src.backend.app import create_app

app, socketio = create_app({
    'DEBUG': os.getenv('FLASK_DEBUG', 'False') == 'True',
})

if __name__ == '__main__':
    # For development
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
    
# For production (gunicorn uses 'app' directly)
```

### Step 5: Deploy Backend

1. Go back to Web Service page
2. Click **Manual Deploy** or wait for auto-deployment
3. Monitor logs in **Logs** tab
4. Wait for status to change to **Live** (green)

**Expected output:**
```
2026-07-26 10:30:45 Building...
2026-07-26 10:32:15 Deploying...
2026-07-26 10:35:00 [OK] Deployed successfully
```

---

## Frontend Deployment

### Step 1: Create Frontend Web Service

**In Render Dashboard:**

1. Click **+ New** → **Static Site**
2. Connect GitHub:
   - Select `ais-sitl` repository
   - Branch: `feat/veha5-multidrone`
   - **Publish directory:** `web/dist`

3. Configure:
   - **Name:** `ais-sitl-frontend`
   - **Build Command:**
     ```
     cd web && npm install && npm run build
     ```
   - **Publish Directory:** `web/dist`

4. Click **Create Static Site**

### Step 2: Configure Environment for Frontend

In `web/.env`:

```bash
VITE_API_URL=https://ais-sitl-backend.onrender.com
```

Or update at build time via Render environment variables:

```bash
VITE_API_URL=https://[your-backend-url].onrender.com
```

### Step 3: Deploy Frontend

Frontend will auto-deploy after build completes.

**Expected output:**
```
2026-07-26 10:40:00 Building...
2026-07-26 10:42:30 Publishing...
2026-07-26 10:45:00 [OK] Deployed successfully
Site: https://ais-sitl-frontend.onrender.com
```

---

## Environment Variables

### Complete Environment Setup

**Backend Service Environment Variables:**

```
# Database
DATABASE_URL=postgresql://user:password@host:5432/ais_sitl

# Flask
FLASK_ENV=production
FLASK_DEBUG=False
SECRET_KEY=[random-generated-key]

# Application
API_HOST=0.0.0.0
API_PORT=10000
LOG_LEVEL=INFO

# CORS
CORS_ORIGINS=https://ais-sitl-frontend.onrender.com,http://localhost:3000

# Optional: Redis (for caching)
REDIS_URL=

# Optional: Monitoring
SENTRY_DSN=
```

### Frontend Environment Variables (in web/.env)

```
VITE_API_URL=https://ais-sitl-backend.onrender.com
VITE_API_TIMEOUT=30000
VITE_DEBUG=false
```

---

## Verification & Testing

### Step 1: Test Backend Health

```bash
curl https://ais-sitl-backend.onrender.com/api/health

# Expected response:
# {"status": "ok", "version": "0.1.0", "drone_connected": false}
```

### Step 2: Test Frontend

```bash
# Open in browser
https://ais-sitl-frontend.onrender.com
```

### Step 3: Test Key Endpoints

```bash
# Fleet management
curl https://ais-sitl-backend.onrender.com/api/fleet/status

# Metrics
curl https://ais-sitl-backend.onrender.com/api/metrics/summary

# Geofence
curl https://ais-sitl-backend.onrender.com/api/geofence/list
```

### Step 4: Test Database Connection

In Render PostgreSQL dashboard:

```bash
# Connect via psql
psql postgresql://user:password@host:5432/ais_sitl

# Inside psql:
\dt              # List tables
SELECT * FROM drones;  # Test query
```

---

## Monitoring & Logs

### Step 1: Access Logs

**Backend Logs:**
- Render Dashboard → Backend Service → **Logs**
- Real-time streaming of application output

**Frontend Logs:**
- Render Dashboard → Static Site → **Logs**
- Build and deployment logs

### Step 2: Set Up Error Tracking (Optional)

**Using Sentry (free tier):**

1. Create [Sentry.io](https://sentry.io) account
2. Create new project (Python)
3. Get DSN key
4. Add to backend environment:
   ```
   SENTRY_DSN=https://[key]@[sentry-host].ingest.sentry.io/[project-id]
   ```
5. Update `run_backend.py`:
   ```python
   import sentry_sdk
   sentry_sdk.init(
       dsn=os.getenv('SENTRY_DSN'),
       traces_sample_rate=0.1
   )
   ```

### Step 3: Monitor Performance

- **Render Dashboard** → **Metrics**
  - CPU usage
  - Memory usage
  - Request count
  - Response times

### Step 4: Set Up Alerts (Pro Feature)

Enable alerts for:
- Service down
- High CPU usage (> 80%)
- High memory usage (> 80%)
- Frequent restarts

---

## Troubleshooting

### Backend Won't Deploy

**Error: "Build failed"**
```
Solution:
1. Check Dockerfile.backend exists
2. Verify requirements.txt has all dependencies
3. Check logs for missing dependencies
4. Ensure Python version is 3.11+
```

**Error: "Application failed to start"**
```
Solution:
1. Check DATABASE_URL is set correctly
2. Verify database is running
3. Check SECRET_KEY is set
4. Run migrations if needed
```

### Database Connection Issues

```bash
# Test connection locally first
psql postgresql://user:password@host:5432/ais_sitl

# Check DATABASE_URL format
postgresql://username:password@hostname:port/database

# Verify firewall rules
# Render → Database → Settings → Firewall
# Ensure backend service IP is whitelisted
```

### Frontend Not Loading API

**Error: "CORS error"**
```
Solution:
1. Check CORS_ORIGINS environment variable
2. Verify frontend URL is included
3. Check backend is returning correct headers
4. Restart backend service
```

**Error: "API not responding"**
```
Solution:
1. Verify backend service is running (green status)
2. Check API_URL in frontend .env file
3. Test endpoint directly: curl https://backend-url/api/health
4. Check network tab in browser dev tools
```

### Slow Performance

```
Solution:
1. Upgrade to paid tier for more resources
2. Enable Redis caching
3. Optimize database queries
4. Check Render metrics for bottlenecks
5. Consider using CDN for static files
```

### Database Size Exceeded

```
Solution:
1. Render free tier: 256MB limit
2. Delete old recordings: DELETE FROM mission_recordings WHERE created_at < NOW() - INTERVAL '30 days'
3. Archive telemetry data
4. Upgrade to larger plan
```

---

## Production Deployment Checklist

### Pre-Deployment
- [ ] Code committed to `feat/veha5-multidrone` branch
- [ ] All tests passing locally
- [ ] Environment variables documented
- [ ] Dockerfile.backend tested locally
- [ ] requirements.txt up to date
- [ ] Database migrations ready

### Deployment
- [ ] PostgreSQL database created on Render
- [ ] Backend service created and configured
- [ ] Frontend service created and configured
- [ ] Environment variables set
- [ ] Build commands configured
- [ ] Start commands configured

### Post-Deployment
- [ ] Backend health check passing
- [ ] Frontend loads without errors
- [ ] Database connection verified
- [ ] API endpoints responding
- [ ] Logs being collected
- [ ] Monitoring configured

### Production Hardening
- [ ] HTTPS enabled (automatic on Render)
- [ ] CORS configured properly
- [ ] Rate limiting enabled
- [ ] Error tracking setup (Sentry)
- [ ] Database backups enabled
- [ ] Uptime monitoring configured

---

## Scaling Considerations

### Free Tier Limitations
- Backend: 0.5 CPU, 512MB RAM
- Database: 256MB storage
- Suitable for: Testing, demo, small deployments

### Recommended for Production
- Backend: **Starter** plan ($7/month)
  - 0.5 CPU, 1GB RAM
  - Suitable for: 2-5 drones, testing
- Backend: **Standard** plan ($12/month)
  - 1 CPU, 2GB RAM
  - Suitable for: 5-20 drones, production
- Database: **Starter** plan ($15/month)
  - 1GB storage
  - Daily backups

### Multi-Drone Fleet Scaling
```
Fleet Size | Recommended Resources
-----------|----------------------
2-5        | Free tier (testing)
5-20       | Starter plan
20-50      | Standard plan
50+        | Pro plan + additional workers
```

---

## Deployment URLs

Once deployed, your platform will be available at:

```
Backend API:       https://ais-sitl-backend.onrender.com
Frontend:          https://ais-sitl-frontend.onrender.com

API Health:        https://ais-sitl-backend.onrender.com/api/health
Fleet Status:      https://ais-sitl-backend.onrender.com/api/fleet/status
Metrics:           https://ais-sitl-backend.onrender.com/api/metrics/summary
Prometheus:        https://ais-sitl-backend.onrender.com/metrics
```

---

## Post-Deployment Operations

### Database Maintenance

```bash
# Connect to database
psql postgresql://user:password@host:5432/ais_sitl

# Backup database
pg_dump postgresql://user:password@host:5432/ais_sitl > backup.sql

# Monitor database size
SELECT pg_size_pretty(pg_database_size('ais_sitl'));

# Clean up old data
DELETE FROM telemetry_records WHERE timestamp < NOW() - INTERVAL '90 days';
VACUUM ANALYZE;
```

### Monitoring Health

```bash
# Check service status daily
curl https://ais-sitl-backend.onrender.com/api/health

# View metrics
curl https://ais-sitl-backend.onrender.com/api/metrics/summary | jq

# Monitor logs via Render Dashboard
# Backend Logs → Search for errors
```

### Updating Deployment

```bash
# Make changes locally
git add .
git commit -m "Update configuration"
git push origin feat/veha5-multidrone

# Render auto-deploys on push
# Monitor in Render Dashboard → Deployments
```

---

## Support & Resources

- **Render Documentation:** https://render.com/docs
- **PostgreSQL Help:** https://www.postgresql.org/docs/
- **Flask Deployment:** https://flask.palletsprojects.com/deployment/
- **Docker Compose Guide:** https://docs.docker.com/compose/

---

**Deployment Status:** ✅ Ready for Render.com  
**Last Updated:** 2026-07-26  
**Version:** 5.0.0
