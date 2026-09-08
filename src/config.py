import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional, Any

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "photo_importer"
DEFAULT_CONFIG_FILE = DEFAULT_CONFIG_DIR / "config.json"
DEFAULT_DB_FILE = DEFAULT_CONFIG_DIR / "library.db"

DEFAULT_EXTENSIONS = [
    ".cr2", ".cr3", ".crw",  # Canon RAW formats
    ".jpg", ".jpeg", ".png", ".heic", ".tiff",  # Images
    ".mp4", ".mov", ".avi"  # Videos
]

@dataclass
class GoogleAccountConfig:
    credentials_path: str = str(DEFAULT_CONFIG_DIR / "credentials_default.json")
    token_path: str = str(DEFAULT_CONFIG_DIR / "token_default.json")

    @property
    def expanded_credentials_path(self) -> Path:
        return Path(self.credentials_path).expanduser()

    @property
    def expanded_token_path(self) -> Path:
        return Path(self.token_path).expanduser()

@dataclass
class UploadConfig:
    enabled: bool = True
    google_account: str = "default"
    album: Optional[str] = None

@dataclass
class VolumeConfig:
    dest_base_dir: Optional[str] = None
    folder_structure: Optional[str] = None
    delete_after_import: Optional[bool] = None
    use_move: Optional[bool] = None
    upload: UploadConfig = field(default_factory=UploadConfig)
    supported_extensions: Optional[List[str]] = None

@dataclass
class DefaultsConfig:
    dest_base_dir: str = "~/local/photos"
    folder_structure: str = "%Y-%m-%d"
    delete_after_import: bool = False
    use_move: bool = False
    supported_extensions: List[str] = field(default_factory=lambda: list(DEFAULT_EXTENSIONS))

