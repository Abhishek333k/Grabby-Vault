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
        self.geometry("500x520")
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
            text="Pro: 1080p/4K/Best · up to 5 concurrent · Lemon Squeezy key",
            font=("Segoe UI", 11),
            text_color=TEXT_MUTED,
        ).pack(pady=(0, 8))

        ctk.CTkLabel(
            self, text="License key (from your purchase email):", font=("Segoe UI", 12), text_color=TEXT_PRIMARY
        ).pack(anchor="w", padx=30)
        self.key_var = ctk.StringVar(value=self.license.license_key)
        ctk.CTkEntry(
            self,
            textvariable=self.key_var,
            width=400,
            fg_color=INPUT_BG,
            border_color=BORDER_MUTED,
            text_color=TEXT_PRIMARY,
            placeholder_text="Paste Lemon Squeezy license key",
        ).pack(padx=30, pady=6)

        ctk.CTkLabel(
            self,
            text=f"This device: {self.license.instance_label()[:48]}…",
            font=("Segoe UI", 9),
            text_color=TEXT_MUTED,
        ).pack(pady=(0, 4))

        self.msg = ctk.CTkLabel(
            self, text="", font=("Segoe UI", 11), text_color=TEXT_MUTED, wraplength=420
        )
        self.msg.pack(pady=4)

        ctk.CTkLabel(
            self,
            text=self.license.seat_status_text(),
            font=("Segoe UI", 11),
            text_color=NEON_PURPLE if self.license.is_pro else TEXT_MUTED,
        ).pack(pady=(0, 6))

        ctk.CTkLabel(
            self,
            text=(
                "Single-seat mode: only this PC uses Pro at a time "
                "(like one Netflix screen). Sharing the key does not unlock "
                "two machines at once."
            ),
            font=("Segoe UI", 10),
            text_color=TEXT_MUTED,
            wraplength=420,
            justify="center",
        ).pack(padx=20, pady=(0, 8))

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(pady=8)
        self.btn_act = ctk.CTkButton(
            row, text="Activate", width=100, fg_color=NEON_BLUE, command=self._activate
        )
        self.btn_act.pack(side="left", padx=4)
        self.btn_takeover = ctk.CTkButton(
            row,
            text="Take over this PC",
            width=130,
            fg_color=NEON_PURPLE,
            command=self._takeover,
        )
        self.btn_takeover.pack(side="left", padx=4)
        ctk.CTkButton(
            row,
            text="Buy Pro",
            width=90,
            fg_color="transparent",
            border_width=1,
            border_color=NEON_PURPLE,
            text_color=NEON_PURPLE,
            command=lambda: webbrowser.open(self.license.checkout_url()),
        ).pack(side="left", padx=4)

        row2 = ctk.CTkFrame(self, fg_color="transparent")
        row2.pack(pady=6)
        ctk.CTkButton(
            row2,
            text="Release seat",
            width=110,
            fg_color="transparent",
            border_width=1,
            border_color=BORDER_MUTED,
            text_color=TEXT_MUTED,
            command=self._deactivate,
        ).pack(side="left", padx=4)
        ctk.CTkButton(
            row2,
            text="Close",
            width=80,
            fg_color="transparent",
            border_width=1,
            border_color=BORDER_MUTED,
            text_color=TEXT_PRIMARY,
            command=self.destroy,
        ).pack(side="left", padx=4)

        if self.license.allow_dev_keys:
            ctk.CTkLabel(
                self,
                text="Dev: GV-PRO-DEV-UNLOCK  ·  set allow_dev_keys=false for release",
                font=("Segoe UI", 10),
                text_color=TEXT_MUTED,
            ).pack(pady=(8, 0))

    def _activate(self):
        import threading

        self.btn_act.configure(state="disabled", text="…")
        self.msg.configure(text="Contacting Lemon Squeezy…", text_color=TEXT_MUTED)

        def work():
            ok, message = self.license.activate(self.key_var.get())
            self.after(0, lambda: self._done(ok, message))

        threading.Thread(target=work, daemon=True).start()

    def _takeover(self):
        import threading

        self.btn_takeover.configure(state="disabled", text="…")
        self.msg.configure(
            text="Moving single seat to this PC (other device loses Pro)…",
            text_color=TEXT_MUTED,
        )

        def work():
            ok, message = self.license.take_over_device(self.key_var.get())
            self.after(0, lambda: self._done(ok, message, takeover=True))

        threading.Thread(target=work, daemon=True).start()

    def _done(self, ok, message, takeover=False):
        self.btn_act.configure(state="normal", text="Activate")
        self.btn_takeover.configure(state="normal", text="Take over this PC")
        self.msg.configure(text=message, text_color=NEON_GREEN if ok else NEON_RED)
        if ok:
            self.lbl_status.configure(text="Current plan: PRO ✓", text_color=NEON_GREEN)
            if hasattr(self.master, "refresh_license_ui"):
                self.master.refresh_license_ui()

    def _deactivate(self):
        import threading

        def work():
            ok, message = self.license.deactivate_online()

            def ui():
                self.msg.configure(
                    text=message, text_color=NEON_GREEN if ok else NEON_RED
                )
                self.lbl_status.configure(
                    text="Current plan: FREE", text_color=TEXT_MUTED
                )
                if hasattr(self.master, "refresh_license_ui"):
                    self.master.refresh_license_ui()

            self.after(0, ui)

        threading.Thread(target=work, daemon=True).start()


