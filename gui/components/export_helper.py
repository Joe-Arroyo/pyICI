"""Shared figure-export helpers for the pyICI GUI tabs.

Two operations the tabs' export buttons were each re-implementing:

* ``export_figure`` — save a whole :class:`~matplotlib.figure.Figure` to disk at
  a chosen size and DPI. Axis titles are stripped for a clean publication export
  (``strip_titles=True``) and the figure's original size and titles are restored
  afterwards, so exporting never changes what is shown on screen.
* ``export_single_axis`` — copy one :class:`~matplotlib.axes.Axes` (its lines,
  scatter collections, shaded vertical spans, axis labels, limits, grid and
  legend) into a fresh single-axes figure and save that, for exporting one
  subplot on its own.

Neither helper shows a dialog; both raise on failure so the calling tab controls
its own success / error messaging. Kept framework-neutral (plain matplotlib) —
the customtkinter restyle (Track F) does not touch this module.
"""
import matplotlib.pyplot as plt


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


def export_single_axis(source_ax, filepath, width_in=8, height_in=6, dpi=300):
    """Copy ``source_ax`` into a standalone one-axes figure and save it.

    Reproduces the axis's lines, scatter collections, shaded vertical spans,
    axis labels (keeping their font sizes), limits, grid and legend — but no
    title, for a clean export. The temporary figure is always closed. Raises on
    write failure.
    """
    temp_fig, temp_ax = plt.subplots(figsize=(width_in, height_in))
    try:
        # Lines
        for line in source_ax.get_lines():
            temp_ax.plot(line.get_xdata(), line.get_ydata(),
                         color=line.get_color(), linewidth=line.get_linewidth(),
                         linestyle=line.get_linestyle(), marker=line.get_marker(),
                         markersize=line.get_markersize(), alpha=line.get_alpha(),
                         label=line.get_label())
        # Scatter collections
        for collection in source_ax.collections:
            if hasattr(collection, 'get_offsets') and len(collection.get_offsets()) > 0:
                offsets = collection.get_offsets()
                temp_ax.scatter(offsets[:, 0], offsets[:, 1],
                                c=collection.get_facecolors(),
                                s=collection.get_sizes(),
                                alpha=collection.get_alpha())
        # Shaded vertical spans (axvspan patches)
        for patch in source_ax.patches:
            if hasattr(patch, 'get_x') and hasattr(patch, 'get_width'):
                x = patch.get_x()
                temp_ax.axvspan(x, x + patch.get_width(),
                                color=patch.get_facecolor(), alpha=patch.get_alpha())
        # Formatting (no title)
        temp_ax.set_xlabel(source_ax.get_xlabel(),
                           fontsize=source_ax.xaxis.label.get_fontsize())
        temp_ax.set_ylabel(source_ax.get_ylabel(),
                           fontsize=source_ax.yaxis.label.get_fontsize())
        temp_ax.set_xlim(source_ax.get_xlim())
        temp_ax.set_ylim(source_ax.get_ylim())
        temp_ax.grid(True, alpha=0.3)
        if source_ax.get_legend():
            temp_ax.legend(loc='best')

        temp_fig.tight_layout()
        temp_fig.savefig(filepath, dpi=dpi, bbox_inches='tight', facecolor='white')
    finally:
        plt.close(temp_fig)
