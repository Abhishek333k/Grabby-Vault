import customtkinter as ctk
import os
import sys

# Ensure src/ is on path when launched as python src/main.py
_SRC = os.path.dirname(os.path.abspath(__file__))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from core.logging_setup import setup_logging
from core.paths import app_root
from ui.main_window import MainWindow
from ui.tray import SystemTrayIcon


def main():
    setup_logging()
    # Stable CWD so relative assets / accidental relpaths resolve
    try:
        os.chdir(app_root())
    except OSError:
        pass

    app = MainWindow()
    tray = None

    def on_app_quit():
        print("[App] Cleaning up and exiting...")
        if tray:
            tray.stop()
        app.destroy()
        sys.exit(0)

    def on_window_close():
        print("[App] Hiding window to system tray.")
        app.withdraw()

    app.on_close_callback = on_window_close
    tray = SystemTrayIcon(app, on_quit_callback=on_app_quit)
    tray.run()
    app.mainloop()


if __name__ == "__main__":
    main()
