import json
from pathlib import Path
from src.config import Config

def test_default_config(tmp_path):
    cfg_file = tmp_path / "config.json"
    cfg = Config.load(cfg_file)
    assert "EOS_DIGITAL" in cfg.monitored_volumes
    assert cfg.folder_structure == "%Y-%m-%d"
    assert cfg_file.exists()

def test_add_remove_sd_card(tmp_path):
    cfg_file = tmp_path / "config.json"
    cfg = Config.load(cfg_file)
    
    assert cfg.add_monitored_volume("TEST_SD", cfg_file) is True
    assert "TEST_SD" in cfg.monitored_volumes
    
    # Adding again should return False
    assert cfg.add_monitored_volume("TEST_SD", cfg_file) is False
    
    # Reload and verify persistence
    reloaded = Config.load(cfg_file)
    assert "TEST_SD" in reloaded.monitored_volumes
    
    # Remove
    assert reloaded.remove_monitored_volume("TEST_SD", cfg_file) is True
    assert "TEST_SD" not in reloaded.monitored_volumes
