import json
import os
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from pydantic import BaseModel
from datetime import datetime
from app.db.database import get_session
from app.db.models import Media
from app.db import crud
from app.core.scanner import VIDEO_EXT, scan_entry
from app.core.linker import create_links, delete_link

router = APIRouter(prefix="/scan", tags=["scan"])


@router.post("/")
def scan_all(session: Session = Depends(get_session)):
    entries = crud.entry_get_all(session)
    results = []
    for entry in entries:
        existing = crud.media_get_by_entry(session, entry.id)

        result = scan_entry(entry, existing)

        # auto-remove records whose link was manually deleted
        auto_removed = []
        for media in result.link_missing:
            if media.generated_files:
                paths = json.loads(media.generated_files)
                for f in paths:
                    Path(f).unlink(missing_ok=True)
            crud.media_delete(session, media)
            auto_removed.append(media.source_name)

        results.append({
            "entry_id": entry.id,
            "entry_name": entry.name,
            "added": result.added,
            "removed": [{"id": m.id, "source_name": m.source_name} for m in result.removed],
            "episode_updates": [
                {"media_id": u.media_id, "source_name": u.source_name, "files": u.files}
                for u in result.episode_updates
            ],
            "auto_removed": auto_removed,
            "notes": result.notes,
        })
    return results


class ConfirmAdd(BaseModel):
    entry_id: int
    source_path: str


class ConfirmRemove(BaseModel):
    media_id: int


class ConfirmEpisodeUpdates(BaseModel):
    media_id: int
    files: list[str]


@router.post("/confirm-add", status_code=204)
def confirm_add(data: ConfirmAdd, session: Session = Depends(get_session)):
    entry = crud.entry_get(session, data.entry_id)
    if not entry:
        raise HTTPException(404, "Entry not found")
    item_path = Path(entry.source_path) / data.source_path
    if not item_path.exists():
        raise HTTPException(422, f"Source not found: {data.source_path}")
    if entry.media_type == "movie" and item_path.is_file():
        source_name = item_path.stem
        link_name = source_name
    else:
        source_name = data.source_path
        link_name = None
    if crud.media_get_by_source_name(session, data.entry_id, source_name):
        raise HTTPException(400, "Media already exists")
    link_dir = Path(entry.link_path) / source_name
    if not link_dir.exists():
        create_links(entry.source_path, entry.link_path, data.source_path, link_name=link_name)
    size = sum(f.stat().st_size for f in link_dir.rglob("*") if f.is_file())
    media = Media(
        entry_id=data.entry_id,
        source_name=source_name,
        date_added=datetime.now().isoformat(timespec="seconds"),
        size=size,
    )
    crud.media_create(session, media)


def _safe_relative_path(value: str) -> Path:
    rel = Path(value)
    if rel.is_absolute() or ".." in rel.parts or value in {"", "."}:
        raise HTTPException(422, f"Invalid episode path: {value}")
    return rel


def _resolve_child(root: Path, rel: Path) -> Path:
    root_resolved = root.resolve()
    child = (root / rel).resolve()
    if child != root_resolved and root_resolved not in child.parents:
        raise HTTPException(422, f"Path escapes media directory: {rel}")
    return child


@router.post("/confirm-episode-updates")
def confirm_episode_updates(data: ConfirmEpisodeUpdates, session: Session = Depends(get_session)):
    media = crud.media_get(session, data.media_id)
    if not media:
        raise HTTPException(404, "Media not found")
    entry = crud.entry_get(session, media.entry_id)
    if not entry:
        raise HTTPException(404, "Entry not found")
    if entry.media_type != "tv":
        raise HTTPException(400, "Not a TV entry")

    source_root = Path(entry.source_path) / media.source_name
    link_root = Path(entry.link_path) / media.source_name
    if not source_root.exists():
        raise HTTPException(422, f"Source not found: {media.source_name}")
    if not link_root.exists():
        raise HTTPException(422, f"Link target not found: {media.source_name}")

    linked = 0
    existing = 0
    for value in data.files:
        rel = _safe_relative_path(value)
        if rel.suffix.lower() not in VIDEO_EXT:
            raise HTTPException(422, f"Not a supported video file: {value}")
        source_file = _resolve_child(source_root, rel)
        link_file = _resolve_child(link_root, rel)
        if not source_file.exists() or not source_file.is_file():
            raise HTTPException(422, f"Source episode not found: {value}")
        if link_file.exists():
            existing += 1
            continue
        link_file.parent.mkdir(parents=True, exist_ok=True)
        os.link(source_file, link_file)
        linked += 1

    if linked:
        link_dir = Path(entry.link_path) / media.source_name
        media.size = sum(f.stat().st_size for f in link_dir.rglob("*") if f.is_file())
        if media.scrape_status == "confirmed":
            media.scrape_status = "partial"
        crud.media_update(session, media)

    return {"linked": linked, "existing": existing}


@router.post("/confirm-remove", status_code=204)
def confirm_remove(data: ConfirmRemove, session: Session = Depends(get_session)):
    media = crud.media_get(session, data.media_id)
    if not media:
        raise HTTPException(404, "Media not found")
    entry = crud.entry_get(session, media.entry_id)
    delete_link(entry.link_path, media.source_name)
    crud.media_delete(session, media)
