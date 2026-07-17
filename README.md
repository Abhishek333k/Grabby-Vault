# GrabbyVault

Desktop video downloader for Windows — **no ads**. Free tier + **Pro** (Lemon Squeezy). Optional donations.

## Features

- Multi-site downloads via **yt-dlp** (YouTube, TikTok, Instagram, Facebook, X, Vimeo, Twitch, Reddit, Dailymotion, …)
- Quality presets (720p free · 1080p/4K/Best on Pro) with **ffmpeg** video+audio merge
- Concurrent queue, pause/cancel, SQLite persistence, system tray
- Playwright fallback for stubborn stream sites
- License dialog + Donate link (Lemon Squeezy ready)

## Quick start

```bat
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Put `ffmpeg.exe` and `ffprobe.exe` in `bin\`.

```bat
run.bat
```

Or:

```bat
venv\Scripts\python src\main.py
```

## Test a download (CLI)

```bat
venv\Scripts\python scripts\test_download.py https://youtu.be/aCBO8uFwGNA 1080
```

## Free vs Pro

| | Free | Pro |
|--|------|-----|
| Max quality | 720p | 1080p / 4K / Best |
| Concurrent | 1 | up to 5 |
| Price | $0 | Lemon Squeezy |

**Dev unlock key (testing):** `GV-PRO-DEV-UNLOCK`  
Set in Settings → License, or `config.json` → `"license_key"`.

Replace checkout URLs in `config.json`:

- `lemonsqueezy_checkout_url`
- `lemonsqueezy_donate_url`

## Build installer folder

```bat
build.bat
```

Output: `dist\GrabbyVault\GrabbyVault.exe` — copy `bin\ffmpeg*.exe` beside it if not already copied.

## Project layout

```
src/main.py          entry
src/core/            downloader, queue, license, paths, formats
src/ui/              CustomTkinter window + dialogs
bin/                 ffmpeg (not in git — too large)
downloads/           output
logs/                app + crash logs
config.json          portable settings
```

## Legal

Only download content you have the right to access. Respect site terms of service. GrabbyVault is a personal utility tool.

