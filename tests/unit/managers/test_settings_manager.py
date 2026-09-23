import json

import pytest

from src.managers.settings_manager import SettingsManager
from src.utils.constants import Difficulty


class TestSettingsManager:
    def test_default_volume(self, tmp_path):
        path = str(tmp_path / "settings.json")
        sm = SettingsManager(path=path)
        assert sm.master_volume == 1.0

    def test_load_existing_settings(self, tmp_path):
        path = str(tmp_path / "settings.json")
        with open(path, "w") as f:
            json.dump({"master_volume": 0.5}, f)
        sm = SettingsManager(path=path)
        assert sm.master_volume == 0.5

    def test_save_creates_file(self, tmp_path):
        path = str(tmp_path / "settings.json")
        sm = SettingsManager(path=path)
        sm.master_volume = 0.7
        sm.save()
        with open(path) as f:
            data = json.load(f)
        assert data["master_volume"] == 0.7

    def test_corrupted_file_uses_defaults(self, tmp_path):
        path = str(tmp_path / "settings.json")
        with open(path, "w") as f:
            f.write("not json!")
        sm = SettingsManager(path=path)
        assert sm.master_volume == 1.0

    @pytest.mark.parametrize("stored, expected", [(5.0, 1.0), (-0.5, 0.0)])
    def test_loaded_volume_clamped(self, tmp_path, stored, expected):
        path = str(tmp_path / "settings.json")
        with open(path, "w") as f:
            json.dump({"master_volume": stored}, f)
        sm = SettingsManager(path=path)
        assert sm.master_volume == expected

    def test_missing_key_uses_default(self, tmp_path):
        path = str(tmp_path / "settings.json")
        with open(path, "w") as f:
            json.dump({}, f)
        sm = SettingsManager(path=path)
        assert sm.master_volume == 1.0

    def test_adjust_volume_applies_delta(self, tmp_path):
        sm = SettingsManager(path=str(tmp_path / "settings.json"))
        sm.master_volume = 0.5
        sm.adjust_volume(0.1)
        assert sm.master_volume == 0.6

    @pytest.mark.parametrize(
        "start, delta, expected", [(0.0, -0.1, 0.0), (1.0, 0.1, 1.0)]
    )
    def test_adjust_volume_clamps(self, tmp_path, start, delta, expected):
        sm = SettingsManager(path=str(tmp_path / "settings.json"))
        sm.master_volume = start
        sm.adjust_volume(delta)
        assert sm.master_volume == expected

    def test_cycle_difficulty_forward_wraps(self, tmp_path):
        sm = SettingsManager(path=str(tmp_path / "settings.json"))
        difficulties = list(Difficulty)
        sm.difficulty = difficulties[-1]
        sm.cycle_difficulty(1)
        assert sm.difficulty == difficulties[0]

    def test_cycle_difficulty_backward_wraps(self, tmp_path):
        sm = SettingsManager(path=str(tmp_path / "settings.json"))
        difficulties = list(Difficulty)
        sm.difficulty = difficulties[0]
        sm.cycle_difficulty(-1)
        assert sm.difficulty == difficulties[-1]
