from contextlib import nullcontext

from app.core import scraper
from app.core.nfo import write_episode_nfo


class _NoopClient:
    pass


def _disable_network(monkeypatch):
    monkeypatch.setattr(scraper, "_client", lambda proxy, timeout: nullcontext(_NoopClient()))
    monkeypatch.setattr(scraper, "download_season_artwork", lambda *args, **kwargs: [])


def test_existing_episode_nfo_is_restored_to_result(tmp_path, monkeypatch):
    _disable_network(monkeypatch)
    base = tmp_path / "Show"
    base.mkdir()
    video = base / "Show.S01E01.mkv"
    video.touch()
    write_episode_nfo(video, {
        "title": "Episode One", "season": 1, "episode": 1,
        "aired": "2026-01-01", "tmdb_id": 123,
    })
    thumb = base / "Show.S01E01-thumb.jpg"
    thumb.touch()

    result = scraper.generate_episode_nfos(str(tmp_path), "Show", 99)

    assert result.scrape_detail == [{
        "file": "Show.S01E01.mkv", "season": 1, "episode": 1,
        "status": "matched", "title": "Episode One", "aired": "2026-01-01",
    }]
    assert result.generated == [str(video.with_suffix(".nfo")), str(thumb)]


def test_overwrite_refetches_and_rewrites_existing_episode_nfo(tmp_path, monkeypatch):
    _disable_network(monkeypatch)
    base = tmp_path / "Show"
    base.mkdir()
    video = base / "Show.S01E01.mkv"
    video.touch()
    write_episode_nfo(video, {
        "title": "Old title", "season": 1, "episode": 1, "tmdb_id": 123,
    })
    monkeypatch.setattr(scraper, "fetch_tmdb_episode", lambda *args, **kwargs: {
        "title": "Fresh title", "season": 1, "episode": 1, "aired": "2026-02-02",
        "plot": None, "rating": None, "tmdb_id": 456, "still_path": None,
    })

    result = scraper.generate_episode_nfos(str(tmp_path), "Show", 99, overwrite=True)

    assert result.scrape_detail[0]["title"] == "Fresh title"
    assert "Fresh title" in video.with_suffix(".nfo").read_text(encoding="utf-8")
    assert result.generated == [str(video.with_suffix(".nfo"))]


def test_existing_season_artwork_is_included_in_generated_files(tmp_path, monkeypatch):
    monkeypatch.setattr(scraper, "_client", lambda proxy, timeout: nullcontext(_NoopClient()))
    base = tmp_path / "Show"
    base.mkdir()
    poster = base / "season01-poster.jpg"
    poster.touch()
    monkeypatch.setattr(scraper, "fetch_tmdb_season", lambda *args, **kwargs: {
        "season_number": 1, "poster_path": "/poster.jpg",
    })

    generated = scraper.download_season_artwork(str(tmp_path), "Show", 99, {1}, "zh-CN")

    assert generated == [str(poster)]
