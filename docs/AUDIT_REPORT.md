# GrabbyVault — Living Audit Report

**Last updated:** 2026-07-17  
**Status:** Core product + most open items implemented. Remaining work is **ops / polish**.

Completed history: `docs/FIXES_APPLIED.md` · Release steps: `docs/RELEASE_CHECKLIST.md`

---

## Grade

| Area | Grade |
|------|--------|
| Download / queue / cancel | **A−** |
| License / Free-Pro | **B+** |
| UI / packaging scripts | **B+** |
| Release ops (you) | **B−** until clean-PC test + live checkout URL |

---

## Done in this codebase (closed)

Icons, tray branding, process cancel + watchdog, batch URLs, cookies file, speed limit, yt-dlp update button, unit tests, CI workflow, smoke_release.bat, Inno Setup scaffold, requirements.lock.txt, config.example, schema migration, Open Folder, etc.

---

## Still open (action outside pure “bugfix”)

| ID | Item | Owner |
|----|------|--------|
| O-1 | Run `scripts\smoke_release.bat` + **clean PC** install test | You |
| O-2 | Set **live** store/checkout URL in shipped config when product is live | You |
| O-3 | Fill `lemonsqueezy_product_ids` after product exists | You |
| O-4 | Code **signing** certificate for installer | You / budget |
| O-5 | True mid-stream pause (keep socket) | Optional future |
| O-6 | Mac build | Future |
| O-7 | Per-host concurrency (not just global workers) | Future |

---

## How to verify now

```bat
scripts\smoke_release.bat
```

```bat
run.bat
```

Check: crest icon on tray, Batch button, Settings → cookies / speed / update yt-dlp, cancel mid-download.

---

*Prefer adding new closed work to FIXES_APPLIED.md rather than re-listing fixed bugs here.*
