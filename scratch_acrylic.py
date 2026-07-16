import customtkinter as ctk
import pywinstyles

app = ctk.CTk()
app.geometry("400x300")
app.title("Acrylic Test")
app.overrideredirect(True)

# Set bg to a specific color
bg_color = "#000001"
app.configure(fg_color=bg_color)

# Apply acrylic
pywinstyles.apply_style(app, "acrylic")

# Make the bg color transparent to reveal the acrylic background
app.wm_attributes("-transparentcolor", bg_color)

btn = ctk.CTkButton(app, text="Close", command=app.destroy)
btn.pack(expand=True)

app.mainloop()
