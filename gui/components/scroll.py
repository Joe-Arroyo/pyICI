"""Shared scrollable-controls widget for the pyICI GUI.

``AutoHideScrollableFrame`` is a ``CTkScrollableFrame`` whose vertical scrollbar
is shown ONLY when the content is taller than the visible area (a short window),
and hidden otherwise (e.g. when the window is maximized and everything fits). The
section control columns (Regression, R & k analysis) use it so they keep the
scroll safety net on small screens without an always-on scrollbar, and all behave
identically.
"""
import customtkinter as ctk


class AutoHideScrollableFrame(ctk.CTkScrollableFrame):
    """A scrollable frame that hides its vertical scrollbar when not needed."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._sb_visible = True
        self.bind("<Configure>", self._schedule_check, add="+")
        self._parent_canvas.bind("<Configure>", self._schedule_check, add="+")

    def _schedule_check(self, _event=None):
        # Defer to after-idle so geometry has settled; avoids Configure recursion.
        self.after_idle(self._check_scrollbar)

    def _check_scrollbar(self):
        try:
            bbox = self._parent_canvas.bbox("all")
            if bbox is None:
                return
            content_h = bbox[3] - bbox[1]
            canvas_h = self._parent_canvas.winfo_height()
            needed = content_h > canvas_h + 2       # small tolerance
            if needed and not self._sb_visible:
                self._scrollbar.grid()
                self._sb_visible = True
            elif not needed and self._sb_visible:
                self._scrollbar.grid_remove()
                self._sb_visible = False
                self._parent_canvas.yview_moveto(0.0)
        except Exception:
            pass
