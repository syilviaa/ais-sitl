# GitHub Repository Setup

Instructions for uploading the AIS SITL Platform to GitHub.

## Prerequisites

- GitHub account with write access
- `git` CLI installed
- SSH key configured (or GitHub token)

## Setup Steps

### 1. Create Empty Repository on GitHub

1. Go to https://github.com/new
2. **Repository name:** `ais-sitl-platform`
3. **Description:** "AIS Territorial Intelligence & Security Platform - SITL MVP"
4. **Visibility:** Public (for team collaboration)
5. **DO NOT** initialize with README, .gitignore, or license
6. Click "Create repository"

### 2. Add Remote & Push

```bash
# Navigate to project directory
cd ais-sitl-platform

# Add GitHub remote
git remote add origin git@github.com:YOUR-USERNAME/ais-sitl-platform.git

# Or use HTTPS if SSH not configured:
# git remote add origin https://github.com/YOUR-USERNAME/ais-sitl-platform.git

# Verify remote
git remote -v

# Push to GitHub
git push -u origin main
```

### 3. Configure Branch Protection (Optional)

On GitHub repository:

1. Go to **Settings** → **Branches**
2. Add rule for `main` branch:
   - ✅ Require a pull request before merging
   - ✅ Require status checks to pass
   - ✅ Require branches to be up to date
3. Save

### 4. Enable GitHub Actions

1. Go to **Actions** tab
2. Authorize workflows if prompted
3. Workflows should run automatically on push to `main`

### 5. Add Secrets (if needed for CI/CD)

Go to **Settings** → **Secrets and variables** → **Actions**

No secrets currently needed for SITL-only CI, but add if you later integrate with:
- Docker Hub push
- Cloud deployment
- Slack notifications

---

## Verify Setup

```bash
# Confirm origin is set
git remote -v
# Should show:
# origin  git@github.com:YOUR-USERNAME/ais-sitl-platform.git (fetch)
# origin  git@github.com:YOUR-USERNAME/ais-sitl-platform.git (push)

# Check if push was successful
git log --oneline -1
# Should show the initial commit

# Visit GitHub repository
# https://github.com/YOUR-USERNAME/ais-sitl-platform
```

---

## Team Onboarding

Once repository is live, team members can:

```bash
# Clone repository
git clone https://github.com/YOUR-USERNAME/ais-sitl-platform.git
cd ais-sitl-platform

# Set up local environment
make install

# Verify setup
make docker-test
```

---

## Continuous Development

### Creating Feature Branches

```bash
# Create feature branch from main
git checkout -b feature/your-feature-name

# Make changes, commit
git add <files>
git commit -m "feat(scope): description"

# Push branch
git push -u origin feature/your-feature-name

# Open Pull Request on GitHub
# → GitHub Actions runs CI automatically
# → Request review from team
# → Merge after approval
```

### Commit Message Format

```
<type>(<scope>): <subject>

<body (optional)>

Closes #<issue-number (if applicable)>
```

**Types:** `feat`, `fix`, `docs`, `test`, `refactor`, `ci`, `chore`

**Examples:**
```
feat(autopilot): implement arm/disarm commands
fix(geofence): correct polygon intersection check
docs(api): add MAVSDK connection examples
test(failsafe): add battery monitoring tests
```

---

## CI/CD Status

Check workflow status:

1. Go to **Actions** tab on GitHub
2. Select workflow: "PX4 SITL CI/CD Pipeline"
3. View job logs if failed

**Workflow jobs:**
- ✅ build-docker — Build Docker image
- ✅ validate-sitl — Test SITL build
- ✅ code-quality — Lint Python code
- ✅ security-scan — Trivy vulnerability scan
- ✅ documentation — Check README exists
- ✅ notify — Notify of CI status

---

## Troubleshooting GitHub Setup

### SSH Key Issues

```bash
# Test SSH connection
ssh -T git@github.com

# Should print:
# Hi YOUR-USERNAME! You've successfully authenticated...

# If fails, follow:
# https://docs.github.com/en/authentication/connecting-to-github-with-ssh
```

### HTTP/HTTPS Alternative

If SSH not configured, use HTTPS with token:

```bash
# Generate personal access token
# https://github.com/settings/tokens

# Clone with token
git clone https://YOUR-USERNAME:YOUR-TOKEN@github.com/YOUR-USERNAME/ais-sitl-platform.git
```

### Already Have Remote Origin

If you already have a remote, remove and re-add:

```bash
git remote remove origin
git remote add origin git@github.com:YOUR-USERNAME/ais-sitl-platform.git
git push -u origin main
```

---

## Next Steps (After GitHub Setup)

1. **Invite team members** — Settings → Manage access
2. **Create project** — Projects tab for sprint tracking
3. **Setup wiki** — Document team conventions
4. **Enable discussions** — For Q&A about development
5. **Set up deployments** — Actions for auto-deploy to servers (later)

---

**Repository:** https://github.com/YOUR-USERNAME/ais-sitl-platform

**Documentation:** See README.md for full project details

**Timeline:** Veha 1 complete (July 17, 2026) — Ready for Veha 2 (Flight control, July 21)
