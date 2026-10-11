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
        super().__init__(master, **kwargs)

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
        """Redraw the canvas after the figure's contents have changed."""
        self.canvas.draw_idle()