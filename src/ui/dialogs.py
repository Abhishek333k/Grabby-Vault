import customtkinter as ctk
import os
from core.config_manager import ConfigManager
from ui.themes import (
    DEEP_DARK, CARD_BG, INPUT_BG, BORDER_MUTED, TEXT_PRIMARY, TEXT_MUTED,
    NEON_BLUE, NEON_PURPLE, NEON_GREEN, NEON_RED
)

class FormatSelectionDialog(ctk.CTkToplevel):
    def __init__(self, master, title="Select Quality", on_submit=None):
        super().__init__(master)
        self.title(title)
        self.geometry("350x300")
        self.resizable(False, False)
        
        # Make modal
        self.transient(master)
        self.grab_set()
        
        self.on_submit = on_submit
        self.selected_format = ctk.StringVar(value="bestvideo+bestaudio/best")
        
        self.configure(fg_color=DEEP_DARK)
        
        lbl = ctk.CTkLabel(self, text="Select Download Quality", font=("Segoe UI", 16, "bold"), text_color=NEON_BLUE)
        lbl.pack(pady=(20, 15))
        
        formats = [
            ("Best Quality (Default)", "bestvideo+bestaudio/best"),
            ("4K (2160p)", "bestvideo[height<=2160]+bestaudio/best"),
            ("1080p", "bestvideo[height<=1080]+bestaudio/best"),
            ("720p", "bestvideo[height<=720]+bestaudio/best"),
            ("Audio Only (MP3)", "bestaudio/best")
        ]
        
        for text, val in formats:
            rb = ctk.CTkRadioButton(
                self, 
                text=text, 
                value=val, 
                variable=self.selected_format,
                font=("Segoe UI", 12),
                text_color=TEXT_PRIMARY,
                fg_color=NEON_PURPLE,
                hover_color="#3e3e42"
            )
            rb.pack(anchor="w", padx=40, pady=8)
            
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=20)
        
        btn_confirm = ctk.CTkButton(
            btn_frame, text="Confirm", width=100,
            fg_color=NEON_BLUE, text_color=TEXT_PRIMARY, hover_color="#005999", font=("Segoe UI", 12, "bold"),
            command=self._confirm
        )
        btn_confirm.pack(side="left", padx=10)
        
        btn_cancel = ctk.CTkButton(
            btn_frame, text="Cancel", width=100,
            fg_color="transparent", border_width=1, border_color=NEON_RED, text_color=NEON_RED, hover_color="#3d2a2a", font=("Segoe UI", 12, "bold"),
            command=self.destroy
        )
        btn_cancel.pack(side="left", padx=10)
        
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
        
        # Make modal
        self.transient(master)
        self.grab_set()
        
        self.on_submit = on_submit
        self.entries = entries
        self.checkbox_vars = {}
        
        self.configure(fg_color=DEEP_DARK)
        
        lbl = ctk.CTkLabel(self, text="Select Playlist Items", font=("Segoe UI", 16, "bold"), text_color=NEON_BLUE)
        lbl.pack(pady=(20, 10))
        
        self.scroll = ctk.CTkScrollableFrame(self, fg_color=CARD_BG, border_width=1, border_color=BORDER_MUTED)
        self.scroll.pack(fill="both", expand=True, padx=20, pady=10)
        
        for idx, entry in enumerate(self.entries):
            title = entry.get("title", f"Video {idx+1}")
            var = ctk.BooleanVar(value=True)
            self.checkbox_vars[idx] = var
            
            cb = ctk.CTkCheckBox(
                self.scroll, 
                text=title, 
                variable=var,
                font=("Segoe UI", 12),
                text_color=TEXT_PRIMARY,
                fg_color=NEON_PURPLE,
                hover_color="#3e3e42"
            )
            cb.pack(anchor="w", padx=10, pady=5)
            
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", pady=10, padx=20)
        
        btn_all = ctk.CTkButton(
            btn_frame, text="Select All", width=90, height=30,
            fg_color="transparent", border_width=1, border_color=TEXT_MUTED, text_color=TEXT_MUTED, font=("Segoe UI", 11), hover_color="#3e3e42",
            command=self._select_all
        )
        btn_all.pack(side="left", padx=5)
        
        btn_none = ctk.CTkButton(
            btn_frame, text="Select None", width=90, height=30,
            fg_color="transparent", border_width=1, border_color=TEXT_MUTED, text_color=TEXT_MUTED, font=("Segoe UI", 11), hover_color="#3e3e42",
            command=self._select_none
        )
        btn_none.pack(side="left", padx=5)
        
        btn_confirm = ctk.CTkButton(
            btn_frame, text="Confirm", width=100, height=30,
            fg_color=NEON_BLUE, text_color=TEXT_PRIMARY, hover_color="#005999", font=("Segoe UI", 12, "bold"),
            command=self._confirm
        )
        btn_confirm.pack(side="right", padx=5)
        
    def _select_all(self):
        for var in self.checkbox_vars.values():
            var.set(True)
            
    def _select_none(self):
        for var in self.checkbox_vars.values():
            var.set(False)
            
    def _confirm(self):
        selected_entries = []
        for idx, entry in enumerate(self.entries):
            if self.checkbox_vars[idx].get():
                selected_entries.append(entry)
                
        if self.on_submit:
            self.on_submit(selected_entries)
        self.destroy()

