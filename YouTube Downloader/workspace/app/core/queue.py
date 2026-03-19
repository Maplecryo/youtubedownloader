import threading
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional


class DownloadStatus(Enum):
    PENDING = "Pending"
    FETCHING = "Fetching Metadata"
    DOWNLOADING = "Downloading"
    POST_PROCESSING = "Post-processing"
    COMPLETE = "Complete"
    FAILED = "Failed"
    CANCELLED = "Cancelled"


@dataclass
class DownloadItem:
    url: str
    title: str = ""
    mode: str = "video"            # "video" | "audio"
    quality: str = "best"          # "best" | "1080p" | "720p" etc.
    audio_format: str = "mp3"
    audio_bitrate: str = "192"
    video_format: str = "mp4"
    output_dir: str = ""
    filename_template: str = "%(title)s.%(ext)s"
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: DownloadStatus = DownloadStatus.PENDING
    progress: float = 0.0
    speed: str = ""
    eta: str = ""
    downloaded: str = ""
    total_size: str = ""
    output_path: str = ""
    error: str = ""
    cancel_event: threading.Event = field(default_factory=threading.Event)


class DownloadQueue:
    def __init__(self) -> None:
        self._items: list[DownloadItem] = []
        self._lock = threading.Lock()
        self._listeners: list[Callable] = []

    def add_listener(self, cb: Callable) -> None:
        self._listeners.append(cb)

    def _notify(self) -> None:
        for cb in self._listeners:
            try:
                cb()
            except Exception:
                pass

    def add(self, item: DownloadItem) -> DownloadItem:
        with self._lock:
            self._items.append(item)
        self._notify()
        return item

    def remove(self, item_id: str) -> None:
        with self._lock:
            self._items = [i for i in self._items if i.id != item_id]
        self._notify()

    def get(self, item_id: str) -> Optional[DownloadItem]:
        with self._lock:
            for i in self._items:
                if i.id == item_id:
                    return i
        return None

    def all(self) -> list[DownloadItem]:
        with self._lock:
            return list(self._items)

    def update(self, item_id: str, **kwargs) -> None:
        with self._lock:
            for item in self._items:
                if item.id == item_id:
                    for k, v in kwargs.items():
                        setattr(item, k, v)
                    break
        self._notify()

    def clear_completed(self) -> None:
        terminal = {DownloadStatus.COMPLETE, DownloadStatus.CANCELLED, DownloadStatus.FAILED}
        with self._lock:
            self._items = [i for i in self._items if i.status not in terminal]
        self._notify()

    def pending_count(self) -> int:
        with self._lock:
            return sum(1 for i in self._items if i.status == DownloadStatus.PENDING)

    def active_count(self) -> int:
        active = {DownloadStatus.DOWNLOADING, DownloadStatus.POST_PROCESSING, DownloadStatus.FETCHING}
        with self._lock:
            return sum(1 for i in self._items if i.status in active)
