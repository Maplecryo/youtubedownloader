# YouTube Downloader — GUI Application Requirements

## Project Overview

Build a cross-platform desktop GUI application in Python that allows users to download
video or audio content from YouTube.com. The application must be intuitive enough for
non-technical users while providing enough control for power users.

---

## 1. Technology Stack

| Layer | Technology | Notes |
|---|---|---|
| Language | Python 3.11+ | |
| GUI Framework | `tkinter` (stdlib) or `customtkinter` | Prefer `customtkinter` for modern look |
| Download Backend | `yt-dlp` | Actively maintained `youtube-dl` fork |
| Audio Processing | `ffmpeg` (system binary) + `ffmpeg-python` | Required for audio extraction and merging |
| Packaging | `PyInstaller` | Produce single-file executables |

---

## 2. Functional Requirements

### 2.1 URL Input

- Single text field accepting any valid YouTube URL:
  - Standard watch URLs (`https://www.youtube.com/watch?v=...`)
  - Shortened URLs (`https://youtu.be/...`)
  - Playlist URLs (`https://www.youtube.com/playlist?list=...`)
- "Paste" button that reads from clipboard automatically
- URL validation with inline error message before fetching metadata
- Support for up to 10 queued URLs simultaneously

### 2.2 Metadata Fetch

- On URL submission, fetch and display without starting download:
  - Video title
  - Channel name
  - Duration (formatted `HH:MM:SS`)
  - Thumbnail image (displayed at 160×90 px minimum)
  - Available format list
- Fetch must be non-blocking (run in background thread)
- Show a loading spinner during fetch
- Display a clear error if the video is unavailable, private, or region-locked

### 2.3 Download Modes

#### Video Download
- Let the user choose a video quality from a dropdown populated by fetched formats:
  - Best available (default)
  - 1080p, 720p, 480p, 360p (only show resolutions the video actually has)
- Video container: MP4 (preferred), MKV fallback when MP4 mux is unavailable
- Merge separate video+audio streams via ffmpeg when needed (common for 1080p+)

#### Audio-Only Download
- Toggle to switch to audio-only mode
- Output format selector: MP3, M4A, OGG, WAV
- Bitrate selector: 320 kbps, 256 kbps, 192 kbps, 128 kbps (default 192)
- Strip video stream completely; embed thumbnail as album art for MP3/M4A

### 2.4 Output Settings

- Output directory picker (opens native OS folder dialog)
- Remember last-used directory across sessions (persist in config file)
- Filename template field with variable hints:
  - `%(title)s` — video title
  - `%(uploader)s` — channel name
  - `%(upload_date)s` — upload date (YYYYMMDD)
  - Default template: `%(title)s.%(ext)s`
- Option to automatically sanitize filenames (remove illegal characters)
- Duplicate file handling: Skip, Overwrite, or Auto-rename

### 2.5 Download Queue & Progress

- Queue panel listing all added downloads with individual status:
  - Pending, Fetching Metadata, Downloading, Post-processing, Complete, Failed
- Per-item progress bar showing:
  - Percentage complete
  - Download speed (e.g. `3.2 MB/s`)
  - ETA (e.g. `~0:42 remaining`)
  - File size (downloaded / total)
- Global progress bar when multiple items are in queue
- "Download All" and "Download Selected" buttons
- "Cancel" button per item and a "Cancel All" button
- Completed items show the output file path with a clickable "Open Folder" link

### 2.6 Playlist Support

- When a playlist URL is detected:
  - Fetch playlist metadata (title, item count)
  - Show a checklist of all videos in the playlist
  - "Select All" / "Deselect All" controls
  - User selects which items to download before starting
- Apply the same video/audio mode and quality settings to all selected items
- Download playlist items sequentially (one at a time) to avoid rate-limiting

### 2.7 Settings Panel

Accessible via a Settings button or menu. Settings persist to a JSON config file.

| Setting | Type | Default |
|---|---|---|
| Max concurrent downloads | Integer (1–5) | 1 |
| Speed limit | String (e.g. `5M`, blank = unlimited) | Blank |
| Proxy URL | String | Blank |
| ffmpeg binary path | File path | Auto-detect |
| Use cookies from browser | Dropdown (Chrome, Firefox, None) | None |
| Embed metadata in file | Boolean | True |
| Embed thumbnail | Boolean | True (MP3/M4A only) |
| Preferred video codec | Dropdown (any, h264, vp9, av1) | any |
| Theme | Dropdown (Dark, Light, System) | System |

---

## 3. Non-Functional Requirements

### 3.1 Performance
- Metadata fetch must complete within 5 seconds on a standard broadband connection
- UI must remain responsive at all times; all network and disk I/O runs in daemon threads
- Application launch time must be under 3 seconds on a modern machine

### 3.2 Reliability
- Any download error must be caught, logged, and displayed to the user without crashing the app
- Network interruptions must trigger an automatic retry (up to 3 attempts with exponential back-off)
- Log all errors with timestamps to `~/YouTube Downloader/logs/app.log` (rotating, max 5 MB)

