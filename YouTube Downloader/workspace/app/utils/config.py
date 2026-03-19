import json
from pathlib import Path
from typing import Any

CONFIG_PATH = Path.home() / "YouTube Downloader" / "config.json"

DEFAULTS: dict[str, Any] = {
    "output_dir": str(Path.home() / "Downloads"),
    "filename_template": "%(title)s.%(ext)s",
    "sanitize_filenames": True,
    "duplicate_handling": "auto_rename",  # skip | overwrite | auto_rename
    "max_concurrent": 1,
    "speed_limit": "",
    "proxy_url": "",
    "ffmpeg_path": "",
    "use_cookies": "none",  # none | chrome | firefox
    "embed_metadata": True,
    "embed_thumbnail": True,
    "preferred_video_codec": "any",  # any | h264 | vp9 | av1
    "theme": "System",
    "window_geometry": "",
    "disclaimer_shown": False,
}


class Config:
    def __init__(self) -> None:
        self._data: dict[str, Any] = dict(DEFAULTS)
        self.load()

    def load(self) -> None:
        if CONFIG_PATH.exists():
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    stored = json.load(f)
                self._data.update(stored)
            except Exception:
                pass

    def save(self) -> None:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2)

    def get(self, key: str, default: Any = None) -> Any:
        if default is not None:
            return self._data.get(key, default)
        return self._data.get(key, DEFAULTS.get(key))

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value

    def update(self, data: dict) -> None:
        self._data.update(data)


config = Config()
