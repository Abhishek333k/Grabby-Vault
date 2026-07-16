import os
import webbrowser
import customtkinter as ctk

from core.config_manager import ConfigManager
from core.license_manager import LicenseManager
from core.downloader import Downloader
from core.paths import logs_dir, app_root
from ui.themes import (
    DEEP_DARK,
    CARD_BG,
    INPUT_BG,
    BORDER_MUTED,
    TEXT_PRIMARY,
    TEXT_MUTED,
    NEON_BLUE,
    NEON_PURPLE,
    NEON_GREEN,
    NEON_RED,
)


class FormatSelectionDialog(ctk.CTkToplevel):
    def __init__(self, master, title="Select Quality", on_submit=None):
        super().__init__(master)
        self.title(title)
        self.geometry("400x500")
        self.resizable(False, False)

        self.transient(master)
        self.grab_set()

        self.on_submit = on_submit
        self.license = LicenseManager()
        presets = self.license.allowed_presets()
        default_id = presets[0]["id"] if presets else "720"
        # Prefer 1080 for pro, 720 for free
        if self.license.is_pro:
            for p in presets:
                if p["id"] == "1080":
                    default_id = "1080"
                    break
        else:
            for p in presets:
                if p["id"] == "720":
                    default_id = "720"
                    break

        self.selected_format = ctk.StringVar(value=default_id)
        self.configure(fg_color=DEEP_DARK)

        lbl = ctk.CTkLabel(
            self,
            text="Select Download Quality",
            font=("Segoe UI", 16, "bold"),
            text_color=NEON_BLUE,
        )
        lbl.pack(pady=(20, 6))

        tier = self.license.tier_label()
        hint_text = (
            f"Plan: {tier} · ffmpeg merges video+audio"
            if self.license.is_pro
            else f"Plan: {tier} · max 720p · Upgrade for 1080p/4K"
        )
        ctk.CTkLabel(
            self, text=hint_text, font=("Segoe UI", 11), text_color=TEXT_MUTED
        ).pack(pady=(0, 10))

        for preset in presets:
            rb = ctk.CTkRadioButton(
                self,
                text=preset["label"],
                value=preset["id"],
                variable=self.selected_format,
                font=("Segoe UI", 12),
                text_color=TEXT_PRIMARY,
                fg_color=NEON_PURPLE,
                hover_color="#3e3e42",
            )
            rb.pack(anchor="w", padx=40, pady=5)

        if not self.license.is_pro:
            ctk.CTkLabel(
                self,
                text="🔒 1080p / 4K / Best require Pro",
                font=("Segoe UI", 11),
                text_color=NEON_PURPLE,
            ).pack(pady=(8, 0))

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=18)

        ctk.CTkButton(
            btn_frame,
            text="Confirm",
            width=100,
            fg_color=NEON_BLUE,
            text_color=TEXT_PRIMARY,
            hover_color="#005999",
            font=("Segoe UI", 12, "bold"),
            command=self._confirm,
        ).pack(side="left", padx=10)

        ctk.CTkButton(
            btn_frame,
            text="Cancel",
            width=100,
            fg_color="transparent",
            border_width=1,
            border_color=NEON_RED,
            text_color=NEON_RED,
            hover_color="#3d2a2a",
            font=("Segoe UI", 12, "bold"),
            command=self.destroy,
        ).pack(side="left", padx=10)

    def _confirm(self):
        val = self.selected_format.get()
        if self.on_submit:
            self.on_submit(val)
        self.destroy()