@dataclass
class Config:
    defaults: DefaultsConfig = field(default_factory=DefaultsConfig)
    google_accounts: Dict[str, GoogleAccountConfig] = field(default_factory=lambda: {
        "default": GoogleAccountConfig()
    })
    volumes: Dict[str, VolumeConfig] = field(default_factory=lambda: {
        "EOS_DIGITAL": VolumeConfig(
            dest_base_dir="~/local/photos/canon",
            folder_structure="%Y-%m-%d",
            upload=UploadConfig(enabled=True, google_account="default", album="Canon RAW")
        ),
        "CANON_SD": VolumeConfig(
            dest_base_dir="~/local/photos/canon",
            folder_structure="%Y-%m-%d",
            upload=UploadConfig(enabled=True, google_account="default", album=None)
        )
    })
    db_path: str = str(DEFAULT_DB_FILE)

    @property
    def expanded_db_path(self) -> Path:
        return Path(self.db_path).expanduser()

    @property
    def monitored_volumes(self) -> List[str]:
        return list(self.volumes.keys())

    def get_resolved_volume_config(self, volume_name: str) -> VolumeConfig:
        """
        Get resolved volume config, merging volume-specific settings with global defaults.
        """
        vol = self.volumes.get(volume_name, VolumeConfig())
        return VolumeConfig(
            dest_base_dir=vol.dest_base_dir or self.defaults.dest_base_dir,
            folder_structure=vol.folder_structure or self.defaults.folder_structure,
            delete_after_import=vol.delete_after_import if vol.delete_after_import is not None else self.defaults.delete_after_import,
            use_move=vol.use_move if vol.use_move is not None else self.defaults.use_move,
            upload=vol.upload if vol.upload is not None else UploadConfig(enabled=True, google_account="default"),
            supported_extensions=vol.supported_extensions or self.defaults.supported_extensions
        )

    def get_google_account(self, account_name: str = "default") -> GoogleAccountConfig:
        if account_name in self.google_accounts:
            return self.google_accounts[account_name]
        # Return fallback with named paths
        return GoogleAccountConfig(
            credentials_path=str(DEFAULT_CONFIG_DIR / f"credentials_{account_name}.json"),
            token_path=str(DEFAULT_CONFIG_DIR / f"token_{account_name}.json")
        )

    def add_google_account(
        self,
        account_name: str,
        credentials_path: Optional[str] = None,
        token_path: Optional[str] = None,
        config_path: Optional[Path] = None
    ) -> None:
        acc_name = account_name.strip()
        creds = credentials_path or str(DEFAULT_CONFIG_DIR / f"credentials_{acc_name}.json")
        token = token_path or str(DEFAULT_CONFIG_DIR / f"token_{acc_name}.json")
        self.google_accounts[acc_name] = GoogleAccountConfig(credentials_path=creds, token_path=token)
        self.save(config_path)

    def set_volume_config(
        self,
        volume_name: str,
        dest_base_dir: Optional[str] = None,
        folder_structure: Optional[str] = None,
        use_move: Optional[bool] = None,
        delete_after_import: Optional[bool] = None,
        upload_enabled: Optional[bool] = None,
        google_account: Optional[str] = None,
        album: Optional[str] = None,
        config_path: Optional[Path] = None
    ) -> None:
        vol_name = volume_name.strip()
        existing = self.volumes.get(vol_name, VolumeConfig())

        up = existing.upload or UploadConfig()
        if upload_enabled is not None:
            up.enabled = upload_enabled
        if google_account is not None:
            up.google_account = google_account
        if album is not None:
            up.album = album

        new_vol = VolumeConfig(
            dest_base_dir=dest_base_dir if dest_base_dir is not None else existing.dest_base_dir,
            folder_structure=folder_structure if folder_structure is not None else existing.folder_structure,
            use_move=use_move if use_move is not None else existing.use_move,
            delete_after_import=delete_after_import if delete_after_import is not None else existing.delete_after_import,
            upload=up,
            supported_extensions=existing.supported_extensions
        )
        self.volumes[vol_name] = new_vol
        self.save(config_path)

    def remove_volume(self, volume_name: str, config_path: Optional[Path] = None) -> bool:
        vol_name = volume_name.strip()
        if vol_name in self.volumes:
            del self.volumes[vol_name]
            self.save(config_path)
            return True
        return False

    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> "Config":
        path = config_path or DEFAULT_CONFIG_FILE
        path = Path(path).expanduser()
        
        if not path.exists():
            cfg = cls()
            cfg.save(path)
            return cfg

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Handle migration from legacy flat config if present
            if "monitored_volumes" in data and "volumes" not in data:
                return cls._migrate_legacy_config(data, path)

            # Parse defaults
            def_data = data.get("defaults", {})
            defaults = DefaultsConfig(**{k: v for k, v in def_data.items() if k in DefaultsConfig.__dataclass_fields__})

            # Parse google_accounts
            accounts = {}
            for acc_name, acc_val in data.get("google_accounts", {}).items():
                accounts[acc_name] = GoogleAccountConfig(**{k: v for k, v in acc_val.items() if k in GoogleAccountConfig.__dataclass_fields__})
            if not accounts:
                accounts["default"] = GoogleAccountConfig()

            # Parse volumes matrix
            volumes = {}
            for v_name, v_val in data.get("volumes", {}).items():
                up_data = v_val.get("upload", {})
                up_cfg = UploadConfig(**{k: v for k, v in up_data.items() if k in UploadConfig.__dataclass_fields__})
                v_clean = {k: v for k, v in v_val.items() if k in VolumeConfig.__dataclass_fields__ and k != "upload"}
                volumes[v_name] = VolumeConfig(**v_clean, upload=up_cfg)

            db_path = data.get("db_path", str(DEFAULT_DB_FILE))
            return cls(defaults=defaults, google_accounts=accounts, volumes=volumes, db_path=db_path)

        except Exception as e:
            print(f"Warning: Failed to load config from {path} ({e}). Using default config.")
            return cls()

    @classmethod
    def _migrate_legacy_config(cls, data: dict, path: Path) -> "Config":
        """Migrate legacy flat config to matrix JSON structure."""
        cfg = cls()
        monitored = data.get("monitored_volumes", [])
        legacy_dest = data.get("dest_base_dir", "~/local/photos")
        legacy_upload = data.get("auto_upload_to_gphotos", True)
        legacy_album = data.get("gphotos_album")
        legacy_move = data.get("use_move", False)

        cfg.defaults.dest_base_dir = legacy_dest
        cfg.defaults.use_move = legacy_move

        cfg.volumes = {}
        for vol_name in monitored:
            cfg.volumes[vol_name] = VolumeConfig(
                dest_base_dir=legacy_dest,
                upload=UploadConfig(enabled=legacy_upload, google_account="default", album=legacy_album)
            )

        cfg.save(path)
        return cfg

    def save(self, config_path: Optional[Path] = None) -> None:
        path = config_path or DEFAULT_CONFIG_FILE
        path = Path(path).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, indent=2, ensure_ascii=False)
