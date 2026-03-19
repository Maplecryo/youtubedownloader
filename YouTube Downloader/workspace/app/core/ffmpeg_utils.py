import shutil
import subprocess
from pathlib import Path

from app.utils.logger import logger


def find_ffmpeg() -> str | None:
    """Return absolute path to ffmpeg binary, or None."""
    # Lazy import to avoid circular deps at module load time
    from app.utils.config import config

    cfg_path = config.get("ffmpeg_path", "")
    if cfg_path and Path(cfg_path).is_file():
        return cfg_path

    found = shutil.which("ffmpeg")
    if found:
        return found

    # Common installation paths
    candidates = [
        "/opt/homebrew/bin/ffmpeg",   # macOS Apple Silicon (Homebrew)
        "/usr/local/bin/ffmpeg",      # macOS Intel (Homebrew)
        "/usr/bin/ffmpeg",            # Linux system package
        r"C:\ffmpeg\bin\ffmpeg.exe",  # Windows manual install
    ]
    for path in candidates:
        if Path(path).is_file():
            return path

    return None


def check_ffmpeg() -> tuple[bool, str]:
    """Returns (available, version_string)."""
    path = find_ffmpeg()
    if not path:
        return False, ""
    try:
        result = subprocess.run(
            [path, "-version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        first_line = result.stdout.split("\n")[0] if result.stdout else ""
        return True, first_line
    except Exception as e:
        logger.warning(f"ffmpeg check failed: {e}")
        return False, ""


FFMPEG_INSTALL_URL = "https://ffmpeg.org/download.html"
