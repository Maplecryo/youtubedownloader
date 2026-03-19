import platform
import subprocess
import tkinter as tk
from typing import Callable

import customtkinter as ctk

from app.core.downloader import DownloadManager
from app.core.queue import DownloadItem, DownloadQueue, DownloadStatus
from app.gui.widgets import Tooltip


_STATUS_ICON = {
    DownloadStatus.PENDING: "⏳",
    DownloadStatus.FETCHING: "🔍",
    DownloadStatus.DOWNLOADING: "↓",
    DownloadStatus.POST_PROCESSING: "⚙",
    DownloadStatus.COMPLETE: "✓",
    DownloadStatus.FAILED: "✗",
    DownloadStatus.CANCELLED: "⊘",
}

_TERMINAL = {DownloadStatus.COMPLETE, DownloadStatus.FAILED, DownloadStatus.CANCELLED}


class _QueueItemWidget(ctk.CTkFrame):
    def __init__(
        self,
        parent: tk.Widget,
        item: DownloadItem,
        on_cancel: Callable,
        on_remove: Callable,
        on_open_folder: Callable,
        **kwargs,
    ) -> None:
        super().__init__(parent, **kwargs)
        self.item = item
        self._on_cancel = on_cancel
        self._on_remove = on_remove
        self._on_open_folder = on_open_folder
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.grid_columnconfigure(1, weight=1)

        # Status icon
        self.icon_lbl = ctk.CTkLabel(self, text="⏳", width=28, font=ctk.CTkFont(size=14))
        self.icon_lbl.grid(row=0, column=0, rowspan=2, padx=(8, 4), pady=6, sticky="n")

        # Content
        content = ctk.CTkFrame(self, fg_color="transparent")
        content.grid(row=0, column=1, padx=4, pady=(6, 0), sticky="ew")
        content.grid_columnconfigure(0, weight=1)

        self.title_lbl = ctk.CTkLabel(
            content,
            text=self._truncate_title(),
            anchor="w",
            font=ctk.CTkFont(weight="bold"),
        )
        self.title_lbl.grid(row=0, column=0, sticky="ew")

        self.progress_bar = ctk.CTkProgressBar(content, height=10)
        self.progress_bar.set(0)
        self.progress_bar.grid(row=1, column=0, sticky="ew", pady=(3, 2))

        self.stat_lbl = ctk.CTkLabel(
            content, text="Pending…", anchor="w", font=ctk.CTkFont(size=11)
        )
        self.stat_lbl.grid(row=2, column=0, sticky="w")

        self.size_lbl = ctk.CTkLabel(
            content,
            text="",
            anchor="w",
            font=ctk.CTkFont(size=11),
            text_color="gray",
        )
        self.size_lbl.grid(row=3, column=0, sticky="w", pady=(0, 4))

        # Buttons
        btn_col = ctk.CTkFrame(self, fg_color="transparent")
        btn_col.grid(row=0, column=2, padx=8, pady=6, sticky="ne")

        self.action_btn = ctk.CTkButton(btn_col, text="Remove", width=80, command=self._action)
        self.action_btn.pack()

        self.folder_btn = ctk.CTkButton(
            btn_col,
            text="Open Folder",
            width=90,
            fg_color="transparent",
            text_color=("RoyalBlue3", "light blue"),
            hover=False,
            command=self._open_folder,
        )
        # shown only when complete

    # ------------------------------------------------------------------

    def refresh(self, item: DownloadItem) -> None:
        self.item = item
        self.title_lbl.configure(text=self._truncate_title())
        self.icon_lbl.configure(text=_STATUS_ICON.get(item.status, "?"))

        s = item.status

        if s == DownloadStatus.PENDING:
            self.progress_bar.set(0)
            self.stat_lbl.configure(text="Pending…", text_color=("gray40", "gray70"))
            self.size_lbl.configure(text="")
            self.action_btn.configure(text="Remove")
            self.folder_btn.pack_forget()

        elif s == DownloadStatus.FETCHING:
            self.progress_bar.set(0)
            self.stat_lbl.configure(text="Fetching metadata…", text_color=("gray40", "gray70"))
            self.size_lbl.configure(text="")
            self.action_btn.configure(text="Cancel")
            self.folder_btn.pack_forget()

        elif s == DownloadStatus.DOWNLOADING:
            self.progress_bar.set(item.progress / 100)
            parts = []
            if item.progress:
                parts.append(f"{item.progress:.1f}%")
            if item.speed:
                parts.append(item.speed)
            if item.eta:
                parts.append(f"ETA: {item.eta}")
            self.stat_lbl.configure(
                text="  ".join(parts) or "Downloading…",
                text_color=("gray10", "gray90"),
            )
            if item.downloaded and item.total_size:
                self.size_lbl.configure(text=f"{item.downloaded} / {item.total_size}")
            self.action_btn.configure(text="Cancel")
            self.folder_btn.pack_forget()

        elif s == DownloadStatus.POST_PROCESSING:
            self.progress_bar.set(1.0)
            self.stat_lbl.configure(text="Post-processing…", text_color=("gray40", "gray70"))
            self.action_btn.configure(text="Cancel")
            self.folder_btn.pack_forget()

        elif s == DownloadStatus.COMPLETE:
            self.progress_bar.set(1.0)
            self.stat_lbl.configure(text="Complete ✓", text_color="green")
            self.size_lbl.configure(text=item.output_path or "")
            self.action_btn.configure(text="Remove")
            if item.output_path:
                self.folder_btn.pack(pady=(4, 0))

        elif s == DownloadStatus.FAILED:
            self.progress_bar.set(0)
            err = (item.error or "Unknown error")[:80]
            self.stat_lbl.configure(text=f"Failed: {err}", text_color="red")
            self.size_lbl.configure(text="")
            self.action_btn.configure(text="Remove")
            self.folder_btn.pack_forget()

        elif s == DownloadStatus.CANCELLED:
            self.progress_bar.set(0)
            self.stat_lbl.configure(text="Cancelled", text_color=("gray50", "gray60"))
            self.size_lbl.configure(text="")
            self.action_btn.configure(text="Remove")
            self.folder_btn.pack_forget()

    def _truncate_title(self) -> str:
        title = self.item.title or self.item.url
        return title[:65] + "…" if len(title) > 65 else title

    def _action(self) -> None:
        s = self.item.status
        if s in _TERMINAL or s == DownloadStatus.PENDING:
            self._on_remove(self.item.id)
        else:
            self._on_cancel(self.item.id)

    def _open_folder(self) -> None:
        self._on_open_folder(self.item.output_path)


