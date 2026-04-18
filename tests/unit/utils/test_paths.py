import os
import sys
from pathlib import Path
from unittest.mock import patch


class TestResourcePath:
    """Tests for resource_path() helper."""

    def test_returns_project_root_path_in_dev_mode(self):
        """In non-frozen mode, resource_path returns path relative to project root."""
        from src.utils.paths import resource_path

        if hasattr(sys, "_MEIPASS"):
            delattr(sys, "_MEIPASS")

        result = resource_path("assets/sprites/sprites.png")
        expected_root = Path(__file__).resolve().parents[3]
        assert result == str(expected_root / "assets/sprites/sprites.png")

    def test_returns_meipass_path_in_frozen_mode(self):
        """In frozen mode, resource_path returns path relative to _MEIPASS."""
        from src.utils.paths import resource_path

        fake_meipass = "/tmp/fake_meipass"
        with patch.object(sys, "_MEIPASS", fake_meipass, create=True):
            result = resource_path("assets/sprites/sprites.png")
            assert result == os.path.join(fake_meipass, "assets/sprites/sprites.png")


class TestGetLogPath:
    """Tests for get_log_path() helper."""

    def test_returns_relative_path_in_dev_mode(self):
        """In non-frozen mode, returns 'game.log' (current directory)."""
        from src.utils.paths import get_log_path

        if hasattr(sys, "_MEIPASS"):
            delattr(sys, "_MEIPASS")

        result = get_log_path()
        assert result == "game.log"

    def test_uses_platformdirs_in_frozen_mode(self):
        """In frozen mode, delegates to platformdirs.user_log_dir."""
        from src.utils import paths

        fake_meipass = "/tmp/fake_meipass"
        fake_log_dir = "/tmp/fake_log_dir/BattleCity"
        with (
            patch.object(sys, "_MEIPASS", fake_meipass, create=True),
            patch.object(paths, "user_log_dir", return_value=fake_log_dir) as mock_dir,
            patch("pathlib.Path.mkdir") as mock_mkdir,
        ):
            result = paths.get_log_path()

        mock_dir.assert_called_once_with("BattleCity", appauthor=False)
        mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)
        assert result == os.path.join(fake_log_dir, "game.log")
