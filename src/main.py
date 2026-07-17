import customtkinter as ctk
import os
import sys
import threading

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

    ctk.set_appearance_mode("dark")
    root_holder = {"app": None, "tray": None}

    def build_app():
        app = MainWindow()
        root_holder["app"] = app

        def on_app_quit():
            print("[App] Cleaning up and exiting...")
            try:
                lic = LicenseManager()
                lic.stop_heartbeat()
            except Exception:
                pass
            try:
                if hasattr(app, "queue_manager"):
                    app.queue_manager.shutdown()
            except Exception:
                pass
            tray = root_holder.get("tray")
            if tray:
                tray.stop()
            try:
                app.destroy()
            except Exception:
                pass
            sys.exit(0)

        def on_window_close():
            print("[App] Hiding window to system tray.")
            app.withdraw()

        app.on_close_callback = on_window_close
        tray = SystemTrayIcon(app, on_quit_callback=on_app_quit)
        root_holder["tray"] = tray
        tray.run()

        # Startup license check only — demote callback owned by MainWindow
        def bg_license():
            try:
                lic = LicenseManager()
                if lic.license_key:
                    ok, msg = lic.revalidate_online(force_demote=True)
                    print(f"[License] startup revalidate: {ok} ({msg})")
                    app.after(0, app.refresh_license_ui)
                # Heartbeat already started in MainWindow; ensure running
                lic.start_heartbeat()
            except Exception as e:
                print(f"[License] revalidate error: {e}")

        threading.Thread(target=bg_license, daemon=True).start()
        return app

    cfg = ConfigManager()
    show_splash = cfg.get("show_splash", True)

    if show_splash:
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
