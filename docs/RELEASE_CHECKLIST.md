# Release checklist

1. `scripts\smoke_release.bat` — all steps green (WARN on missing ffmpeg only if you will copy it next)
2. `build.bat` — produces `dist\GrabbyVault\`
3. Copy `bin\ffmpeg.exe` + `bin\ffprobe.exe` into dist folder if not already
4. Confirm dist `config.json` is from **config.example.json** (`allow_dev_keys: false`)
5. Set production `store_url` / checkout URL in the shipped config if needed
6. Optional: compile `installer\grabbyvault.iss` with Inno Setup (generate `assets\grabbyvault.ico` via first app run or smoke script)
7. Clean PC / second Windows user: install → activate license → download one short public video → open folder → cancel mid-download
8. Tag git release when satisfied
