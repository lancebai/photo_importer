import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Optional

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "photo_importer"
DEFAULT_CONFIG_FILE = DEFAULT_CONFIG_DIR / "config.json"
DEFAULT_DB_FILE = DEFAULT_CONFIG_DIR / "library.db"
DEFAULT_CREDENTIALS_FILE = DEFAULT_CONFIG_DIR / "credentials.json"
DEFAULT_TOKEN_FILE = DEFAULT_CONFIG_DIR / "token.json"

DEFAULT_EXTENSIONS = [
    ".cr2", ".cr3", ".crw",  # Canon RAW formats
    ".jpg", ".jpeg", ".png", ".heic", ".tiff",  # Images
    ".mp4", ".mov", ".avi"  # Videos
]

@dataclass
class Config:
    monitored_volumes: List[str] = field(default_factory=lambda: ["EOS_DIGITAL", "CANON_SD"])
    dest_base_dir: str = "~/local/photos"
    folder_structure: str = "%Y-%m-%d"  # Or "%Y/%Y-%m-%d"
    delete_after_import: bool = False
    use_move: bool = False
    auto_upload_to_gphotos: bool = True
    gphotos_album: Optional[str] = None
    google_credentials_path: str = str(DEFAULT_CREDENTIALS_FILE)
    google_token_path: str = str(DEFAULT_TOKEN_FILE)
    db_path: str = str(DEFAULT_DB_FILE)
    supported_extensions: List[str] = field(default_factory=lambda: list(DEFAULT_EXTENSIONS))

    @property
    def expanded_dest_dir(self) -> Path:
        return Path(self.dest_base_dir).expanduser()

    @property
    def expanded_db_path(self) -> Path:
        return Path(self.db_path).expanduser()

    @property
    def expanded_credentials_path(self) -> Path:
        return Path(self.google_credentials_path).expanduser()

    @property
    def expanded_token_path(self) -> Path:
        return Path(self.google_token_path).expanduser()

    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> "Config":
        path = config_path or DEFAULT_CONFIG_FILE
        path = Path(path).expanduser()
        
        if not path.exists():
            config = cls()
            config.save(path)
            return config

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
        except Exception as e:
            print(f"Warning: Failed to load config from {path} ({e}). Using default config.")
            return cls()

    def save(self, config_path: Optional[Path] = None) -> None:
        path = config_path or DEFAULT_CONFIG_FILE
        path = Path(path).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, indent=2, ensure_ascii=False)

    def add_monitored_volume(self, volume_name: str, config_path: Optional[Path] = None) -> bool:
        vol = volume_name.strip()
        if vol and vol not in self.monitored_volumes:
            self.monitored_volumes.append(vol)
            self.save(config_path)
            return True
        return False

    def remove_monitored_volume(self, volume_name: str, config_path: Optional[Path] = None) -> bool:
        vol = volume_name.strip()
        if vol in self.monitored_volumes:
            self.monitored_volumes.remove(vol)
            self.save(config_path)
            return True
        return False
