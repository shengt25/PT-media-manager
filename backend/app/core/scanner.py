from pathlib import Path
from dataclasses import dataclass, field
from app.db.models import Entry, Media
from app.config import settings

VIDEO_EXT = {'.mkv', '.mp4', '.avi', '.m4v', '.mov', '.wmv', '.ts', '.flv', '.rmvb', '.webm', '.iso', '.m2ts', '.vob', '.mpg', '.mpeg'}


def _is_incomplete(path: Path) -> bool:
    if path.is_file():
        return path.suffix in settings.incomplete_ext
    for f in path.rglob("*"):
        if f.is_file() and f.suffix in settings.incomplete_ext:
            return True
    return False


def _is_only_hidden(path: Path) -> bool:
    if not path.is_dir():
        return False
    all_files = [f for f in path.rglob("*") if f.is_file()]
    return len(all_files) > 0 and all(f.name.startswith(".") for f in all_files)


def _movie_source_exists(source: Path, source_name: str) -> bool:
    """Check whether a movie's source item (directory or standalone video file) still exists."""
    item = source / source_name
    if item.is_dir():
        return not _is_only_hidden(item)
    if item.exists():
        return True
    return any(
        f.is_file() and f.suffix.lower() in VIDEO_EXT and not _is_incomplete(f)
        for f in source.glob(f"{source_name}.*")
    )


def find_main_video_stem(media_dir: Path) -> str | None:
    """Return the stem of the largest video/disc file directly in media_dir, or None if there isn't one."""
    if not media_dir.exists():
        return None
    candidates = [
        f for f in media_dir.iterdir()
        if f.is_file() and f.suffix.lower() in VIDEO_EXT and not f.name.startswith(".")
        and not _is_incomplete(f)
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda f: f.stat().st_size).stem


@dataclass
class ScanResult:
    entry_id: int
    entry_name: str
    added: list[dict]
    removed: list[Media]
    link_missing: list[Media]
    notes: list[str] = field(default_factory=list)


def scan_entry(entry: Entry, existing_media: list[Media]) -> ScanResult:
    source = Path(entry.source_path)

    try:
        items = sorted(source.iterdir(), key=lambda p: p.stat().st_ctime)
    except FileNotFoundError:
        return ScanResult(entry.id, entry.name, [], [], [])

    added = []
    notes = []

    existing_names = {m.source_name for m in existing_media}

    if entry.media_type == "movie":
        for item in items:
            name = item.name
            if name.startswith("."):
                continue
            if item.is_dir():
                if name in existing_names:
                    continue
                if _is_incomplete(item):
                    continue
                if _is_only_hidden(item):
                    notes.append(f'"{name}" has only hidden files in source, directory may be a leftover')
                    continue
                if find_main_video_stem(item) is None:
                    continue
                added.append({"source_path": name})
            elif item.is_file():
                if item.suffix.lower() not in VIDEO_EXT or _is_incomplete(item):
                    continue
                if item.stem in existing_names:
                    continue
                added.append({"source_path": name})
    else:
        for item in items:
            name = item.name
            if name in existing_names:
                continue
            if name.startswith("."):
                continue
            if _is_incomplete(source / name):
                continue
            if _is_only_hidden(source / name):
                notes.append(f'"{name}" has only hidden files in source, directory may be a leftover')
                continue
            added.append({"source_path": name})

    removed = []
    link_missing = []
    for media in existing_media:
        if entry.media_type == "movie":
            source_gone = not _movie_source_exists(source, media.source_name)
        else:
            source_item = source / media.source_name
            source_gone = not source_item.exists() or _is_only_hidden(source_item)

        if entry.media_type == "movie":
            link_dir = Path(entry.link_path) / media.source_name
            link_gone = find_main_video_stem(link_dir) is None
        else:
            link_gone = not (Path(entry.link_path) / media.source_name).exists()

        if source_gone:
            removed.append(media)
        elif link_gone:
            link_missing.append(media)

    return ScanResult(entry.id, entry.name, added, removed, link_missing, notes)
