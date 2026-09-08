import json
from pathlib import Path
from src.config import Config, VolumeConfig, UploadConfig

def test_default_config_matrix(tmp_path):
    cfg_file = tmp_path / "config.json"
    cfg = Config.load(cfg_file)
    assert "EOS_DIGITAL" in cfg.volumes
    assert "default" in cfg.google_accounts
    assert cfg.defaults.folder_structure == "%Y-%m-%d"
    assert cfg_file.exists()

def test_set_and_remove_volume_matrix(tmp_path):
    cfg_file = tmp_path / "config.json"
    cfg = Config.load(cfg_file)
    
    cfg.set_volume_config(
        volume_name="DRONE_SD",
        dest_base_dir="~/local/photos/drone",
        upload_enabled=False,
        config_path=cfg_file
    )
    assert "DRONE_SD" in cfg.volumes
    assert cfg.volumes["DRONE_SD"].upload.enabled is False
    assert cfg.volumes["DRONE_SD"].dest_base_dir == "~/local/photos/drone"

    # Reload and verify
    reloaded = Config.load(cfg_file)
    assert "DRONE_SD" in reloaded.volumes
    resolved = reloaded.get_resolved_volume_config("DRONE_SD")
    assert resolved.dest_base_dir == "~/local/photos/drone"
    assert resolved.upload.enabled is False

    # Remove volume
    assert reloaded.remove_volume("DRONE_SD", cfg_file) is True
    assert "DRONE_SD" not in reloaded.volumes

def test_add_and_remove_google_account(tmp_path):
    cfg_file = tmp_path / "config.json"
    cfg = Config.load(cfg_file)

    cfg.add_google_account(
        account_name="work",
        credentials_path="/path/to/work_creds.json",
        token_path="/path/to/work_token.json",
        config_path=cfg_file
    )

    reloaded = Config.load(cfg_file)
    assert "work" in reloaded.google_accounts
    assert reloaded.google_accounts["work"].credentials_path == "/path/to/work_creds.json"
