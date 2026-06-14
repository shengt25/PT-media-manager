# PT Media Manager

Personal media management tool for Private Tracker (PT) downloads. Replaces TinyMediaManager with a self-hosted web app.

## What it does

- Creates hard links from PT download directory to Kodi library directory, source files are never touched, seeding is unaffected
- Scrapes metadata from TMDB and writes Kodi-compatible NFO files
- Generates episode NFOs for TV shows (incremental sync supported)
- Downloads poster and fanart artwork

## Architecture

```
browser → nginx (443) → frontend/dist/   (static files)
                      → /api/* → uvicorn :8000 → FastAPI
                                                 └── SQLite (backend/data/ptmm.db)
```

- **Frontend**: React + TypeScript + Vite + shadcn/ui, built to `frontend/dist/`
- **Backend**: FastAPI + SQLModel + SQLite, runs with uvicorn
- **nginx**: SSL termination, serves frontend, proxies `/api/` to backend
- **systemd**: manages the backend process

## Project structure

```
frontend/       React frontend
backend/        FastAPI backend
nginx/          nginx site config template
systemd/        systemd service template
install.sh      install / update script
uninstall.sh    remove service and nginx config
.env.example    configuration template
```

## Quick start (development)

```bash
# Backend
cd backend
uv sync
uv run dev.py          # http://localhost:8000

# Frontend
cd frontend
npm install
npm run dev            # http://localhost:5173
```

## Deployment

The installer supports two deployment modes:

- **Internal**: HTTP, no auth, intended for access by NAS IP inside a trusted private network
- **Public**: HTTPS + JWT auth, intended for domain-based internet access

```bash
# 1. Clone on server, set up config
cp .env.example .env
vim .env

# 2. For public mode only, set up SSL first
sudo certbot --nginx -d yourdomain.com

# 3. Install
bash install.sh

# 4. Update (after git pull)
bash install.sh
```

## Configuration

All deployment config lives in `.env` (see `.env.example`). The only secret the backend needs is `TMDB_API_KEY`, which `install.sh` writes to `backend/.env` automatically.
