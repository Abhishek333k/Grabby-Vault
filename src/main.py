import customtkinter as ctk
import sys
from ui.main_window import MainWindow
from ui.tray import SystemTrayIcon

def main():
    # Instantiate the custom MainWindow
    app = MainWindow()
    
    # Initialize references to ensure clean shutdown coordination
    tray = None
    
    def on_app_quit():
        print("[App] Cleaning up and exiting...")
        if tray:
            tray.stop()
        app.destroy()
        sys.exit(0)
        
    def on_window_close():
        # Minimize (hide) the window to system tray instead of destroying it
        print("[App] Hiding window to system tray. Access GrabbyVault from the taskbar tray.")
        app.withdraw()

    # Configure window close callback
    app.on_close_callback = on_window_close
    
    # Initialize and launch system tray
    tray = SystemTrayIcon(app, on_quit_callback=on_app_quit)
    tray.run()
    
    # Start the Tkinter main loop (blocks until app.destroy is called)
    app.mainloop()

if __name__ == "__main__":
    main()
