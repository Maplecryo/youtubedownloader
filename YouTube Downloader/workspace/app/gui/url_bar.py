import tkinter as tk
import customtkinter as ctk

from app.gui.widgets import SpinnerLabel, Tooltip
from app.utils.validators import is_valid_youtube_url


class URLBar(ctk.CTkFrame):
    def __init__(
        self,
        parent: tk.Widget,
        on_fetch,
        on_cancel,
        **kwargs,
    ) -> None:
        super().__init__(parent, **kwargs)
        self.on_fetch = on_fetch
        self.on_cancel = on_cancel
        self._loading = False
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(self, text="URL", width=40).grid(
            row=0, column=0, padx=(8, 4), pady=8
        )

        self.url_var = tk.StringVar()
        self.url_entry = ctk.CTkEntry(
            self,
            textvariable=self.url_var,
            placeholder_text="Paste YouTube URL here…",
        )
        self.url_entry.grid(row=0, column=1, padx=4, pady=8, sticky="ew")
        self.url_entry.bind("<Return>", lambda _e: self._fetch())

        self.error_label = ctk.CTkLabel(
            self, text="", text_color="red", height=16, anchor="w"
        )
        self.error_label.grid(row=1, column=1, padx=4, pady=(0, 4), sticky="w")

        self.paste_btn = ctk.CTkButton(
            self, text="Paste", width=70, command=self._paste_and_fetch
        )
        self.paste_btn.grid(row=0, column=2, padx=4, pady=8)
        Tooltip(self.paste_btn, "Read URL from clipboard and fetch metadata (Ctrl+V)")

        self.fetch_btn = ctk.CTkButton(
            self, text="Fetch", width=70, command=self._fetch_or_cancel
        )
        self.fetch_btn.grid(row=0, column=3, padx=(4, 8), pady=8)
        Tooltip(self.fetch_btn, "Fetch video metadata (Enter)")

        self.spinner = SpinnerLabel(self)
        self.spinner.grid(row=0, column=4, padx=(0, 8), pady=8)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def set_loading(self, loading: bool) -> None:
        self._loading = loading
        if loading:
            self.spinner.start()
            self.fetch_btn.configure(text="Cancel")
            self.paste_btn.configure(state="disabled")
        else:
            self.spinner.stop()
            self.fetch_btn.configure(text="Fetch")
            self.paste_btn.configure(state="normal")

    def show_error(self, msg: str) -> None:
        self.error_label.configure(text=msg)
        border = "red" if msg else ["#979DA2", "#565B5E"]
        self.url_entry.configure(border_color=border)

    def get_url(self) -> str:
        return self.url_var.get().strip()

    def set_url(self, url: str) -> None:
        self.url_var.set(url)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _fetch_or_cancel(self) -> None:
        if self._loading:
            self.on_cancel()
        else:
            self._fetch()

    def _paste_and_fetch(self) -> None:
        try:
            text = self.url_entry.clipboard_get()
            if text:
                self.url_var.set(text.strip())
        except tk.TclError:
            pass
        self._fetch()

    def _fetch(self) -> None:
        url = self.url_var.get().strip()
        if not is_valid_youtube_url(url):
            self.show_error("Please enter a valid YouTube URL.")
            return
        self.show_error("")
        self.on_fetch(url)
