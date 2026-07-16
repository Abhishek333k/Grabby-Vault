"""Startup splash using SilenVault brand assets."""
from __future__ import annotations

import os
import customtkinter as ctk
from PIL import Image

from core.paths import app_root, resource_path
from ui.themes import DEEP_DARK, NEON_BLUE, NEON_PURPLE, TEXT_MUTED, TEXT_PRIMARY


def _find_brand_image() -> str | None:
    root = app_root()
    candidates = [
        os.path.join(root, "assets", "Banner with CREST.png"),
        os.path.join(root, "assets", "Banner with CREST.webp"),
        os.path.join(root, "assets", "BANNER.png"),
        os.path.join(root, "assets", "BANNER.webp"),
        os.path.join(root, "assets", "SILENVAULT_LOGO.png"),
        os.path.join(root, "assets", "SILENVAULT CREST.png"),
        resource_path("assets", "Banner with CREST.png"),
        resource_path("assets", "BANNER.png"),
    ]
    for p in candidates:
        if p and os.path.isfile(p):
            return p
    return None


class SplashScreen(ctk.CTkToplevel):
    def __init__(self, master, duration_ms: int = 2200):
        super().__init__(master)
        self.duration_ms = duration_ms
        self.overrideredirect(True)
        self.configure(fg_color=DEEP_DARK)
        self.attributes("-topmost", True)

        w, h = 520, 300
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")

        frame = ctk.CTkFrame(self, fg_color=DEEP_DARK, corner_radius=12)
        frame.pack(fill="both", expand=True, padx=2, pady=2)

        img_path = _find_brand_image()
        self._photo = None
        if img_path:
            try:
                pil = Image.open(img_path)
                # Fit banner width
                pil.thumbnail((480, 160), Image.Resampling.LANCZOS)
                self._photo = ctk.CTkImage(
                    light_image=pil, dark_image=pil, size=pil.size
                )
                ctk.CTkLabel(frame, text="", image=self._photo).pack(pady=(28, 8))
            except Exception:
                self._title_only(frame)
        else:
            self._title_only(frame)

        ctk.CTkLabel(
            frame,
            text="GrabbyVault",
            font=("Segoe UI", 22, "bold"),
            text_color=NEON_BLUE,
        ).pack(pady=(4, 0))
        ctk.CTkLabel(
            frame,
            text="by SilenVault",
            font=("Segoe UI", 12),
            text_color=NEON_PURPLE,
        ).pack()
        ctk.CTkLabel(
            frame,
            text="Loading engine · yt-dlp · queue · license",
            font=("Segoe UI", 11),
            text_color=TEXT_MUTED,
        ).pack(pady=(16, 8))

        self.bar = ctk.CTkProgressBar(
            frame, width=360, height=6, progress_color=NEON_BLUE, fg_color="#1a1a24"
        )
        self.bar.pack(pady=(4, 24))
        self.bar.set(0.08)
        self._progress = 0.08
        self._tick()

    def _title_only(self, frame):
        ctk.CTkLabel(
            frame,
            text="SV",
            font=("Segoe UI", 48, "bold"),
            text_color=NEON_BLUE,
        ).pack(pady=(40, 0))

    def _tick(self):
        self._progress = min(0.95, self._progress + 0.07)
        self.bar.set(self._progress)
        if self._progress < 0.95:
            self.after(90, self._tick)

    def finish(self):
        try:
            self.bar.set(1.0)
            self.destroy()
        except Exception:
            pass


def show_splash_then(master, build_main_callback, duration_ms: int = 2000):
    """
    master: root CTk (withdrawn). build_main_callback creates/shows main UI.
    """
    master.withdraw()
    splash = SplashScreen(master, duration_ms=duration_ms)

    def _done():
        splash.finish()
        build_main_callback()
        master.deiconify()

    master.after(duration_ms, _done)
    return splash