class QueuePanel(ctk.CTkFrame):
    def __init__(
        self,
        parent: tk.Widget,
        queue: DownloadQueue,
        manager: DownloadManager,
        **kwargs,
    ) -> None:
        super().__init__(parent, **kwargs)
        self._queue = queue
        self._manager = manager
        self._widgets: dict[str, _QueueItemWidget] = {}
        self._setup_ui()
        queue.add_listener(lambda: self.after(0, self.refresh))

    def _setup_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header = ctk.CTkLabel(
            self, text="QUEUE", font=ctk.CTkFont(weight="bold", size=12), anchor="w"
        )
        header.grid(row=0, column=0, padx=12, pady=(8, 2), sticky="w")

        self.scroll = ctk.CTkScrollableFrame(self)
        self.scroll.grid(row=1, column=0, sticky="nsew", padx=8, pady=4)
        self.scroll.grid_columnconfigure(0, weight=1)

        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.grid(row=2, column=0, sticky="ew", padx=8, pady=(0, 8))

        self.dl_all_btn = ctk.CTkButton(btns, text="Download All", command=self._download_all)
        self.dl_all_btn.pack(side="left", padx=4)
        Tooltip(self.dl_all_btn, "Start downloading all pending items (Ctrl+D)")

        self.cancel_all_btn = ctk.CTkButton(
            btns, text="Cancel All", command=self._cancel_all,
            fg_color=("gray60", "gray40"), hover_color=("gray50", "gray30"),
        )
        self.cancel_all_btn.pack(side="left", padx=4)

        self.clear_btn = ctk.CTkButton(
            btns,
            text="Clear Completed",
            command=self._clear_completed,
            fg_color="transparent",
            text_color=("gray30", "gray70"),
            hover_color=("gray85", "gray25"),
        )
        self.clear_btn.pack(side="right", padx=4)

    # ------------------------------------------------------------------

    def refresh(self) -> None:
        items = self._queue.all()
        present_ids = {i.id for i in items}

        # Remove stale widgets
        for wid in list(self._widgets):
            if wid not in present_ids:
                self._widgets[wid].destroy()
                del self._widgets[wid]

        for row_idx, item in enumerate(items):
            if item.id not in self._widgets:
                w = _QueueItemWidget(
                    self.scroll,
                    item,
                    on_cancel=self._cancel_item,
                    on_remove=self._remove_item,
                    on_open_folder=self._open_folder,
                )
                w.grid(row=row_idx, column=0, sticky="ew", padx=4, pady=3)
                self._widgets[item.id] = w
            else:
                w = self._widgets[item.id]
                w.grid(row=row_idx, column=0, sticky="ew", padx=4, pady=3)
                w.refresh(item)

    def status_text(self) -> str:
        items = self._queue.all()
        if not items:
            return "Ready"
        downloading = sum(1 for i in items if i.status == DownloadStatus.DOWNLOADING)
        pending = sum(1 for i in items if i.status == DownloadStatus.PENDING)
        complete = sum(1 for i in items if i.status == DownloadStatus.COMPLETE)
        parts = []
        if downloading:
            parts.append(f"{downloading} downloading")
        if pending:
            parts.append(f"{pending} pending")
        if complete:
            parts.append(f"{complete} complete")
        return "Ready · " + " · ".join(parts) if parts else "Ready"

    # ------------------------------------------------------------------

    def _download_all(self) -> None:
        self._manager.start_all_pending(
            on_update=lambda: self.after(0, self.refresh)
        )

    def _cancel_all(self) -> None:
        self._manager.cancel_all()

    def _clear_completed(self) -> None:
        self._queue.clear_completed()

    def _cancel_item(self, item_id: str) -> None:
        self._manager.cancel_item(item_id)

    def _remove_item(self, item_id: str) -> None:
        self._queue.remove(item_id)

    def _open_folder(self, path: str) -> None:
        try:
            system = platform.system()
            if system == "Darwin":
                subprocess.run(["open", path], check=False)
            elif system == "Windows":
                subprocess.run(["explorer", path], check=False)
            else:
                subprocess.run(["xdg-open", path], check=False)
        except Exception as e:
            from app.utils.logger import logger
            logger.warning(f"Could not open folder '{path}': {e}")
