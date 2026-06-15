import httpx
from pathlib import Path
from typing import Callable
from dataclasses import dataclass, field
from app.config import settings
from app.core.episodes import infer_episode_numbers
from app.core.nfo import write_episode_nfo
from app.core.scanner import VIDEO_EXT

TMDB_BASE = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/original"
TMDB_THUMB_IMAGE_BASE = "https://image.tmdb.org/t/p/w185"


class ArtworkDownloadError(RuntimeError):
    pass


@dataclass
class EpisodeNfoResult:
    generated: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    scrape_detail: list[dict] = field(default_factory=list)
    pending_thumbnails: list[tuple[Path, str]] = field(default_factory=list)


def _headers() -> dict:
    return {"Authorization": f"Bearer {settings.tmdb_api_key}"}


def _client(proxy: str | None, timeout: int) -> httpx.Client:
    return httpx.Client(proxy=proxy, timeout=timeout)


def search_tmdb(query: str, media_type: str, year: int | None = None, language: str = "zh-CN", proxy: str | None = None) -> list[dict]:
    endpoint = "movie" if media_type == "movie" else "tv"
    params = {"query": query, "language": language}
    if year:
        params["year"] = year
    with _client(proxy, timeout=20) as client:
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


def fetch_tmdb_poster_path(tmdb_id: int, media_type: str, language: str = "en-US", proxy: str | None = None) -> str | None:
    with _client(proxy, timeout=20) as client:
        return _fetch_tmdb_poster(client, tmdb_id, media_type, language)


def fetch_tmdb_detail(tmdb_id: int, media_type: str, language: str = "zh-CN", image_language: str | None = None, proxy: str | None = None) -> dict:
    endpoint = "movie" if media_type == "movie" else "tv"
    with _client(proxy, timeout=20) as client:
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


def download_artwork(link_path: str, name: str, poster_path: str | None, backdrop_path: str | None, filename_prefix: str = "", proxy: str | None = None) -> list[str]:
    base = Path(link_path) / name
    base.mkdir(parents=True, exist_ok=True)
    poster_name = f"{filename_prefix}poster.jpg"
    fanart_name = f"{filename_prefix}fanart.jpg"
    generated = []
    try:
        with _client(proxy, timeout=45) as client:
            if poster_path:
                r = client.get(f"{TMDB_IMAGE_BASE}{poster_path}")
                r.raise_for_status()
                p = base / poster_name
                p.write_bytes(r.content)
                generated.append(str(p))
            if backdrop_path:
                r = client.get(f"{TMDB_IMAGE_BASE}{backdrop_path}")
                r.raise_for_status()
                p = base / fanart_name
                p.write_bytes(r.content)
                generated.append(str(p))
    except httpx.HTTPError as e:
        raise ArtworkDownloadError(f"Artwork download failed: {e}") from e
    return generated


def get_poster_thumb_path(link_path: str, name: str) -> Path:
    return Path(link_path) / name / ".ptmm-thumb.jpg"


def download_poster_thumbnail(link_path: str, name: str, poster_path: str | None, proxy: str | None = None) -> str | None:
    if not poster_path:
        return None
    thumb_path = get_poster_thumb_path(link_path, name)
    thumb_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with _client(proxy, timeout=30) as client:
            r = client.get(f"{TMDB_THUMB_IMAGE_BASE}{poster_path}")
            r.raise_for_status()
            thumb_path.write_bytes(r.content)
    except httpx.HTTPError as e:
        raise ArtworkDownloadError(f"Poster thumbnail download failed: {e}") from e
    if not thumb_path.exists():
        return None
    return str(thumb_path)


def fetch_tmdb_episode(tmdb_id: int, season: int, episode: int, language: str = "zh-CN", proxy: str | None = None) -> dict:
    with _client(proxy, timeout=20) as client:
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


def fetch_tmdb_season(tmdb_id: int, season: int, language: str, proxy: str | None = None) -> dict:
    with _client(proxy, timeout=20) as client:
        r = client.get(
            f"{TMDB_BASE}/tv/{tmdb_id}/season/{season}",
            params={"language": language},
            headers=_headers(),
        )
        if r.status_code == 404:
            return {"season_number": season, "poster_path": None}
        r.raise_for_status()
    return r.json()


