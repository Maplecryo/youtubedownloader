import tkinter as tk
import customtkinter as ctk


class Tooltip:
    """Simple tooltip that appears on hover."""

    def __init__(self, widget: tk.Widget, text: str) -> None:
        self.widget = widget
        self.text = text
        self._tip: tk.Toplevel | None = None
        widget.bind("<Enter>", self._show)
        widget.bind("<Leave>", self._hide)

    def _show(self, event=None) -> None:
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self._tip = tk.Toplevel(self.widget)
        self._tip.wm_overrideredirect(True)
        self._tip.wm_geometry(f"+{x}+{y}")
        lbl = tk.Label(
            self._tip,
            text=self.text,
            background="#ffffe0",
            relief="solid",
            borderwidth=1,
            font=("TkDefaultFont", 9),
            padx=4,
            pady=2,
            wraplength=300,
        )
        lbl.pack()

    def _hide(self, event=None) -> None:
        if self._tip:
            self._tip.destroy()
            self._tip = None


class SpinnerLabel(ctk.CTkLabel):
    """Animated spinner using braille characters."""

    _FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def __init__(self, parent: tk.Widget, **kwargs) -> None:
        super().__init__(parent, text="", width=20, **kwargs)
        self._idx = 0
        self._running = False
        self._job: str | None = None

    def start(self) -> None:
        self._running = True
        self._tick()

    def stop(self) -> None:
        self._running = False
        if self._job:
            self.after_cancel(self._job)
            self._job = None
        self.configure(text="")

    def _tick(self) -> None:
        if not self._running:
            return
        self.configure(text=self._FRAMES[self._idx % len(self._FRAMES)])
        self._idx += 1
        self._job = self.after(100, self._tick)
