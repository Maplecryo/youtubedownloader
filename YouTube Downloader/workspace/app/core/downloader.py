import threading
from pathlib import Path
from typing import Callable, Optional

import yt_dlp

from app.core.ffmpeg_utils import find_ffmpeg
from app.core.queue import DownloadItem, DownloadQueue, DownloadStatus
from app.utils.logger import logger

MAX_RETRIES = 3


def _fmt_size(b: int) -> str:
    if b >= 1024 ** 3:
        return f"{b / 1024 ** 3:.1f} GB"
    if b >= 1024 ** 2:
        return f"{b / 1024 ** 2:.1f} MB"
    if b >= 1024:
        return f"{b / 1024:.1f} KB"
    return f"{b} B"


def _build_ydl_opts(item: DownloadItem) -> dict:
    from app.utils.config import config  # lazy to avoid circular import at module level

    opts: dict = {
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "outtmpl": str(Path(item.output_dir) / item.filename_template),
        "retries": MAX_RETRIES,
        "fragment_retries": MAX_RETRIES,
        "ignoreerrors": False,
    }

    ffmpeg = find_ffmpeg()
    if ffmpeg:
        opts["ffmpeg_location"] = str(Path(ffmpeg).parent)

    speed = config.get("speed_limit", "")
    if speed:
        opts["ratelimit"] = speed

    proxy = config.get("proxy_url", "")
    if proxy:
        opts["proxy"] = proxy

    cookies = config.get("use_cookies", "none")
    if cookies != "none":
        opts["cookiesfrombrowser"] = (cookies,)

    if config.get("sanitize_filenames", True):
        opts["restrictfilenames"] = True

    dup = config.get("duplicate_handling", "auto_rename")
    if dup == "overwrite":
        opts["overwrites"] = True
    else:
        opts["nooverwrites"] = True

    codec_pref: str = config.get("preferred_video_codec", "any")

    if item.mode == "audio":
        opts["format"] = "bestaudio/best"
        fmt = item.audio_format.lower()
        bitrate = item.audio_bitrate
        postprocessors: list[dict] = [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": fmt,
                "preferredquality": bitrate,
            }
        ]
        if fmt in ("mp3", "m4a") and config.get("embed_thumbnail", True):
            postprocessors += [
                {"key": "FFmpegThumbnailsConvertor", "format": "jpg"},
                {"key": "EmbedThumbnail"},
            ]
            opts["writethumbnail"] = True
        if config.get("embed_metadata", True):
            postprocessors.append({"key": "FFmpegMetadata", "add_metadata": True})
        opts["postprocessors"] = postprocessors
    else:
        # Video
        height_map = {
            "best": None,
            "1080p": 1080,
            "720p": 720,
            "480p": 480,
            "360p": 360,
            "240p": 240,
            "144p": 144,
        }
        h = height_map.get(item.quality.lower())

        codec_filter = {
            "h264": "[vcodec^=avc]",
            "vp9": "[vcodec^=vp9]",
            "av1": "[vcodec^=av01]",
        }.get(codec_pref, "")

        if h:
            opts["format"] = (
                f"bestvideo[height<={h}]{codec_filter}+bestaudio/"
                f"bestvideo[height<={h}]+bestaudio/"
                f"best[height<={h}]"
            )
        else:
            opts["format"] = (
                f"bestvideo{codec_filter}+bestaudio/bestvideo+bestaudio/best"
            )

        vfmt = item.video_format.lower()
        opts["merge_output_format"] = vfmt if vfmt in ("mp4", "mkv") else "mp4"

        postprocessors = []
        if config.get("embed_metadata", True):
            postprocessors.append({"key": "FFmpegMetadata", "add_metadata": True})
        if postprocessors:
            opts["postprocessors"] = postprocessors

    return opts