class PlaylistSelectionDialog(ctk.CTkToplevel):
    def __init__(self, master, entries, on_submit=None):
        super().__init__(master)
        self.title("Playlist Selection")
        self.geometry("500x500")

        self.transient(master)
        self.grab_set()

        self.on_submit = on_submit
        self.entries = entries
        self.checkbox_vars = {}
        self.configure(fg_color=DEEP_DARK)

        ctk.CTkLabel(
            self,
            text="Select Playlist Items",
            font=("Segoe UI", 16, "bold"),
            text_color=NEON_BLUE,
        ).pack(pady=(20, 10))

        self.scroll = ctk.CTkScrollableFrame(
            self, fg_color=CARD_BG, border_width=1, border_color=BORDER_MUTED
        )
        self.scroll.pack(fill="both", expand=True, padx=20, pady=10)

        for idx, entry in enumerate(self.entries):
            title = entry.get("title", f"Video {idx + 1}")
            var = ctk.BooleanVar(value=True)
            self.checkbox_vars[idx] = var
            ctk.CTkCheckBox(
                self.scroll,
                text=title,
                variable=var,
                font=("Segoe UI", 12),
                text_color=TEXT_PRIMARY,
                fg_color=NEON_PURPLE,
                hover_color="#3e3e42",
            ).pack(anchor="w", padx=10, pady=5)

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", pady=10, padx=20)

        ctk.CTkButton(
            btn_frame,
            text="Select All",
            width=90,
            height=30,
            fg_color="transparent",
            border_width=1,
            border_color=TEXT_MUTED,
            text_color=TEXT_MUTED,
            font=("Segoe UI", 11),
            hover_color="#3e3e42",
            command=self._select_all,
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            btn_frame,
            text="Select None",
            width=90,
            height=30,
            fg_color="transparent",
            border_width=1,
            border_color=TEXT_MUTED,
            text_color=TEXT_MUTED,
            font=("Segoe UI", 11),
            hover_color="#3e3e42",
            command=self._select_none,
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            btn_frame,
            text="Confirm",
            width=100,
            height=30,
            fg_color=NEON_BLUE,
            text_color=TEXT_PRIMARY,
            hover_color="#005999",
            font=("Segoe UI", 12, "bold"),
            command=self._confirm,
        ).pack(side="right", padx=5)

    def _select_all(self):
        for var in self.checkbox_vars.values():
            var.set(True)

    def _select_none(self):
        for var in self.checkbox_vars.values():
            var.set(False)

    def _confirm(self):
        selected = [
            self.entries[idx]
            for idx in self.checkbox_vars
            if self.checkbox_vars[idx].get()
        ]
        if self.on_submit:
            self.on_submit(selected)
        self.destroy()


