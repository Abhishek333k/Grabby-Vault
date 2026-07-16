import threading
import pystray
from PIL import Image, ImageDraw
import sys

class SystemTrayIcon:
    def __init__(self, app, on_quit_callback=None):
        self.app = app
        self.on_quit_callback = on_quit_callback
        self.icon = None
        self.thread = None
        
    def _create_image(self):
        """
        Generates a 64x64 neon cyberpunk icon programmatically using PIL.
        Features a neon-blue rounded vault shield and a purple lightning bolt center.
        """
        # Create an RGBA image with transparent background
        image = Image.new('RGBA', (64, 64), color=(0, 0, 0, 0))
        dc = ImageDraw.Draw(image)
        
        # Draw a dark gray rounded rectangle container with neon blue outline
        dc.rounded_rectangle(
            [8, 8, 56, 56], 
            radius=12, 
            outline=(0, 240, 255, 255), 
            width=4, 
            fill=(15, 15, 18, 220)
        )
        
        # Draw a neon-purple lightning bolt in the center
        dc.polygon(
            [(32, 14), (46, 28), (36, 28), (40, 50), (20, 34), (30, 34)], 
            fill=(189, 0, 255, 255)
        )
        
        return image

    def _on_show(self, icon, item):
        self.app.after(0, self._show_window)
        
    def _show_window(self):
        self.app.deiconify()
        self.app.lift()
        self.app.focus_force()

    def _on_add_url(self, icon, item):
        self.app.after(0, self._add_url_action)
        
    def _add_url_action(self):
        self._show_window()
        if hasattr(self.app, 'url_input'):
            self.app.url_input.focus()

    def _on_quit(self, icon, item):
        print("[Tray] Shutting down application...")
        # Stop tray icon loop
        self.icon.stop()
        # Safely shut down Tkinter application on the main thread
        if self.on_quit_callback:
            self.app.after(0, self.on_quit_callback)
        else:
            self.app.after(0, self.app.destroy)

    def run(self):
        """
        Creates and starts the pystray system tray icon in a background daemon thread.
        """
        menu = pystray.Menu(
            pystray.MenuItem("Show App", self._on_show, default=True),
            pystray.MenuItem("Add URL", self._on_add_url),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", self._on_quit)
        )
        
        self.icon = pystray.Icon(
            "GrabbyVault",
            self._create_image(),
            title="GrabbyVault - Video Downloader",
            menu=menu
        )
        
        # Run the system tray icon loop in a background daemon thread
        self.thread = threading.Thread(target=self.icon.run, daemon=True)
        self.thread.start()

    def stop(self):
        """
        Stops the system tray icon loop.
        """
        if self.icon:
            self.icon.stop()
