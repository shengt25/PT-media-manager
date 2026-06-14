import re
from pathlib import Path

from guessit import guessit

_NUMBER_RE = re.compile(r"\d+")


def _natural_key(path: Path) -> list[int | str]:
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", str(path))]


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


def infer_episode_numbers(video_files: list[Path], base: Path) -> dict[Path, tuple[int, int]]:
    """Infer (season, episode) for each video file without renaming anything.

    Tries guessit first; for files guessit can't resolve, falls back to a
    natural-number-sequence heuristic across the unresolved files.
    """
    result: dict[Path, tuple[int, int]] = {}
    unresolved: list[Path] = []

    for video_file in video_files:
        rel = video_file.relative_to(base)
        info = guessit(str(rel))
        season = info.get("season")
        episode = info.get("episode")
        if episode is None:
            unresolved.append(video_file)
            continue
        if isinstance(episode, list):
            episode = episode[0]
        if season is None:
            season = 1
        if isinstance(season, list):
            season = season[0]
        result[video_file] = (int(season), int(episode))

    if len(unresolved) >= 2:
        ordered = sorted(unresolved, key=lambda path: _natural_key(path.relative_to(base)))
        number_rows = [_extract_numbers(path.relative_to(base)) for path in ordered]
        col = _find_sequence_column(number_rows)
        if col is not None:
            for video_file, numbers in zip(ordered, number_rows, strict=True):
                result[video_file] = (1, numbers[col])

    return result
