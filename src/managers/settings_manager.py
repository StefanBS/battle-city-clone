"""Manages persistent game settings."""

import json

from loguru import logger


class SettingsManager:
    """Loads and saves game settings to a JSON file."""

    def __init__(self, path: str = "settings.json") -> None:
        self.master_volume: float = 1.0
        self._path = path
        self._load()

    def _load(self) -> None:
        """Load settings from file. Use defaults on error."""
        try:
            with open(self._path) as f:
                data = json.load(f)
            self.master_volume = max(
                0.0, min(1.0, float(data.get("master_volume", 1.0)))
            )
        except (FileNotFoundError, json.JSONDecodeError, ValueError, TypeError):
            logger.warning(
                f"Could not load settings from {self._path}; using defaults."
            )
            self.master_volume = 1.0

    def save(self) -> None:
        """Save current settings to file."""
        data = {"master_volume": self.master_volume}
        with open(self._path, "w") as f:
            json.dump(data, f, indent=2)
        logger.debug(f"Settings saved to {self._path}")
