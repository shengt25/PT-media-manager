import json
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlmodel import Session
from app.db.database import engine, get_session
from app.db import crud
from app.core.nfo import read_nfo

router = APIRouter(prefix="/media", tags=["media"])


def _get_generated_files(media_id: int) -> str:
    with Session(engine) as session:
        media = crud.media_get(session, media_id)
        if not media:
            raise HTTPException(404, "Media not found")
        if not media.generated_files:
            raise HTTPException(404, "Artwork not found")
        return media.generated_files


@router.get("/entry/{entry_id}")
def list_media(entry_id: int, session: Session = Depends(get_session)):
    entry = crud.entry_get(session, entry_id)
    if not entry:
        raise HTTPException(404, "Entry not found")
    media_list = crud.media_get_by_entry(session, entry_id)
    result = []
    for m in media_list:
        item = m.model_dump()
        if m.scrape_status in {"confirmed", "partial"}:
            item["metadata"] = read_nfo(m.generated_files, entry.media_type)
        if m.scrape_detail:
            detail = json.loads(m.scrape_detail)
            item["incomplete"] = any(e["status"] != "matched" for e in detail)
        else:
            item["incomplete"] = False
        result.append(item)
    return result


@router.get("/{media_id}/poster")
def get_poster(media_id: int):
    generated_files = _get_generated_files(media_id)
    paths = json.loads(generated_files)
    poster_path = next((p for p in paths if p.endswith("poster.jpg")), None)
    if poster_path is None or not Path(poster_path).exists():
        raise HTTPException(404, "Poster not found")
    return FileResponse(poster_path, media_type="image/jpeg")


@router.get("/{media_id}/thumb")
def get_thumb(media_id: int):
    generated_files = _get_generated_files(media_id)
    paths = json.loads(generated_files)
    thumb_path = next((p for p in paths if Path(p).name.endswith(".ptmm-thumb.jpg")), None)
    if thumb_path and Path(thumb_path).exists():
        return FileResponse(thumb_path, media_type="image/jpeg")
    raise HTTPException(404, "Thumbnail not found")


@router.get("/{media_id}/episodes")
def list_episodes(media_id: int, session: Session = Depends(get_session)):
    media = crud.media_get(session, media_id)
    if not media:
        raise HTTPException(404, "Media not found")
    if media.scrape_status not in {"confirmed", "partial"}:
        raise HTTPException(400, "Media is not confirmed")
    entry = crud.entry_get(session, media.entry_id)
    if entry.media_type != "tv":
        raise HTTPException(400, "Not a TV entry")
    return json.loads(media.scrape_detail) if media.scrape_detail else []
