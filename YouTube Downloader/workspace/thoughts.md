

## 1. Technology Stack

| Layer | Technology | Notes |
|---|---|---|
| Language | Python 3.11+ | |
| GUI Framework | `tkinter` (stdlib) or `customtkinter` | Prefer `customtkinter` for modern look |
| Download Backend | `yt-dlp` | Actively maintained `youtube-dl` fork |
| Audio Processing | `ffmpeg` (system binary) + `ffmpeg-python` | Required for audio extraction and merging |
| Packaging | `PyInstaller` | Produce single-file executables |

---


## 8. Acceptance Criteria

- [ ] Pasting a valid YouTube URL fetches and displays correct metadata within 5 s
- [ ] A 1080p video downloads successfully as MP4 with merged audio
- [ ] An audio-only download produces a valid 192 kbps MP3 with embedded thumbnail
- [ ] A playlist URL shows a selectable list and downloads checked items sequentially
- [ ] Cancelling a download mid-way deletes the partial file
- [ ] Settings persist after application restart
- [ ] Application does not crash on network loss; shows error and allows retry
- [ ] All UI interactions remain responsive during active downloads
- [ ] Application runs without modification on macOS, Windows, and Linux

---
