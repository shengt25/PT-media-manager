# PT Media Manager

Personal media management tool for Private Tracker (PT) downloads. Replaces TinyMediaManager with a self-hosted web app.

## What it does

- Creates hard links from PT download directory to Kodi library directory, source files are never touched, seeding is unaffected
- Scrapes metadata from TMDB and writes Kodi-compatible NFO files
- Generates episode NFOs for TV shows (incremental sync supported)
- Downloads poster and fanart artwork

## Architecture

```
browser → web container (TLS + static frontend)
                      → /api/* → backend container → FastAPI
                                                   └── SQLite (/data/ptmm.db)
```

- **Frontend**: React + TypeScript + Vite + shadcn/ui, built to `frontend/dist/`
- **Backend**: FastAPI + SQLModel + SQLite, runs with uvicorn
- **Docker Compose**: runs the backend (non-root, as `PUID:PGID`) and the web
  container side by side
- **nginx** (web container): TLS termination, serves the frontend, proxies
  `/api/` to the backend, rate-limits login, reloads itself when the
  certificate changes

## Project structure

```
frontend/       React frontend
backend/        FastAPI backend
docker/         backend/frontend images and nginx configuration
compose.yaml    container definitions
up.sh           validated build/start helper
gen-auth.sh     generates AUTH_PASSWORD_HASH / JWT_SECRET for .env
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

Needs only Docker with the Compose plugin on the server.

```bash
cp .env.example .env
vim .env                 # TMDB key, MEDIA_ROOT, CERT_DIR, HTTPS_PORT
./gen-auth.sh            # optional: prints the auth lines to paste into .env
./up.sh                  # validates .env, then builds and starts
```

- **User and data**: `up.sh` runs the backend as the invoking user
  (`SUDO_UID`/`SUDO_GID` under `sudo`) and keeps the database plus its
  rotating backups in `~/.config/ptmm`. Override with `PUID`/`PGID`/`DATA_DIR`
  in `.env`.
- **Media**: mount a common parent of both the download and library
  directories as `MEDIA_ROOT`. Hard links fail with `Invalid cross-device link`
  if source and destination are separate container mounts. It is mounted at
  the same path as on the host because the database stores absolute paths.
- **Certificates**: `CERT_DIR` is mounted read-only as a directory, and the web
  container checks it every `CERT_RELOAD_INTERVAL` seconds (default 3600),
  reloading nginx when the files change. Whatever renews the certificate on
  the host needs no hook for this container. A root-only private key is fine:
  nginx's master process reads it as root inside the container.
- **Auth**: `gen-auth.sh` hashes the password inside the backend image. Keep
  the single quotes around `AUTH_PASSWORD_HASH` in `.env` — without them
  Compose expands the `$` signs in the bcrypt hash; `up.sh` refuses to start in
  that case.

Useful commands:

```bash
docker compose logs -f
docker compose down
./up.sh                 # rebuild and update after git pull
```

## Configuration

All deployment configuration lives in the gitignored root `.env`; use
`.env.example` as its template. The backend receives secrets through Compose
environment variables, so they are not copied into either image.
