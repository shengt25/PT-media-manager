import sqlite3
import time
from pathlib import Path
from app.config import settings

BACKUP_INTERVAL_DAYS = 7


def _db_path() -> Path:
    return Path(settings.db_path)


def _backup_dir() -> Path:
    return _db_path().parent / "bak"


def _needs_backup() -> bool:
    latest = _backup_dir() / "ptmm.db.1"
    if not latest.exists():
        return True
    age_days = (time.time() - latest.stat().st_mtime) / 86400
    return age_days >= BACKUP_INTERVAL_DAYS


def run_backup():
    db = _db_path()
    if not db.exists():
        return
    bak = _backup_dir()
    bak.mkdir(parents=True, exist_ok=True)

    # rotate: .4 -> .5, .3 -> .4, ..., .1 -> .2
    for i in range(settings.backup_count - 1, 0, -1):
        src = bak / f"ptmm.db.{i}"
        dst = bak / f"ptmm.db.{i + 1}"
        if src.exists():
            if dst.exists():
                dst.unlink()
            src.rename(dst)

    with sqlite3.connect(str(db)) as src_conn:
        with sqlite3.connect(str(bak / "ptmm.db.1")) as dst_conn:
            src_conn.backup(dst_conn)
