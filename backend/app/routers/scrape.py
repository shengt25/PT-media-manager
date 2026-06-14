import json
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from pydantic import BaseModel
from app.db.database import get_session
from app.db import crud
from app.core.scraper import ArtworkDownloadError, search_tmdb, fetch_tmdb_detail, fetch_tmdb_poster_path, download_artwork, download_poster_thumbnail, generate_episode_nfos
from app.core.nfo import write_movie_nfo, write_tvshow_nfo
from app.core.scanner import find_main_video_stem

router = APIRouter(prefix="/scrape", tags=["scrape"])


def _delete_generated_files(media):
    if not media.generated_files:
        return
    paths = json.loads(media.generated_files)
    for path_str in paths:
        p = Path(path_str)
        if p.exists():
            p.unlink()


def _run_scrape(media, entry, tmdb_id: int, session: Session, language: str = "zh-CN", image_language: str | None = None):
    proxy = crud.get_app_settings(session).tmdb_proxy
    try:
        tmdb_data = fetch_tmdb_detail(tmdb_id, entry.media_type, language, image_language, proxy)

        if entry.media_type == "movie":
            link_dir = Path(entry.link_path) / media.source_name
            video_stem = find_main_video_stem(link_dir) or media.source_name
            prefix = f"{video_stem}-"
            generated = download_artwork(
                entry.link_path, media.source_name,
                tmdb_data.get("poster_path"),
                tmdb_data.get("backdrop_path"),
                filename_prefix=prefix,
                proxy=proxy,
            )
            thumb_path = download_poster_thumbnail(
                entry.link_path,
                media.source_name,
                tmdb_data.get("poster_path"),
                proxy=proxy,
            )
            nfo_path = write_movie_nfo(entry.link_path, media.source_name, video_stem, tmdb_data)
            generated.append(nfo_path)
        else:
            generated = download_artwork(
                entry.link_path, media.source_name,
                tmdb_data.get("poster_path"),
                tmdb_data.get("backdrop_path"),
                proxy=proxy,
            )
            thumb_path = download_poster_thumbnail(
                entry.link_path,
                media.source_name,
                tmdb_data.get("poster_path"),
                proxy=proxy,
            )
            nfo_path = write_tvshow_nfo(entry.link_path, media.source_name, tmdb_data)
            generated.append(nfo_path)
            episode_result = generate_episode_nfos(entry.link_path, media.source_name, tmdb_id, language, proxy)
            generated.extend(episode_result.generated)
    except ArtworkDownloadError as e:
        raise HTTPException(502, str(e))

    media.tmdb_id = tmdb_id
    media.scrape_status = "confirmed"
    media.scrape_language = language
    media.image_language = image_language or language
    if thumb_path:
        generated.append(thumb_path)
    elif tmdb_data.get("poster_path"):
        raise HTTPException(502, "Poster thumbnail download failed")
    media.generated_files = json.dumps(generated)
    return crud.media_update(session, media)


@router.get("/poster")
def get_poster(tmdb_id: int, media_type: str, language: str = "en-US", session: Session = Depends(get_session)):
    proxy = crud.get_app_settings(session).tmdb_proxy
    path = fetch_tmdb_poster_path(tmdb_id, media_type, language, proxy)
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
    proxy = crud.get_app_settings(session).tmdb_proxy
    return search_tmdb(data.query, entry.media_type, data.year, data.language, proxy)


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
    if media.scrape_status != "partial":
        raise HTTPException(400, "Media is not partial")
    entry = crud.entry_get(session, media.entry_id)
    if entry.media_type != "tv":
        raise HTTPException(400, "Not a TV entry")
    if not media.tmdb_id:
        raise HTTPException(400, "Media has no TMDB id")
    if not media.scrape_language:
        raise HTTPException(400, "Media has no saved scrape language. Run Full re-scrape first.")
    proxy = crud.get_app_settings(session).tmdb_proxy
    episode_result = generate_episode_nfos(
        entry.link_path,
        media.source_name,
        media.tmdb_id,
        media.scrape_language,
        proxy,
    )
    existing = json.loads(media.generated_files) if media.generated_files else []
    media.generated_files = json.dumps(existing + episode_result.generated)
    media.scrape_status = "confirmed"
    crud.media_update(session, media)
    added_nfos = len([path for path in episode_result.generated if path.endswith(".nfo")])
    return {"added": added_nfos, "generated": len(episode_result.generated), "warnings": episode_result.warnings}
