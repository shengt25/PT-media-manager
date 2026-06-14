import json
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from pydantic import BaseModel
from datetime import datetime
from app.db.database import get_session
from app.db.models import Media
from app.db import crud
from app.core.scanner import scan_entry
from app.core.linker import create_links, delete_link
from app.core.nfo import nfo_exists

router = APIRouter(prefix="/scan", tags=["scan"])


@router.post("/")
def scan_all(session: Session = Depends(get_session)):
    entries = crud.entry_get_all(session)
    results = []
    for entry in entries:
        existing = crud.media_get_by_entry(session, entry.id)

        # reset scrape_status to pending if NFO file has been deleted
        for media in existing:
            if media.scrape_status == "confirmed":
                if not nfo_exists(entry.link_path, media.source_name, entry.media_type, video_stem=media.video_stem):
                    media.scrape_status = "pending"
                    crud.media_update(session, media)

        result = scan_entry(entry, existing)

        # auto-remove records whose link was manually deleted
        auto_removed = []
        for media in result.link_missing:
            if media.generated_files:
                try:
                    paths = json.loads(media.generated_files)
                except (json.JSONDecodeError, TypeError):
                    paths = []
                for f in paths:
                    Path(f).unlink(missing_ok=True)
            crud.media_delete(session, media)
            auto_removed.append(media.source_name)

        results.append({
            "entry_id": entry.id,
            "entry_name": entry.name,
            "added": result.added,
            "removed": [{"id": m.id, "source_name": m.source_name} for m in result.removed],
            "auto_removed": auto_removed,
            "notes": result.notes,
        })
    return results


class ConfirmAdd(BaseModel):
    entry_id: int
    source_name: str
    video_stem: str | None = None


class ConfirmRemove(BaseModel):
    media_id: int


@router.post("/confirm-add", status_code=204)
def confirm_add(data: ConfirmAdd, session: Session = Depends(get_session)):
    entry = crud.entry_get(session, data.entry_id)
    if not entry:
        raise HTTPException(404, "Entry not found")
    video_stem = data.video_stem
    if crud.media_get_by_source_and_link(session, data.entry_id, data.source_name, video_stem):
        raise HTTPException(400, "Media already exists")
    if not (Path(entry.source_path) / data.source_name).exists():
        raise HTTPException(422, f"Source not found: {data.source_name}")
    link_dir = Path(entry.link_path) / data.source_name
    if not link_dir.exists():
        create_links(entry.source_path, entry.link_path, data.source_name)
    size = sum(f.stat().st_size for f in link_dir.rglob("*") if f.is_file())
    media = Media(
        entry_id=data.entry_id,
        source_name=data.source_name,
        video_stem=video_stem,
        date_added=datetime.now().isoformat(timespec="seconds"),
        size=size,
    )
    crud.media_create(session, media)


@router.post("/confirm-remove", status_code=204)
def confirm_remove(data: ConfirmRemove, session: Session = Depends(get_session)):
    media = crud.media_get(session, data.media_id)
    if not media:
        raise HTTPException(404, "Media not found")
    entry = crud.entry_get(session, media.entry_id)
    delete_link(entry.link_path, media.source_name)
    crud.media_delete(session, media)
