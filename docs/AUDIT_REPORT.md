# GrabbyVault — Full Repository Audit Report

**Scope:** `O:\Projects\GitHub Repos\GrabbyVault` (application source, scripts, packaging, config)  
**Out of scope (except notes):** `venv/`, `.venv/`, `bin/*.exe`, user `downloads/` media  
**Date:** 2026-07-17  
**Syntax compile check:** `python -m compileall src` → **PASS** (no syntax errors)  
**Auditor lens:** production-readiness for a paid Windows desktop app (SilenVault / Lemon Squeezy)

---

## 0. Executive summary

| Dimension | Grade | One line |
|-----------|-------|----------|
| **What it is today** | C+ / B− | Working Windows yt-dlp downloader MVP with Free/Pro, queue, splash, LS license hooks |
| **What it should be** | — | Stable, shippable installer; reliable pause/cancel; no secret leakage; polished UX |
| **What it could be** | — | Competitive multi-site offline tool with updates, cookies UI, link grabber, Mac later |
| **Ship today?** | **No** (not as “Pro product”) | Blockers: security defaults, broken Open Folder, packaging gaps, pause/cancel reliability |
| **Core idea** | Strong | Desktop download on-user-machine is the right architecture vs web downloader sites |

**Bottom line:** The *engine path* (formats + ffmpeg + yt-dlp + queue) is real and was proven on a 1080p sample. The *product shell* (license, UI, packaging, DB lifecycle, stubs) is incomplete and has several **P0/P1** bugs that will hit paying users immediately.

---

## 1. What is / What should be / What could be

### 1.1 What **is** (current reality)

```
GrabbyVault/
├── src/main.py              Entry + splash + dual Tk roots
├── src/core/                Download, queue, DB, license, paths, formats
├── src/ui/                  CustomTkinter window, dialogs, tray, splash
├── src/models/              EMPTY
├── src/extensions/          EMPTY
├── src/config/              EMPTY
├── assets/                  SilenVault branding
├── bin/                     ffmpeg (gitignored, local only)
├── config.json              Runtime + license state (tracked in git!)
├── queue.db                 Job state (gitignored)
├── scripts/test_download.py CLI quality probe
├── run.bat / build.bat      Dev run + PyInstaller sketch
└── requirements.txt         Deps (no pins / lockfile)
```

**Actually implemented**

- URL paste → metadata fetch (yt-dlp + fallbacks + Playwright)
- Quality presets + Free/Pro clamp
- Priority queue, concurrent workers, SQLite persistence (partial)
- Progress UI via queue → main thread
- License: LS activate/validate/deactivate, machine fingerprint, heartbeat, take-over
- Splash, About/Developer/Donate, Settings health
- System tray hide-on-close

**Stubs / dead weight**

- `plugin_manager.py`, `utils.py` → empty
- `models/`, `extensions/`, `config/` → empty packages
- Thumbnail URL accepted but thumbnails **removed** from cards
- `open_folder_on_complete` in config → **never used**
- `DatabaseManager.get_job` / `filepath` column → **referenced but do not exist**

### 1.2 What **should be** (minimum for a sellable v1)

| Area | Should be |
|------|-----------|
| Packaging | One signed/zipped build; ffmpeg bundled or first-run fetch; no dev keys |
| Config | `config.example.json` in git; real `config.json` gitignored |
| Queue | True pause/cancel (abort yt-dlp); resume; no auto-replay of errors forever |
| DB | Store filepath, full metadata JSON; migrations; close on exit |
| License | `allow_dev_keys: false` in release; product_id allowlist; no keys in repo |
| UI | First-run wizard; readable errors; Open folder works; DPI-safe chrome |
| Quality | Keep current format pipeline; surface actual resolution after download |
| Ops | Crash log UX; auto-update yt-dlp or document update path |
| Tests | Smoke: import, license clamp, format resolve, one mocked download |

### 1.3 What **could be** (roadmap / aspirational)

