"""
One-time migration from old ptmm database to new schema.
Backs up the original to .db.bak, then overwrites it with the new schema.

Default db: ~/.config/ptmm/ptmm.db
Run with --dry-run to preview without writing anything.
"""

import argparse
import json
import shutil
import sqlite3
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

DEFAULT_DB = Path("~/.config/ptmm/ptmm.db").expanduser()

MEDIA_TYPE_MAP = {
    "Series":    "tv",
    "Movies":    "movie",
    "Movies-PT": "movie",
    "Series-PT": "tv",
}

ARTWORK_EXT = {".nfo", ".jpg", ".png"}


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


def _calc_size(media_dir: Path) -> int | None:
    if not media_dir.exists():
        return None
    return sum(f.stat().st_size for f in media_dir.rglob("*") if f.is_file())


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


def migrate(old_db: Path, dry_run: bool = False):
    if not old_db.exists():
        print(f"Error: old database not found: {old_db}")
        sys.exit(1)

    old = sqlite3.connect(old_db)

    entries = old.execute(
        "SELECT entry_name, source_path, link_path FROM entry_path"
    ).fetchall()
    print(f"Found {len(entries)} entries in {old_db}")

    confirmed_total = 0
    pending_total = 0
    warnings = []

    if dry_run:
        for entry_name, source_path, link_path in entries:
            media_type = MEDIA_TYPE_MAP.get(entry_name, "movie")
            media_rows = old.execute(
                f'SELECT media_name, date FROM "{entry_name}"'
            ).fetchall()
            confirmed = 0
            pending = 0
            for media_name, _ in media_rows:
                status, _, _, _, warn = _scan_media(media_name, link_path, media_type)
                if status == "confirmed":
                    confirmed += 1
                else:
                    pending += 1
                if warn:
                    warnings.append(f"{entry_name}/{media_name}: {warn}")
            print(f"  {entry_name} ({media_type}): {len(media_rows)} items: confirmed {confirmed} / pending {pending}")
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
    print(f"Backup saved to: {bak}")

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
        for media_name, date in media_rows:
            status, tmdb_id, generated_files, size, warn = _scan_media(media_name, link_path, media_type)
            if warn:
                warnings.append(f"{entry_name}/{media_name}: {warn}")
            new.execute(
                "INSERT INTO media (entry_id, source_name, date_added, scrape_status, tmdb_id, generated_files, size)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (entry_id, media_name, date, status, tmdb_id, generated_files, size),
            )
            if status == "confirmed":
                confirmed += 1
            else:
                pending += 1

        confirmed_total += confirmed
        pending_total += pending
        print(f"  {entry_name} ({media_type}): {len(media_rows)} items: confirmed {confirmed} / pending {pending}")

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
    args = parser.parse_args()

    if not args.db.exists():
        print(f"Error: database not found: {args.db}")
        print("Use --db to specify the path.")
        sys.exit(1)

    migrate(args.db, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