### 3.3 Usability
- All interactive elements must have descriptive tooltips
- Keyboard shortcuts:
  - `Ctrl+V` — paste URL and auto-fetch
  - `Ctrl+D` — start download
  - `Ctrl+,` — open settings
  - `Escape` — cancel current fetch
- Status bar at the bottom showing overall queue state
- Application remembers window size and position between sessions

### 3.4 Compatibility
- Must run on: macOS 12+, Windows 10+, Ubuntu 22.04+
- Python 3.11+ required; no C extensions that require compilation by the end user
- ffmpeg must be bundled or clearly directed by the installer; app must detect absence and guide user

### 3.5 Security & Legal
- Application must display a one-time disclaimer on first launch:
  > "This tool is for downloading content you have the right to download.
  >  Respect YouTube's Terms of Service and copyright law."
- No credentials are stored in plaintext; cookie-based auth uses browser's own encrypted store
- No telemetry, analytics, or network calls other than to YouTube and its CDNs

---

## 4. Application Layout

```
┌─────────────────────────────────────────────────────────────────┐
│  YouTube Downloader                              [─] [□] [✕]   │
├─────────────────────────────────────────────────────────────────┤
│  URL  [ paste URL here...                    ] [Paste] [Fetch]  │
├────────────────┬────────────────────────────────────────────────┤
│                │  Title:    My Video Title                       │
│  [Thumbnail]   │  Channel:  Channel Name                        │
│  160 × 90      │  Duration: 12:34                               │
│                │  Mode: ◉ Video  ○ Audio                        │
│                │  Quality: [1080p ▼]   Format: [MP4 ▼]          │
└────────────────┴────────────────────────────────────────────────┤
│  Output: [/Users/admin/Downloads          ] [Browse] [Download] │
├─────────────────────────────────────────────────────────────────┤
│  QUEUE                                                           │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ ✓  My Video Title          [████████░░] 78%  2.1 MB/s   │   │
│  │    ETA: 0:18   124 MB / 159 MB          [Cancel]        │   │
│  ├─────────────────────────────────────────────────────────┤   │
│  │ ⏳  Another Video           Pending...          [Remove] │   │
│  └─────────────────────────────────────────────────────────┘   │
│  [Download All]  [Cancel All]              [Clear Completed]    │
├─────────────────────────────────────────────────────────────────┤
│  Ready · 1 downloading · 1 pending                  [Settings] │
└─────────────────────────────────────────────────────────────────┘
```

---

## 5. File & Folder Structure

```
YouTube Downloader/
├── workspace/
│   ├── REQUIREMENTS.md          ← this file
│   ├── main.py                  ← entry point, launches GUI
│   ├── app/
│   │   ├── __init__.py
│   │   ├── gui/
│   │   │   ├── main_window.py   ← root window, layout manager
│   │   │   ├── url_bar.py       ← URL input + fetch controls
│   │   │   ├── preview_panel.py ← thumbnail + metadata display
│   │   │   ├── queue_panel.py   ← download list + progress bars
│   │   │   ├── settings_dialog.py
│   │   │   └── widgets.py       ← reusable custom widgets
│   │   ├── core/
│   │   │   ├── downloader.py    ← yt-dlp wrapper, threading
│   │   │   ├── metadata.py      ← fetch & parse video metadata
│   │   │   ├── queue.py         ← download queue manager
│   │   │   └── ffmpeg_utils.py  ← ffmpeg detection & invocation
│   │   └── utils/
│   │       ├── config.py        ← read/write settings JSON
│   │       ├── logger.py        ← rotating log setup
│   │       └── validators.py    ← URL and filename validation
│   ├── assets/
│   │   ├── icon.png
│   │   └── icon.ico
│   ├── requirements.txt
│   └── build.spec               ← PyInstaller spec file
└── logs/
    └── app.log
```

---

## 6. Python Dependencies (`requirements.txt`)

```
yt-dlp>=2024.1.1
customtkinter>=5.2.2
Pillow>=10.2.0
requests>=2.31.0
ffmpeg-python>=0.2.0
```

> **System dependency:** `ffmpeg` must be installed separately or bundled.
> Provide installation instructions in README for each OS.

---

## 7. Error Handling Matrix

| Scenario | User-Facing Message | Recovery |
|---|---|---|
| Invalid URL | "Please enter a valid YouTube URL." | Highlight field red |
| Video unavailable | "This video is unavailable or private." | Remove from queue |
| No internet | "No internet connection detected." | Retry button |
| ffmpeg missing | "ffmpeg not found. [How to install]" | Link to guide |
| Disk full | "Not enough disk space in output folder." | Prompt to change folder |
| Download rate-limited | "YouTube is rate-limiting requests. Retrying in {n}s…" | Auto-retry × 3 |
| Unknown yt-dlp error | "Download failed: {error}. See log for details." | Show log button |

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
