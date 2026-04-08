import json
from src.managers.settings_manager import SettingsManager


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

    def test_volume_clamped_high(self, tmp_path):
        path = str(tmp_path / "settings.json")
        with open(path, "w") as f:
            json.dump({"master_volume": 5.0}, f)
        sm = SettingsManager(path=path)
        assert sm.master_volume == 1.0

    def test_volume_clamped_low(self, tmp_path):
        path = str(tmp_path / "settings.json")
        with open(path, "w") as f:
            json.dump({"master_volume": -0.5}, f)
        sm = SettingsManager(path=path)
        assert sm.master_volume == 0.0

    def test_missing_key_uses_default(self, tmp_path):
        path = str(tmp_path / "settings.json")
        with open(path, "w") as f:
            json.dump({}, f)
        sm = SettingsManager(path=path)
        assert sm.master_volume == 1.0