| Horizon | Ideas |
|---------|--------|
| Near | Cookies.txt import UI; batch URL paste; speed limit; per-host concurrency |
| Medium | Link grabber (JDownloader-style analyze → queue); auto-update channel |
| Far | Mac build; optional companion Android; server-side license session (true multi-device Netflix concurrency without LS limits only) |
| Explicit non-goals | Netflix/DRM streaming; mobile app store “YouTube downloader”; ad-supported web downloader |

---

## 2. Architecture map (as-is)

```
┌─────────────┐     callbacks      ┌──────────────┐
│  MainWindow │ ◄───────────────── │ QueueManager │
│  (Tk main)  │  ui_queue 50ms     │ workers N    │
└──────┬──────┘                    └──────┬───────┘
       │                                  │
       │ LicenseManager (singleton)       ▼
       │ Heartbeat thread            Downloader (yt-dlp)
       │                                  │
       ▼                                  ├── ffmpeg bin/
  Lemon Squeezy API                       ├── JS runtime (node)
  activate/validate                       └── PlaywrightExtractor (visible browser)
       │
       ▼
  config.json  +  queue.db (SQLite)
```

**Strengths:** Clear split UI / queue / downloader; progress marshalled to UI thread; portable `paths.py`.  
**Weaknesses:** Singletons + disk write on every `config.set`; incomplete DB schema; no clean shutdown; dual CTk roots on splash path.

---

## 3. Severity legend

| Sev | Meaning |
|-----|---------|
| **P0** | Breaks core flow / security / data integrity for real users |
| **P1** | Major UX or reliability bug; fix before paid launch |
| **P2** | Medium; fix soon after launch |
| **P3** | Polish / debt / future |

---

## 4. Critical & high findings (detailed)

### P0-01 — Open Folder button calls non-existent API

**Where:** `src/ui/main_window.py` ~527–533  

```python
job_data = self.queue_manager.db.get_job(job_id)  # AttributeError: no get_job
filepath = job_data.get('filepath')  # column never stored
```

**Impact:** Clicking 📁 after complete → **exception**. Feature is dead.  
**Should be:** Persist `filepath` (or folder) from yt-dlp post-hook / `prepare_filename`; add `get_job()`.

---

### P0-02 — Secrets & Pro unlock defaults shippable to customers

**Where:** `config.json` (tracked), `license_manager.py` `allow_dev_keys` default **True**, `DEV_PRO_KEYS`, optional `pro_unlocked`

**Impact:**

- Repo can contain license keys / machine state  
- Anyone with the build can use `GV-PRO-DEV-UNLOCK` if defaults not flipped  
- `build.bat` copies live `config.json` into `dist/` (may bake Pro on)

**Should be:**

- `.gitignore` → `config.json`  
- Commit `config.example.json` only  
- Release build forces `allow_dev_keys=false`, empty license fields  
- Never copy developer config into dist without sanitizing  

---

### P0-03 — Pause / cancel do not stop yt-dlp reliably

**Where:** `queue_manager.py` progress_hook raises `Exception` on pause/cancel  

**Impact:**

- yt-dlp only hits the hook on progress ticks; long stalls ignore cancel  
- Pause does **not** leave a clean resumable state; often partial files + job marked paused/error  
- User thinks “Paused” but disk/network may continue  

**Should be:** Use yt-dlp abort mechanisms / process kill + document resume limits; or download in subprocess you can terminate.

---

### P0-04 — Error jobs auto re-queue forever on every app start

**Where:** `queue_manager.py` ~35–40  

```python
elif j["status"] in ("downloading", "error"):
    ... reset to queued and put back on queue
```

**Impact:** Broken URLs / permanent failures **retry every launch** → spam errors, CPU, network.  
**Should be:** Only re-queue `downloading` (interrupted). Leave `error` until user clicks Retry.

---

### P1-05 — Config write storm / race

**Where:** `ConfigManager.set` writes entire JSON **per key**  

