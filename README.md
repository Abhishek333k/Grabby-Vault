# GrabbyVault

**GrabbyVault** is a Windows desktop application for downloading online video and audio to your own drive. Built by [SilenVault](https://store.silenvault.com).

No ads. No account required to run the free tier.

---

## Features

- Paste a link, pick quality, download to a folder of your choice  
- Multi-source support via [yt-dlp](https://github.com/yt-dlp/yt-dlp) (YouTube, TikTok, Instagram, Facebook, X, Vimeo, Twitch, Reddit, Dailymotion, and many others)  
- Reliable video + audio merge with **ffmpeg**  
- Download queue with priority, pause / cancel, and retry  
- Concurrent downloads (Pro)  
- Job history stored locally (SQLite)  
- System tray (minimize without quitting)  
- Optional advanced browser extraction for difficult pages  
- Free and Pro tiers (Pro unlocked with a license key)

---

## Requirements

| Item | Notes |
|------|--------|
| OS | Windows 10 or 11 (64-bit) |
| Python | 3.11+ (development) |
| ffmpeg | `ffmpeg.exe` and `ffprobe.exe` in `bin\` |
| Node.js (optional) | Improves YouTube format discovery for yt-dlp |

---

## Install (development)

```bat
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

1. Create `bin\` in the project root.  
2. Copy **ffmpeg.exe** and **ffprobe.exe** into `bin\`.  
3. Copy `config.example.json` to `config.json` and adjust paths if needed.

```bat
run.bat
```

Or:

```bat
venv\Scripts\python src\main.py
```

---

## Free vs Pro

| | Free | Pro |
|--|------|-----|
| Max quality | 720p | 1080p / 1440p / 4K / Best |
| Concurrent downloads | 1 | Up to 5 |
| License | Not required | Activate a license key in **Pro** |

Activate Pro from the app title bar: **Pro** → paste key → **Activate**.  
One active device seat per license (release or take over from the same dialog).

---

## Configuration

| File | Purpose |
|------|---------|
| `config.example.json` | Template checked into the repository |
| `config.json` | Local settings (not committed; created from the example) |

Useful settings:

- `download_path` — where files are saved  
- `max_concurrent_downloads` — capped by Free / Pro limits  
- `use_acrylic` — window transparency (Windows)  
- `open_folder_on_complete` — open Explorer when a job finishes  
- `store_url` / `support_email` — links shown in About  

---

## Build a release folder

```bat
scripts\smoke_release.bat
build.bat
```

Output: `dist\GrabbyVault\`

Optional installer (Inno Setup 6): compile `installer\grabbyvault.iss` after the build.

Before shipping:

1. Confirm `bin\ffmpeg.exe` and `bin\ffprobe.exe` are present.  
2. Ship a clean `config.json` based on `config.example.json` (no developer unlocks).  
3. Smoke-test activate, download, cancel, and open-folder on a clean machine.  
4. See `docs/RELEASE_CHECKLIST.md`.

---

## CLI quality check

```bat
venv\Scripts\python scripts\test_download.py https://example.com/watch?v=VIDEO 1080
```

Use a URL you are allowed to download. Add `--full` for the entire file (default samples a short segment for long videos).

---

## Project layout

```text
src/main.py           Application entry
src/core/             Download engine, queue, database, license, paths
src/ui/               Main window, dialogs, tray, splash
assets/               Branding
bin/                  ffmpeg / ffprobe (local; not in git)
downloads/            Default output folder
logs/                 App and crash logs
config.example.json   Settings template
run.bat               Dev launcher
build.bat             PyInstaller package
```

---

## Responsible use

Only download media you have the right to access. Follow the terms of each site you use. GrabbyVault is a personal utility; you are responsible for how you use it.

---

## Support

- Store: [store.silenvault.com](https://store.silenvault.com)  
- Issues: use the GitHub repository issue tracker for the project  
- Support email: see `support_email` in your `config.json` / About dialog  

---

## License

Application source in this repository is provided for the GrabbyVault / SilenVault product. Third-party tools (yt-dlp, ffmpeg, and others) remain under their own licenses.
