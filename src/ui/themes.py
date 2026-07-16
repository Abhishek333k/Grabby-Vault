import customtkinter as ctk

# Cyberpunk Theme Constants
TRANSPARENT_KEY = "#000001" # Transparent color key for acrylic glassmorphism
DEEP_DARK = "#0a0a0f"       # Main background
CARD_BG = "#12121a"         # Frame/Card background
INPUT_BG = "#181822"        # Text input background
BORDER_MUTED = "#2a2a35"    # Standard inactive border
TEXT_PRIMARY = "#ffffff"    # Main high-contrast text
TEXT_MUTED = "#8a8a9a"      # Secondary/muted text

# Cyberpunk Accents
NEON_BLUE = "#00f3ff"       # Primary accent
NEON_PURPLE = "#b026ff"     # Secondary accent
NEON_GREEN = "#00ff9d"      # Success indicator
NEON_RED = "#ff003c"        # Error/danger indicator

def apply_cyberpunk_theme(app: ctk.CTk):
    """
    Applies the base dark mode appearance and sets the main window background.
    """
    ctk.set_appearance_mode("dark")
    app.configure(fg_color=DEEP_DARK)
