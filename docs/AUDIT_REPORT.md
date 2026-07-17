# GrabbyVault — Living Audit Report

**Last updated:** 2026-07-17  
**Scope:** application source under `src/`, packaging scripts, config templates  
**Status:** Prior P0/P1 items from the original audit are **closed**. This file tracks **remaining open work only**.

Historical detail of completed work: `docs/FIXES_APPLIED.md`

---

## Current grade

| Dimension | Grade | Note |
|-----------|-------|------|
| Core download path | **B+** | Formats + ffmpeg + process cancel + queue lifecycle solid |
| Product shell | **B** | License API, Free/Pro, settings, tray, first-run ffmpeg warning |
| Ship readiness | **B−** | Needs real product checkout URL, clean-machine release test, optional installer |

**Ship for your own sales?** Yes, after a clean-PC smoke test with a real license key and ffmpeg in `bin\`.  
**Ship as polished “big brand” app?** Not yet — packaging/signing/update channel still open.

---

## Closed (do not re-open without regression)

| Area | Resolved |
|------|----------|
| Open Folder / filepath DB | Yes |
| Error jobs auto-requeue | Yes — stay error until Retry |
| Cancel / pause abort | Yes — process kill + watchdog |
| Secrets in git / dist config | Yes — `config.json` ignored; example for release |
| Config write storms | Yes — batch `update()` + atomic write |
| Metadata restore | Yes — `metadata_json` |
| Schema migration | Yes |
| License API activate/validate/deactivate | Yes — docs-aligned client |
| Single-seat / machine bind | Yes |
| First-run ffmpeg warning | Yes |
| Acrylic toggle, clear done, URL validate | Yes |
| Dev keys off in frozen builds | Yes |
| Empty utils / plugin_manager | Filled with minimal real code |
| Scratch/test junk scripts | Removed |

---

## Open items (remaining)

### P1 — before wide public release

| ID | Item | Why it still matters |
|----|------|----------------------|
| O-1 | **Clean-machine release test** | Catch path, ffmpeg, config.example, activate, download, open folder |
| O-2 | **Pin real checkout URL** in shipped config / store listing | Sales path must not point at a placeholder |
| O-3 | **Optional product/variant ID allowlist** after LS product exists | Reject wrong-product keys |
| O-4 | **Release zip checklist** (ffmpeg, no dev keys, About links) | Support load |

### P2 — quality / UX debt

| ID | Item | Notes |
|----|------|--------|
| O-5 | True mid-stream **pause** (keep connection) | Current: stop process + resume re-queues (acceptable) |
| O-6 | Richer process-download **progress** (real bytes, not % only) | Works; can improve |
| O-7 | Taskbar / window **icon** from assets | Still generated tray icon only |
| O-8 | Frameless window edge cases (multi-monitor snap) | Maximize uses work-area now; snap still limited |
| O-9 | Cookie import UI | Power users only |
| O-10 | Auto-update **yt-dlp** channel | Sites break; document manual update for now |

### P3 — roadmap (not bugs)

| ID | Item |
|----|------|
| O-11 | Batch multi-URL paste / link grabber |
| O-12 | Speed limit / per-host concurrency |
| O-13 | Code signing + proper installer (Inno/MSIX) |
| O-14 | Automated CI smoke tests |
| O-15 | Mac build |
| O-16 | requirements lockfile |

### Soft limits (by design — not defects)

- License enforcement is seat + online validate, not DRM.  
- Cannot download DRM/Netflix-class streams.  
- Playwright path remains optional and heavy.  
- Pause is stop-and-resume, not Netflix-style pause.

---

## Architecture (current)

```
MainWindow ──ui_queue──► QueueManager workers
                              │
                              ▼
                     Downloader ──► ProcessDownloadRunner (yt-dlp subprocess)
                              │         kill on cancel/pause
                              └──► in-process path (audio extract)
LicenseManager ──► LemonSqueezyClient (activate / validate / deactivate)
config.json (local) · queue.db · logs/
```

---

## Recommended next sprint (code)

1. ~~Cancel watchdog~~ **done this pass**  
2. ~~Progress % for process runner~~ **done this pass**  
3. ~~Borderless maximize work-area~~ **done this pass**  
4. App icon from `assets/` for window + tray  
5. Tiny unit tests: `resolve_preset`, `clamp_format`, `is_http_url`, DB migrate  
6. One `scripts/smoke_release.bat` that checks ffmpeg + imports + config.example  

---

## Recommended next sprint (ops / product)

1. Create live product checkout link  
2. Set `lemonsqueezy_checkout_url` + optional product ids  
3. Build with `build.bat`, copy ffmpeg, test on a second Windows user/profile  
4. Keep `allow_dev_keys=false` in anything you distribute  

---

## Regression checklist (run after each release build)

- [ ] App starts; splash optional  
- [ ] Missing ffmpeg shows warning  
- [ ] Free: only ≤720p presets  
- [ ] Pro activate with real key → badge PRO  
- [ ] Download finishes with audio; 📁 opens file  
- [ ] Cancel mid-download stops process (Task Manager: no leftover yt-dlp)  
- [ ] Pause then resume re-queues  
- [ ] Error job survives restart without auto-start  
- [ ] Clear done removes finished cards  
- [ ] Quit from tray stops cleanly  

---

*Update this file when open items close. Do not re-list fixed bugs — put them in `FIXES_APPLIED.md`.*
