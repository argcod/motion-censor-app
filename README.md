# Smart Motion Detection Alarm System using IoT

Windows desktop IoT security console (Python 3 + CustomTkinter). Login → ESP32 serial + camera → isometric floor plan → motion events in MySQL → optional mobile alerts (Telegram / Discord / Twilio WhatsApp).

## Requirements

- Python 3.10+ recommended
- MySQL Server (local)
- Webcam (optional)
- ESP32 with PIR firmware in `esp32_firmware/main.ino` (optional)

## Setup

1. Create and activate a virtualenv, then install deps:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

2. Start MySQL. Default connection is `localhost` / database `motion_db` / user `root` / password `root`. On first launch the app creates the database, tables, and seeds admin + a default floor plan.

3. Confirm `assets/isometric_base.jpg` exists (shipped with the project).

4. Copy `.env.example` to `.env` and fill secrets for Mobile Alerts. Do not commit real tokens.

5. Flash `esp32_firmware/main.ino` to your ESP32. Note the COM port. Firmware sends `MOTION,{location},{sensorID}` at 115200 baud (e.g. `MOTION,Room1,Sensor01`).

6. Run:

```bash
python main.py
```

Default login: **admin** / **admin123** — change the password in Settings → Change Admin Password.

## Phase status

All phases **0–6** are complete for v1.

| Phase | What shipped |
|-------|----------------|
| 0 | Foundation, schema, 11 routes, login lifecycle |
| 1 | Floor-plan viewport (zoom/pan/fullscreen) |
| 2 | Place Mode + DeviceManager + Sensors/Cameras sync |
| 3 | 5-step animation, Active Alert, Simulate Motion |
| 4 | Snapshots, bell / unread, event details modal |
| 5 | Mobile Alert Hub (policy + TG / Discord / Twilio WA) |
| 6 | Reports PDF, Analytics ranges, image replace, serial reconnect polish, health widgets |

## Phase 6 highlights

- **Reports:** date range, summary KPIs, event table, PDF export
- **Analytics:** daily range chart + hourly chart for a selected day
- **Floor Plan / Settings:** Replace Image (copies into `assets/`, updates MySQL)
- **Settings → Serial:** port list, Save & Reconnect, live status label
- **Command Center:** ESP32 / Camera / Database health strip
- **Settings:** camera index restart, change admin password

## Mobile alerts

1. Copy `.env.example` → `.env` and fill Telegram / Discord / Twilio secrets (or enter them in Settings).
2. **Arm** = Away (external alerts). **Disarm** = Home (desktop toasts only).
3. Optional schedule e.g. `22:00` → `06:00` (overnight window supported).
4. Cooldown is separate from the ~2s desktop motion debounce.
5. WhatsApp uses **Twilio WhatsApp API** only (sandbox is fine for demos).
6. Never commit real tokens.

### Quick verify

| Case | Expected |
|------|----------|
| Disarmed + real motion | No mobile send |
| Armed + Telegram only | Telegram receives; Discord/WA silent |
| Outside schedule | No send |
| Cooldown active | Second event suppressed |
| Test Alert while Disarmed | Still sends + warning toast |

Run policy unit tests:

```bash
python -m unittest tests.test_alert_policy -v
```

## Acceptance checklist (v1)

1. App launches; login success/fail; Enter submits
2. Logout stops camera/serial; re-login starts them
3. All 11 sidebar routes open distinct pages
4. AI Security is a stub (not a dashboard clone)
5. Isometric image loads; missing asset shows guidance
6. Place PIR/camera; restart; markers remain
7. Simulate / real MOTION animates at marker; timeline syncs
8. Active Alert + MySQL event + unread badges
9. Sensors/Cameras stay in sync with floor markers
10. Settings Save & Reconnect applies new COM/baud
11. Mobile Disarmed quiet; Armed + channels send; schedule/cooldown work
12. Reports PDF + Analytics date range work
13. Floor plan image replace updates the viewport
14. No AI detection required for v1

## Project layout

```
main.py
requirements.txt
.env.example
assets/
snapshots/          # runtime
logs/
esp32_firmware/
utils/
core/
components/
ui/
tests/
_legacy/            # quarantined unused modules
```
