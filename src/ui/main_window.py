import customtkinter as ctk
import ctypes
import os
import sys
import uuid
from core.queue_manager import QueueManager
from core.url_router import URLRouter
from core.config_manager import ConfigManager
from core.downloader import Downloader
from ui.dialogs import (
    PlaylistSelectionDialog,
    FormatSelectionDialog,
    SettingsDialog,
    LicenseDialog,
    DonateDialog,
    AboutDialog,
)
from core.license_manager import LicenseManager
from ui.themes import (
    DEEP_DARK, CARD_BG, INPUT_BG, BORDER_MUTED, TEXT_PRIMARY, TEXT_MUTED,
    NEON_BLUE, NEON_PURPLE, NEON_GREEN, NEON_RED, apply_cyberpunk_theme
)
import threading
import queue
try:
    import pywinstyles
except ImportError:
    pywinstyles = None

class MainWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        # Configure window settings
        self.title("GrabbyVault")
        self.geometry("900x650")
        self.minsize(850, 550)
        
        # Frameless window
        self.overrideredirect(True)
        
        # Apply true glass blur behind the window
        if pywinstyles:
            pywinstyles.apply_style(self, "acrylic")
            
        # Set window opacity so the acrylic blur shines through
        self.attributes("-alpha", 0.88)
        
        # Set up cyberpunk dark theme
        apply_cyberpunk_theme(self)
        self.configure(fg_color=DEEP_DARK)
        
        # Dragging variables
        self.drag_data = {"x": 0, "y": 0}
        self.is_maximized = False
        self.normal_geometry = "900x650+100+100"
        
        # UI Event Queue
        self.ui_queue = queue.Queue()
        
        # Download Queue State
        self.queue_cards = {}  # Map job_id to UI elements
        
        # Initialize QueueManager with callbacks
        self.queue_manager = QueueManager(ui_callbacks={
            'on_start': self._on_download_start,
            'on_progress': self._on_download_progress,
            'on_finish': self._on_download_finish,
            'on_error': self._on_download_error
        })
        
        # Start UI event poller
        self._process_ui_events()
        
        # Enable Windows taskbar integration (adds app icon & window grouping)
        self.after(10, self._enable_taskbar_integration)
        
        # Callback for when app closing is requested (will minimize to system tray)
        self.on_close_callback = None
        
        self.license = LicenseManager()

        # Create all layout components
        self._create_layout()
        self.refresh_license_ui()

        # Load persistent jobs into UI
        self.after(100, self._load_persistent_jobs)

    def _load_persistent_jobs(self):
        for job_id, job in self.queue_manager.jobs.items():
            if job['status'] not in ('finished', 'cancelled'):
                title = job['metadata'].get('title', 'Unknown Video')
                platform = job.get('platform', 'Unknown')
                self._add_queue_item(job_id, f"{title} (Restored)", platform)
                # Set initial status
                status = job['status']
                card = self.queue_cards[job_id]
                if status == 'paused':
                    card['lbl_status'].configure(text="Paused", text_color=TEXT_MUTED)
                    card['btn_pause'].configure(text="▶", text_color=NEON_GREEN)
                elif status == 'error':
                    card['lbl_status'].configure(text="Error", text_color=NEON_RED)
                    
    def _enable_taskbar_integration(self):
        """
        Force Windows OS to register this borderless window in the taskbar.
        """
        if os.name == 'nt':
            try:
                # GWL_EXSTYLE = -20
                # WS_EX_APPWINDOW = 0x00040000 (shows in taskbar)
                # WS_EX_TOOLWINDOW = 0x00000080 (hides from taskbar)
                hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
                style = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
                style = style & ~0x00000080
                style = style | 0x00040000
                ctypes.windll.user32.SetWindowLongW(hwnd, -20, style)
                
                # Re-map the window to force-apply the styles
                self.withdraw()
                self.deiconify()
            except Exception as e:
                print(f"Error configuring taskbar integration: {e}", file=sys.stderr)

    def _create_layout(self):
        # Configure grid system for the main window
        self.grid_rowconfigure(1, weight=1)  # Main content row expands
        self.grid_columnconfigure(0, weight=1)
        
        # 1. Custom Header Bar (for logo and settings)
        self.title_bar = ctk.CTkFrame(self, height=45, fg_color="transparent", corner_radius=0)
        self.title_bar.grid(row=0, column=0, sticky="ew")
        self.title_bar.grid_propagate(False)
        
        # Title text
        self.title_label = ctk.CTkLabel(
            self.title_bar, 
            text="GrabbyVault", 
            font=("Segoe UI", 16, "bold"), 
            text_color=NEON_BLUE
        )
        self.title_label.pack(side="left", padx=(15, 6))

        self.tier_badge = ctk.CTkLabel(
            self.title_bar,
            text="FREE",
            font=("Segoe UI", 11, "bold"),
            text_color=TEXT_MUTED,
            fg_color="#1a1a22",
            corner_radius=4,
            width=48,
            height=22,
        )
        self.tier_badge.pack(side="left", padx=(0, 8))
        
        # Bind dragging
        self.title_bar.bind("<ButtonPress-1>", self._start_drag)
        self.title_bar.bind("<B1-Motion>", self._drag_window)
        self.title_label.bind("<ButtonPress-1>", self._start_drag)
        self.title_label.bind("<B1-Motion>", self._drag_window)
        
        btn_opts = {"width": 30, "height": 30, "fg_color": "transparent", "hover_color": "#1f1f24", "corner_radius": 4}
        
        # Window Controls
        self.btn_close = ctk.CTkButton(self.title_bar, text="✕", text_color=TEXT_PRIMARY, font=("Segoe UI", 14), command=self._handle_close, **btn_opts)
        self.btn_close.pack(side="right", padx=(5, 10), pady=7)
        
        self.btn_max = ctk.CTkButton(self.title_bar, text="▢", text_color=TEXT_PRIMARY, font=("Segoe UI", 14), command=self._toggle_maximize, **btn_opts)
        self.btn_max.pack(side="right", padx=2, pady=7)
        
        self.btn_min = ctk.CTkButton(self.title_bar, text="—", text_color=TEXT_PRIMARY, font=("Segoe UI", 14), command=self._minimize, **btn_opts)
        self.btn_min.pack(side="right", padx=2, pady=7)
        
        # Settings / Pro / Donate
        self.btn_settings = ctk.CTkButton(self.title_bar, text="⚙", text_color=TEXT_PRIMARY, font=("Segoe UI", 14), command=self._open_settings, **btn_opts)
        self.btn_settings.pack(side="right", padx=(4, 10), pady=7)

        self.btn_about = ctk.CTkButton(self.title_bar, text="ⓘ", text_color=TEXT_PRIMARY, font=("Segoe UI", 14), command=self._open_about, **btn_opts)
        self.btn_about.pack(side="right", padx=2, pady=7)

        self.btn_donate = ctk.CTkButton(
            self.title_bar, text="♥", text_color=NEON_GREEN, font=("Segoe UI", 14),
            command=self._open_donate, **btn_opts
        )
        self.btn_donate.pack(side="right", padx=2, pady=7)

        self.btn_pro = ctk.CTkButton(
            self.title_bar, text="Pro", width=44, height=28,
            fg_color=NEON_PURPLE, text_color=TEXT_PRIMARY, hover_color="#7a00cc",
            font=("Segoe UI", 12, "bold"), corner_radius=6,
            command=self._open_license,
        )
        self.btn_pro.pack(side="right", padx=6, pady=7)
        
        # 2. Main Content Frame
        self.content_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.content_frame.grid(row=1, column=0, sticky="nsew", padx=20, pady=20)
        self.content_frame.grid_columnconfigure(0, weight=1)
        self.content_frame.grid_rowconfigure(1, weight=1)
        
        # URL Input Section
        self._build_url_section()
        
        # Queue Section
        self._build_queue_section()
        
        # 3. Bottom Status Bar
        self.status_bar = ctk.CTkFrame(self, height=25, fg_color="transparent", corner_radius=0)
        self.status_bar.grid(row=2, column=0, sticky="ew")
        
        self.status_left = ctk.CTkLabel(
            self.status_bar, 
            text="System Ready | Network Connected", 
            font=("Segoe UI", 11), 
            text_color=TEXT_MUTED
        )
        self.status_left.pack(side="left", padx=15)
        
        self.status_right = ctk.CTkLabel(
            self.status_bar, 
            text="Speed: 0.0 KB/s", 
            font=("Segoe UI", 11), 
            text_color=NEON_PURPLE
        )
        self.status_right.pack(side="right", padx=(15, 5))
        
        # Resize Grip
        self.resize_grip = ctk.CTkLabel(self.status_bar, text="⤡", text_color=TEXT_MUTED, font=("Segoe UI", 14), width=15, cursor="size_nw_se")
        self.resize_grip.pack(side="right", padx=(0, 5))
        self.resize_grip.bind("<ButtonPress-1>", self._start_resize)
        self.resize_grip.bind("<B1-Motion>", self._drag_resize)

    def _build_url_section(self):
        url_frame = ctk.CTkFrame(
            self.content_frame, 
            fg_color="transparent", 
            border_width=1, 
            border_color=BORDER_MUTED,
            corner_radius=8
        )
        url_frame.grid(row=0, column=0, sticky="ew", pady=(0, 15))
        url_frame.grid_columnconfigure(0, weight=1)
        
        # URL Field Label (Cyberpunk styling)
        lbl = ctk.CTkLabel(
            url_frame, 
            text="Input Source Link", 
            font=("Segoe UI", 12, "bold"), 
            text_color=NEON_PURPLE
        )
        lbl.grid(row=0, column=0, columnspan=3, sticky="w", padx=15, pady=(10, 5))
        
        # Text Input
        self.url_input = ctk.CTkEntry(
            url_frame,
            placeholder_text="Paste your video, audio, or playlist URL here...",
            fg_color=INPUT_BG,
            border_color=BORDER_MUTED,
            text_color=TEXT_PRIMARY,
            placeholder_text_color=TEXT_MUTED,
            font=("Segoe UI", 12),
            height=38
        )
        self.url_input.grid(row=1, column=0, sticky="ew", padx=(15, 10), pady=(0, 15))
        
        self.priority_var = ctk.StringVar(value="Normal")
        self.priority_menu = ctk.CTkOptionMenu(
            url_frame,
            values=["High", "Normal", "Low"],
            variable=self.priority_var,
            width=90,
            height=38,
            fg_color=INPUT_BG,
            button_color=BORDER_MUTED,
            button_hover_color="#2b2b32",
            font=("Segoe UI", 12)
        )
        self.priority_menu.grid(row=1, column=1, padx=5, pady=(0, 15))
        
        # Paste Button
        self.btn_paste = ctk.CTkButton(
            url_frame,
            text="Paste",
            width=70,
            height=38,
            fg_color="transparent",
            border_width=1,
            border_color=NEON_PURPLE,
            text_color=NEON_PURPLE,
            hover_color="#262626",
            font=("Segoe UI", 12, "bold"),
            command=self._handle_paste
        )
        self.btn_paste.grid(row=1, column=2, padx=5, pady=(0, 15))
        
        # Add to Queue Button
        self.btn_add = ctk.CTkButton(
            url_frame,
            text="Add to Queue",
            width=130,
            height=38,
            fg_color=NEON_BLUE,
            text_color=TEXT_PRIMARY,
            hover_color="#005999",
            font=("Segoe UI", 12, "bold"),
            command=self._handle_add_to_queue
        )
        self.btn_add.grid(row=1, column=3, padx=(5, 15), pady=(0, 15))

    def _build_queue_section(self):
        queue_container = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        queue_container.grid(row=1, column=0, sticky="nsew")
        queue_container.grid_columnconfigure(0, weight=1)
        queue_container.grid_rowconfigure(1, weight=1)
        
        # Header
        header_frame = ctk.CTkFrame(queue_container, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        
        lbl_queue = ctk.CTkLabel(
            header_frame, 
            text="Active Download Queue", 
            font=("Segoe UI", 14, "bold"), 
            text_color=NEON_BLUE
        )
        lbl_queue.pack(side="left")
        
        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", self._filter_queue)
        self.search_input = ctk.CTkEntry(
            header_frame,
            placeholder_text="Search queue...",
            textvariable=self.search_var,
            width=150,
            height=28,
            fg_color=INPUT_BG,
            border_color=BORDER_MUTED,
            text_color=TEXT_PRIMARY,
            font=("Segoe UI", 12)
        )
        self.search_input.pack(side="left", padx=20)
        
        self.lbl_count = ctk.CTkLabel(
            header_frame, 
            text="0 Jobs", 
            font=("Segoe UI", 12), 
            text_color=TEXT_MUTED
        )
        self.lbl_count.pack(side="right")
        
        # Scrollable list
        self.queue_scroll = ctk.CTkScrollableFrame(
            queue_container,
            fg_color="transparent",
            border_width=1,
            border_color=BORDER_MUTED,
            corner_radius=8
        )
        self.queue_scroll.grid(row=1, column=0, sticky="nsew")

    def _add_queue_item(self, job_id, title, platform="Unknown", thumbnail_url=None):
        card = ctk.CTkFrame(
            self.queue_scroll, 
            fg_color="transparent", 
            border_width=1, 
            border_color=BORDER_MUTED,
            corner_radius=6
        )
        card.pack(fill="x", pady=5, padx=5)
        
        info_frame = ctk.CTkFrame(card, fg_color="transparent")
        info_frame.pack(fill="x", padx=12, pady=(8, 4))
        
        # Thumbnail container (REMOVED)
        
        lbl_platform = ctk.CTkLabel(
            info_frame,
            text=f"{platform}",
            font=("Segoe UI", 11, "bold"),
            text_color=NEON_PURPLE
        )
        lbl_platform.pack(side="left", padx=(0, 8))
        
        lbl_title = ctk.CTkLabel(
            info_frame, 
            text=title, 
            font=("Segoe UI", 12, "bold"), 
            text_color=TEXT_PRIMARY,
            anchor="w"
        )
        lbl_title.pack(side="left")
        
        lbl_status = ctk.CTkLabel(
            info_frame, 
            text="Queued", 
            font=("Segoe UI", 11), 
            text_color=NEON_PURPLE
        )
        lbl_status.pack(side="right")
        
        pb_frame = ctk.CTkFrame(card, fg_color="transparent")
        pb_frame.pack(fill="x", padx=12, pady=(0, 8))
        
        pb = ctk.CTkProgressBar(
            pb_frame, 
            progress_color=NEON_BLUE,
            fg_color="#181822",
            height=6
        )
        pb.pack(side="left", fill="x", expand=True, padx=(0, 10))
        pb.set(0)
        
        btn_action = ctk.CTkButton(
            pb_frame,
            text="✕",
            width=24,
            height=24,
            fg_color="transparent",
            hover_color="#1f1f26",
            text_color=NEON_RED,
            font=("Segoe UI", 12),
            command=lambda j=job_id: self._handle_cancel(j)
        )
        btn_action.pack(side="right")
        
        btn_pause = ctk.CTkButton(
            pb_frame,
            text="⏸",
            width=24,
            height=24,
            fg_color="transparent",
            hover_color="#1f1f26",
            text_color=NEON_BLUE,
            font=("Segoe UI", 12),
            command=lambda j=job_id: self._handle_pause_resume(j)
        )
        btn_pause.pack(side="right", padx=(0, 5))
        
        btn_locate = ctk.CTkButton(
            pb_frame,
            text="📁",
            width=24,
            height=24,
            fg_color="transparent",
            hover_color="#1f1f26",
            text_color=NEON_GREEN,
            font=("Segoe UI", 12),
        )
        # Not packed initially, only on finish
        
        self.queue_cards[job_id] = {
            'card': card,
            'title': title.lower(),
            'pb': pb,
            'lbl_status': lbl_status,
            'btn_action': btn_action,
            'btn_pause': btn_pause,
            'btn_locate': btn_locate
        }
        self._update_job_count()

    def _update_job_count(self):
        count = len(self.queue_cards)
        self.lbl_count.configure(text=f"{count} Jobs")

    # QueueManager Callbacks
    def _on_download_start(self, job_id):
        self.ui_queue.put(('start', job_id))
        
    def _update_ui_start(self, job_id):
        if job_id in self.queue_cards:
            card = self.queue_cards[job_id]
            card['lbl_status'].configure(text="Downloading...", text_color=NEON_BLUE)
            card['pb'].configure(progress_color=NEON_BLUE)

    def _on_download_progress(self, job_id, d):
        self.ui_queue.put(('progress', job_id, d))
        
    def _update_ui_progress(self, job_id, d):
        if job_id not in self.queue_cards:
            return
            
        card = self.queue_cards[job_id]
        
        if d['status'] == 'downloading':
            try:
                downloaded_bytes = d.get('downloaded_bytes', 0)
                total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                speed = d.get('speed', 0)
                
                percent = (downloaded_bytes / total_bytes) if total_bytes else 0
                speed_str = f"{speed / 1024 / 1024:.1f} MB/s" if speed else "Unknown speed"
                
                if total_bytes:
                    status_text = f"Downloading... {downloaded_bytes / 1024 / 1024:.1f}MB / {total_bytes / 1024 / 1024:.1f}MB ({int(percent * 100)}%)"
                else:
                    status_text = f"Downloading... {downloaded_bytes / 1024 / 1024:.1f}MB ({int(percent * 100)}%)"
                
                card['pb'].set(percent)
                card['lbl_status'].configure(text=status_text)
                self.status_right.configure(text=f"Speed: {speed_str}")
            except Exception as e:
                print(f"Error parsing progress: {e}")
        elif d['status'] == 'finished':
            card['lbl_status'].configure(text="Merging fragments...", text_color=NEON_BLUE)
            card['pb'].set(1.0)
            self.status_right.configure(text=f"Speed: 0.0 MB/s")

    def _on_download_finish(self, job_id):
        self.ui_queue.put(('finish', job_id))

    def _update_ui_finish(self, job_id):
        if job_id in self.queue_cards:
            card = self.queue_cards[job_id]
            card['lbl_status'].configure(text="Completed", text_color=NEON_GREEN)
            card['pb'].set(1.0)
            card['pb'].configure(progress_color=NEON_GREEN)
            card['btn_action'].configure(state="normal", text="🗑", text_color=TEXT_MUTED, command=lambda j=job_id: self._handle_remove(j))
            # Enable locate button if we add one later
            if 'btn_locate' in card:
                import subprocess
                def open_folder():
                    job_data = self.queue_manager.db.get_job(job_id)
                    filepath = job_data.get('filepath') if job_data else None
                    if filepath and os.path.exists(filepath):
                        # Use explorer /select to highlight the file
                        subprocess.Popen(f'explorer /select,"{os.path.normpath(filepath)}"')
                    elif filepath and os.path.exists(os.path.dirname(filepath)):
                        os.startfile(os.path.dirname(filepath))
                card['btn_locate'].configure(command=open_folder)
                card['btn_locate'].pack(side="right", padx=5)

    def _on_download_error(self, job_id, error_msg):
        self.ui_queue.put(('error', job_id, error_msg))

    def _update_ui_error(self, job_id, error_msg):
        if job_id in self.queue_cards:
            card = self.queue_cards[job_id]
            if error_msg == "Cancelled":
                card['lbl_status'].configure(text="Cancelled", text_color=TEXT_MUTED)
                card['pb'].configure(progress_color=TEXT_MUTED)
                card['btn_action'].configure(state="normal", text="🗑", text_color=TEXT_MUTED, command=lambda j=job_id: self._handle_remove(j))
            elif error_msg == "Paused":
                card['lbl_status'].configure(text="Paused", text_color=TEXT_MUTED)
                card['pb'].configure(progress_color=TEXT_MUTED)
            else:
                short_error = error_msg.split('\n')[0][:50]
                card['lbl_status'].configure(text=f"Error: {short_error}...", text_color=NEON_RED)
                card['pb'].configure(progress_color=NEON_RED)
                card['btn_action'].configure(state="normal", text="🗑", text_color=TEXT_MUTED, command=lambda j=job_id: self._handle_remove(j))

    def _process_ui_events(self):
        try:
            while True:
                event = self.ui_queue.get_nowait()
                msg_type = event[0]
                if msg_type == 'start':
                    self._update_ui_start(event[1])
                elif msg_type == 'progress':
                    self._update_ui_progress(event[1], event[2])
                elif msg_type == 'finish':
                    self._update_ui_finish(event[1])
                elif msg_type == 'error':
                    self._update_ui_error(event[1], event[2])
                self.ui_queue.task_done()
        except queue.Empty:
            pass
        self.after(50, self._process_ui_events)

    def _handle_cancel(self, job_id):
        print(f"[UI] Cancelling job: {job_id}")
        self.queue_manager.cancel_job(job_id)
        if job_id in self.queue_cards:
            card = self.queue_cards[job_id]
            card['lbl_status'].configure(text="Cancelling...", text_color=TEXT_MUTED)
            card['btn_action'].configure(state="disabled")
            
            # Force UI update if stuck
            self.after(2000, lambda: self._update_ui_error(job_id, "Cancelled") if self.queue_manager.jobs.get(job_id, {}).get('status') == 'cancelled' else None)

    def _handle_remove(self, job_id):
        self.queue_manager.delete_job(job_id)
        if job_id in self.queue_cards:
            self.queue_cards[job_id]['card'].destroy()
            del self.queue_cards[job_id]
            self._update_job_count()

    def _open_settings(self):
        SettingsDialog(self, self.queue_manager)

    def _open_license(self):
        LicenseDialog(self)

    def _open_donate(self):
        DonateDialog(self)

    def _open_about(self):
        AboutDialog(self)

    def refresh_license_ui(self):
        """Update FREE/PRO badge after activation."""
        self.license = LicenseManager()
        if not hasattr(self, "tier_badge"):
            return
        if self.license.is_pro:
            self.tier_badge.configure(text="PRO", text_color=NEON_GREEN)
            self.btn_pro.configure(text="Pro ✓", fg_color="#1a3d2a")
        else:
            self.tier_badge.configure(text="FREE", text_color=TEXT_MUTED)
            self.btn_pro.configure(text="Pro", fg_color=NEON_PURPLE)
        # Status bar plan hint
        if hasattr(self, "status_left"):
            plan = self.license.tier_label()
            self.status_left.configure(text=f"SYSTEM READY · {plan}")

    def _filter_queue(self, *args):
        query = self.search_var.get().lower()
        for job_id, card_data in self.queue_cards.items():
            if query in card_data['title']:
                card_data['card'].pack(fill="x", pady=5, padx=5)
            else:
                card_data['card'].pack_forget()

    def _handle_pause_resume(self, job_id):
        if job_id not in self.queue_cards: return
        card = self.queue_cards[job_id]
        
        btn = card['btn_pause']
        if btn.cget("text") == "⏸":
            print(f"[UI] Pausing job: {job_id}")
            self.queue_manager.pause_job(job_id)
            btn.configure(text="▶", text_color=NEON_GREEN)
            card['lbl_status'].configure(text="Pausing...", text_color=TEXT_MUTED)
        else:
            print(f"[UI] Resuming job: {job_id}")
            self.queue_manager.resume_job(job_id)
            btn.configure(text="⏸", text_color=NEON_BLUE)
            card['lbl_status'].configure(text="Queued", text_color=NEON_PURPLE)

    # Drag Handlers (Smooth Screen-Relative Logic)
    def _start_drag(self, event):
        self.drag_data["x"] = event.x_root - self.winfo_x()
        self.drag_data["y"] = event.y_root - self.winfo_y()

    def _drag_window(self, event):
        if self.is_maximized:
            return  # Prevent dragging while maximized
        x = event.x_root - self.drag_data["x"]
        y = event.y_root - self.drag_data["y"]
        self.geometry(f"+{x}+{y}")
        
    def _start_resize(self, event):
        self.resize_data = {"x": event.x_root, "y": event.y_root, "w": self.winfo_width(), "h": self.winfo_height()}

    def _drag_resize(self, event):
        dx = event.x_root - self.resize_data["x"]
        dy = event.y_root - self.resize_data["y"]
        new_w = max(self.minsize()[0], self.resize_data["w"] + dx)
        new_h = max(self.minsize()[1], self.resize_data["h"] + dy)
        self.geometry(f"{new_w}x{new_h}")

    # Window Actions
    def _toggle_maximize(self):
        if not self.is_maximized:
            self.normal_geometry = self.geometry()
            self.state('zoomed')
            self.is_maximized = True
            self.btn_max.configure(text="❐")
        else:
            self.state('normal')
            self.geometry(self.normal_geometry)
            self.is_maximized = False
            self.btn_max.configure(text="▢")

    def _minimize(self):
        try:
            hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
            ctypes.windll.user32.ShowWindow(hwnd, 6) # SW_MINIMIZE = 6
        except Exception as e:
            print(f"Minimize failed: {e}")
            # fallback
            self.withdraw()

    def _handle_close(self):
        if self.on_close_callback:
            self.on_close_callback()
        else:
            self.destroy()

    # Button Callbacks
    def _handle_paste(self):
        try:
            clipboard = self.clipboard_get()
            self.url_input.delete(0, 'end')
            self.url_input.insert(0, clipboard)
            print("[UI] Clipboard pasted into input field.")
        except Exception:
            print("[UI] Paste failed - Clipboard is empty or contains non-text content.")

    def _handle_add_to_queue(self):
        url = self.url_input.get().strip()
        if url:
            print(f"[UI] Adding link to download queue: {url}")
            self.url_input.delete(0, 'end')
            
            # Show a temporary fetching state
            self.status_left.configure(text="FETCHING METADATA...")
            
            def info_callback(success, data):
                def update_ui():
                    if success:
                        self.status_left.configure(text="SYSTEM READY // NET_CONNECTED")
                        _type = data.get('_type', 'video')
                        platform = URLRouter.get_platform(url)
                        p_map = {"High": 0, "Normal": 1, "Low": 2}
                        pri = p_map.get(self.priority_var.get(), 1)
                        
                        if _type == 'playlist':
                            entries = data.get('entries', [])
                            is_playwright = data.get('extractor') == 'playwright'
                            
                            def on_playlist_submit(selected_entries):
                                if not selected_entries: return
                                
                                def queue_selected(fmt_str):
                                    playlist_title = data.get('title', 'Playlist')
                                    for entry in selected_entries:
                                        entry_url = entry.get('url', entry.get('webpage_url', ''))
                                        if not entry_url: continue
                                        title = entry.get('title', 'Unknown Video')
                                        job_id = str(uuid.uuid4())
                                        thumb = entry.get('thumbnail', '')
                                        
                                        # Always use the chosen quality preset (even for Playwright
                                        # direct streams / m3u8). Old code forced 'best', which often
                                        # grabbed the lowest HLS rung → pixelated / silent files.
                                        final_fmt = fmt_str
                                        
                                        entry['id'] = job_id
                                        # Inject playlist_title for folder grouping
                                        entry['playlist_title'] = playlist_title
                                        
                                        self._add_queue_item(job_id, f"{title} [{entry.get('ext', 'unknown')}]", platform, thumbnail_url=thumb)
                                        _jid, warning = self.queue_manager.add_job(
                                            entry_url, entry, priority=pri,
                                            format_str=final_fmt, platform=platform,
                                        )
                                        if warning:
                                            self.status_left.configure(text=warning[:80])
                                        
                                # Always ask quality — applies to Playwright streams too
                                FormatSelectionDialog(
                                    self,
                                    title=f"Format for Playlist ({len(selected_entries)} items)",
                                    on_submit=queue_selected,
                                )
                                
                            dialog_title = "Select Alternative Streams" if is_playwright else "Select Videos"
                            PlaylistSelectionDialog(self, entries, on_submit=on_playlist_submit)
                        else:
                            def on_format_submit(fmt_str):
                                title = data.get('title', 'Unknown Video')
                                job_id = str(uuid.uuid4())
                                thumb = data.get('thumbnail')
                                self._add_queue_item(job_id, f"{title} [{data.get('ext', 'unknown')}]", platform, thumbnail_url=thumb)
                                
                                meta = data.copy()
                                meta['id'] = job_id
                                _jid, warning = self.queue_manager.add_job(
                                    url, meta, priority=pri,
                                    format_str=fmt_str, platform=platform,
                                )
                                if warning:
                                    self.status_left.configure(text=warning[:80])
                            FormatSelectionDialog(self, title="Format for Video", on_submit=on_format_submit)
                    else:
                        print(f"[UI] Failed to fetch info: {data}")
                        short_error = data.split('\n')[0][:60]
                        self.status_left.configure(text=f"ERROR: {short_error.upper()}...")
                self.after(0, update_ui)

            def status_cb(msg):
                self.after(0, lambda: self.status_left.configure(text=msg.upper()))
                
            self.queue_manager.fetch_info_async(url, info_callback, status_callback=status_cb)
        else:
            print("[UI] Add to Queue clicked, but URL field is empty.")
