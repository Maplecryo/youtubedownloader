import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Optional

import customtkinter as ctk

from app.core.downloader import DownloadManager
from app.core.metadata import VideoMetadata, fetch_metadata
from app.core.queue import DownloadItem, DownloadQueue, DownloadStatus
from app.core.ffmpeg_utils import check_ffmpeg, FFMPEG_INSTALL_URL
from app.gui.preview_panel import PreviewPanel
from app.gui.queue_panel import QueuePanel
from app.gui.settings_dialog import SettingsDialog
from app.gui.url_bar import URLBar
from app.gui.widgets import Tooltip
from app.utils.config import config
from app.utils.logger import logger


class _PlaylistDialog(ctk.CTkToplevel):
    def __init__(
        self,
        parent: tk.Widget,
        meta: VideoMetadata,
        on_confirm,
        **kwargs,
    ) -> None:
        super().__init__(parent, **kwargs)
        self._meta = meta
        self._on_confirm = on_confirm
        self.title(f"Playlist — {meta.playlist_title}")
        self.geometry("520x520")
        self.grab_set()
        self._vars: dict[str, tuple[tk.BooleanVar, object]] = {}
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            self,
            text=f"Playlist: {self._meta.playlist_title}",
            font=ctk.CTkFont(weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, padx=16, pady=(16, 4), sticky="w")

        scroll = ctk.CTkScrollableFrame(self)
        scroll.grid(row=1, column=0, sticky="nsew", padx=12, pady=4)
        scroll.grid_columnconfigure(0, weight=1)

        for i, entry in enumerate(self._meta.playlist_entries):
            var = tk.BooleanVar(value=True)
            self._vars[entry.url] = (var, entry)
            label = f"{i + 1}. {entry.title[:65]}"
            ctk.CTkCheckBox(scroll, text=label, variable=var).grid(
                row=i, column=0, padx=8, pady=2, sticky="w"
            )

        sel_row = ctk.CTkFrame(self, fg_color="transparent")
        sel_row.grid(row=2, column=0, padx=12, pady=(4, 0), sticky="ew")
        ctk.CTkButton(sel_row, text="Select All", width=90, command=self._select_all).pack(
            side="left", padx=4
        )
        ctk.CTkButton(sel_row, text="Deselect All", width=90, command=self._deselect_all).pack(
            side="left", padx=4
        )

        ctk.CTkLabel(sel_row, text=f"{len(self._meta.playlist_entries)} videos").pack(
            side="right", padx=8
        )

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.grid(row=3, column=0, padx=12, pady=(4, 16), sticky="ew")
        ctk.CTkButton(btn_row, text="Add to Queue", command=self._confirm).pack(
            side="right", padx=4
        )
        ctk.CTkButton(
            btn_row,
            text="Cancel",
            command=self.destroy,
            fg_color=("gray60", "gray40"),
        ).pack(side="right", padx=4)

    def _select_all(self) -> None:
        for var, _ in self._vars.values():
            var.set(True)

    def _deselect_all(self) -> None:
        for var, _ in self._vars.values():
            var.set(False)

    def _confirm(self) -> None:
        selected = [
            (url, entry)
            for url, (var, entry) in self._vars.items()
            if var.get()
        ]
        if selected:
            self._on_confirm(selected)
        self.destroy()