class SettingsDialog(ctk.CTkToplevel):
    def __init__(self, master, queue_manager):
        super().__init__(master)
        self.title("Settings")
        self.geometry("400x300")
        self.resizable(False, False)
        
        self.transient(master)
        self.grab_set()
        
        self.queue_manager = queue_manager
        self.config = ConfigManager()
        
        self.configure(fg_color=DEEP_DARK)
        
        lbl = ctk.CTkLabel(self, text="Settings", font=("Segoe UI", 16, "bold"), text_color=NEON_BLUE)
        lbl.pack(pady=(20, 15))
        
        # Download Path
        path_frame = ctk.CTkFrame(self, fg_color="transparent")
        path_frame.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkLabel(path_frame, text="Download Path:", font=("Segoe UI", 12), text_color=TEXT_PRIMARY).pack(anchor="w")
        
        self.path_var = ctk.StringVar(value=self.config.get("download_path", os.path.abspath("downloads")))
        path_input = ctk.CTkEntry(path_frame, textvariable=self.path_var, width=280, fg_color=INPUT_BG, border_color=BORDER_MUTED, text_color=TEXT_PRIMARY)
        path_input.pack(side="left", pady=5)
        
        btn_browse = ctk.CTkButton(path_frame, text="...", width=30, fg_color=NEON_PURPLE, text_color=TEXT_PRIMARY, hover_color="#2b8ebd", command=self._browse)
        btn_browse.pack(side="left", padx=10, pady=5)
        
        # Concurrency
        conc_frame = ctk.CTkFrame(self, fg_color="transparent")
        conc_frame.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkLabel(conc_frame, text="Max Concurrent Downloads (1-5):", font=("Segoe UI", 12), text_color=TEXT_PRIMARY).pack(anchor="w")
        
        self.conc_var = ctk.StringVar(value=str(self.config.get("max_concurrent_downloads", 2)))
        conc_menu = ctk.CTkOptionMenu(conc_frame, values=["1", "2", "3", "4", "5"], variable=self.conc_var, fg_color=INPUT_BG, button_color=BORDER_MUTED)
        conc_menu.pack(anchor="w", pady=5)
        
        # Buttons
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", pady=20)
        
        btn_save = ctk.CTkButton(btn_frame, text="Save", width=100, fg_color=NEON_GREEN, text_color=TEXT_PRIMARY, hover_color="#367c39", font=("Segoe UI", 12, "bold"), command=self._save)
        btn_save.pack(side="left", padx=(40, 10))
        
        btn_cancel = ctk.CTkButton(btn_frame, text="Cancel", width=100, fg_color="transparent", border_width=1, border_color=NEON_RED, text_color=NEON_RED, hover_color="#3d2a2a", font=("Segoe UI", 12, "bold"), command=self.destroy)
        btn_cancel.pack(side="right", padx=(10, 40))

    def _browse(self):
        directory = ctk.filedialog.askdirectory(title="Select Download Folder")
        if directory:
            self.path_var.set(directory)

    def _save(self):
        self.config.set("download_path", self.path_var.get())
        self.config.set("max_concurrent_downloads", int(self.conc_var.get()))
        self.queue_manager.apply_settings_change()
        self.destroy()
