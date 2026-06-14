"""
One-time migration from old ptmm database to new schema.
Backs up the original to .db.bak, then overwrites it with the new schema.

Default db: ~/.config/ptmm/ptmm.db
Run with --dry-run to preview without writing anything.
"""

import argparse
import json
import os
import shutil
import sqlite3
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import httpx

DEFAULT_DB = Path("~/.config/ptmm/ptmm.db").expanduser()
DEFAULT_BACKEND_ENV = Path(__file__).resolve().parents[1] / "backend" / ".env"
VIDEO_EXT = {".mkv", ".mp4", ".avi", ".m4v", ".mov", ".wmv", ".ts", ".flv", ".rmvb", ".webm", ".iso", ".m2ts", ".vob", ".mpg", ".mpeg"}

MEDIA_TYPE_MAP = {
    "Series":    "tv",
    "Movies":    "movie",
    "Movies-PT": "movie",
    "Series-PT": "tv",
}

ARTWORK_EXT = {".nfo", ".jpg", ".png"}
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w185"


def _read_tmdb_id(nfo_path: Path) -> int:
    tree = ET.parse(nfo_path)
    root = tree.getroot()
    uid = None
    for el in root.iter("uniqueid"):
        if el.get("type") == "tmdb":
            uid = el
            break
    if uid is None:
        uid = root.find("uniqueid")
    if uid is None or not uid.text:
        raise ValueError(f"No <uniqueid> found in {nfo_path}")
    return int(uid.text)


def _collect_generated(media_dir: Path) -> list[str]:
    return [
        str(p) for p in sorted(media_dir.rglob("*"))
        if p.is_file() and p.suffix.lower() in ARTWORK_EXT
    ]


def _find_poster_path(generated: list[str]) -> str | None:
    return next((p for p in generated if Path(p).name.endswith("poster.jpg")), None)


def _infer_thumb_path(poster_path: str) -> Path:
    return Path(poster_path).with_name(".ptmm-thumb.jpg")


def _httpx_client(proxy: str | None, timeout: int) -> httpx.Client:
    if not proxy:
        return httpx.Client(timeout=timeout)
    try:
        return httpx.Client(proxy=proxy, timeout=timeout)
    except TypeError:
        return httpx.Client(proxies=proxy, timeout=timeout)


