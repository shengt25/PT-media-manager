import httpx
from pathlib import Path
from guessit import guessit
from app.config import settings
from app.core.nfo import write_episode_nfo
from app.core.scanner import VIDEO_EXT

TMDB_BASE = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/original"
TMDB_THUMB_IMAGE_BASE = "https://image.tmdb.org/t/p/w185"



def _headers() -> dict:
    return {"Authorization": f"Bearer {settings.tmdb_api_key}"}


def search_tmdb(query: str, media_type: str, year: int | None = None, language: str = "zh-CN", proxy: str | None = None) -> list[dict]:
    endpoint = "movie" if media_type == "movie" else "tv"
    params = {"query": query, "language": language}
    if year:
        params["year"] = year
    with httpx.Client(proxy=proxy) as client:
        r = client.get(f"{TMDB_BASE}/search/{endpoint}", params=params, headers=_headers())
        r.raise_for_status()
    results = r.json().get("results", [])[:5]
    return [_format_result(item, media_type) for item in results]


def _fetch_tmdb_poster(client: httpx.Client, tmdb_id: int, media_type: str, image_language: str) -> str | None:
    endpoint = "movie" if media_type == "movie" else "tv"
    lang_code = image_language.split("-")[0]  # "en-US" → "en", "zh-CN" → "zh"
    r = client.get(
        f"{TMDB_BASE}/{endpoint}/{tmdb_id}/images",
        params={"include_image_language": f"{lang_code},null"},
        headers=_headers(),
    )
    if r.status_code != 200:
        return None
    posters = r.json().get("posters", [])
    # prefer language-specific poster, fall back to language-neutral
    for p in posters:
        if p.get("iso_639_1") == lang_code:
            return p["file_path"]
    for p in posters:
        if p.get("iso_639_1") is None:
            return p["file_path"]
    return None


def fetch_tmdb_detail(tmdb_id: int, media_type: str, language: str = "zh-CN", image_language: str | None = None, proxy: str | None = None) -> dict:
    endpoint = "movie" if media_type == "movie" else "tv"
    with httpx.Client(proxy=proxy) as client:
        r = client.get(
            f"{TMDB_BASE}/{endpoint}/{tmdb_id}",
            params={"language": language},
            headers=_headers(),
        )
        r.raise_for_status()
        data = r.json()

        poster_path = data.get("poster_path")
        backdrop_path = data.get("backdrop_path")
        if image_language and image_language != language:
            fetched = _fetch_tmdb_poster(client, tmdb_id, media_type, image_language)
            if fetched:
                poster_path = fetched

    title_key = "title" if media_type == "movie" else "name"
    orig_key = "original_title" if media_type == "movie" else "original_name"
    date_key = "release_date" if media_type == "movie" else "first_air_date"
    return {
        "tmdb_id": data["id"],
        "title": data.get(title_key),
        "original_title": data.get(orig_key),
        "year": data.get(date_key, "")[:4] or None,
        "overview": data.get("overview"),
        "rating": data.get("vote_average"),
        "genres": [g["name"] for g in data.get("genres", [])],
        "poster_path": poster_path,
        "backdrop_path": backdrop_path,
    }


def download_artwork(link_path: str, name: str, poster_path: str | None, backdrop_path: str | None, skip_if_exists: bool = False, filename_prefix: str = "", proxy: str | None = None) -> list[str]:
    base = Path(link_path) / name
    base.mkdir(parents=True, exist_ok=True)
    poster_name = f"{filename_prefix}poster.jpg"
    fanart_name = f"{filename_prefix}fanart.jpg"
    if skip_if_exists and (base / poster_name).exists():
        return []
    generated = []
    with httpx.Client(proxy=proxy) as client:
        if poster_path:
            r = client.get(f"{TMDB_IMAGE_BASE}{poster_path}")
            if r.status_code == 200:
                p = base / poster_name
                p.write_bytes(r.content)
                generated.append(str(p))
        if backdrop_path:
            r = client.get(f"{TMDB_IMAGE_BASE}{backdrop_path}")
            if r.status_code == 200:
                p = base / fanart_name
                p.write_bytes(r.content)
                generated.append(str(p))
    return generated


def get_poster_thumb_path(link_path: str, name: str) -> Path:
    return Path(link_path) / name / ".ptmm-thumb.jpg"


def download_poster_thumbnail(link_path: str, name: str, poster_path: str | None, proxy: str | None = None) -> str | None:
    if not poster_path:
        return None
    thumb_path = get_poster_thumb_path(link_path, name)
    thumb_path.parent.mkdir(parents=True, exist_ok=True)
    with httpx.Client(proxy=proxy) as client:
        r = client.get(f"{TMDB_THUMB_IMAGE_BASE}{poster_path}")
        if r.status_code != 200:
            return None
        thumb_path.write_bytes(r.content)
    if not thumb_path.exists():
        return None
    return str(thumb_path)


def fetch_tmdb_episode(tmdb_id: int, season: int, episode: int, language: str = "zh-CN", proxy: str | None = None) -> dict:
    with httpx.Client(proxy=proxy) as client:
        r = client.get(
            f"{TMDB_BASE}/tv/{tmdb_id}/season/{season}/episode/{episode}",
            params={"language": language},
            headers=_headers(),
        )
        if r.status_code == 404:
            return {"season": season, "episode": episode, "tmdb_id": None, "still_path": None}
        r.raise_for_status()
    data = r.json()
    return {
        "season": season,
        "episode": episode,
        "title": data.get("name"),
        "aired": data.get("air_date"),
        "plot": data.get("overview"),
        "rating": data.get("vote_average"),
        "tmdb_id": data.get("id"),
        "still_path": data.get("still_path"),
    }


def generate_episode_nfos(link_path: str, name: str, tmdb_id: int, language: str = "zh-CN", proxy: str | None = None) -> list[str]:
    base = Path(link_path) / name
    generated = []
    with httpx.Client(proxy=proxy) as client:
        for video_file in sorted(base.rglob("*")):
            if not video_file.is_file():
                continue
            if video_file.suffix.lower() not in VIDEO_EXT:
                continue
            nfo_path = video_file.with_suffix(".nfo")
            if nfo_path.exists():
                continue
            rel = video_file.relative_to(base)
            info = guessit(str(rel))
            season = info.get("season")
            episode = info.get("episode")
            if episode is None:
                continue
            if isinstance(episode, list):
                episode = episode[0]
            if season is None:
                season = 1
            if isinstance(season, list):
                season = season[0]
            try:
                ep_data = fetch_tmdb_episode(tmdb_id, int(season), int(episode), language, proxy)
            except Exception:
                ep_data = {"season": int(season), "episode": int(episode), "tmdb_id": None, "still_path": None}
            path = write_episode_nfo(video_file, ep_data)
            generated.append(path)
            if ep_data.get("still_path"):
                thumb_path = video_file.with_name(video_file.stem + "-thumb.jpg")
                if not thumb_path.exists():
                    r = client.get(f"{TMDB_IMAGE_BASE}{ep_data['still_path']}")
                    if r.status_code == 200:
                        thumb_path.write_bytes(r.content)
                        generated.append(str(thumb_path))
    return generated


def _format_result(item: dict, media_type: str) -> dict:
    title_key = "title" if media_type == "movie" else "name"
    date_key = "release_date" if media_type == "movie" else "first_air_date"
    return {
        "tmdb_id": item["id"],
        "title": item.get(title_key),
        "year": item.get(date_key, "")[:4] or None,
        "overview": item.get("overview"),
        "rating": item.get("vote_average"),
        "poster_path": item.get("poster_path"),
    }
