import io
import threading
import tkinter as tk
from typing import Optional

import customtkinter as ctk
import requests
from PIL import Image

from app.core.metadata import VideoMetadata
from app.utils.logger import logger


class PreviewPanel(ctk.CTkFrame):
    def __init__(self, parent: tk.Widget, **kwargs) -> None:
        super().__init__(parent, **kwargs)
        self._metadata: Optional[VideoMetadata] = None
        self._thumb_ref = None  # keep reference so GC doesn't collect it
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.grid_columnconfigure(2, weight=1)

        # ── Thumbnail ──────────────────────────────────────────────────
        self.thumb_label = ctk.CTkLabel(
            self,
            text="No Preview",
            width=160,
            height=90,
            fg_color=("gray85", "gray25"),
        )
        self.thumb_label.grid(row=0, column=0, rowspan=5, padx=(8, 12), pady=8, sticky="nw")

        # ── Metadata labels ────────────────────────────────────────────
        self.title_var = tk.StringVar(value="—")
        self.channel_var = tk.StringVar(value="—")
        self.duration_var = tk.StringVar(value="—")

        for row_idx, (label, var) in enumerate(
            [("Title:", self.title_var), ("Channel:", self.channel_var), ("Duration:", self.duration_var)]
        ):
            ctk.CTkLabel(self, text=label, width=70, anchor="w").grid(
                row=row_idx, column=1, padx=(4, 0), pady=2, sticky="w"
            )
            ctk.CTkLabel(self, textvariable=var, anchor="w", wraplength=360).grid(
                row=row_idx, column=2, padx=(4, 8), pady=2, sticky="w"
            )

        # ── Mode selector ──────────────────────────────────────────────
        mode_row = 3
        mode_frame = ctk.CTkFrame(self, fg_color="transparent")
        mode_frame.grid(row=mode_row, column=1, columnspan=2, padx=4, pady=(6, 2), sticky="w")

        ctk.CTkLabel(mode_frame, text="Mode:", width=70).pack(side="left")
        self.mode_var = tk.StringVar(value="video")
        ctk.CTkRadioButton(
            mode_frame, text="Video", variable=self.mode_var, value="video",
            command=self._on_mode_change,
        ).pack(side="left", padx=4)
        ctk.CTkRadioButton(
            mode_frame, text="Audio Only", variable=self.mode_var, value="audio",
            command=self._on_mode_change,
        ).pack(side="left", padx=4)

        # ── Options row (shared row — one frame visible at a time) ─────
        opts_row = 4

        # Video options
        self.video_opts = ctk.CTkFrame(self, fg_color="transparent")
        self.video_opts.grid(row=opts_row, column=1, columnspan=2, padx=4, pady=(2, 8), sticky="w")

        ctk.CTkLabel(self.video_opts, text="Quality:", width=70).pack(side="left")
        self.quality_var = tk.StringVar(value="Best")
        self.quality_menu = ctk.CTkOptionMenu(
            self.video_opts, variable=self.quality_var, values=["Best"], width=110
        )
        self.quality_menu.pack(side="left", padx=4)

        ctk.CTkLabel(self.video_opts, text="Format:").pack(side="left", padx=(12, 0))
        self.video_fmt_var = tk.StringVar(value="mp4")
        ctk.CTkOptionMenu(
            self.video_opts, variable=self.video_fmt_var, values=["mp4", "mkv"], width=80
        ).pack(side="left", padx=4)

        # Audio options (hidden initially)
        self.audio_opts = ctk.CTkFrame(self, fg_color="transparent")
        self.audio_opts.grid(row=opts_row, column=1, columnspan=2, padx=4, pady=(2, 8), sticky="w")
        self.audio_opts.grid_remove()

        ctk.CTkLabel(self.audio_opts, text="Format:", width=70).pack(side="left")
        self.audio_fmt_var = tk.StringVar(value="mp3")
        ctk.CTkOptionMenu(
            self.audio_opts, variable=self.audio_fmt_var,
            values=["mp3", "m4a", "ogg", "wav"], width=90,
        ).pack(side="left", padx=4)

        ctk.CTkLabel(self.audio_opts, text="Bitrate:").pack(side="left", padx=(12, 0))
        self.bitrate_var = tk.StringVar(value="192")
        ctk.CTkOptionMenu(
            self.audio_opts, variable=self.bitrate_var,
            values=["320", "256", "192", "128"], width=90,
        ).pack(side="left", padx=4)
        ctk.CTkLabel(self.audio_opts, text="kbps").pack(side="left", padx=(2, 0))

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def update_metadata(self, meta: VideoMetadata) -> None:
        self._metadata = meta

        title = meta.title
        if len(title) > 70:
            title = title[:67] + "…"
        self.title_var.set(title)
        self.channel_var.set(meta.channel or "—")
        self.duration_var.set(meta.duration_str)

        if meta.formats:
            resolutions = ["Best"] + [f.resolution for f in meta.formats]
            self.quality_menu.configure(values=resolutions)
        else:
            self.quality_menu.configure(values=["Best"])
        self.quality_var.set("Best")

        if meta.thumbnail_url:
            threading.Thread(
                target=self._load_thumbnail,
                args=(meta.thumbnail_url,),
                daemon=True,
            ).start()

    def clear(self) -> None:
        self._metadata = None
        self.title_var.set("—")
        self.channel_var.set("—")
        self.duration_var.set("—")
        self.thumb_label.configure(image=None, text="No Preview")
        self._thumb_ref = None
        self.quality_menu.configure(values=["Best"])
        self.quality_var.set("Best")

    def get_metadata(self) -> Optional[VideoMetadata]:
        return self._metadata

    def get_settings(self) -> dict:
        quality = self.quality_var.get()
        if quality.lower() == "best":
            quality = "best"
        return {
            "mode": self.mode_var.get(),
            "quality": quality,
            "audio_format": self.audio_fmt_var.get(),
            "audio_bitrate": self.bitrate_var.get(),
            "video_format": self.video_fmt_var.get(),
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _on_mode_change(self) -> None:
        if self.mode_var.get() == "video":
            self.audio_opts.grid_remove()
            self.video_opts.grid()
        else:
            self.video_opts.grid_remove()
            self.audio_opts.grid()

    def _load_thumbnail(self, url: str) -> None:
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            img = Image.open(io.BytesIO(resp.content))
            img = img.resize((160, 90), Image.LANCZOS)
            ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(160, 90))
            # Schedule GUI update on main thread
            self.after(0, lambda: self._apply_thumbnail(ctk_img))
        except Exception as e:
            logger.warning(f"Failed to load thumbnail: {e}")

    def _apply_thumbnail(self, ctk_img) -> None:
        self._thumb_ref = ctk_img
        self.thumb_label.configure(image=ctk_img, text="")
