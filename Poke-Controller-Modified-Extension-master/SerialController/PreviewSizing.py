"""Debounced, display-only fitting for the Origin preview."""
import tkinter as tk
from tkinter import ttk

from CaptureGeometry import capture_frame_size, fit_preview_size


class PreviewSizing:
    def __init__(self, app):
        self.app = app
        self.pending = None
        self.enabled = tk.BooleanVar(
            master=app.root, value=getattr(app.settings, "preview_auto_fit", True))
        self.label = tk.StringVar(master=app.root)
        controls = ttk.Frame(app.camera_f)
        controls.grid(row=10, column=0, sticky="ew", padx=5, pady=4)
        ttk.Checkbutton(controls, text="表示をウィンドウに合わせる（取得解像度は固定）",
                        variable=self.enabled, command=self.schedule).pack(side="left")
        ttk.Label(controls, textvariable=self.label).pack(side="left", padx=12)
        app.root.bind("<Configure>", self.on_configure, add="+")
        app.camera_lf.bind("<Configure>", self.on_configure, add="+")
        self.schedule()

    def on_configure(self, event):
        if event.widget in (self.app.root, self.app.camera_lf):
            self.schedule()

    def schedule(self):
        if self.pending is not None:
            self.app.root.after_cancel(self.pending)
        self.pending = self.app.root.after(120, self.fit)

    def fit(self):
        self.pending = None
        app = self.app
        source = capture_frame_size(app.camera)
        if self.enabled.get() and app.root.winfo_width() > 100:
            # Leave room for the existing scrollable operation tabs. The
            # preview is the only image being resized, never Camera or AVI.
            controls_height = min(330, max(240, app.controller_nb.winfo_reqheight()))
            header_height = app.main_panel_header_f.winfo_reqheight()
            available = (max(160, app.camera_lf.winfo_width() - 16),
                         max(90, app.root.winfo_height() - controls_height - header_height - 60))
            companion = getattr(app, "companion_pane", None)
            if companion is not None:
                available = (max(160, (available[0] - 16) // 2), available[1])
            target = fit_preview_size(source, available)
            if target != tuple(app.preview.show_size):
                app.preview.setShowsize(target[1], target[0])
                app.changeAreaSize()
            if companion is not None:
                companion.fit((target[0], available[1]))
        self.label.set("取得 {}×{} / 表示 {}×{}".format(
            *source, *app.preview.show_size))

    def manual_size(self, width, height):
        self.enabled.set(False)
        self.app.preview.setShowsize(height, width)
        self.app.changeAreaSize()
        self.fit()
