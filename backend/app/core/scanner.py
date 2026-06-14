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

    if entry.media_type == "movie":
        existing_pairs = {(m.source_name, m.video_stem) for m in existing_media}
        for item in items:
            if not item.is_dir():
                continue
            folder_name = item.name
            if folder_name.startswith("."):
                continue
            if _is_incomplete(item):
                continue
            if _is_only_hidden(item):
                notes.append(f'"{folder_name}" has only hidden files in source, directory may be a leftover')
                continue
            video_stem = find_main_video_stem(item)
            if video_stem is None:
                continue
            if (folder_name, video_stem) in existing_pairs:
                continue
            added.append({"source_name": folder_name, "video_stem": video_stem})
    else:
        existing_names = {m.source_name for m in existing_media}
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
            added.append({"source_name": name, "video_stem": None})

    removed = []
    link_missing = []
    for media in existing_media:
        source_item = source / media.source_name
        source_gone = not source_item.exists() or _is_only_hidden(source_item)

        if entry.media_type == "movie" and media.video_stem:
            link_dir = Path(entry.link_path) / media.source_name
            link_gone = not link_dir.exists() or not any(
                f for f in link_dir.glob(f"{media.video_stem}.*")
                if f.suffix.lower() in VIDEO_EXT
            )
        else:
            link_gone = not (Path(entry.link_path) / media.source_name).exists()

        if source_gone:
            removed.append(media)
        elif link_gone:
            link_missing.append(media)

    return ScanResult(entry.id, entry.name, added, removed, link_missing, notes)
