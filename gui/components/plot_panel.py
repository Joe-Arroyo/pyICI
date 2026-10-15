"""Shared embedded-matplotlib panel for the pyICI GUI tabs.

One reusable widget that owns a matplotlib Figure, its Tk canvas, and the
navigation toolbar, so each tab no longer rebuilds that plumbing itself. A tab
draws with normal matplotlib on ``panel.figure`` (e.g.
``panel.figure.add_subplot(...)``), or on a single fresh Axes from
``panel.get_axes()``, then calls ``panel.refresh()`` to redraw the canvas.

Introduced in the GUI overhaul as the first shared presentation component. Kept
framework-neutral (a plain ``tkinter.Frame``) for now; the customtkinter restyle
happens later, in the Track F polish stage, and does not change this API.
"""
import tkinter as tk

from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk


class PlotPanel(tk.Frame):
    """A Tk frame that embeds a matplotlib Figure + canvas + navigation toolbar.

    Parameters
    ----------
    master : tkinter widget
        Parent container.
    figsize : tuple of (float, float), optional
        Figure size in inches. Default ``(8, 6)``.
    toolbar : bool, optional
        Show the matplotlib navigation toolbar (zoom / pan / save). Default
        ``True``.
    **kwargs
        Passed through to ``tkinter.Frame``.

    Attributes
    ----------
    figure : matplotlib.figure.Figure
        The figure to draw on (``add_subplot`` etc.), exactly as a tab's own
        figure was used before.
    canvas : matplotlib.backends.backend_tkagg.FigureCanvasTkAgg
        The embedded canvas.
    toolbar : matplotlib.backends.backend_tkagg.NavigationToolbar2Tk or None
        The navigation toolbar, or ``None`` when ``toolbar=False``.
    """

    def __init__(self, master, *, figsize=(8, 6), toolbar=True, **kwargs):
        # Stop the panel from resizing itself to the canvas's requested size.
        # FigureCanvasTkAgg asks for the figure's pixel size (figsize x dpi),
        # which — left to propagate — pushes the toplevel window larger, then
        # matplotlib refits the figure to the widget and it shrinks again,
        # oscillating on every redraw. With pack_propagate(False) the panel is
        # sized top-down by its parent (it still fills via pack(expand=True)) and
        # the canvas fills the panel, so the figure never drives the window.
        # No baseline width/height is set: a floor larger than the space a parent
        # hands over at first render would clip the (taller) figure.
        super().__init__(master, **kwargs)
        self.pack_propagate(False)

        self.figure = Figure(figsize=figsize)
        self.canvas = FigureCanvasTkAgg(self.figure, self)

        if toolbar:
            self.toolbar = NavigationToolbar2Tk(self.canvas, self)
            self.toolbar.update()
            self.toolbar.pack(side=tk.BOTTOM, fill=tk.X)
        else:
            self.toolbar = None

        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

    # -- convenience API (pattern "A": the tab draws, the panel refreshes) --

    def get_axes(self):
        """Clear the figure and return a single fresh Axes.

        Convenience for the common one-plot case. Tabs that need several
        subplots use ``self.figure`` directly (``figure.add_subplot(...)``).
        """
        self.figure.clear()
        return self.figure.add_subplot(111)

    def clear(self):
        """Remove all axes from the figure (does not redraw)."""
        self.figure.clear()

    def refresh(self):
        """Redraw the canvas after the figure's contents have changed.

        First fit the figure to the widget's CURRENT pixel size. matplotlib only
        rescales the figure to the widget on a later ``<Configure>`` event, so a
        plot drawn right after a section is shown (before the widget is laid out)
        would render at the initial ``figsize`` — taller than the viewport, which
        clips the lower subplot until the window is resized. Flushing pending
        geometry with ``update_idletasks`` and then matching the figure to the
        widget removes that race. ``forward=False`` keeps it from resizing the
        toplevel window.
        """
        widget = self.canvas.get_tk_widget()
        try:
            widget.update_idletasks()
            w, h = widget.winfo_width(), widget.winfo_height()
            if w > 1 and h > 1:
                dpi = self.figure.get_dpi()
                self.figure.set_size_inches(w / dpi, h / dpi, forward=False)
        except Exception:
            pass
        self.canvas.draw_idle()