class DonateDialog(ctk.CTkToplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("Donate — SilenVault")
        self.geometry("460x360")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()
        self.configure(fg_color=DEEP_DARK)
        self.license = LicenseManager()

        ctk.CTkLabel(
            self,
            text="Support SilenVault",
            font=("Segoe UI", 16, "bold"),
            text_color=NEON_GREEN,
        ).pack(pady=(22, 8))

        ctk.CTkLabel(
            self,
            text=(
                "GrabbyVault has no ads and no tracking upsells.\n\n"
                "A donation is optional. It does not unlock Pro features.\n"
                "Pro is a separate license. Tips go to keeping SilenVault alive\n"
                "(store, tools, and this app).\n\n"
                "Suggested: whatever feels fair — $3, $5, or more."
            ),
            font=("Segoe UI", 12),
            text_color=TEXT_PRIMARY,
            justify="center",
        ).pack(padx=28, pady=6)

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(pady=16)
        ctk.CTkButton(
            row,
            text="Open donate page",
            width=150,
            height=36,
            fg_color=NEON_GREEN,
            text_color="#0a0a0c",
            font=("Segoe UI", 12, "bold"),
            command=lambda: webbrowser.open(self.license.donate_url()),
        ).pack(side="left", padx=8)
        ctk.CTkButton(
            row,
            text="Visit store",
            width=120,
            height=36,
            fg_color="transparent",
            border_width=1,
            border_color=NEON_BLUE,
            text_color=NEON_BLUE,
            command=lambda: webbrowser.open(self.license.store_url()),
        ).pack(side="left", padx=8)
        ctk.CTkButton(
            row,
            text="Close",
            width=90,
            height=36,
            fg_color="transparent",
            border_width=1,
            border_color=BORDER_MUTED,
            text_color=TEXT_PRIMARY,
            command=self.destroy,
        ).pack(side="left", padx=8)

        ctk.CTkLabel(
            self,
            text="store.silenvault.com/sponsor  ·  or your Lemon Squeezy tip product",
            font=("Segoe UI", 10),
            text_color=TEXT_MUTED,
        ).pack(pady=(4, 0))


class AboutDialog(ctk.CTkToplevel):
    """About + Developer tabs."""

    def __init__(self, master):
        super().__init__(master)
        self.title("About GrabbyVault")
        self.geometry("520x480")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()
        self.configure(fg_color=DEEP_DARK)
        self.lic = LicenseManager()

        ctk.CTkLabel(
            self, text="GrabbyVault", font=("Segoe UI", 18, "bold"), text_color=NEON_BLUE
        ).pack(pady=(16, 2))
        ctk.CTkLabel(
            self,
            text=f"by SilenVault  ·  {self.lic.tier_label()}",
            font=("Segoe UI", 12),
            text_color=NEON_PURPLE,
        ).pack()

        self.tabs = ctk.CTkTabview(
            self,
            width=480,
            height=340,
            fg_color=CARD_BG,
            segmented_button_selected_color=NEON_BLUE,
            segmented_button_selected_hover_color="#0099bb",
            segmented_button_unselected_color=INPUT_BG,
            text_color=TEXT_PRIMARY,
        )
        self.tabs.pack(padx=16, pady=12, fill="both", expand=True)
        self.tabs.add("About")
        self.tabs.add("Developer")
        self.tabs.add("Credits")

        # --- About ---
        about = self.tabs.tab("About")
        ctk.CTkLabel(
            about,
            text=(
                "Windows desktop downloader for personal offline use.\n"
                "Paste a link → pick quality → save to your folder.\n\n"
                "Free: 720p · 1 download at a time\n"
                "Pro: higher quality · multi-queue · no ads ever\n\n"
                "Only download content you have the right to access."
            ),
            font=("Segoe UI", 12),
            text_color=TEXT_PRIMARY,
            justify="left",
            wraplength=440,
        ).pack(anchor="w", padx=12, pady=12)

        brow = ctk.CTkFrame(about, fg_color="transparent")
        brow.pack(fill="x", padx=12, pady=4)
        ctk.CTkButton(
            brow, text="Store", width=100, command=lambda: webbrowser.open(self.lic.store_url())
        ).pack(side="left", padx=4)
        ctk.CTkButton(
            brow, text="Buy Pro", width=100, fg_color=NEON_PURPLE,
            command=lambda: webbrowser.open(self.lic.checkout_url()),
        ).pack(side="left", padx=4)
        ctk.CTkButton(
            brow, text="Donate", width=100, fg_color="transparent",
            border_width=1, border_color=NEON_GREEN, text_color=NEON_GREEN,
            command=lambda: webbrowser.open(self.lic.donate_url()),
        ).pack(side="left", padx=4)

        # --- Developer ---
        dev = self.tabs.tab("Developer")
        ctk.CTkLabel(
            dev,
            text="SilenVault",
            font=("Segoe UI", 14, "bold"),
            text_color=NEON_BLUE,
        ).pack(anchor="w", padx=12, pady=(12, 4))
        ctk.CTkLabel(
            dev,
            text=(
                "Indie studio building desktop tools and digital assets.\n"
                "Store: store.silenvault.com\n\n"
                f"Support: {self.lic.support_email()}\n"
                "Licensing: Lemon Squeezy (activate online once per device seat).\n\n"
                "Bug reports: use email with logs from Settings → Open Logs.\n"
                "Do not send license keys in public issues."
            ),
            font=("Segoe UI", 12),
            text_color=TEXT_PRIMARY,
            justify="left",
            wraplength=440,
        ).pack(anchor="w", padx=12, pady=4)

        drow = ctk.CTkFrame(dev, fg_color="transparent")
        drow.pack(fill="x", padx=12, pady=10)
        ctk.CTkButton(
            drow, text="Developer page", width=130,
            command=lambda: webbrowser.open(self.lic.developer_url()),
        ).pack(side="left", padx=4)
        ctk.CTkButton(
            drow, text="Open data folder", width=130,
            command=lambda: os.startfile(app_root()),
        ).pack(side="left", padx=4)

        ctk.CTkLabel(
            dev,
            text=f"Install path:\n{app_root()}",
            font=("Segoe UI", 10),
            text_color=TEXT_MUTED,
            justify="left",
            wraplength=440,
        ).pack(anchor="w", padx=12, pady=6)

        # --- Credits ---
        cred = self.tabs.tab("Credits")
        ctk.CTkLabel(
            cred,
            text=(
                "Core download engine: yt-dlp (open source)\n"
                "Media tooling: FFmpeg\n"
                "UI: CustomTkinter\n"
                "Browser fallback: Playwright\n"
                "Payments & license keys: Lemon Squeezy\n"
                "Brand & store: SilenVault\n\n"
                "Third-party tools are used under their respective licenses.\n"
                "GrabbyVault itself is a commercial SilenVault product."
            ),
            font=("Segoe UI", 12),
            text_color=TEXT_PRIMARY,
            justify="left",
            wraplength=440,
        ).pack(anchor="w", padx=12, pady=16)

        ctk.CTkButton(
            self, text="Close", width=100, command=self.destroy, fg_color=NEON_BLUE
        ).pack(pady=(0, 12))
