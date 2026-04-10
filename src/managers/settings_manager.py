"""Manages persistent game settings."""

import json

from loguru import logger

from src.utils.constants import Difficulty


class SettingsManager:
    """Loads and saves game settings to a JSON file."""

    def __init__(self, path: str = "settings.json") -> None:
        self.master_volume: float = 1.0
        self.difficulty: Difficulty = Difficulty.NORMAL
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
            raw_diff = data.get("difficulty", Difficulty.NORMAL.value)
            try:
                self.difficulty = Difficulty(raw_diff)
            except ValueError:
                self.difficulty = Difficulty.NORMAL
        except (FileNotFoundError, json.JSONDecodeError, ValueError, TypeError):
            logger.warning(
                f"Could not load settings from {self._path}; using defaults."
            )
            self.master_volume = 1.0
            self.difficulty = Difficulty.NORMAL

    def save(self) -> None:
        """Save current settings to file."""
        data = {
            "master_volume": round(self.master_volume, 1),
            "difficulty": self.difficulty.value,
        }
        with open(self._path, "w") as f:
            json.dump(data, f, indent=2)
        logger.debug(f"Settings saved to {self._path}")
