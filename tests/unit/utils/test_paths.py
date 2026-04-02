import os
import sys
from unittest.mock import patch


class TestResourcePath:
    """Tests for resource_path() helper."""

    def test_returns_relative_path_in_dev_mode(self):
        """In non-frozen mode, resource_path returns path relative to project root."""
        from src.utils.paths import resource_path

        # Ensure sys._MEIPASS is not set (normal dev mode)
        if hasattr(sys, "_MEIPASS"):
            delattr(sys, "_MEIPASS")

        result = resource_path("assets/sprites/sprites.png")
        assert result == os.path.join(
            os.path.dirname(
                os.path.dirname(
                    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                )
            ),
            "assets/sprites/sprites.png",
        )

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

    def test_returns_platform_path_in_frozen_mode_linux(self):
        """In frozen mode on Linux, uses XDG_DATA_HOME."""
        from src.utils.paths import get_log_path

        fake_meipass = "/tmp/fake_meipass"
        with (
            patch.object(sys, "_MEIPASS", fake_meipass, create=True),
            patch("sys.platform", "linux"),
            patch.dict(os.environ, {"XDG_DATA_HOME": "/tmp/xdg_data"}, clear=False),
            patch("src.utils.paths.os.makedirs"),
        ):
            result = get_log_path()
            assert result == os.path.join("/tmp/xdg_data", "BattleCity", "game.log")

    def test_returns_platform_path_in_frozen_mode_windows(self):
        """In frozen mode on Windows, uses APPDATA."""
        from src.utils.paths import get_log_path

        fake_meipass = "/tmp/fake_meipass"
        appdata = "C:\\Users\\Test\\AppData\\Roaming"
        with (
            patch.object(sys, "_MEIPASS", fake_meipass, create=True),
            patch("sys.platform", "win32"),
            patch.dict(os.environ, {"APPDATA": appdata}, clear=False),
            patch("src.utils.paths.os.makedirs"),
        ):
            result = get_log_path()
            assert result == os.path.join(appdata, "BattleCity", "game.log")

    def test_frozen_linux_defaults_xdg_when_env_missing(self):
        """Falls back to ~/.local/share when XDG_DATA_HOME is not set."""
        from src.utils.paths import get_log_path

        fake_meipass = "/tmp/fake_meipass"
        env = os.environ.copy()
        env.pop("XDG_DATA_HOME", None)
        with (
            patch.object(sys, "_MEIPASS", fake_meipass, create=True),
            patch("sys.platform", "linux"),
            patch.dict(os.environ, env, clear=True),
            patch("src.utils.paths.os.makedirs"),
        ):
            result = get_log_path()
            expected = os.path.join(
                os.path.expanduser("~"), ".local", "share", "BattleCity", "game.log"
            )
            assert result == expected
