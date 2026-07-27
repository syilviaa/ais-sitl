# AIS SITL — Demo за 10 минут (Sprint 1 MVP)

## Требования

- **Python 3.11** (не 3.14 — MAVSDK)
- **Node.js 18+**
- **PX4 SITL** локально (UDP onboard 14580 → remote 14540)

## 1. PX4 SITL (real)

```bash
chmod +x scripts/start-px4-sitl.sh
./scripts/start-px4-sitl.sh
```

Official image `px4io/px4-sitl` (SIH, headless). **Не пробрасывайте** host UDP 14540 — его занимает MAVSDK.

Проверка UDP:
```bash
./venv/bin/python scripts/mavlink_udp_probe.py --port 14540 --seconds 3
```
Должны быть datagrams (сотни/сек).

После неудачного Initialize: `docker restart ais-px4-sitl`

Проверка UDP:
```bash
./venv/bin/python scripts/mavlink_udp_probe.py --port 14540 --seconds 3
```
Должны быть datagrams с `127.0.0.1:14580`.

## 2. Backend

```bash
chmod +x scripts/setup-dev.sh scripts/start-backend.sh
./scripts/setup-dev.sh    # first time: Python 3.11 + MAVSDK
./scripts/start-backend.sh
```

Demo-only (no SITL):
```bash
curl -X POST http://127.0.0.1:5000/api/drone/initialize \
  -H 'Content-Type: application/json' \
  -d '{"demo":true}'
```

Проверка:
```bash
curl http://127.0.0.1:5000/api/health
curl -X POST http://127.0.0.1:5000/api/drone/initialize \
  -H 'Content-Type: application/json' \
  -d '{"port":14540,"sitl_port":14580}'
```

## 3. Dashboard

```bash
cd web
cp .env.example .env.local   # optional
npm install
npm run dev
```

Откройте http://127.0.0.1:5173

## 4. E2E сценарий

1. **Initialize SITL** → success  
2. **WS LIVE** в шапке + телеметрия на карте  
3. Mission → **Validate** (4 WP Astana) → OK  
4. Добавьте WP в NFZ → **Validate blocked**  
5. **Takeoff → Hold → RTL**

## Troubleshooting

- `lsof -i :14540` — порт свободен  
- SITL в Docker → `--network host`  
- См. `docs/TROUBLESHOOTING.md`
