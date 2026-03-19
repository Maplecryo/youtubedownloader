import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

import yt_dlp

from app.core.ffmpeg_utils import find_ffmpeg
from app.utils.logger import logger


@dataclass
class VideoFormat:
    format_id: str
    resolution: str   # e.g. "1080p"
    ext: str
    note: str = ""
    filesize: Optional[int] = None
    vcodec: str = ""
    acodec: str = ""


@dataclass
class PlaylistEntry:
    id: str
    title: str
    url: str
    duration: int = 0


@dataclass
class VideoMetadata:
    url: str
    title: str = ""
    channel: str = ""
    duration: int = 0
    thumbnail_url: str = ""
    formats: list[VideoFormat] = field(default_factory=list)
    is_playlist: bool = False
    playlist_title: str = ""
    playlist_entries: list[PlaylistEntry] = field(default_factory=list)

    @property
    def duration_str(self) -> str:
        if not self.duration:
            return "N/A"
        h = self.duration // 3600
        m = (self.duration % 3600) // 60
        s = self.duration % 60
        if h:
            return f"{h:02d}:{m:02d}:{s:02d}"
        return f"{m:02d}:{s:02d}"


def _base_opts() -> dict:
    opts: dict = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
    }
    ffmpeg = find_ffmpeg()
    if ffmpeg:
        opts["ffmpeg_location"] = str(Path(ffmpeg).parent)
    return opts


def _parse_video_info(url: str, info: dict) -> VideoMetadata:
    meta = VideoMetadata(url=url)
    meta.title = info.get("title", "Unknown")
    meta.channel = info.get("uploader") or info.get("channel", "")
    meta.duration = int(info.get("duration") or 0)
    meta.thumbnail_url = info.get("thumbnail", "")

    seen: set[str] = set()
    formats: list[VideoFormat] = []
    for f in info.get("formats", []):
        if f.get("vcodec") in (None, "none"):
            continue
        height = f.get("height")
        if not height:
            continue
        res = f"{height}p"
        if res not in seen:
            seen.add(res)
            formats.append(
                VideoFormat(
                    format_id=f.get("format_id", ""),
                    resolution=res,
                    ext=f.get("ext", "mp4"),
                    note=f.get("format_note", ""),
                    filesize=f.get("filesize"),
                    vcodec=f.get("vcodec", ""),
                    acodec=f.get("acodec", ""),
                )
            )

    formats.sort(key=lambda x: int(x.resolution.rstrip("p")), reverse=True)
    meta.formats = formats
    return meta


def fetch_metadata(
    url: str,
    on_success: Callable[[VideoMetadata], None],
    on_error: Callable[[str], None],
    cancel_event: Optional[threading.Event] = None,
) -> threading.Thread:
    def _fetch() -> None:
        try:
            # First pass: flat extract to detect playlist quickly
            flat_opts = _base_opts()
            flat_opts["extract_flat"] = "in_playlist"

            if cancel_event and cancel_event.is_set():
                return

            with yt_dlp.YoutubeDL(flat_opts) as ydl:
                info = ydl.extract_info(url, download=False)

            if cancel_event and cancel_event.is_set():
                return

            if info is None:
                on_error("Failed to retrieve video info.")
                return

            if info.get("_type") == "playlist" or (
                "entries" in info and info.get("entries")
            ):
                # Playlist
                meta = VideoMetadata(url=url)
                meta.is_playlist = True
                meta.playlist_title = info.get("title", "Playlist")
                meta.title = meta.playlist_title
                entries = info.get("entries") or []
                meta.playlist_entries = [
                    PlaylistEntry(
                        id=e.get("id", ""),
                        title=e.get("title") or f"Video {i+1}",
                        url=(
                            e.get("url")
                            or e.get("webpage_url")
                            or f"https://www.youtube.com/watch?v={e.get('id', '')}"
                        ),
                        duration=int(e.get("duration") or 0),
                    )
                    for i, e in enumerate(entries)
                    if e
                ]
                on_success(meta)
            else:
                # Single video — re-fetch with full format info
                full_opts = _base_opts()
                with yt_dlp.YoutubeDL(full_opts) as ydl:
                    full_info = ydl.extract_info(url, download=False)
                if cancel_event and cancel_event.is_set():
                    return
                if full_info is None:
                    on_error("Failed to retrieve video info.")
                    return
                on_success(_parse_video_info(url, full_info))

        except yt_dlp.utils.DownloadError as e:
            msg = str(e).lower()
            if "private" in msg:
                on_error("This video is unavailable or private.")
            elif "unavailable" in msg:
                on_error("This video is unavailable.")
            elif "region" in msg or "not available in your country" in msg:
                on_error("This video is region-locked.")
            else:
                on_error(f"Failed to fetch metadata: {str(e)[:200]}")
        except Exception as e:
            logger.exception(f"Metadata fetch error for {url}")
            on_error(f"An error occurred: {str(e)[:200]}")

    t = threading.Thread(target=_fetch, daemon=True)
    t.start()
    return t
