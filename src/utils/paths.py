"""Path helpers for frozen (PyInstaller) and development builds."""

import os
import sys


def _is_frozen() -> bool:
    """Return True if running inside a PyInstaller bundle."""
    return hasattr(sys, "_MEIPASS")


def _project_root() -> str:
    """Return the project root directory (for development mode)."""
    # src/utils/paths.py -> go up 3 levels to reach project root
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


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
        base = sys._MEIPASS  # type: ignore[attr-defined]
    else:
        base = _project_root()
    return os.path.join(base, relative_path)


def get_log_path() -> str:
    """Return the path for the game log file.

    In frozen builds, writes to a platform-appropriate user data directory.
    In development, writes to the current directory.

    Returns:
        Absolute or relative path to game.log.
    """
    if not _is_frozen():
        return "game.log"

    if sys.platform == "win32":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    else:
        base = os.environ.get(
            "XDG_DATA_HOME", os.path.join(os.path.expanduser("~"), ".local", "share")
        )

    log_dir = os.path.join(base, "BattleCity")
    os.makedirs(log_dir, exist_ok=True)
    return os.path.join(log_dir, "game.log")
