# Backend

FastAPI backend for PT Media Manager.

## Stack

- **FastAPI**: web framework
- **SQLModel**: ORM, models shared between DB and API schemas
- **SQLite**: database, stored at `data/ptmm.db`
- **uvicorn**: ASGI server
- **httpx**: async-compatible HTTP client for TMDB API
- **guessit**: filename parser for extracting title/season/episode

## Structure

```
app/
  main.py         FastAPI app entry, mounts routers, runs backup loop
  config.py       pydantic-settings config (TMDB_API_KEY from .env)
  routers/
    entries.py    Entry CRUD (/entries/)
    media.py      Media list + episode list (/media/)
    scan.py       Scan + confirm-add/remove (/scan/)
    scrape.py     TMDB scraping + NFO generation (/scrape/)
  core/
    linker.py     Hard link creation and deletion
    scanner.py    Diff between source dir and DB records
    scraper.py    TMDB API calls, artwork download, episode NFO generation
    nfo.py        Read/write Kodi NFO files (XML)
    backup.py     Periodic SQLite backup
  db/
    database.py   SQLModel engine + session
    models.py     Entry and Media table models
    crud.py       DB operations
data/
  ptmm.db         SQLite database (gitignored)
  bak/            Automatic backups (gitignored)
dev.py            Development server (uvicorn with --reload)
```

## Key concepts

**Hard links**: `linker.py` creates hard links from `entry.source_path` to `entry.link_path`. The source is never modified. If source is a single file (not a directory), a subdirectory named after the file stem is created in `link_path` so NFO and artwork have a home.

**NFO files**: Kodi reads `.nfo` XML files for metadata. `nfo.py` writes `movie.nfo`, `tvshow.nfo`, and per-episode `<filename>.nfo`. NFO presence determines scrape status: if an NFO is deleted, the media is reset to `pending` on next scan.

**Scrape flow**: `GET /scrape/pending` -> guessit parses filename, TMDB search returns candidates -> `POST /scrape/{id}/confirm` fetches full detail, downloads artwork, writes NFOs, updates DB.

**Scan flow**: `POST /scan/` diffs source directory against DB records. Returns `added` (new files to link) and `removed` (source gone). Links manually deleted from `link_path` are auto-removed from DB with a warning.

## Running

```bash
uv sync
uv run dev.py        # development, with auto-reload

# production
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
```

## Environment

`.env` in this directory:
```
TMDB_API_KEY=your_tmdb_api_read_access_token
```
