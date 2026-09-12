import importlib.util
import json
import sqlite3
from pathlib import Path

from app.core.nfo import write_episode_nfo, write_movie_nfo


_SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "migrate.py"
_SPEC = importlib.util.spec_from_file_location("ptmm_migrate", _SCRIPT_PATH)
assert _SPEC and _SPEC.loader
migrate_script = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(migrate_script)


def test_build_tv_scrape_detail_from_existing_nfos(tmp_path):
    show = tmp_path / "Show"
    show.mkdir()
    matched = show / "Show.S01E01.mkv"
    unmatched = show / "Show.S01E02.mkv"
    unknown = show / "bonus.mkv"
    for video in (matched, unmatched, unknown):
        video.touch()
    write_episode_nfo(matched, {
        "title": "One", "season": 1, "episode": 1,
        "aired": "2026-01-01", "tmdb_id": 101,
    })
    write_episode_nfo(unmatched, {"season": 1, "episode": 2})

    detail = json.loads(migrate_script._build_scrape_detail("Show", str(tmp_path), "tv"))

    assert [item["status"] for item in detail] == ["matched", "no_tmdb_data", "unidentified"]
    assert detail[0]["title"] == "One"
    assert detail[1]["season"] == 1
    assert detail[2]["file"] == "bonus.mkv"


def test_build_movie_scrape_detail_from_existing_nfo(tmp_path):
    movie = tmp_path / "Movie"
    movie.mkdir()
    write_movie_nfo(str(tmp_path), "Movie", "Movie", {
        "title": "Movie title", "tmdb_id": 202, "genres": [],
    })

    detail = json.loads(migrate_script._build_scrape_detail("Movie", str(tmp_path), "movie"))

    assert detail == [{
        "file": "Movie", "season": None, "episode": None,
        "status": "matched", "title": "Movie title", "aired": None,
    }]


def test_old_database_migrates_directly_to_schema_with_scrape_detail(tmp_path):
    source = tmp_path / "source"
    library = tmp_path / "library"
    source.mkdir()
    show = library / "Show"
    show.mkdir(parents=True)
    video = show / "Show.S01E01.mkv"
    video.touch()
    write_episode_nfo(video, {"title": "One", "season": 1, "episode": 1, "tmdb_id": 101})
    write_movie_nfo(str(library), "Show", "tvshow", {
        "title": "Show", "tmdb_id": 99, "genres": [],
    })

    db_path = tmp_path / "ptmm.db"
    with sqlite3.connect(db_path) as db:
        db.execute("CREATE TABLE entry_path (entry_name TEXT, source_path TEXT, link_path TEXT)")
        db.execute("INSERT INTO entry_path VALUES (?, ?, ?)", ("Series", str(source), str(library)))
        db.execute('CREATE TABLE "Series" (media_name TEXT, date TEXT)')
        db.execute('INSERT INTO "Series" VALUES (?, ?)', ("Show", "2026-01-01"))

    migrate_script.migrate(db_path, skip_thumbnails=True)

    with sqlite3.connect(db_path) as db:
        columns = {row[1] for row in db.execute("PRAGMA table_info(media)")}
        row = db.execute("SELECT scrape_status, scrape_detail FROM media").fetchone()
    assert "scrape_detail" in columns
    assert row[0] == "confirmed"
    assert json.loads(row[1])[0]["status"] == "matched"