License activate does ~6 sequential `set()` → 6 full file rewrites. Concurrent heartbeat + UI can interleave.  

**Should be:** `update({...}); save_once()`; optional file lock.

---

### P1-06 — Operator precedence bug in path migration

**Where:** `config_manager.py` ~54  

```python
if not path or not os.path.isdir(os.path.dirname(path)) and "GitHub Repos" in path:
```

Parsed as: `not path OR (not isdir AND GitHub in path)` — not the intended grouping. Can fail to migrate odd paths or mis-handle empty path.

**Should be:** Explicit parentheses + simpler portable rules.

---

### P1-07 — Queue restore loses metadata

**Where:** `queue_manager.py` restore builds `metadata: {id, title}` only  

**Impact:** Playlist folder grouping, headers, playwright flags gone after restart.  
**Should be:** JSON column `metadata` or separate blob.

---

### P1-08 — No `filepath` / output path in DB schema

**Where:** `database.py` schema  

**Impact:** Cannot implement Open Folder, re-download skip, or cleanup. Migration needed.

---

### P1-09 — Playwright: visible browser, long block, no timeout kill-switch for users

**Where:** `playwright_extractor.py`  

- `headless=False` always  
- Up to ~60s wait loops  
- Runs on worker thread (UI ok) but scary UX; no cancel  
- Captures cookies into download headers (privacy)

**Should be:** Optional advanced mode; headless default; cancel button; clearer “browser opened” toast.

---

### P1-10 — Dual virtualenvs / dual config roots

**Present:** `venv/` and `.venv/`  

`run.bat` prefers `.venv` then `venv`. Easy to install packages in one and run the other → “module not found” / wrong yt-dlp version.

---

### P1-11 — Packaging incomplete for real ship

**Where:** `build.bat`  

- No version pinning / lockfile  
- Copies unsanitized config  
- Playwright Chromium not reliably bundled for frozen app  
- No code signing  
- `*.exe` gitignored — correct for ffmpeg, but release pipeline must document fetch  

---

### P1-12 — License demote callback overwritten

**Where:** `MainWindow` sets demote callback; `main.py` bg thread **sets again**  

Last writer wins. Can drop UI hook depending on race.  
**Should be:** Single owner (MainWindow only).

---

### P1-13 — Free tier concurrent still configurable above 1 in UI before license clamp?

Settings OptionMenu uses `license.max_concurrent()` for menu values — OK for free (1).  
But `config max_concurrent_downloads: 2` may remain in file; `_target_workers` correctly min’s with lic_max. **OK**, but Settings display can confuse.

---

### P2-14 — Memory / UI growth

- Finished jobs stay as cards until user deletes → long sessions = many widgets  
- No max history  
- `ui_queue` polled every 50ms forever (fine, small cost)  
- Thumbnail fetch removed but if re-added without cache, PIL images can leak if not held carefully  

---

### P2-15 — PriorityQueue edge cases

- Same priority: secondary compare is job_id (str) — OK  
- Paused jobs removed from active download but **not** left in PQ correctly if dequeued then paused mid-flight — handled via status  
- Resume puts new PQ item; old cancelled dequeued items may still appear — OK if status check  

---

### P2-16 — Maximize with `overrideredirect(True)`

`state('zoomed')` on borderless windows is **unreliable** on Windows (taskbar overlap, restore geometry wrong).  
**Should be:** Manual work-area geometry or drop custom chrome for v1.

---

### P2-17 — Acrylic + alpha 0.88

- GPU / remote desktop / older Windows: blank or unreadable window  
- Accessibility: low contrast for muted text on glass  

**Should be:** Setting “disable transparency”.

---

### P2-18 — EmbedSubtitle / EmbedThumbnail failures silent

`quiet` + `no_warnings` hide postprocessor failures; user still gets video but “feature lies”.  

---

### P2-19 — No URL validation / SSRF-ish local file risks

Any string goes to yt-dlp. Local paths / file:// may behave oddly. Low risk for desktop app but poor UX.

