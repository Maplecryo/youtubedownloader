"""YouTube Downloader — entry point."""
import sys
from pathlib import Path

# Ensure the workspace directory is on sys.path so imports work whether
# the script is launched from inside or outside the workspace folder.
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))


def main() -> None:
    from app.utils.logger import logger
    logger.info("Starting YouTube Downloader")

    import customtkinter as ctk
    from app.gui.main_window import MainWindow

    app = MainWindow()
    app.mainloop()

    logger.info("YouTube Downloader exited")


if __name__ == "__main__":
    main()
