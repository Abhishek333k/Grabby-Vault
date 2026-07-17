import threading
import pystray
from PIL import Image, ImageDraw


class SystemTrayIcon:
    def __init__(self, app, on_quit_callback=None):
        self.app = app
        self.on_quit_callback = on_quit_callback
        self.icon = None
        self.thread = None

    def _create_image(self):
        try:
            from core.branding import load_brand_image

            return load_brand_image((64, 64))
        except Exception:
            image = Image.new("RGBA", (64, 64), color=(0, 0, 0, 0))
            dc = ImageDraw.Draw(image)
            dc.rounded_rectangle(
                [8, 8, 56, 56],
                radius=12,
                outline=(0, 240, 255, 255),
                width=4,
                fill=(15, 15, 18, 220),
            )
            dc.polygon(
                [(32, 14), (46, 28), (36, 28), (40, 50), (20, 34), (30, 34)],
                fill=(189, 0, 255, 255),
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
        if hasattr(self.app, "url_input"):
            self.app.url_input.focus()

    def _on_quit(self, icon, item):
        print("[Tray] Shutting down application...")
        if self.icon:
            self.icon.stop()
        if self.on_quit_callback:
            self.app.after(0, self.on_quit_callback)
        else:
            self.app.after(0, self.app.destroy)

    def run(self):
        menu = pystray.Menu(
            pystray.MenuItem("Show App", self._on_show, default=True),
            pystray.MenuItem("Add URL", self._on_add_url),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", self._on_quit),
        )
        self.icon = pystray.Icon(
            "GrabbyVault",
            self._create_image(),
            title="GrabbyVault — Video Downloader",
            menu=menu,
        )
        self.thread = threading.Thread(target=self.icon.run, daemon=True)
        self.thread.start()

    def stop(self):
        if self.icon:
            self.icon.stop()