class MainWindow(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()

        ctk.set_appearance_mode(config.get("theme", "System"))
        ctk.set_default_color_theme("blue")

        self.title("YouTube Downloader")
        self.minsize(720, 620)

        geom = config.get("window_geometry", "")
        self.geometry(geom if geom else "960x720")

        self._queue = DownloadQueue()
        self._manager = DownloadManager(self._queue)
        self._fetch_cancel = threading.Event()
        self._metadata: Optional[VideoMetadata] = None

        self._setup_ui()
        self._bind_shortcuts()
        self._check_first_run()
        self._check_ffmpeg_warning()
        self._schedule_status_update()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        # URL bar
        self.url_bar = URLBar(
            self,
            on_fetch=self._on_fetch,
            on_cancel=self._on_fetch_cancel,
        )
        self.url_bar.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 0))

        # Preview panel
        self.preview = PreviewPanel(self)
        self.preview.grid(row=1, column=0, sticky="ew", padx=8, pady=4)

        # Output row
        out_frame = ctk.CTkFrame(self)
        out_frame.grid(row=2, column=0, sticky="ew", padx=8, pady=4)
        out_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(out_frame, text="Output:", width=60).grid(
            row=0, column=0, padx=(8, 4), pady=8
        )

        self.output_var = tk.StringVar(
            value=config.get("output_dir", str(Path.home() / "Downloads"))
        )
        self.output_entry = ctk.CTkEntry(out_frame, textvariable=self.output_var)
        self.output_entry.grid(row=0, column=1, padx=4, pady=8, sticky="ew")
        Tooltip(self.output_entry, "Folder where downloaded files will be saved")

        browse_btn = ctk.CTkButton(out_frame, text="Browse", width=70, command=self._browse_output)
        browse_btn.grid(row=0, column=2, padx=4, pady=8)
        Tooltip(browse_btn, "Choose output folder")

        self.dl_btn = ctk.CTkButton(
            out_frame, text="Download", width=90, command=self._download_current
        )
        self.dl_btn.grid(row=0, column=3, padx=(4, 8), pady=8)
        Tooltip(self.dl_btn, "Add current video to queue and start downloading (Ctrl+D)")

        ctk.CTkLabel(out_frame, text="Filename:", width=60).grid(
            row=1, column=0, padx=(8, 4), pady=(0, 8)
        )
        self.template_var = tk.StringVar(
            value=config.get("filename_template", "%(title)s.%(ext)s")
        )
        ctk.CTkEntry(out_frame, textvariable=self.template_var).grid(
            row=1, column=1, padx=4, pady=(0, 8), sticky="ew"
        )
        ctk.CTkLabel(
            out_frame,
            text="%(title)s  %(uploader)s  %(upload_date)s  %(ext)s",
            font=ctk.CTkFont(size=10),
            text_color=("gray50", "gray60"),
        ).grid(row=1, column=2, columnspan=2, padx=(4, 8), pady=(0, 8), sticky="w")

        # Queue panel
        self.queue_panel = QueuePanel(self, self._queue, self._manager)
        self.queue_panel.grid(row=3, column=0, sticky="nsew", padx=8, pady=4)

        # Status bar
        status_frame = ctk.CTkFrame(self, height=36)
        status_frame.grid(row=4, column=0, sticky="ew", padx=8, pady=(0, 8))
        status_frame.grid_columnconfigure(0, weight=1)
        status_frame.grid_propagate(False)

        self.status_var = tk.StringVar(value="Ready")
        ctk.CTkLabel(status_frame, textvariable=self.status_var, anchor="w").grid(
            row=0, column=0, padx=12, sticky="w"
        )

        settings_btn = ctk.CTkButton(
            status_frame, text="⚙  Settings", width=100, command=self._open_settings
        )
        settings_btn.grid(row=0, column=1, padx=8, pady=4)
        Tooltip(settings_btn, "Open settings (Ctrl+,)")

    # ------------------------------------------------------------------
    # Keyboard shortcuts
    # ------------------------------------------------------------------

    def _bind_shortcuts(self) -> None:
        self.bind("<Control-v>", lambda _e: self.url_bar._paste_and_fetch())
        self.bind("<Control-d>", lambda _e: self._download_current())
        self.bind("<Control-comma>", lambda _e: self._open_settings())
        self.bind("<Escape>", lambda _e: self._on_fetch_cancel())

    # ------------------------------------------------------------------
    # Metadata fetch
    # ------------------------------------------------------------------

    def _on_fetch(self, url: str) -> None:
        self._fetch_cancel.clear()
        self.url_bar.set_loading(True)
        self.preview.clear()
        self._metadata = None
        logger.info(f"Fetching metadata for: {url}")
        fetch_metadata(
            url,
            on_success=lambda meta: self.after(0, lambda: self._fetch_success(meta)),
            on_error=lambda msg: self.after(0, lambda: self._fetch_error(msg)),
            cancel_event=self._fetch_cancel,
        )

    def _on_fetch_cancel(self) -> None:
        self._fetch_cancel.set()
        self.url_bar.set_loading(False)

    def _fetch_success(self, meta: VideoMetadata) -> None:
        self.url_bar.set_loading(False)
        self._metadata = meta
        if meta.is_playlist:
            self.preview.title_var.set(meta.playlist_title[:70])
            self.preview.channel_var.set(f"{len(meta.playlist_entries)} videos in playlist")
            self.preview.duration_var.set("Playlist")
            _PlaylistDialog(self, meta, on_confirm=self._add_playlist_items)
        else:
            self.preview.update_metadata(meta)

    def _fetch_error(self, msg: str) -> None:
        self.url_bar.set_loading(False)
        self.url_bar.show_error(msg)
        logger.warning(f"Fetch error: {msg}")

    # ------------------------------------------------------------------
    # Download
    # ------------------------------------------------------------------

    def _download_current(self) -> None:
        if not self._metadata:
            self.status_var.set("Fetch a video URL first.")
            return

        if self._metadata.is_playlist:
            _PlaylistDialog(self, self._metadata, on_confirm=self._add_playlist_items)
            return

        self._enqueue_single(self._metadata)

    def _enqueue_single(self, meta: VideoMetadata) -> None:
        settings = self.preview.get_settings()
        out_dir = self.output_var.get().strip() or str(Path.home() / "Downloads")
        template = self.template_var.get().strip() or "%(title)s.%(ext)s"

        config.set("output_dir", out_dir)
        config.set("filename_template", template)
        config.save()

        item = DownloadItem(
            url=meta.url,
            title=meta.title,
            mode=settings["mode"],
            quality=settings["quality"],
            audio_format=settings["audio_format"],
            audio_bitrate=settings["audio_bitrate"],
            video_format=settings["video_format"],
            output_dir=out_dir,
            filename_template=template,
        )
        self._queue.add(item)
        self._manager.start_item(
            item, on_update=lambda: self.after(0, self.queue_panel.refresh)
        )

    def _add_playlist_items(self, selected: list) -> None:
        settings = self.preview.get_settings()
        out_dir = self.output_var.get().strip() or str(Path.home() / "Downloads")
        template = self.template_var.get().strip() or "%(title)s.%(ext)s"

        config.set("output_dir", out_dir)
        config.set("filename_template", template)
        config.save()

        for url, entry in selected:
            item = DownloadItem(
                url=url,
                title=entry.title,
                mode=settings["mode"],
                quality=settings["quality"],
                audio_format=settings["audio_format"],
                audio_bitrate=settings["audio_bitrate"],
                video_format=settings["video_format"],
                output_dir=out_dir,
                filename_template=template,
            )
            self._queue.add(item)

        # Start up to max_concurrent downloads
        self._manager.start_all_pending(
            on_update=lambda: self.after(0, self.queue_panel.refresh)
        )

    # ------------------------------------------------------------------
    # Output folder
    # ------------------------------------------------------------------

    def _browse_output(self) -> None:
        path = filedialog.askdirectory(
            title="Select Output Folder",
            initialdir=self.output_var.get(),
        )
        if path:
            self.output_var.set(path)
            config.set("output_dir", path)
            config.save()

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    def _open_settings(self) -> None:
        SettingsDialog(self, on_save=self._on_settings_saved)

    def _on_settings_saved(self) -> None:
        ctk.set_appearance_mode(config.get("theme", "System"))

    # ------------------------------------------------------------------
    # First-run / startup checks
    # ------------------------------------------------------------------

    def _check_first_run(self) -> None:
        if not config.get("disclaimer_shown", False):
            messagebox.showinfo(
                "Important Notice",
                "This tool is for downloading content you have the right to download.\n"
                "Respect YouTube's Terms of Service and copyright law.",
            )
            config.set("disclaimer_shown", True)
            config.save()

    def _check_ffmpeg_warning(self) -> None:
        ok, _ = check_ffmpeg()
        if not ok:
            self.after(
                800,
                lambda: messagebox.showwarning(
                    "ffmpeg Not Found",
                    "ffmpeg was not found on your system.\n\n"
                    "High-quality video downloads (1080p+) and audio extraction\n"
                    "require ffmpeg for merging streams.\n\n"
                    f"Install ffmpeg: {FFMPEG_INSTALL_URL}\n"
                    "Then set the path in Settings if needed.",
                ),
            )

    # ------------------------------------------------------------------
    # Status bar
    # ------------------------------------------------------------------

    def _schedule_status_update(self) -> None:
        self.status_var.set(self.queue_panel.status_text())
        self.after(1000, self._schedule_status_update)

    # ------------------------------------------------------------------
    # Close
    # ------------------------------------------------------------------

    def _on_close(self) -> None:
        config.set("window_geometry", self.geometry())
        config.save()
        self.destroy()
