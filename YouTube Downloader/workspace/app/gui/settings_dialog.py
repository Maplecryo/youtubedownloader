import tkinter as tk
from tkinter import filedialog
from typing import Callable, Optional

import customtkinter as ctk

from app.core.ffmpeg_utils import FFMPEG_INSTALL_URL, check_ffmpeg
from app.utils.config import config


class SettingsDialog(ctk.CTkToplevel):
    def __init__(
        self,
        parent: tk.Widget,
        on_save: Optional[Callable] = None,
        **kwargs,
    ) -> None:
        super().__init__(parent, **kwargs)
        self.on_save = on_save
        self.title("Settings")
        self.geometry("500x620")
        self.resizable(False, False)
        self.grab_set()
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        scroll = ctk.CTkScrollableFrame(self)
        scroll.grid(row=0, column=0, sticky="nsew", padx=12, pady=(12, 4))
        scroll.grid_columnconfigure(1, weight=1)
        f = scroll

        row = 0

        def section(title: str) -> None:
            nonlocal row
            ctk.CTkLabel(
                f, text=title, font=ctk.CTkFont(weight="bold", size=13), anchor="w"
            ).grid(row=row, column=0, columnspan=2, padx=4, pady=(14, 4), sticky="w")
            row += 1

        def field(label: str) -> tuple[int, int]:
            nonlocal row
            ctk.CTkLabel(f, text=label, anchor="w").grid(
                row=row, column=0, padx=4, pady=4, sticky="w"
            )
            r = row
            row += 1
            return r, 1

        # ── Download ──────────────────────────────────────────────────
        section("Download")

        r, c = field("Max concurrent downloads")
        self.max_var = tk.StringVar(value=str(config.get("max_concurrent", 1)))
        ctk.CTkOptionMenu(f, variable=self.max_var, values=["1", "2", "3", "4", "5"]).grid(
            row=r, column=c, padx=4, pady=4, sticky="w"
        )

        r, c = field("Speed limit (e.g. 5M, blank = unlimited)")
        self.speed_var = tk.StringVar(value=config.get("speed_limit", ""))
        ctk.CTkEntry(f, textvariable=self.speed_var).grid(
            row=r, column=c, padx=4, pady=4, sticky="ew"
        )

        # ── Network ───────────────────────────────────────────────────
        section("Network")

        r, c = field("Proxy URL")
        self.proxy_var = tk.StringVar(value=config.get("proxy_url", ""))
        ctk.CTkEntry(f, textvariable=self.proxy_var).grid(
            row=r, column=c, padx=4, pady=4, sticky="ew"
        )

        r, c = field("Use cookies from browser")
        self.cookies_var = tk.StringVar(value=config.get("use_cookies", "none"))
        ctk.CTkOptionMenu(
            f, variable=self.cookies_var, values=["none", "chrome", "firefox"]
        ).grid(row=r, column=c, padx=4, pady=4, sticky="w")

        # ── ffmpeg ────────────────────────────────────────────────────
        section("ffmpeg")

        r, c = field("ffmpeg binary path")
        ffmpeg_inner = ctk.CTkFrame(f, fg_color="transparent")
        ffmpeg_inner.grid(row=r, column=c, padx=4, pady=4, sticky="ew")
        ffmpeg_inner.grid_columnconfigure(0, weight=1)
        self.ffmpeg_var = tk.StringVar(value=config.get("ffmpeg_path", ""))
        ctk.CTkEntry(ffmpeg_inner, textvariable=self.ffmpeg_var).grid(
            row=0, column=0, sticky="ew"
        )
        ctk.CTkButton(
            ffmpeg_inner, text="Browse", width=70, command=self._browse_ffmpeg
        ).grid(row=0, column=1, padx=(4, 0))

        ok, version = check_ffmpeg()
        status_text = f"✓ {version[:50]}" if ok else f"✗ Not found — {FFMPEG_INSTALL_URL}"
        ctk.CTkLabel(
            f,
            text=status_text,
            text_color="green" if ok else "red",
            wraplength=380,
            anchor="w",
        ).grid(row=row, column=0, columnspan=2, padx=4, pady=(0, 6), sticky="w")
        row += 1

        # ── Metadata & output ─────────────────────────────────────────
        section("Metadata & Output")

        r, c = field("Embed metadata in file")
        self.embed_meta_var = tk.BooleanVar(value=config.get("embed_metadata", True))
        ctk.CTkCheckBox(f, text="", variable=self.embed_meta_var).grid(
            row=r, column=c, padx=4, pady=4, sticky="w"
        )

        r, c = field("Embed thumbnail (MP3/M4A)")
        self.embed_thumb_var = tk.BooleanVar(value=config.get("embed_thumbnail", True))
        ctk.CTkCheckBox(f, text="", variable=self.embed_thumb_var).grid(
            row=r, column=c, padx=4, pady=4, sticky="w"
        )

        r, c = field("Duplicate file handling")
        self.dup_var = tk.StringVar(value=config.get("duplicate_handling", "auto_rename"))
        ctk.CTkOptionMenu(
            f, variable=self.dup_var, values=["auto_rename", "skip", "overwrite"]
        ).grid(row=r, column=c, padx=4, pady=4, sticky="w")

        r, c = field("Sanitize filenames")
        self.sanitize_var = tk.BooleanVar(value=config.get("sanitize_filenames", True))
        ctk.CTkCheckBox(f, text="", variable=self.sanitize_var).grid(
            row=r, column=c, padx=4, pady=4, sticky="w"
        )

        # ── Video ──────────────────────────────────────────────────────
        section("Video")

        r, c = field("Preferred video codec")
        self.codec_var = tk.StringVar(value=config.get("preferred_video_codec", "any"))
        ctk.CTkOptionMenu(
            f, variable=self.codec_var, values=["any", "h264", "vp9", "av1"]
        ).grid(row=r, column=c, padx=4, pady=4, sticky="w")

        # ── Appearance ─────────────────────────────────────────────────
        section("Appearance")

        r, c = field("Theme")
        self.theme_var = tk.StringVar(value=config.get("theme", "System"))
        ctk.CTkOptionMenu(
            f, variable=self.theme_var, values=["Dark", "Light", "System"]
        ).grid(row=r, column=c, padx=4, pady=4, sticky="w")

        # ── Buttons ────────────────────────────────────────────────────
        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.grid(row=1, column=0, padx=12, pady=(4, 12), sticky="ew")

        ctk.CTkButton(btn_row, text="Save", command=self._save).pack(side="right", padx=4)
        ctk.CTkButton(
            btn_row,
            text="Cancel",
            command=self.destroy,
            fg_color=("gray60", "gray40"),
        ).pack(side="right", padx=4)

    # ------------------------------------------------------------------

    def _browse_ffmpeg(self) -> None:
        path = filedialog.askopenfilename(title="Select ffmpeg binary")
        if path:
            self.ffmpeg_var.set(path)

    def _save(self) -> None:
        config.update(
            {
                "max_concurrent": int(self.max_var.get()),
                "speed_limit": self.speed_var.get().strip(),
                "proxy_url": self.proxy_var.get().strip(),
                "use_cookies": self.cookies_var.get(),
                "ffmpeg_path": self.ffmpeg_var.get().strip(),
                "embed_metadata": self.embed_meta_var.get(),
                "embed_thumbnail": self.embed_thumb_var.get(),
                "duplicate_handling": self.dup_var.get(),
                "sanitize_filenames": self.sanitize_var.get(),
                "preferred_video_codec": self.codec_var.get(),
                "theme": self.theme_var.get(),
            }
        )
        config.save()
        ctk.set_appearance_mode(self.theme_var.get())
        if self.on_save:
            self.on_save()
        self.destroy()
