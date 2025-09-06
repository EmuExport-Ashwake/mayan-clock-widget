# Mayan Clock Widget

This repository contains a **Mayan Calendar Clock Widget** for Windows with optional Snap-to-Taskbar mode.

## Features
- Mayan Long Count, Tzolk'in, Haab dates
- Snap-to-Taskbar overlay mode
- System tray icon, autostart toggle
- Fully automatic EXE build via GitHub Actions

## Build EXE (GitHub Actions)
1. Push any commit to the repository.
2. The workflow will automatically build the EXE.
3. Download the artifact from Actions → Latest Workflow → Artifacts → MayanClockWidget.zip

## Manual Local Build
```bash
pip install -r requirements.txt
pyinstaller --noconfirm --clean mayan_clock_widget_with_snap.spec
```