def _fetch_tmdb_poster_path(tmdb_id: int, media_type: str, api_key: str, proxy: str | None = None) -> str | None:
    endpoint = "movie" if media_type == "movie" else "tv"
    with _httpx_client(proxy, timeout=15) as client:
        response = client.get(
            f"https://api.themoviedb.org/3/{endpoint}/{tmdb_id}",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        response.raise_for_status()
        data = response.json()
    return data.get("poster_path")


def _download_thumb(thumb_path: Path, poster_path: str, proxy: str | None = None) -> bool:
    thumb_path.parent.mkdir(parents=True, exist_ok=True)
    with _httpx_client(proxy, timeout=20) as client:
        response = client.get(f"{TMDB_IMAGE_BASE}{poster_path}")
        response.raise_for_status()
        thumb_path.write_bytes(response.content)
    return True


def _read_env_value(path: Path, key: str) -> str | None:
    if not path.exists():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, value = line.split("=", 1)
        if k == key:
            return value
    return None


def _resolve_tmdb_api_key(explicit_key: str | None) -> str | None:
    return explicit_key or os.environ.get("TMDB_API_KEY") or _read_env_value(DEFAULT_BACKEND_ENV, "TMDB_API_KEY")


def _resolve_tmdb_proxy(explicit_proxy: str | None) -> str | None:
    return explicit_proxy or os.environ.get("TMDB_PROXY") or _read_env_value(DEFAULT_BACKEND_ENV, "TMDB_PROXY")


def _ensure_poster_thumb(tmdb_id: int | None, media_type: str, generated_files: str | None, api_key: str | None, proxy: str | None) -> tuple[str | None, str | None]:
    if not generated_files:
        return generated_files, None
    try:
        generated = json.loads(generated_files)
    except (json.JSONDecodeError, TypeError):
        return generated_files, "generated_files is not valid JSON"

    existing_thumb = next((p for p in generated if Path(p).name.endswith(".ptmm-thumb.jpg")), None)
    if existing_thumb and Path(existing_thumb).exists():
        return generated_files, None

    poster_path = _find_poster_path(generated)
    if not poster_path:
        return generated_files, "poster.jpg not found, thumbnail skipped"
    if tmdb_id is None:
        return generated_files, "tmdb_id missing, thumbnail skipped"
    if not api_key:
        return generated_files, "TMDB API key missing, thumbnail skipped"

    thumb_path = _infer_thumb_path(poster_path)
    try:
        remote_poster_path = _fetch_tmdb_poster_path(tmdb_id, media_type, api_key, proxy)
        if not remote_poster_path:
            return generated_files, "TMDB poster_path missing, thumbnail skipped"
        _download_thumb(thumb_path, remote_poster_path, proxy)
    except (OSError, TimeoutError, httpx.HTTPError, json.JSONDecodeError) as e:
        return generated_files, f"thumbnail download failed: {e}"

    generated.append(str(thumb_path))
    return json.dumps(generated), None


def _calc_size(media_dir: Path) -> int | None:
    if not media_dir.exists():
        return None
    return sum(f.stat().st_size for f in media_dir.rglob("*") if f.is_file())


def _normalize_movie_source_name(source_path: str, link_path: str, media_name: str) -> tuple[str, str | None]:
    source_item = Path(source_path) / media_name
    if not source_item.is_file() or source_item.suffix.lower() not in VIDEO_EXT:
        return media_name, None

    normalized_name = source_item.stem
    old_link_dir = Path(link_path) / media_name
    new_link_dir = Path(link_path) / normalized_name
    if old_link_dir == new_link_dir:
        return normalized_name, None
    if not old_link_dir.exists():
        return normalized_name, f'old link directory not found for single-file movie: {old_link_dir}'
    if new_link_dir.exists():
        return normalized_name, f'target link directory already exists, not renamed: {new_link_dir}'
    old_link_dir.rename(new_link_dir)
    return normalized_name, f'renamed link directory: {old_link_dir.name} -> {new_link_dir.name}'


def _preview_source_name(source_path: str, media_name: str, media_type: str) -> tuple[str, str | None]:
    if media_type != "movie":
        return media_name, None
    source_item = Path(source_path) / media_name
    if not source_item.is_file() or source_item.suffix.lower() not in VIDEO_EXT:
        return media_name, None
    normalized_name = source_item.stem
    return normalized_name, f'single-file movie will use source_name: {normalized_name}'


def _scan_media(source_name: str, link_path: str, media_type: str) -> tuple[str, int | None, str | None, int | None, str | None]:
    media_dir = Path(link_path) / source_name
    if media_type == "movie":
        nfo_candidates = list(media_dir.glob("*.nfo")) if media_dir.exists() else []
        if nfo_candidates:
            nfo_path = nfo_candidates[0]
        else:
            nfo_path = media_dir / f"{source_name}.nfo"
    else:
        nfo_path = media_dir / "tvshow.nfo"

    size = _calc_size(media_dir)

    if not nfo_path.exists():
        return "pending", None, None, size, None

    try:
        tmdb_id = _read_tmdb_id(nfo_path)
    except (ValueError, ET.ParseError) as e:
        return "pending", None, None, size, str(e)

    generated = _collect_generated(media_dir)
    return "confirmed", tmdb_id, json.dumps(generated), size, None


def migrate(old_db: Path, dry_run: bool = False, tmdb_api_key: str | None = None, tmdb_proxy: str | None = None, skip_thumbnails: bool = False):
    if not old_db.exists():
        print(f"Error: old database not found: {old_db}")
        sys.exit(1)

    old = sqlite3.connect(old_db)
    tmdb_api_key = _resolve_tmdb_api_key(tmdb_api_key)
    tmdb_proxy = _resolve_tmdb_proxy(tmdb_proxy)

    entries = old.execute(
        "SELECT entry_name, source_path, link_path FROM entry_path"
    ).fetchall()
    print(f"Found {len(entries)} entries in {old_db}", flush=True)

    confirmed_total = 0
    pending_total = 0
    warnings = []

    if dry_run:
        if tmdb_api_key:
            print("TMDB API key found; confirmed items can download PTMM thumbnails during migration.", flush=True)
        else:
            print("TMDB API key not found; confirmed items will migrate without PTMM thumbnails.", flush=True)
        if tmdb_proxy:
            print(f"TMDB proxy configured: {tmdb_proxy}", flush=True)
        for entry_name, source_path, link_path in entries:
            media_type = MEDIA_TYPE_MAP.get(entry_name, "movie")
            media_rows = old.execute(
                f'SELECT media_name, date FROM "{entry_name}"'
            ).fetchall()
            confirmed = 0
            pending = 0
            for media_name, _ in media_rows:
                source_name, normalize_note = _preview_source_name(source_path, media_name, media_type)
                status, _, _, _, warn = _scan_media(source_name, link_path, media_type)
                if status == "confirmed":
                    confirmed += 1
                else:
                    pending += 1
                if normalize_note:
                    warnings.append(f"{entry_name}/{media_name}: {normalize_note}")
                if warn:
                    warnings.append(f"{entry_name}/{media_name}: {warn}")
            print(f"  {entry_name} ({media_type}): {len(media_rows)} items: confirmed {confirmed} / pending {pending}", flush=True)
            confirmed_total += confirmed
            pending_total += pending
        print(f"\nTotal: confirmed {confirmed_total} / pending {pending_total}")
        if warnings:
            print(f"\nWarnings ({len(warnings)}):")
            for w in warnings:
                print(f"  - {w}")
        print("\nDry run complete. Run without --dry-run to migrate.")
        old.close()
        return

    bak = old_db.with_suffix(".db.bak")
    shutil.copy2(old_db, bak)
    print(f"Backup saved to: {bak}", flush=True)
    if skip_thumbnails:
        print("Skipping PTMM thumbnail downloads.", flush=True)
    elif tmdb_proxy:
        print(f"TMDB proxy configured: {tmdb_proxy}", flush=True)

    old_db.unlink()
    new = sqlite3.connect(old_db)
    _create_schema(new)

    for entry_name, source_path, link_path in entries:
        media_type = MEDIA_TYPE_MAP.get(entry_name)
        if not media_type:
            warnings.append(f"Unknown entry '{entry_name}', treated as movie")
            media_type = "movie"

        new.execute(
            "INSERT INTO entry (name, source_path, link_path, media_type) VALUES (?, ?, ?, ?)",
            (entry_name, source_path, link_path, media_type),
        )
        entry_id = new.execute("SELECT last_insert_rowid()").fetchone()[0]

        media_rows = old.execute(
            f'SELECT media_name, date FROM "{entry_name}"'
        ).fetchall()

        confirmed = 0
        pending = 0
        print(f"  Migrating {entry_name} ({media_type}): {len(media_rows)} items", flush=True)
        for index, (media_name, date) in enumerate(media_rows, start=1):
            print(f"    [{index}/{len(media_rows)}] {media_name}", flush=True)
            source_name = media_name
            if media_type == "movie":
                source_name, normalize_warn = _normalize_movie_source_name(source_path, link_path, media_name)
                if normalize_warn:
                    warnings.append(f"{entry_name}/{media_name}: {normalize_warn}")
            status, tmdb_id, generated_files, size, warn = _scan_media(source_name, link_path, media_type)
            if warn:
                warnings.append(f"{entry_name}/{media_name}: {warn}")
            if status == "confirmed" and not skip_thumbnails:
                generated_files, thumb_warn = _ensure_poster_thumb(tmdb_id, media_type, generated_files, tmdb_api_key, tmdb_proxy)
                if thumb_warn:
                    warnings.append(f"{entry_name}/{media_name}: {thumb_warn}")
            new.execute(
                "INSERT INTO media (entry_id, source_name, date_added, scrape_status, tmdb_id, generated_files, size)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (entry_id, source_name, date, status, tmdb_id, generated_files, size),
            )
            if status == "confirmed":
                confirmed += 1
            else:
                pending += 1

        confirmed_total += confirmed
        pending_total += pending
        print(f"  {entry_name} ({media_type}): confirmed {confirmed} / pending {pending}", flush=True)

    new.commit()
    old.close()
    new.close()
    print(f"\nTotal: confirmed {confirmed_total} / pending {pending_total}")
    if warnings:
        print(f"\nWarnings ({len(warnings)}):")
        for w in warnings:
            print(f"  - {w}")
    print(f"\nMigration complete → {old_db} (backup: {bak})")


def _create_schema(conn: sqlite3.Connection):
    conn.executescript("""
        CREATE TABLE entry (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT    UNIQUE NOT NULL,
            source_path TEXT    UNIQUE NOT NULL,
            link_path   TEXT    UNIQUE NOT NULL,
            media_type  TEXT    NOT NULL
        );
        CREATE TABLE media (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            entry_id        INTEGER NOT NULL REFERENCES entry(id),
            source_name     TEXT    NOT NULL,
            date_added      TEXT    NOT NULL,
            scrape_status   TEXT    NOT NULL DEFAULT 'pending',
            tmdb_id         INTEGER,
            generated_files TEXT,
            size            INTEGER
        );
    """)


def main():
    parser = argparse.ArgumentParser(description="Migrate old ptmm database to new schema.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, metavar="PATH",
                        help=f"Path to database (default: {DEFAULT_DB})")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview what would be migrated without writing anything")
    parser.add_argument("--tmdb-api-key",
                        help="TMDB API key for downloading PTMM thumbnails during migration")
    parser.add_argument("--tmdb-proxy",
                        help="HTTP/HTTPS proxy for TMDB requests, e.g. http://127.0.0.1:7890")
    parser.add_argument("--skip-thumbnails", action="store_true",
                        help="Migrate database only; do not download PTMM thumbnails")
    args = parser.parse_args()

    if not args.db.exists():
        print(f"Error: database not found: {args.db}")
        print("Use --db to specify the path.")
        sys.exit(1)

    migrate(
        args.db,
        dry_run=args.dry_run,
        tmdb_api_key=args.tmdb_api_key,
        tmdb_proxy=args.tmdb_proxy,
        skip_thumbnails=args.skip_thumbnails,
    )


if __name__ == "__main__":
    main()
