"""Path helpers for frozen (PyInstaller) and development builds."""

import sys
from pathlib import Path

from platformdirs import user_log_dir

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _is_frozen() -> bool:
    """Return True if running inside a PyInstaller bundle."""
    return hasattr(sys, "_MEIPASS")


def resource_path(relative_path: str) -> str:
    """Resolve a path to a bundled resource.

    In frozen builds, resolves relative to the PyInstaller bundle directory.
    In development, resolves relative to the project root.

    Args:
        relative_path: Path relative to the project root
            (e.g. "assets/sprites/sprites.png").

    Returns:
        Absolute path to the resource.
    """
    if _is_frozen():
        base = Path(sys._MEIPASS)  # type: ignore[attr-defined]
    else:
        base = _PROJECT_ROOT
    return str(base / relative_path)


def get_log_path() -> str:
    """Return the path for the game log file.

    In frozen builds, writes to a platform-appropriate user log directory.
    In development, writes to the current directory.

    Returns:
        Absolute or relative path to game.log.
    """
    if not _is_frozen():
        return "game.log"

    log_dir = Path(user_log_dir("BattleCity", appauthor=False))
    log_dir.mkdir(parents=True, exist_ok=True)
    return str(log_dir / "game.log")
