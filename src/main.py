import customtkinter as ctk
import os
import sys
import threading

# Ensure src/ is on path when launched as python src/main.py
_SRC = os.path.dirname(os.path.abspath(__file__))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from core.logging_setup import setup_logging
from core.paths import app_root
from core.config_manager import ConfigManager
from core.license_manager import LicenseManager
from ui.main_window import MainWindow
from ui.tray import SystemTrayIcon
from ui.splash import SplashScreen


def main():
    setup_logging()
    try:
        os.chdir(app_root())
    except OSError:
        pass

    # Root exists first (required for CTkImage / Toplevel splash)
    ctk.set_appearance_mode("dark")
    root_holder = {"app": None, "tray": None}

    def build_app():
        app = MainWindow()
        root_holder["app"] = app

        def on_app_quit():
            print("[App] Cleaning up and exiting...")
            tray = root_holder.get("tray")
            if tray:
                tray.stop()
            app.destroy()
            sys.exit(0)

        def on_window_close():
            print("[App] Hiding window to system tray.")
            app.withdraw()

        app.on_close_callback = on_window_close
        tray = SystemTrayIcon(app, on_quit_callback=on_app_quit)
        root_holder["tray"] = tray
        tray.run()

        # Background license revalidate (Layer B)
        def bg_license():
            try:
                lic = LicenseManager()
                if lic.license_key and lic.config.get("license_activated"):
                    ok, msg = lic.revalidate_online()
                    print(f"[License] revalidate: {ok} ({msg})")
                    app.after(0, app.refresh_license_ui)
            except Exception as e:
                print(f"[License] revalidate error: {e}")

        threading.Thread(target=bg_license, daemon=True).start()
        return app

    cfg = ConfigManager()
    show_splash = cfg.get("show_splash", True)

    if show_splash:
        # Temporary root for splash only
        bootstrap = ctk.CTk()
        bootstrap.withdraw()
        splash = SplashScreen(bootstrap, duration_ms=2000)

        def after_splash():
            splash.finish()
            bootstrap.destroy()
            app = build_app()
            app.mainloop()

        bootstrap.after(2000, after_splash)
        bootstrap.mainloop()
    else:
        app = build_app()
        app.mainloop()


if __name__ == "__main__":
    main()
