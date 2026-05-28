import tkinter as tk
import customtkinter as ctk


class Tooltip:
    def __init__(self, widget: tk.Widget, text: str) -> None:
        pass


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
