import re
from urllib.parse import urlparse, parse_qs

_YOUTUBE_PATTERNS = [
    r"^https?://(www\.)?youtube\.com/watch\?.*v=[\w-]+",
    r"^https?://youtu\.be/[\w-]+",
    r"^https?://(www\.)?youtube\.com/playlist\?.*list=[\w-]+",
    r"^https?://(www\.)?youtube\.com/shorts/[\w-]+",
    r"^https?://(www\.)?youtube\.com/@[\w-]+",
]


def is_valid_youtube_url(url: str) -> bool:
    url = url.strip()
    if not url:
        return False
    for pattern in _YOUTUBE_PATTERNS:
        if re.match(pattern, url):
            return True
    return False


def is_playlist_url(url: str) -> bool:
    parsed = urlparse(url.strip())
    params = parse_qs(parsed.query)
    return "list" in params and "v" not in params


def sanitize_filename(filename: str) -> str:
    sanitized = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", filename)
    sanitized = sanitized.rstrip(". ")
    return sanitized or "download"