---

### P2-20 — Security: license DRM is soft

Machine fingerprint + LS activation_limit is **casual anti-share**, not anti-crack. Acceptable for ₹/low price; don’t market as “uncrackable”.

Take-over only deactivates **local** `instance_id` — cannot always free another user’s seat without LS dashboard.

---

### P3-21 — Empty modules & clutter

- `scratch_acrylic.py`, `test_dl.py` (hardcoded CDN m3u8)  
- Empty `utils`, `plugin_manager`, `models`, `extensions`  

Ship noise and confusion.

---

### P3-22 — No automated tests

Only ad-hoc `scripts/test_download.py`. No CI.

---

### P3-23 — Logging path mixes slashes

`logs/grabbyvault.log` works on Windows; cosmetic.

---

### P3-24 — Cookie browser fallbacks

Trying Firefox/Chrome/Edge cookies can trigger OS security prompts / DPAPI errors (already messaged). Slow fetch_info for public videos.

---

## 5. File-by-file audit notes

### `src/main.py`

| Issue | Sev |
|-------|-----|
| Splash bootstrap CTk destroyed then second MainWindow CTk — works but fragile | P2 |
| Demote callback set in bg thread races MainWindow | P1 |
| No `db.close()` / heartbeat stop on quit | P2 |
| `sys.exit(0)` from tray quit abrupt | P3 |

### `src/core/downloader.py`

| Issue | Sev |
|-------|-----|
| Mutates global `PATH` repeatedly | P3 |
| Logs every rebuild “JS runtimes” → log spam | P3 |
| `fetch_info` can open browser cookies without consent | P2 |
| No progress for post-merge phase beyond hook ‘finished’ | P3 |
| Title sanitization only for playlist folder, not full filesystem safety | P2 |

### `src/core/queue_manager.py`

| Issue | Sev |
|-------|-----|
| Error auto-requeue | P0 |
| Pause/cancel incomplete | P0 |
| Metadata loss on restore | P1 |
| Daemon workers never join on exit | P2 |
| Double `update_status` removed earlier (good) | — |

### `src/core/database.py`

| Issue | Sev |
|-------|-----|
| No schema version / migrations | P1 |
| No filepath, created_at, progress | P1 |
| `check_same_thread=False` + lock — OK if always used with lock | P3 |
| Connection never closed | P2 |

### `src/core/config_manager.py`

| Issue | Sev |
|-------|-----|
| Migration boolean logic bug | P1 |
| Per-key disk write | P1 |
| No validation of types (string concurrent etc.) | P2 |

### `src/core/license_manager.py`

| Issue | Sev |
|-------|-----|
| Dev keys on by default | P0 for release |
| Heartbeat starts even for free users if key set | P3 |
| `is_pro` logic dense; grace vs activated needs unit tests | P2 |
| Network errors demote after grace — correct for single-seat, harsh on flaky net | P2 |

### `src/core/playwright_extractor.py`

| Issue | Sev |
|-------|-----|
| headless=False default | P1 |
| Unused imports `json`, `time`, `re` | P3 |
| Cookie injection privacy | P2 |

### `src/core/formats.py`

| Issue | Sev |
|-------|-----|
| Solid design; main quality fix lives here | Good |
| Free presets omit 1080 — enforced again in license clamp (defense in depth) | Good |

### `src/core/url_router.py`

| Issue | Sev |
|-------|-----|
| Labels only; “Unknown” still works via yt-dlp | OK |
| No ani sites legal disclaimer in UI | P2 product |

### `src/core/paths.py`

| Issue | Sev |
|-------|-----|
| Reasonable frozen/source detection | Good |

### `src/ui/main_window.py`

| Issue | Sev |
|-------|-----|
| get_job AttributeError | P0 |
| Title labels no wrap → layout break long titles | P2 |
| Frameless window a11y / snap / Alt+Tab | P2 |
| Search re-pack can reorder cards | P3 |
| `dialog_title` unused | P3 |
| Network Connected always claimed | P3 lie |

