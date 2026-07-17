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

## Still soft / known limits

- Pause is **stop-and-resume** (not true mid-stream pause of yt-dlp)
- Cancel only aborts on next progress tick (or between extract/download)
- DRM / hard anti-crack not claimed
- Playwright still optional/heavy
