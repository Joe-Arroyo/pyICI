"""Shared figure-export helper for the pyICI GUI.

``export_figure`` saves a whole :class:`~matplotlib.figure.Figure` to disk at a
chosen size and DPI. Axis titles are stripped for a clean publication export
(``strip_titles=True``) and the figure's original size and titles are restored
afterwards, so exporting never changes what is shown on screen.

The helper does not show a dialog; it raises on failure so the calling section
controls its own success / error messaging. Kept framework-neutral (plain
matplotlib).
"""


def export_figure(fig, filepath, width_in=8, height_in=6, dpi=300, strip_titles=True):
    """Save ``fig`` to ``filepath`` at ``width_in`` x ``height_in`` inches / ``dpi``.

    With ``strip_titles`` (default), axis titles are blanked for the export and
    restored afterwards, along with the figure's original size, so the on-screen
    figure is left exactly as it was. Raises on write failure.
    """
    original_size = fig.get_size_inches()
    original_titles = [ax.get_title() for ax in fig.get_axes()]
    try:
        if strip_titles:
            for ax in fig.get_axes():
                ax.set_title("")
        fig.set_size_inches(width_in, height_in)
        fig.savefig(filepath, dpi=dpi, bbox_inches='tight', facecolor='white')
    finally:
        fig.set_size_inches(original_size)
        for ax, title in zip(fig.get_axes(), original_titles):
            ax.set_title(title)
