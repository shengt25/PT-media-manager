from pathlib import Path


def test_movie_source_exists_with_glob_special_characters(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("TMDB_API_KEY", "test")
    from app.core.scanner import _movie_source_exists

    source_name = "[movie].Name.2024"
    (tmp_path / f"{source_name}.mp4").write_text("video")

    assert _movie_source_exists(tmp_path, source_name)
