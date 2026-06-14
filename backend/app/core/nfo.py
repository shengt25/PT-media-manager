import json
import xml.etree.ElementTree as ET
from pathlib import Path
from xml.dom import minidom


def _pretty_xml(root: ET.Element) -> str:
    raw = ET.tostring(root, encoding="unicode")
    return minidom.parseString(raw).toprettyxml(indent="  ", encoding=None)


def _write(path: Path, root: ET.Element) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_pretty_xml(root), encoding="utf-8")
    return str(path)


def _add(parent: ET.Element, tag: str, text: str | int | float | None):
    if text is not None:
        el = ET.SubElement(parent, tag)
        el.text = str(text)


def write_movie_nfo(link_path: str, source_name: str, video_stem: str, data: dict) -> str:
    root = ET.Element("movie")
    _add(root, "title", data.get("title"))
    _add(root, "originaltitle", data.get("original_title"))
    _add(root, "year", data.get("year"))
    _add(root, "plot", data.get("overview"))
    _add(root, "rating", data.get("rating"))
    uid = ET.SubElement(root, "uniqueid", type="tmdb", default="true")
    uid.text = str(data["tmdb_id"])
    for genre in data.get("genres", []):
        _add(root, "genre", genre)
    return _write(Path(link_path) / source_name / f"{video_stem}.nfo", root)


def write_tvshow_nfo(link_path: str, name: str, data: dict) -> str:
    root = ET.Element("tvshow")
    _add(root, "title", data.get("title"))
    _add(root, "originaltitle", data.get("original_title"))
    _add(root, "year", data.get("year"))
    _add(root, "plot", data.get("overview"))
    _add(root, "rating", data.get("rating"))
    uid = ET.SubElement(root, "uniqueid", type="tmdb", default="true")
    uid.text = str(data["tmdb_id"])
    for genre in data.get("genres", []):
        _add(root, "genre", genre)
    return _write(Path(link_path) / name / "tvshow.nfo", root)


def _find_nfo_path(generated_files: str | None, media_type: str) -> Path | None:
    if not generated_files:
        return None
    try:
        paths = json.loads(generated_files)
    except (json.JSONDecodeError, TypeError):
        return None
    for f in paths:
        if media_type == "movie":
            if f.endswith(".nfo"):
                return Path(f)
        else:
            if Path(f).name == "tvshow.nfo":
                return Path(f)
    return None


def nfo_exists(generated_files: str | None, media_type: str) -> bool:
    nfo_path = _find_nfo_path(generated_files, media_type)
    return nfo_path is not None and nfo_path.exists()


def write_episode_nfo(video_path: Path, data: dict) -> str:
    root = ET.Element("episodedetails")
    _add(root, "title", data.get("title"))
    _add(root, "season", data.get("season"))
    _add(root, "episode", data.get("episode"))
    _add(root, "aired", data.get("aired"))
    _add(root, "plot", data.get("plot"))
    _add(root, "rating", data.get("rating"))
    if data.get("tmdb_id"):
        uid = ET.SubElement(root, "uniqueid", type="tmdb", default="true")
        uid.text = str(data["tmdb_id"])
    nfo_path = video_path.with_suffix(".nfo")
    return _write(nfo_path, root)


def read_episode_nfos(link_path: str, name: str) -> list[dict]:
    base = Path(link_path) / name
    episodes = []
    for nfo_path in sorted(base.rglob("*.nfo")):
        try:
            tree = ET.parse(nfo_path)
            root = tree.getroot()
        except ET.ParseError:
            continue
        if root.tag != "episodedetails":
            continue
        data = {el.tag: el.text for el in root if el.text}
        episodes.append({
            "season": int(data.get("season", 1)),
            "episode": int(data.get("episode", 0)),
            "title": data.get("title"),
            "aired": data.get("aired"),
            "plot": data.get("plot"),
            "rating": float(data["rating"]) if data.get("rating") else None,
        })
    episodes.sort(key=lambda e: (e["season"], e["episode"]))
    return episodes


def read_nfo(generated_files: str | None, media_type: str) -> dict:
    nfo_path = _find_nfo_path(generated_files, media_type)
    if nfo_path is None or not nfo_path.exists():
        return {}
    try:
        tree = ET.parse(nfo_path)
        root = tree.getroot()
        return {el.tag: el.text for el in root if el.text}
    except ET.ParseError:
        return {}
