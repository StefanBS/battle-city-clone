import json

import pytest

from src.managers.settings_manager import SettingsManager
from src.utils.constants import Difficulty


class TestSettingsManager:
    def test_default_volume(self, tmp_path):
        path = str(tmp_path / "settings.json")
        settings_manager = SettingsManager(path=path)
        assert settings_manager.master_volume == 1.0

    def test_load_existing_settings(self, tmp_path):
        path = str(tmp_path / "settings.json")
        with open(path, "w") as f:
            json.dump({"master_volume": 0.5}, f)
        settings_manager = SettingsManager(path=path)
        assert settings_manager.master_volume == 0.5

    def test_save_creates_file(self, tmp_path):
        path = str(tmp_path / "settings.json")
        settings_manager = SettingsManager(path=path)
        settings_manager.master_volume = 0.7
        settings_manager.save()
        with open(path) as f:
            data = json.load(f)
        assert data["master_volume"] == 0.7

    def test_corrupted_file_uses_defaults(self, tmp_path):
        path = str(tmp_path / "settings.json")
        with open(path, "w") as f:
            f.write("not json!")
        settings_manager = SettingsManager(path=path)
        assert settings_manager.master_volume == 1.0

    @pytest.mark.parametrize("stored, expected", [(5.0, 1.0), (-0.5, 0.0)])
    def test_loaded_volume_clamped(self, tmp_path, stored, expected):
        path = str(tmp_path / "settings.json")
        with open(path, "w") as f:
            json.dump({"master_volume": stored}, f)
        settings_manager = SettingsManager(path=path)
        assert settings_manager.master_volume == expected

    def test_missing_key_uses_default(self, tmp_path):
        path = str(tmp_path / "settings.json")
        with open(path, "w") as f:
            json.dump({}, f)
        settings_manager = SettingsManager(path=path)
        assert settings_manager.master_volume == 1.0

    def test_adjust_volume_applies_delta(self, tmp_path):
        settings_manager = SettingsManager(path=str(tmp_path / "settings.json"))
        settings_manager.master_volume = 0.5
        settings_manager.adjust_volume(0.1)
        assert settings_manager.master_volume == 0.6

    @pytest.mark.parametrize(
        "start, delta, expected", [(0.0, -0.1, 0.0), (1.0, 0.1, 1.0)]
    )
    def test_adjust_volume_clamps(self, tmp_path, start, delta, expected):
        settings_manager = SettingsManager(path=str(tmp_path / "settings.json"))
        settings_manager.master_volume = start
        settings_manager.adjust_volume(delta)
        assert settings_manager.master_volume == expected

    def test_cycle_difficulty_forward_wraps(self, tmp_path):
        settings_manager = SettingsManager(path=str(tmp_path / "settings.json"))
        difficulties = list(Difficulty)
        settings_manager.difficulty = difficulties[-1]
        settings_manager.cycle_difficulty(1)
        assert settings_manager.difficulty == difficulties[0]

    def test_cycle_difficulty_backward_wraps(self, tmp_path):
        settings_manager = SettingsManager(path=str(tmp_path / "settings.json"))
        difficulties = list(Difficulty)
        settings_manager.difficulty = difficulties[0]
        settings_manager.cycle_difficulty(-1)
        assert settings_manager.difficulty == difficulties[-1]