### `src/ui/dialogs.py`

| Issue | Sev |
|-------|-----|
| License activate network on thread — good | Good |
| Settings health instantiates new Downloader (side effects PATH) | P3 |

### `src/ui/tray.py` / `splash.py` / `themes.py`

| Issue | Sev |
|-------|-----|
| Tray OK; splash brand image OK | Good |
| Generated tray icon only (no asset icon for taskbar) | P2 |

### Scripts / bat

| Issue | Sev |
|-------|-----|
| `build.bat` copies secrets config | P0 |
| `test_dl.py` external CDN URL | P3 hygiene |
| No `config.example.json` | P1 |

---

## 6. UI / UX audit

| Flow | Break / friction |
|------|------------------|
| First run | No wizard; ffmpeg missing only fails mid-download |
| Add URL empty | Silent log only |
| Fetch fail | Truncated uppercase error — hard to read |
| Quality dialog | Free users blocked from 1080 — good; message OK |
| Queue | No ETA; speed only last job |
| Complete | Open folder crashes if used |
| Pause | Misleading |
| Close X | Tray — good if explained once |
| Acrylic | May fail on some systems → unusable |
| Long titles | Overflow |
| Pro demotion | Status bar only; no modal |

---

## 7. Concurrency, memory, “leaks”

| Topic | Assessment |
|-------|------------|
| Classic C memory leak | N/A (Python) |
| Tk widget leak | Cards retained forever unless user deletes → **UI memory growth** |
| Thread leak | Workers exit only when over target; no shutdown poison-pill → process exit relies on daemon=True |
| SQLite | Connection open for process lifetime — fine if closed on quit |
| Config file | High write frequency under license — disk wear + races |
| Playwright | Browser should always close in finally — **does** `browser.close()` in finally — good |

---

## 8. Staging / packaging / migration / “node”

| Topic | Finding |
|-------|---------|
| **Git staging** | `config.json` tracked (bad); `bin/` ignored (good); dual venv ignored (good) |
| **Migration** | No DB version; additive schema changes will be ad-hoc and break old installs |
| **Node** | Not used by app runtime except as **yt-dlp JS runtime** on PATH — good when present; optional |
| **PyInstaller** | Collects yt_dlp/customtkinter; Playwright browsers not solved; assets path via `resource_path` partial |
| **File staging bugs** | Partial downloads (`.part`, `.ytdl`) left in downloads; no cleanup job |

---

## 9. Security & privacy checklist

| Item | Status |
|------|--------|
| License key in plaintext config | Yes — expected for offline, protect file ACLs |
| Dev unlock in release | Risk if not disabled |
| Browser cookie scrape | Privacy surprise |
| No telemetry (good) | Good |
| HTTPS to LS | Yes |
| Path traversal in outtmpl titles | Partially mitigated (200B); playlist folder filtered |
| Command injection open folder | Would need filepath; currently broken |

---

## 10. Dependency & supply chain

| Package | Role | Risk |
|---------|------|------|
| yt-dlp | Core | Breaks often as sites change — need update path |
| customtkinter | UI | OK |
| playwright + stealth | Fallback | Heavy; install size |
| pystray / Pillow / pywinstyles | Tray/brand/glass | Windows-specific |
| curl-cffi | Transitive via yt-dlp stack | OK |

**No lockfile** (`requirements.txt` has lower bounds only) → non-reproducible builds.

---

## 11. Positive findings (keep these)

1. **Format pipeline** (`formats.py` + merge to MP4) — correct root fix for pixelation/silent video.  
2. **UI progress marshaling** via `ui_queue` — avoids illegal Tk cross-thread calls.  
3. **paths.py** portable app root / frozen-aware design.  
4. **License single-seat design** is coherent with LS activation_limit=1.  
5. **Free/Pro clamp** enforced in queue add, not only UI.  
6. **ffmpeg PATH injection** for yt-dlp partial/merge detection.  
7. **Logging + crash files** skeleton present.  
8. Syntax clean under Python 3.11 compileall.

