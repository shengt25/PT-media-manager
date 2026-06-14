import json
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from pydantic import BaseModel
from app.db.database import get_session
from app.db import crud
from app.core.scraper import search_tmdb, fetch_tmdb_detail, download_artwork, generate_episode_nfos
from app.core.nfo import write_movie_nfo, write_tvshow_nfo
from app.core.scanner import find_main_video_stem

router = APIRouter(prefix="/scrape", tags=["scrape"])


def _delete_generated_files(media):
    if not media.generated_files:
        return
    try:
        paths = json.loads(media.generated_files)
    except (json.JSONDecodeError, TypeError):
        return
    for path_str in paths:
        p = Path(path_str)
        if p.exists():
            p.unlink()


def _run_scrape(media, entry, tmdb_id: int, session: Session, language: str = "zh-CN", image_language: str | None = None):
    tmdb_data = fetch_tmdb_detail(tmdb_id, entry.media_type, language, image_language)

    if entry.media_type == "movie":
        if not media.video_stem:
            link_dir = Path(entry.link_path) / media.source_name
            media.video_stem = find_main_video_stem(link_dir) or media.source_name
        prefix = f"{media.video_stem}-"
        folder_exists_with_artwork = (Path(entry.link_path) / media.source_name / f"{prefix}poster.jpg").exists()
        generated = download_artwork(
            entry.link_path, media.source_name,
            tmdb_data.get("poster_path"),
            tmdb_data.get("backdrop_path"),
            skip_if_exists=folder_exists_with_artwork,
            filename_prefix=prefix,
        )
        nfo_path = write_movie_nfo(entry.link_path, media.source_name, media.video_stem, tmdb_data)
        generated.append(nfo_path)
    else:
        generated = download_artwork(
            entry.link_path, media.source_name,
            tmdb_data.get("poster_path"),
            tmdb_data.get("backdrop_path"),
        )
        nfo_path = write_tvshow_nfo(entry.link_path, media.source_name, tmdb_data)
        generated.append(nfo_path)
        episode_nfos = generate_episode_nfos(entry.link_path, media.source_name, tmdb_id, language)
        generated.extend(episode_nfos)

    media.tmdb_id = tmdb_id
    media.scrape_status = "confirmed"
    media.generated_files = json.dumps(generated)
    return crud.media_update(session, media)


@router.get("/poster")
def get_poster(tmdb_id: int, media_type: str, language: str = "en-US"):
    from app.core.scraper import _fetch_tmdb_poster
    import httpx as _httpx
    with _httpx.Client() as client:
        path = _fetch_tmdb_poster(client, tmdb_id, media_type, language)
    return {"poster_path": path}



class SearchRequest(BaseModel):
    query: str
    year: int | None = None
    language: str = "zh-CN"


@router.post("/{media_id}/search")
def search(media_id: int, data: SearchRequest, session: Session = Depends(get_session)):
    media = crud.media_get(session, media_id)
    if not media:
        raise HTTPException(404, "Media not found")
    entry = crud.entry_get(session, media.entry_id)
    return search_tmdb(data.query, entry.media_type, data.year, data.language)


class ConfirmRequest(BaseModel):
    tmdb_id: int
    language: str = "zh-CN"
    image_language: str | None = None


@router.post("/{media_id}/confirm")
def confirm(media_id: int, data: ConfirmRequest, session: Session = Depends(get_session)):
    media = crud.media_get(session, media_id)
    if not media:
        raise HTTPException(404, "Media not found")
    entry = crud.entry_get(session, media.entry_id)
    return _run_scrape(media, entry, data.tmdb_id, session, data.language, data.image_language)


@router.post("/{media_id}/rescrape")
def rescrape(media_id: int, data: ConfirmRequest, session: Session = Depends(get_session)):
    media = crud.media_get(session, media_id)
    if not media:
        raise HTTPException(404, "Media not found")
    entry = crud.entry_get(session, media.entry_id)
    _delete_generated_files(media)
    return _run_scrape(media, entry, data.tmdb_id, session, data.language, data.image_language)


@router.post("/{media_id}/sync-episodes")
def sync_episodes(media_id: int, session: Session = Depends(get_session)):
    media = crud.media_get(session, media_id)
    if not media:
        raise HTTPException(404, "Media not found")
    if media.scrape_status != "confirmed":
        raise HTTPException(400, "Media is not confirmed")
    entry = crud.entry_get(session, media.entry_id)
    if entry.media_type != "tv":
        raise HTTPException(400, "Not a TV entry")
    new_nfos = generate_episode_nfos(entry.link_path, media.source_name, media.tmdb_id)
    existing = json.loads(media.generated_files) if media.generated_files else []
    media.generated_files = json.dumps(existing + new_nfos)
    crud.media_update(session, media)
    return {"added": len(new_nfos)}


@router.post("/{media_id}/skip", status_code=204)
def skip(media_id: int, session: Session = Depends(get_session)):
    media = crud.media_get(session, media_id)
    if not media:
        raise HTTPException(404, "Media not found")
    media.scrape_status = "skipped"
    crud.media_update(session, media)