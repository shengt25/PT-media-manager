import os
import shutil
from pathlib import Path
from app.config import settings


def _is_ignored(path: Path) -> bool:
    if path.name.startswith("."):
        return True
    if path.is_file() and path.suffix in settings.ignore_ext:
        return True
    return False


def create_links(source_path: str, link_path: str, name: str, link_name: str | None = None):
    source = Path(source_path) / name
    target_name = link_name or name
    created: list[Path] = []

    try:
        if source.is_file():
            subdir = Path(link_path) / (Path(target_name).stem if link_name is None else target_name)
            subdir.mkdir(parents=True, exist_ok=True)
            link_file = subdir / source.name
            os.link(source, link_file)
            created.append(link_file)
        elif source.is_dir():
            for root, dirs, files in os.walk(source):
                root_path = Path(root)
                rel = root_path.relative_to(Path(source_path))
                link_root = Path(link_path) / rel
                if link_name:
                    parts = rel.parts
                    if parts:
                        link_root = Path(link_path) / link_name / Path(*parts[1:]) if len(parts) > 1 else Path(link_path) / link_name
                link_root.mkdir(parents=True, exist_ok=True)

                dirs[:] = [d for d in dirs if not _is_ignored(root_path / d)]

                for file in files:
                    file_path = root_path / file
                    if _is_ignored(file_path):
                        continue
                    link_file = link_root / file
                    os.link(file_path, link_file)
                    created.append(link_file)
    except Exception:
        for f in created:
            f.unlink(missing_ok=True)
        raise


def delete_link(link_path: str, name: str):
    target = Path(link_path) / name
    if target.is_file():
        target.unlink()
    elif target.is_dir():
        shutil.rmtree(target)