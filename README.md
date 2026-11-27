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
up.sh               validated pull/start helper
compose.sh          docker compose with the deployed config (logs, ps, down)
gen-auth.sh         generates AUTH_PASSWORD_HASH / JWT_SECRET for config.env
config.env.example  configuration template
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
./up.sh                         # first run: creates ~/.config/ptmm/config.env, then stops
vim ~/.config/ptmm/config.env   # TMDB key, MEDIA_DISK_MOUNT, CERT_DIR, HTTPS_PORT
./gen-auth.sh                   # optional: prints the auth lines to paste into config.env
./up.sh                         # validates config.env, then pulls the images and starts
```

- **Config directory**: `~/.config/ptmm` of the invoking user (the real user
  under `sudo`) holds everything the deployment keeps: `config.env`, the
  database `ptmm.db` and its rotating backups in `bak/`. Back up this one
  directory; the checkout holds no configuration. To put it elsewhere, set
  `PTMM_CONFIG_DIR` in the environment (not in `config.env`, which lives
  inside it), e.g. `PTMM_CONFIG_DIR=/srv/ptmm ./up.sh`, and the same for
  `compose.sh` and `gen-auth.sh`. `config.env` holds secrets: `up.sh` creates
  it with mode 600 and warns if others can read it.

- **Images**: `up.sh` pulls `ghcr.io/shengt25/ptmm-backend` and
  `ghcr.io/shengt25/ptmm-web` (`latest`), which GitHub Actions builds for
  linux/amd64 on every `v*` tag. `./up.sh --build` builds them from the
  checkout instead. Either way it then removes the dangling old images.
- **Network and ports**: both containers use the host's network. nginx serves
  `HTTPS_PORT` (default 8443); the backend listens on `127.0.0.1:BACKEND_PORT`
  (default 8000), reachable only from the host, for nginx. Set `BACKEND_PORT`
  in `config.env` if 8000 is taken. Because `127.0.0.1` in the containers is the
  host, a TMDB proxy running on the host is entered in Settings as usual, e.g.
  `http://127.0.0.1:7890`.
- **User**: `up.sh` runs the backend as the invoking user
  (`SUDO_UID`/`SUDO_GID` under `sudo`). Override with `PUID`/`PGID` in
  `config.env`; that user must own the config directory and the database.
- **Media**: `MEDIA_DISK_MOUNT` is the mount point of the disk holding both
  the downloads and the library (e.g. `/media/h16t0`). It goes into the
  container as a single mount because hard links fail with
  `Invalid cross-device link` across separate container mounts, even on the
  same disk, and at the same path as on the host because the database stores
  absolute paths.
- **Certificates**: `CERT_DIR` is mounted read-only as a directory, and the web
  container checks it every `CERT_RELOAD_INTERVAL` seconds (default 3600),
  reloading nginx when the files change. Whatever renews the certificate on
  the host needs no hook for this container. A root-only private key is fine:
  nginx's master process reads it as root inside the container.
- **Auth**: `gen-auth.sh` hashes the password inside the backend image. Keep
  the single quotes around `AUTH_PASSWORD_HASH` in `config.env` — without them
  Compose expands the `$` signs in the bcrypt hash; `up.sh` refuses to start in
  that case.

Useful commands:

```bash
./compose.sh logs -f
./compose.sh ps
./compose.sh down
./up.sh                 # update to the latest release (git pull first if compose.yaml changed)
```

`compose.sh` runs `docker compose` with `--env-file` pointing at
`config.env`; plain `docker compose` would look for a `.env` in the checkout
and miss the settings.

## Configuration

All deployment configuration lives in `config.env` in the config directory
(see Deployment); `config.env.example` is its template. The backend receives secrets through Compose
environment variables, so they are not copied into either image.