class SettingsDialog(ctk.CTkToplevel):
    def __init__(self, master, queue_manager):
        super().__init__(master)
        self.title("Settings")
        self.geometry("480x520")
        self.resizable(False, False)

        self.transient(master)
        self.grab_set()

        self.queue_manager = queue_manager
        self.config = ConfigManager()
        self.license = LicenseManager()
        self.configure(fg_color=DEEP_DARK)

        ctk.CTkLabel(
            self, text="Settings", font=("Segoe UI", 16, "bold"), text_color=NEON_BLUE
        ).pack(pady=(16, 8))

        # Download path
        path_frame = ctk.CTkFrame(self, fg_color="transparent")
        path_frame.pack(fill="x", padx=20, pady=6)
        ctk.CTkLabel(
            path_frame, text="Download Path:", font=("Segoe UI", 12), text_color=TEXT_PRIMARY
        ).pack(anchor="w")
        row = ctk.CTkFrame(path_frame, fg_color="transparent")
        row.pack(fill="x")
        self.path_var = ctk.StringVar(value=self.config.get_download_path())
        ctk.CTkEntry(
            row,
            textvariable=self.path_var,
            width=360,
            fg_color=INPUT_BG,
            border_color=BORDER_MUTED,
            text_color=TEXT_PRIMARY,
        ).pack(side="left", pady=4)
        ctk.CTkButton(
            row,
            text="...",
            width=36,
            fg_color=NEON_PURPLE,
            text_color=TEXT_PRIMARY,
            command=self._browse,
        ).pack(side="left", padx=8)

        # Concurrency
        conc_frame = ctk.CTkFrame(self, fg_color="transparent")
        conc_frame.pack(fill="x", padx=20, pady=6)
        max_c = self.license.max_concurrent()
        ctk.CTkLabel(
            conc_frame,
            text=f"Max Concurrent Downloads (1–{max_c}):",
            font=("Segoe UI", 12),
            text_color=TEXT_PRIMARY,
        ).pack(anchor="w")
        values = [str(i) for i in range(1, max_c + 1)]
        cur = str(min(int(self.config.get("max_concurrent_downloads", 1)), max_c))
        self.conc_var = ctk.StringVar(value=cur if cur in values else values[0])
        ctk.CTkOptionMenu(
            conc_frame,
            values=values,
            variable=self.conc_var,
            fg_color=INPUT_BG,
            button_color=BORDER_MUTED,
        ).pack(anchor="w", pady=4)
        if not self.license.is_pro:
            ctk.CTkLabel(
                conc_frame,
                text="Free: 1 concurrent · Pro: up to 5",
                font=("Segoe UI", 11),
                text_color=TEXT_MUTED,
            ).pack(anchor="w")

        # Health
        health = Downloader().health_check()
        health_frame = ctk.CTkFrame(
            self, fg_color=CARD_BG, border_width=1, border_color=BORDER_MUTED, corner_radius=8
        )
        health_frame.pack(fill="x", padx=20, pady=12)
        ctk.CTkLabel(
            health_frame,
            text="System Health",
            font=("Segoe UI", 13, "bold"),
            text_color=NEON_BLUE,
        ).pack(anchor="w", padx=12, pady=(10, 4))

        ff_ok = health["ffmpeg_ok"]
        ff_color = NEON_GREEN if ff_ok else NEON_RED
        ctk.CTkLabel(
            health_frame,
            text=f"ffmpeg: {'OK' if ff_ok else 'MISSING'}  {health.get('ffmpeg_path') or ''}",
            font=("Segoe UI", 11),
            text_color=ff_color,
            wraplength=420,
            justify="left",
        ).pack(anchor="w", padx=12, pady=2)

        js = ", ".join(health["js_runtimes"]) or "none (YouTube may be limited)"
        ctk.CTkLabel(
            health_frame,
            text=f"JS runtime: {js}",
            font=("Segoe UI", 11),
            text_color=TEXT_PRIMARY,
        ).pack(anchor="w", padx=12, pady=2)

        ctk.CTkLabel(
            health_frame,
            text=f"yt-dlp: {health['yt_dlp_version']}",
            font=("Segoe UI", 11),
            text_color=TEXT_MUTED,
        ).pack(anchor="w", padx=12, pady=2)

        ctk.CTkLabel(
            health_frame,
            text=f"App root: {health['app_root']}",
            font=("Segoe UI", 10),
            text_color=TEXT_MUTED,
            wraplength=420,
            justify="left",
        ).pack(anchor="w", padx=12, pady=(2, 10))

        # Links row
        link_row = ctk.CTkFrame(self, fg_color="transparent")
        link_row.pack(fill="x", padx=20, pady=4)
        ctk.CTkButton(
            link_row,
            text="Open Logs",
            width=110,
            fg_color="transparent",
            border_width=1,
            border_color=BORDER_MUTED,
            text_color=TEXT_PRIMARY,
            command=lambda: os.startfile(logs_dir()),
        ).pack(side="left", padx=4)
        ctk.CTkButton(
            link_row,
            text="License / Pro",
            width=110,
            fg_color=NEON_PURPLE,
            text_color=TEXT_PRIMARY,
            command=self._open_license,
        ).pack(side="left", padx=4)
        ctk.CTkButton(
            link_row,
            text="Donate",
            width=90,
            fg_color="transparent",
            border_width=1,
            border_color=NEON_GREEN,
            text_color=NEON_GREEN,
            command=self._open_donate,
        ).pack(side="left", padx=4)

        # Save / Cancel
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", pady=18)
        ctk.CTkButton(
            btn_frame,
            text="Save",
            width=100,
            fg_color=NEON_GREEN,
            text_color=TEXT_PRIMARY,
            hover_color="#367c39",
            font=("Segoe UI", 12, "bold"),
            command=self._save,
        ).pack(side="left", padx=(40, 10))
        ctk.CTkButton(
            btn_frame,
            text="Cancel",
            width=100,
            fg_color="transparent",
            border_width=1,
            border_color=NEON_RED,
            text_color=NEON_RED,
            hover_color="#3d2a2a",
            font=("Segoe UI", 12, "bold"),
            command=self.destroy,
        ).pack(side="right", padx=(10, 40))

    def _browse(self):
        directory = ctk.filedialog.askdirectory(title="Select Download Folder")
        if directory:
            self.path_var.set(directory)

    def _open_license(self):
        LicenseDialog(self.master)

    def _open_donate(self):
        DonateDialog(self.master)

    def _save(self):
        self.config.set("download_path", self.path_var.get())
        self.config.set("max_concurrent_downloads", int(self.conc_var.get()))
        self.queue_manager.apply_settings_change()
        self.destroy()


