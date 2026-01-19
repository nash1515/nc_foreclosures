# Partner Access Design

## Overview

Secure remote access for partner (CJ Taylor) to NC Foreclosures system via Tailscale, with Google OAuth authentication and auto-starting services.

## Decisions Made

- **Network access:** Tailscale (installed on Windows side, WSL ports forwarded automatically)
- **Auth level:** Admin for both users
- **Reliability:** Auto-start on WSL boot (systemd services)
- **Backups:** Automatic daily before morning scrape

## Users

| Email | Role |
|-------|------|
| adamhnash@gmail.com | admin |
| cjtaylor0103@gmail.com | admin |

## Architecture

```
CJ's Computer                        Ahn's Computer (Windows + WSL)
┌─────────────┐                      ┌─────────────────────────────┐
│  Browser    │                      │  Windows                    │
│             │    Tailscale         │  ├─ Tailscale (100.x.x.x)  │
│  Tailscale  │◄──────────────────►  │  └─ WSL2 Port Forwarding    │
└─────────────┘    encrypted         │                             │
                   tunnel            │  WSL2                       │
                                     │  ├─ Flask API (:5001)       │
                                     │  ├─ React Frontend (:5173)  │
                                     │  ├─ PostgreSQL              │
                                     │  └─ Scheduler (existing)    │
                                     └─────────────────────────────┘
```

## Implementation Tasks

### 1. Authentication Setup

- Set `AUTH_DISABLED=false` in `.env`
- Add both users to database with admin role
- Update Google OAuth redirect URIs in Google Cloud Console:
  - Add: `http://[tailscale-ip]:5001/login/google/authorized`
- Set `ADMIN_EMAIL=adamhnash@gmail.com` as safety net

### 2. Systemd Services

**Flask API service** (`/etc/systemd/system/nc-foreclosures-api.service`):
```ini
[Unit]
Description=NC Foreclosures API
After=network.target postgresql.service

[Service]
Type=simple
User=ahn
WorkingDirectory=/home/ahn/projects/nc_foreclosures
Environment=PYTHONPATH=/home/ahn/projects/nc_foreclosures
ExecStart=/home/ahn/projects/nc_foreclosures/venv/bin/python -c "from web_app.app import create_app; create_app().run(host='0.0.0.0', port=5001)"
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Frontend service** (`/etc/systemd/system/nc-foreclosures-frontend.service`):
```ini
[Unit]
Description=NC Foreclosures Frontend
After=network.target

[Service]
Type=simple
User=ahn
WorkingDirectory=/home/ahn/projects/nc_foreclosures/frontend
ExecStart=/usr/bin/npm run dev -- --host --port 5173
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Control script** (`scripts/server_control.sh`):
- Commands: start, stop, status, logs, install
- Manages both API and frontend services

### 3. Backup Automation

**Backup script** (`scripts/backup_database.sh`):
- Runs `pg_dump` with gzip compression
- Stores in `backups/` directory
- Keeps last 7 days, auto-rotates older

**Schedule:** 4:55 AM daily (before 5 AM scraper run)

### 4. Tailscale Configuration

**Ahn's side:**
1. Get Tailscale IP from Windows system tray
2. Share device with cjtaylor0103@gmail.com in Tailscale admin console

**CJ's side:**
1. Install Tailscale from https://tailscale.com/download
2. Create account or sign in with Google
3. Accept device share invitation
4. Open browser to `http://[tailscale-ip]:5173`

## CJ Onboarding Instructions

1. Install Tailscale from https://tailscale.com/download
2. Create account or sign in with Google
3. Accept the device share from Ahn
4. Open browser to `http://[tailscale-ip]:5173`
5. Click "Login with Google" using cjtaylor0103@gmail.com
6. Done - full admin access

## Known Limitations

- System unavailable when Ahn's computer is off/sleeping/restarting
- CJ should ping Ahn if unable to connect