class DownloadManager:
    def __init__(self, queue: DownloadQueue) -> None:
        self.queue = queue
        self._active: dict[str, threading.Thread] = {}
        self._lock = threading.Lock()

    def start_item(
        self,
        item: DownloadItem,
        on_update: Optional[Callable] = None,
    ) -> None:
        t = threading.Thread(
            target=self._download,
            args=(item, on_update),
            daemon=True,
        )
        with self._lock:
            self._active[item.id] = t
        t.start()

    def _download(
        self,
        item: DownloadItem,
        on_update: Optional[Callable],
    ) -> None:
        def update(**kwargs):
            self.queue.update(item.id, **kwargs)
            if on_update:
                on_update()

        update(status=DownloadStatus.DOWNLOADING, progress=0.0)

        def progress_hook(d: dict) -> None:
            if item.cancel_event.is_set():
                raise yt_dlp.utils.DownloadCancelled("Cancelled by user")

            status = d.get("status")
            if status == "downloading":
                pct_str = d.get("_percent_str", "0%").strip().replace("%", "")
                try:
                    progress = float(pct_str)
                except ValueError:
                    progress = 0.0

                speed_str = d.get("_speed_str", "").strip()
                eta_str = d.get("_eta_str", "").strip()
                dl_bytes = d.get("downloaded_bytes") or 0
                total_bytes = d.get("total_bytes") or d.get("total_bytes_estimate") or 0

                update(
                    progress=progress,
                    speed=speed_str,
                    eta=eta_str,
                    downloaded=_fmt_size(dl_bytes),
                    total_size=_fmt_size(total_bytes) if total_bytes else "?",
                )
            elif status == "finished":
                update(
                    status=DownloadStatus.POST_PROCESSING,
                    progress=100.0,
                    speed="",
                    eta="",
                )

        opts = _build_ydl_opts(item)
        opts["progress_hooks"] = [progress_hook]

        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([item.url])

            if item.cancel_event.is_set():
                update(status=DownloadStatus.CANCELLED)
                return

            update(
                status=DownloadStatus.COMPLETE,
                progress=100.0,
                output_path=item.output_dir,
            )
        except yt_dlp.utils.DownloadCancelled:
            update(status=DownloadStatus.CANCELLED)
            self._cleanup_partial(item)
        except yt_dlp.utils.DownloadError as e:
            msg = str(e)
            logger.error(f"Download error for {item.url}: {msg}")
            lo = msg.lower()
            if "rate" in lo or "429" in lo:
                user_msg = f"YouTube is rate-limiting requests. Retrying may help."
            elif "no space" in lo or "disk" in lo:
                user_msg = "Not enough disk space in output folder."
            else:
                user_msg = f"Download failed: {msg[:200]}. See log for details."
            update(status=DownloadStatus.FAILED, error=user_msg)
        except Exception as e:
            logger.exception(f"Unexpected error downloading {item.url}")
            update(status=DownloadStatus.FAILED, error=f"Download failed: {str(e)[:200]}")
        finally:
            with self._lock:
                self._active.pop(item.id, None)

    def _cleanup_partial(self, item: DownloadItem) -> None:
        out_dir = Path(item.output_dir)
        try:
            for f in out_dir.iterdir():
                if f.suffix in (".part", ".ytdl") and f.is_file():
                    f.unlink(missing_ok=True)
        except Exception:
            pass

    def cancel_item(self, item_id: str) -> None:
        item = self.queue.get(item_id)
        if item:
            item.cancel_event.set()

    def cancel_all(self) -> None:
        for item in self.queue.all():
            item.cancel_event.set()

    def start_all_pending(self, on_update: Optional[Callable] = None) -> None:
        from app.utils.config import config

        max_concurrent = int(config.get("max_concurrent", 1))
        for item in self.queue.all():
            if item.status != DownloadStatus.PENDING:
                continue
            with self._lock:
                active = len(self._active)
            if active < max_concurrent:
                self.start_item(item, on_update)
