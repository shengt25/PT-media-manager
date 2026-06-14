import re
from pathlib import Path


_NUMBER_RE = re.compile(r"\d+")
_SEASON_RE = re.compile(
    r"(?i)(?:^|[._\s-])(?:s\d{1,3}(?:[._\s-]*e\d{1,4})?|season[._\s-]*\d{1,3}|\d{1,3}x\d{1,4})(?:$|[._\s-])"
)


def _natural_key(path: Path) -> list[int | str]:
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", str(path))]


def _has_season_marker(path: Path) -> bool:
    return _SEASON_RE.search(path.stem) is not None


def _extract_numbers(path: Path) -> list[int]:
    return [int(match) for match in _NUMBER_RE.findall(path.stem)]


def _is_strict_sequence(values: list[int]) -> bool:
    if len(values) < 2:
        return False
    return all(curr == prev + 1 for prev, curr in zip(values, values[1:]))


def _find_sequence_column(number_rows: list[list[int]]) -> int | None:
    max_cols = max((len(row) for row in number_rows), default=0)
    candidates = []

    for col in range(max_cols):
        if any(len(row) <= col for row in number_rows):
            continue
        values = [row[col] for row in number_rows]
        if _is_strict_sequence(values):
            candidates.append((col, values))

    if not candidates:
        return None

    candidates.sort(key=lambda item: (item[1][0] != 1, -item[0]))
    return candidates[0][0]


def _target_path(video_file: Path, season: int, episode: int) -> Path:
    return video_file.with_name(f"S{season:02d}.E{episode:02d}{video_file.suffix}")


def normalize_episode_filenames(video_files: list[Path], base: Path) -> list[Path]:
    ordered = sorted(video_files, key=lambda path: _natural_key(path.relative_to(base)))
    candidates = [path for path in ordered if not _has_season_marker(path.relative_to(base))]
    if len(candidates) < 2:
        return ordered

    number_rows = [_extract_numbers(path.relative_to(base)) for path in candidates]
    col = _find_sequence_column(number_rows)
    if col is None:
        return ordered

    normalized = {path: path for path in ordered}
    for video_file, numbers in zip(candidates, number_rows, strict=True):
        target = _target_path(video_file, 1, numbers[col])
        if target.exists():
            raise FileExistsError(f"Episode rename target already exists: {target}")
        video_file.rename(target)
        normalized[video_file] = target

    return [normalized[path] for path in ordered]
