# Fixes applied (post-audit)

Date: 2026-07-17  
Source: `docs/AUDIT_REPORT.md` priority backlog

## P0

| ID | Fix |
|----|-----|
| Open Folder | DB `filepath` + `get_job()`; locate button opens Explorer; fallback downloads dir |
| Error requeue | `error` jobs **not** auto-queued on startup; user Retry (↻) |
| Cancel/pause | `abort` flag + `DownloadAborted`; pause aborts active DL then resume re-queues |
| Secrets | `config.json` gitignored; `config.example.json` for ship; `build.bat` copies example only |

## P1

| ID | Fix |
|----|-----|
| Config writes | `ConfigManager.update()` batch + atomic tmp replace + lock |
| Path migration | Simplified portable path rules |
| Metadata restore | `metadata_json` column; restore full meta on startup |
| Schema | Migration via `PRAGMA` + `schema_meta` version |
| License callback | Only `MainWindow` owns demote callback |
| Config batch on license | activate/deactivate use `update()` |

## P2 / polish

| Item | Fix |
|------|-----|
| Acrylic | `use_acrylic` setting; can disable |
| Playwright | configurable headless + timeout |
| Clear done | button removes finished/cancelled cards |
| URL validate | require http(s); empty paste message |
| Title overflow | truncate long titles |
| Quit | stop heartbeat + queue shutdown + db close |
| Retry | error cards get ↻ retry |
| run.bat | prefer `venv\`; auto-create config from example |

## Later production pass

| Item | Fix |
|------|-----|
| Process download cancel | Watchdog thread kills yt-dlp on stall + abort |
| Progress UI | Handles `_percent` from process runner; cleaner speed text |
| Maximize | Work-area geometry for borderless window |
| Status bar | No fake “Network Connected” |
| utils / plugin_manager | Minimal real implementations |
| Scratch scripts | Removed `scratch_acrylic.py`, `test_dl.py` |
| Cancel/pause | Immediate `runner.kill()` from queue manager |

## Full backlog pass (icons → CI)

| Item | Fix |
|------|-----|
| Window / tray icon | `core/branding.py` + `grabbyvault.ico` from crest |
| Smoke | `scripts/smoke_release.bat` |
| Unit tests | `tests/test_formats_license.py` |
| Batch URLs | Batch button + dialog (≤50) |
| Cookies | Settings → cookies.txt path |
| Speed limit | Settings → KB/s → yt-dlp ratelimit |
| yt-dlp update | Settings button → pip install -U |
| CI | `.github/workflows/ci.yml` |
| Installer scaffold | `installer/grabbyvault.iss` |
| Lock pins | `requirements.lock.txt` |
| Release checklist | `docs/RELEASE_CHECKLIST.md` |

## Still soft / known limits

- Pause is **stop-and-resume** (not true mid-stream pause)
- License seat model is not DRM
- Playwright remains optional/heavy
- Remaining open items: `docs/AUDIT_REPORT.md`
