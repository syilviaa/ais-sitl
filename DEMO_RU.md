# Тестирование AIS SITL — пошагово

## Режим A: SIH (лёгкий, без камеры)

```bash
cd ~/ais-sitl-platform
./scripts/start-px4-sitl.sh
./scripts/start-backend.sh
cd ~/ais-sitl-dashboard/web && npm run dev
```

Видео: **синтетический FPV** по телеметрии.

---

## Режим B: Gazebo + настоящая камера

```bash
# 1. GStreamer (один раз)
chmod +x scripts/install-gstreamer.sh
./scripts/install-gstreamer.sh

# 2. Gazebo SITL с камерой (≈650 MB образ)
chmod +x scripts/start-px4-gazebo.sh
./scripts/start-px4-gazebo.sh

# 3. Backend + dashboard (как обычно)
./scripts/start-backend.sh
cd ~/ais-sitl-dashboard/web && npm run dev
```

В dashboard: **Подключить SITL** → блок **Видеопоток** покажет **ЭФИР · Gazebo** (камера из симулятора).

Проверка видео:
```bash
curl http://127.0.0.1:5001/api/video/status
# gstreamer_available: true, udp_packets_sample > 0

# QGroundControl: Video Source = UDP h.264, порт 5600
```

---

## Чеклист MVP

| # | Действие | Ожидание |
|---|----------|----------|
| 1 | API **ОК**, WS **ЭФИР** | Связь есть |
| 2 | **Подключить SITL** | Дрон на карте Astana |
| 3 | **Видеопоток** | Gazebo: реальная картинка / SIH: синт. FPV |
| 4 | **Проверить** маршрут | OK — 4 точек |
| 5 | Точка в NFZ → **Проверить** | Заблокировано NFZ |
| 6 | **Взлёт → Удержание → Домой → Посадка** | Телеметрия меняется |

## Порты

| Порт | Назначение |
|------|------------|
| 5001 | Backend (macOS) |
| 14540 | MAVSDK (не пробрасывать из Docker) |
| 14580 | PX4 onboard |
| 5600 | Gazebo камера H.264/RTP |

После ошибки Initialize: `docker restart ais-px4-gazebo`
