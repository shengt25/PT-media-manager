from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlmodel import Session
from app.db.database import get_session
from app.db import crud
from app.core.nfo import read_nfo, read_episode_nfos

router = APIRouter(prefix="/media", tags=["media"])


@router.get("/entry/{entry_id}")
def list_media(entry_id: int, session: Session = Depends(get_session)):
    entry = crud.entry_get(session, entry_id)
    if not entry:
        raise HTTPException(404, "Entry not found")
    media_list = crud.media_get_by_entry(session, entry_id)
    result = []
    for m in media_list:
        item = m.model_dump()
        if m.scrape_status == "confirmed":
            item["metadata"] = read_nfo(entry.link_path, m.source_name, entry.media_type, video_stem=m.video_stem)
        result.append(item)
    return result


@router.get("/{media_id}/poster")
def get_poster(media_id: int, session: Session = Depends(get_session)):
    media = crud.media_get(session, media_id)
    if not media:
        raise HTTPException(404, "Media not found")
    entry = crud.entry_get(session, media.entry_id)
    if entry.media_type == "movie":
        if not media.video_stem:
            raise HTTPException(404, "Poster not found")
        filename = f"{media.video_stem}-poster.jpg"
    else:
        filename = "poster.jpg"
    path = Path(entry.link_path) / media.source_name / filename
    if not path.exists():
        raise HTTPException(404, "Poster not found")
    return FileResponse(path, media_type="image/jpeg")


@router.get("/{media_id}/episodes")
def list_episodes(media_id: int, session: Session = Depends(get_session)):
    media = crud.media_get(session, media_id)
    if not media:
        raise HTTPException(404, "Media not found")
    if media.scrape_status != "confirmed":
        raise HTTPException(400, "Media is not confirmed")
    entry = crud.entry_get(session, media.entry_id)
    if entry.media_type != "tv":
        raise HTTPException(400, "Not a TV entry")
    return read_episode_nfos(entry.link_path, media.source_name)