---

## 12. Prioritized fix backlog (recommended order)

### Sprint 0 — Before any paid key goes live (1–3 days)

1. Fix/remove Open Folder or implement `filepath` + `get_job`  
2. Stop auto-requeue of `error` jobs  
3. Sanitize release config; gitignore `config.json`; example file  
4. `allow_dev_keys=false` for release builds  
5. Fix `build.bat` to copy example config only  

### Sprint 1 — Reliability (3–7 days)

6. Real cancel (subprocess or yt-dlp abort)  
7. Config batch save + lock  
8. DB migration: filepath, metadata JSON, schema_version  
9. Restore full metadata  
10. Single demote callback owner  

### Sprint 2 — Product polish

11. First-run (download path + ffmpeg check)  
12. Disable acrylic option  
13. Better errors / copy-to-clipboard  
14. Clear finished / history limit  
15. Requirements lockfile + smoke tests  

### Sprint 3 — Could-be features

16. Cookies UI  
17. Batch URLs  
18. Auto-update yt-dlp  
19. Installer (Inno Setup)  

---

## 13. Risk matrix (launch)

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| yt-dlp breaks YouTube | High | High | Update channel; JS runtime docs |
| User hits Open Folder crash | Medium | Medium | Fix P0-01 |
| Dev key leaked in build | Medium | High | Release config policy |
| Error loop on restart | High | Medium | Fix P0-04 |
| Pause/cancel complaints | High | Medium | Fix or hide Pause until real |
| Legal/ToS complaints | Medium | High | Positioning + disclaimer |
| ₹49 fee wipe | High | Revenue | Pricing (business, not code) |

---

## 14. Metrics to watch after launch

- Crash rate (`logs/crash_*.log`)  
- % downloads finish with audio (probe sample)  
- License activate success rate  
- Support tickets: pause, folder, quality, key  

---

## 15. Conclusion

| Question | Answer |
|----------|--------|
| **What is?** | A functional desktop downloader MVP with licensing shell and SilenVault branding. |
| **What should be?** | A **reliable** Free/Pro Windows app: correct queue lifecycle, safe packaging, working post-download actions, no secrets in git/dist. |
| **What could be?** | Differentiated multi-site offline tool with JDownloader-like grabber and continuous extractor updates — **after** Sprint 0–1. |
| **Is the foundation sound?** | **Yes** for core download quality path. |
| **Is it product-complete?** | **No.** Do not market as polished Pro until P0s closed. |

---

## 16. Appendix — Module inventory

| Path | LOC (approx) | Role | Health |
|------|--------------|------|--------|
| `main.py` | ~95 | Entry | Fragile splash |
| `core/downloader.py` | ~280 | yt-dlp | Good core |
| `core/queue_manager.py` | ~200 | Jobs | P0 lifecycle bugs |
| `core/database.py` | ~70 | SQLite | Incomplete schema |
| `core/config_manager.py` | ~100 | Settings | Write/migration issues |
| `core/license_manager.py` | ~560 | LS + seat | Solid idea; release defaults bad |
| `core/formats.py` | ~150 | Quality | Good |
| `core/playwright_extractor.py` | ~180 | Fallback | Rough UX |
| `core/paths.py` | ~100 | Paths | Good |
| `core/url_router.py` | ~30 | Labels | Thin |
| `core/plugin_manager.py` | 0 | — | Dead |
| `core/utils.py` | 0 | — | Dead |
| `ui/main_window.py` | ~800 | Shell | P0 open folder |
| `ui/dialogs.py` | ~700 | Modals | OK |
| `ui/tray.py` | ~90 | Tray | OK |
| `ui/splash.py` | ~120 | Splash | OK |
| `ui/themes.py` | ~25 | Colors | OK |

---

*End of audit. Re-run after Sprint 0 fixes and attach a short “delta audit”.*