def download_season_artwork(link_path: str, name: str, tmdb_id: int, seasons: set[int], language: str, proxy: str | None = None) -> list[str]:
    base = Path(link_path) / name
    generated: list[str] = []
    try:
        with _client(proxy, timeout=45) as client:
            for season in sorted(seasons):
                if season < 0:
                    continue
                season_data = fetch_tmdb_season(tmdb_id, season, language, proxy)
                poster_path = season_data.get("poster_path")
                if not poster_path:
                    continue
                target = base / f"season{season:02d}-poster.jpg"
                if target.exists():
                    continue
                r = client.get(f"{TMDB_IMAGE_BASE}{poster_path}")
                r.raise_for_status()
                target.write_bytes(r.content)
                generated.append(str(target))
    except httpx.HTTPError as e:
        raise ArtworkDownloadError(f"Season artwork download failed: {e}") from e
    return generated


def download_episode_thumbnails(client: httpx.Client, pending_thumbnails: list[tuple[Path, str]], result: EpisodeNfoResult) -> None:
    for thumb_path, still_path in pending_thumbnails:
        try:
            r = client.get(f"{TMDB_IMAGE_BASE}{still_path}")
            r.raise_for_status()
            thumb_path.write_bytes(r.content)
            result.generated.append(str(thumb_path))
        except httpx.HTTPError as e:
            result.warnings.append(f"Thumbnail download failed for {thumb_path.name}: {e}")


def generate_episode_nfos(link_path: str, name: str, tmdb_id: int, language: str = "zh-CN", proxy: str | None = None, on_progress: Callable[[int, int], None] | None = None) -> EpisodeNfoResult:
    base = Path(link_path) / name
    result = EpisodeNfoResult()
    video_files = [
        video_file
        for video_file in base.rglob("*")
        if video_file.is_file() and video_file.suffix.lower() in VIDEO_EXT
    ]
    episode_numbers = infer_episode_numbers(video_files, base)
    seasons: set[int] = set()
    sorted_files = sorted(video_files)
    total = len(sorted_files)
    with _client(proxy, timeout=30) as client:
        for i, video_file in enumerate(sorted_files, start=1):
            if on_progress:
                on_progress(i, total)
            nfo_path = video_file.with_suffix(".nfo")
            if nfo_path.exists():
                continue
            rel = video_file.relative_to(base)
            numbers = episode_numbers.get(video_file)
            if numbers is None:
                path = write_episode_nfo(video_file, {"title": video_file.stem})
                result.generated.append(path)
                result.warnings.append(f"Could not parse episode number: {rel}")
                result.scrape_detail.append({
                    "file": str(rel), "season": None, "episode": None,
                    "status": "unidentified", "title": video_file.stem, "aired": None,
                })
                continue
            season, episode = numbers
            seasons.add(season)
            try:
                ep_data = fetch_tmdb_episode(tmdb_id, season, episode, language, proxy)
            except httpx.HTTPError as e:
                result.warnings.append(f"Failed to fetch TMDB data for {rel}: {e}")
                continue
            path = write_episode_nfo(video_file, ep_data)
            result.generated.append(path)
            status = "matched" if ep_data.get("tmdb_id") else "no_tmdb_data"
            result.scrape_detail.append({
                "file": str(rel), "season": season, "episode": episode,
                "status": status, "title": ep_data.get("title"), "aired": ep_data.get("aired"),
            })
            if ep_data.get("still_path"):
                thumb_path = video_file.with_name(video_file.stem + "-thumb.jpg")
                if not thumb_path.exists():
                    result.pending_thumbnails.append((thumb_path, ep_data["still_path"]))
        download_episode_thumbnails(client, result.pending_thumbnails, result)
    result.generated.extend(download_season_artwork(link_path, name, tmdb_id, seasons, language, proxy))
    return result


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