class LicenseDialog(ctk.CTkToplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("License — GrabbyVault Pro")
        self.geometry("460x360")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()
        self.configure(fg_color=DEEP_DARK)
        self.license = LicenseManager()

        ctk.CTkLabel(
            self,
            text="GrabbyVault License",
            font=("Segoe UI", 16, "bold"),
            text_color=NEON_BLUE,
        ).pack(pady=(18, 6))

        status = "PRO ✓" if self.license.is_pro else "FREE"
        color = NEON_GREEN if self.license.is_pro else TEXT_MUTED
        self.lbl_status = ctk.CTkLabel(
            self, text=f"Current plan: {status}", font=("Segoe UI", 13, "bold"), text_color=color
        )
        self.lbl_status.pack(pady=4)

        ctk.CTkLabel(
            self,
            text="Pro unlocks: 1080p/4K/Best · up to 5 concurrent downloads",
            font=("Segoe UI", 11),
            text_color=TEXT_MUTED,
        ).pack(pady=(0, 10))

        ctk.CTkLabel(
            self, text="License key:", font=("Segoe UI", 12), text_color=TEXT_PRIMARY
        ).pack(anchor="w", padx=30)
        self.key_var = ctk.StringVar(value=self.license.license_key)
        ctk.CTkEntry(
            self,
            textvariable=self.key_var,
            width=380,
            fg_color=INPUT_BG,
            border_color=BORDER_MUTED,
            text_color=TEXT_PRIMARY,
            placeholder_text="GV-XXXX-XXXX-XXXX or paste from Lemon Squeezy",
        ).pack(padx=30, pady=6)

        self.msg = ctk.CTkLabel(self, text="", font=("Segoe UI", 11), text_color=TEXT_MUTED)
        self.msg.pack(pady=4)

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(pady=12)
        ctk.CTkButton(
            row,
            text="Activate",
            width=110,
            fg_color=NEON_BLUE,
            command=self._activate,
        ).pack(side="left", padx=6)
        ctk.CTkButton(
            row,
            text="Buy Pro",
            width=110,
            fg_color=NEON_PURPLE,
            command=lambda: webbrowser.open(self.license.checkout_url()),
        ).pack(side="left", padx=6)
        ctk.CTkButton(
            row,
            text="Close",
            width=90,
            fg_color="transparent",
            border_width=1,
            border_color=BORDER_MUTED,
            text_color=TEXT_PRIMARY,
            command=self.destroy,
        ).pack(side="left", padx=6)

        ctk.CTkLabel(
            self,
            text="Dev test key: GV-PRO-DEV-UNLOCK",
            font=("Segoe UI", 10),
            text_color=TEXT_MUTED,
        ).pack(pady=(8, 0))

    def _activate(self):
        ok, message = self.license.activate(self.key_var.get())
        self.msg.configure(text=message, text_color=NEON_GREEN if ok else NEON_RED)
        if ok:
            self.lbl_status.configure(text="Current plan: PRO ✓", text_color=NEON_GREEN)
            # Refresh main window badge if present
            if hasattr(self.master, "refresh_license_ui"):
                self.master.refresh_license_ui()


class DonateDialog(ctk.CTkToplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("Donate")
        self.geometry("420x280")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()
        self.configure(fg_color=DEEP_DARK)
        self.license = LicenseManager()

        ctk.CTkLabel(
            self,
            text="Support GrabbyVault",
            font=("Segoe UI", 16, "bold"),
            text_color=NEON_GREEN,
        ).pack(pady=(24, 10))

        ctk.CTkLabel(
            self,
            text=(
                "No ads. Ever.\n\n"
                "If GrabbyVault helps you, an optional donation keeps\n"
                "development going. 100% voluntary — no features locked."
            ),
            font=("Segoe UI", 12),
            text_color=TEXT_PRIMARY,
            justify="center",
        ).pack(padx=24, pady=8)

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(pady=18)
        ctk.CTkButton(
            row,
            text="Donate",
            width=120,
            height=36,
            fg_color=NEON_GREEN,
            text_color="#0a0a0c",
            font=("Segoe UI", 12, "bold"),
            command=lambda: webbrowser.open(self.license.donate_url()),
        ).pack(side="left", padx=8)
        ctk.CTkButton(
            row,
            text="Close",
            width=100,
            height=36,
            fg_color="transparent",
            border_width=1,
            border_color=BORDER_MUTED,
            text_color=TEXT_PRIMARY,
            command=self.destroy,
        ).pack(side="left", padx=8)


class AboutDialog(ctk.CTkToplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("About GrabbyVault")
        self.geometry("420x300")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()
        self.configure(fg_color=DEEP_DARK)
        lic = LicenseManager()

        ctk.CTkLabel(
            self, text="GrabbyVault", font=("Segoe UI", 18, "bold"), text_color=NEON_BLUE
        ).pack(pady=(24, 4))
        ctk.CTkLabel(
            self,
            text=f"Desktop video downloader · {lic.tier_label()}",
            font=("Segoe UI", 12),
            text_color=TEXT_MUTED,
        ).pack()
        ctk.CTkLabel(
            self,
            text=(
                "Powered by yt-dlp + ffmpeg\n"
                "Sold via Lemon Squeezy · no ads\n\n"
                f"Data folder:\n{app_root()}"
            ),
            font=("Segoe UI", 11),
            text_color=TEXT_PRIMARY,
            justify="center",
        ).pack(pady=16)
        ctk.CTkButton(
            self, text="Close", width=100, command=self.destroy, fg_color=NEON_BLUE
        ).pack(pady=8)
