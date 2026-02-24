#!/usr/bin/env python
# pylint: disable=invalid-name, too-many-instance-attributes
"""
Plotting widget taken from QuickNXS.

#TODO: refactor this or replace it with a standard solution
"""

import inspect
import logging
import os
import pickle
import tempfile

import matplotlib.colors
import numpy as np
from matplotlib.backends.backend_qt import NavigationToolbar2QT
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.colors import LogNorm, Normalize
from matplotlib.figure import Figure
from qtpy import QtCore, QtGui, QtPrintSupport, QtWidgets

from quicknxs.config import plotting

try:
    import matplotlib.backends.qt_editor.figureoptions as figureoptions
except ImportError:
    figureoptions = None

cmap = matplotlib.colors.LinearSegmentedColormap.from_list(
    "default", ["#0000ff", "#00ff00", "#ffff00", "#ff0000", "#bd7efc", "#000000"], N=256
)
matplotlib.colormaps.register(cmap, name="default")


def _set_default_rc():
    matplotlib.rc("font", **plotting.font)
    matplotlib.rc("savefig", **plotting.savefig)


_set_default_rc()

# path where all of the icons are
ICON_DIR = os.path.join(os.path.split(__file__)[0], "../", "icons")


def getIcon(filename: str) -> "QtGui.QIcon":
    filename_full = os.path.join(ICON_DIR, filename)
    icon = QtGui.QIcon()
    icon.addPixmap(QtGui.QPixmap(filename_full), QtGui.QIcon.Normal, QtGui.QIcon.Off)
    return icon


def centerbins(xvals):
    """For a given numpy array of bin edges, return the bin centers."""
    new_xvals = (xvals + np.roll(xvals, -1)) / 2
    return np.delete(new_xvals, -1)


def _data_lines(ax):
    """Return lines that carry plotted data, excluding overlay markers (axvline/axhline)."""
    return [line for line in ax.lines if line.get_transform() == ax.transData]


def _errorbar_containers(ax):
    """Return ErrorbarContainer objects from the axes, if any."""
    from matplotlib.container import ErrorbarContainer

    return [c for c in ax.containers if isinstance(c, ErrorbarContainer)]


def _detect_plot_type(ax):
    """Classify the current axes content.

    Returns one of: ``"imshow"``, ``"pcolormesh"``, ``"errorbar"``, ``"line"``, ``"empty"``.
    """
    if len(ax.images) > 0:
        return "imshow"
    if any(c.__class__.__name__ == "QuadMesh" for c in ax.collections):
        return "pcolormesh"
    if len(_errorbar_containers(ax)) > 0:
        return "errorbar"
    lines = _data_lines(ax)
    if len(lines) == 0:
        return "empty"
    return "line"


def _extract_errorbar_data(ax):
    """Extract X, Y, Error datasets from ErrorbarContainer objects."""
    containers = _errorbar_containers(ax)
    datasets = []
    for container in containers:
        data_line = container[0]
        x = np.array(data_line.get_xdata(), dtype=float)
        y = np.array(data_line.get_ydata(), dtype=float)
        # Extract error from the vertical bar LineCollection segments
        bar_collections = container[2]
        if bar_collections:
            segments = bar_collections[0].get_segments()
            error = np.array([(seg[1, 1] - seg[0, 1]) / 2.0 for seg in segments])
        else:
            error = np.zeros_like(y)
        label = data_line.get_label() or f"dataset_{len(datasets)}"
        datasets.append({"x": x, "y": y, "error": error, "label": label})
    return {
        "datasets": datasets,
        "xlabel": ax.get_xlabel(),
        "ylabel": ax.get_ylabel(),
        "title": ax.get_title(),
    }


def _extract_imshow_data(ax):
    """Extract the 2D array and extent from an imshow plot."""
    img = ax.images[0]
    data = np.array(img.get_array(), dtype=float)
    extent = np.array(img.get_extent())
    return {
        "data": data,
        "extent": extent,
        "xlabel": ax.get_xlabel(),
        "ylabel": ax.get_ylabel(),
        "title": ax.get_title(),
    }


def _extract_pcolormesh_data(ax):
    """Extract mesh coordinates and Z values from a pcolormesh (QuadMesh) plot."""
    qm = next(c for c in ax.collections if c.__class__.__name__ == "QuadMesh")
    coords = qm.get_coordinates()  # shape (ny+1, nx+1, 2)
    z_data = np.array(qm.get_array(), dtype=float)
    ny, nx = coords.shape[0] - 1, coords.shape[1] - 1
    if z_data.ndim == 1:
        z_data = z_data.reshape(ny, nx)
    x_edges = coords[0, :, 0]
    y_edges = coords[:, 0, 1]
    x_centers = centerbins(x_edges)
    y_centers = centerbins(y_edges)
    return {
        "x_edges": x_edges,
        "y_edges": y_edges,
        "x_centers": x_centers,
        "y_centers": y_centers,
        "z_data": z_data,
        "xlabel": ax.get_xlabel(),
        "ylabel": ax.get_ylabel(),
        "title": ax.get_title(),
    }


def _extract_line_data(ax):
    """Extract X, Y data from simple line plots (non-errorbar)."""
    lines = _data_lines(ax)
    datasets = []
    for line in lines:
        x = np.array(line.get_xdata(), dtype=float)
        y = np.array(line.get_ydata(), dtype=float)
        label = line.get_label() or f"dataset_{len(datasets)}"
        datasets.append({"x": x, "y": y, "label": label})
    return {
        "datasets": datasets,
        "xlabel": ax.get_xlabel(),
        "ylabel": ax.get_ylabel(),
        "title": ax.get_title(),
    }


def _save_dat(fname, extracted, plot_type):
    """Save extracted data as ASCII table."""
    if plot_type == "errorbar":
        _save_dat_errorbar(fname, extracted)
    elif plot_type == "line":
        _save_dat_line(fname, extracted)
    elif plot_type == "imshow":
        _save_dat_imshow(fname, extracted)
    elif plot_type == "pcolormesh":
        _save_dat_pcolormesh(fname, extracted)
    else:
        raise ValueError(f"Cannot save plot type '{plot_type}' as .dat")


def _save_dat_errorbar(fname, extracted):
    with open(fname, "w") as f:
        for i, ds in enumerate(extracted["datasets"]):
            f.write(f"# Dataset {i}: {ds['label']}\n")
            f.write(f"# {extracted['xlabel']}\t{extracted['ylabel']}\tError\n")
            block = np.column_stack([ds["x"], ds["y"], ds["error"]])
            np.savetxt(f, block, delimiter="\t")
            if i < len(extracted["datasets"]) - 1:
                f.write("\n\n")


def _save_dat_line(fname, extracted):
    with open(fname, "w") as f:
        for i, ds in enumerate(extracted["datasets"]):
            f.write(f"# Dataset {i}: {ds['label']}\n")
            f.write(f"# {extracted['xlabel']}\t{extracted['ylabel']}\n")
            block = np.column_stack([ds["x"], ds["y"]])
            np.savetxt(f, block, delimiter="\t")
            if i < len(extracted["datasets"]) - 1:
                f.write("\n\n")


def _save_dat_imshow(fname, extracted):
    header = (
        f"extent: xmin={extracted['extent'][0]}, xmax={extracted['extent'][1]}, "
        f"ymin={extracted['extent'][2]}, ymax={extracted['extent'][3]}\n"
        f"{extracted['xlabel']} vs {extracted['ylabel']}"
    )
    np.savetxt(fname, extracted["data"], header=header, delimiter="\t")


def _save_dat_pcolormesh(fname, extracted):
    """Save pcolormesh data in gnuplot splot xyz format.

    Each row is ``x y z``.  Blank lines separate blocks where the x value changes.
    """
    x_centers = extracted["x_centers"]
    y_centers = extracted["y_centers"]
    z_data = extracted["z_data"]
    with open(fname, "w") as f:
        f.write(f"# title: {extracted['title']}\n")
        f.write(f"# xlabel: {extracted['xlabel']}\n")
        f.write(f"# ylabel: {extracted['ylabel']}\n")
        f.write(f"# x_edges ({len(extracted['x_edges'])}): {' '.join(f'{v:.6g}' for v in extracted['x_edges'])}\n")
        f.write(f"# y_edges ({len(extracted['y_edges'])}): {' '.join(f'{v:.6g}' for v in extracted['y_edges'])}\n")
        f.write(f"# z_data shape: {z_data.shape}\n")
        f.write(f"# {extracted['xlabel']}\t{extracted['ylabel']}\tZ\n")
        for ix, xc in enumerate(x_centers):
            for iy, yc in enumerate(y_centers):
                f.write(f"{xc:.6g}\t{yc:.6g}\t{z_data[iy, ix]:.6g}\n")
            if ix < len(x_centers) - 1:
                f.write("\n")


def _save_npz(fname, extracted, plot_type):
    """Save extracted data as a compressed numpy archive."""
    save_dict = {"plot_type": np.array(plot_type)}
    if plot_type in ("errorbar", "line"):
        save_dict["n_datasets"] = np.array(len(extracted["datasets"]))
        for i, ds in enumerate(extracted["datasets"]):
            save_dict[f"x_{i}"] = ds["x"]
            save_dict[f"y_{i}"] = ds["y"]
            if "error" in ds:
                save_dict[f"error_{i}"] = ds["error"]
            save_dict[f"label_{i}"] = np.array(ds["label"])
    elif plot_type == "imshow":
        save_dict["data"] = extracted["data"]
        save_dict["extent"] = extracted["extent"]
    elif plot_type == "pcolormesh":
        save_dict["x_edges"] = extracted["x_edges"]
        save_dict["y_edges"] = extracted["y_edges"]
        save_dict["x_centers"] = extracted["x_centers"]
        save_dict["y_centers"] = extracted["y_centers"]
        save_dict["z_data"] = extracted["z_data"]
    save_dict["xlabel"] = np.array(extracted.get("xlabel", ""))
    save_dict["ylabel"] = np.array(extracted.get("ylabel", ""))
    save_dict["title"] = np.array(extracted.get("title", ""))
    np.savez_compressed(fname, **save_dict)


def _save_pkl(fname, figure, extracted, plot_type):
    """Save figure and extracted data as a pickle file."""
    payload = {
        "figure": figure,
        "plot_type": plot_type,
        "data": extracted,
    }
    with open(fname, "wb") as f:
        pickle.dump(payload, f, protocol=4)


class NavigationToolbar(NavigationToolbar2QT):
    """A small change to the original navigation toolbar."""

    _auto_toggle = False

    def __init__(self, canvas, parent, coordinates=False):
        NavigationToolbar2QT.__init__(self, canvas, parent, coordinates)
        self.setIconSize(QtCore.QSize(20, 20))
        self.calling_function = None
        self._init_toolbar()
        self._add_buttons()

    def _init_toolbar(self):
        # add the extra default toolbar functions for quicknxs print, & lines
        if not hasattr(self, "_actions"):
            self._actions = {}

        icon = getIcon("document-print.png")
        a = self.addAction(icon, "Print", self.print_figure)
        a.setToolTip("Print the figure with the default printer")

        icon = getIcon("saveData.png")
        self.addSeparator()
        a = self.addAction(icon, "SaveData", self.save_data)
        a.setToolTip("Save plot data to file")

        # Add the x,y location widget at the right side of the toolbar
        # The stretch factor is 1 which means any resizing of the toolbar
        # will resize this label instead of the buttons.
        self.locLabel = QtWidgets.QLabel("", self)
        self.locLabel.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignTop)
        self.locLabel.setSizePolicy(
            QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Ignored)
        )
        self.labelAction = self.addWidget(self.locLabel)
        if self.coordinates:
            self.labelAction.setVisible(True)
        else:
            self.labelAction.setVisible(False)

        # reference holder for subplots_adjust window
        self.adj_window = None

    def _add_buttons(self):
        """Function for derived classes to add buttons to the toolbar."""
        pass

    def print_figure(self):
        """Save the plot to a temporary png file and show a preview dialog also used for printing."""
        filetypes = self.canvas.get_supported_filetypes_grouped()

        filename = os.path.join(tempfile.gettempdir(), "quicknxs_print.png")
        self.canvas.print_figure(filename, dpi=600)
        imgpix = QtGui.QPixmap(filename)
        os.remove(filename)

        imgobj = QtWidgets.QLabel()
        imgobj.setPixmap(imgpix)
        imgobj.setMask(imgpix.mask())
        imgobj.setGeometry(0, 0, imgpix.width(), imgpix.height())

        def getPrintData(printer):
            imgobj.render(printer)

        printer = QtPrintSupport.QPrinter()
        printer.setPrinterName("mrac4a_printer")
        printer.setPageSize(QtPrintSupport.QPrinter.Letter)
        printer.setResolution(600)
        printer.setOrientation(QtPrintSupport.QPrinter.Landscape)

        pd = QtPrintSupport.QPrintPreviewDialog(printer)
        pd.paintRequested.connect(getPrintData)
        pd.exec_()

    def save_figure(self, *args):
        filetypes = self.canvas.get_supported_filetypes_grouped()
        sorted_filetypes = filetypes.items()
        default_filetype = self.canvas.get_default_filetype()

        start = "image." + default_filetype
        filters = []
        for name, exts in sorted_filetypes:
            exts_list = " ".join(["*.%s" % ext for ext in exts])
            filter_ = "%s (%s)" % (name, exts_list)
            if default_filetype in exts:
                filters.insert(0, filter_)
            else:
                filters.append(filter_)
        filters = ";;".join(filters)

        fname = QtWidgets.QFileDialog.getSaveFileName(self, "Choose a filename to save to", start, filters)
        if fname:
            try:
                self.canvas.print_figure((fname[0]))
            except Exception as e:
                QtWidgets.QMessageBox.critical(
                    self, "Error saving file", str(e), QtWidgets.QMessageBox.Ok, QtWidgets.QMessageBox.NoButton
                )

    def save_data(self):
        """Save the current plot data to file (.dat, .npz, or .pkl)."""
        ax = self.canvas.ax
        try:
            plot_type = _detect_plot_type(ax)
            if plot_type == "empty":
                raise ValueError("No data to save: the plot is empty.")

            extractor = {
                "errorbar": _extract_errorbar_data,
                "imshow": _extract_imshow_data,
                "pcolormesh": _extract_pcolormesh_data,
                "line": _extract_line_data,
            }
            extracted = extractor[plot_type](ax)

            filters = "ASCII data (*.dat);;Numpy archive (*.npz);;Pickle (*.pkl)"
            fname, selected_filter = QtWidgets.QFileDialog.getSaveFileName(self, "Save plot data", "", filters)
            if not fname:
                return

            _, ext = os.path.splitext(fname)
            ext = ext.lower()
            if ext not in (".dat", ".npz", ".pkl"):
                for candidate in (".dat", ".npz", ".pkl"):
                    if f"*{candidate}" in selected_filter:
                        fname += candidate
                        ext = candidate
                        break
                else:
                    raise ValueError(f"Unknown file format: {ext or '(none)'}")

            if ext == ".dat":
                _save_dat(fname, extracted, plot_type)
            elif ext == ".npz":
                _save_npz(fname, extracted, plot_type)
            elif ext == ".pkl":
                _save_pkl(fname, self.canvas.figure, extracted, plot_type)

            logging.info(f"Saved {plot_type} data to {fname}")

        except Exception as e:
            logging.error(f"Error saving data: {e}")
            QtWidgets.QMessageBox.critical(
                self,
                "Error saving data",
                str(e),
                QtWidgets.QMessageBox.Ok,
                QtWidgets.QMessageBox.NoButton,
            )


class NavigationToolbarGeneric(NavigationToolbar):
    """A navigation toolbar for a generic plot."""

    def _add_buttons(self):
        """Add buttons specific to this navigation toolbar."""
        icon = getIcon("toggle-log.png")
        self.addSeparator()
        a = self.addAction(icon, "Log", self.toggle_log)
        a.setToolTip("Toggle logarithmic scale")

    def toggle_log(self, *args):
        ax = self.canvas.ax
        if len(ax.images) == 0 and all([c.__class__.__name__ != "QuadMesh" for c in ax.collections]):
            logstate = ax.get_yscale()
            if logstate == "linear":
                ax.set_yscale("log")
            else:
                ax.set_yscale("linear")
            self.canvas.draw()
        else:
            imgs = ax.images + [c for c in ax.collections if c.__class__.__name__ == "QuadMesh"]
            norm = imgs[0].norm
            if norm.__class__ is LogNorm:
                for img in imgs:
                    img.set_norm(Normalize(norm.vmin, norm.vmax))
            else:
                for img in imgs:
                    img.set_norm(LogNorm(norm.vmin, norm.vmax))
        self.canvas.draw()


class NavigationToolbarReflectivity(NavigationToolbar):
    """A navigation toolbar for reflectivity plots created using matplotlib's errorbar function."""

    def __init__(self, canvas, parent, coordinates=False):
        self.q_pow_4_button = None
        super().__init__(canvas, parent, coordinates)

    def _add_buttons(self):
        """Add buttons specific to the reflectivity navigation toolbar."""
        self.addSeparator()
        icon = getIcon("toggle-x-log.png")
        a = self.addAction(icon, "XLog", self.toggle_xlog)
        a.setToolTip("Toggle logarithmic x-scale")

        icon = getIcon("toggle-y-log.png")
        a = self.addAction(icon, "YLog", self.toggle_ylog)
        a.setToolTip("Toggle logarithmic y-scale")

        icon = getIcon("toggle-r-q4.png")
        a = self.addAction(icon, "RQ4", self.toggle_rq4_scale)
        a.setToolTip("Toggle plotting R(Q)*Q$^4$")
        a.setCheckable(True)
        self.q_pow_4_button = a

        icon = getIcon("plotLines.png")
        self.addSeparator()
        a = self.addAction(icon, "Lines", self.toggle_lines)
        a.setToolTip("Toggle lines between points")

    def toggle_xlog(self, *args):
        """Toggle between linear and logarithmic x-axis."""
        ax = self.canvas.ax
        logstate = ax.get_xscale()
        if logstate == "linear":
            ax.set_xscale("log")
        else:
            ax.set_xscale("linear")
        self.canvas.draw()

    def toggle_ylog(self, *args):
        """Toggle between linear and logarithmic y-axis."""
        ax = self.canvas.ax
        logstate = ax.get_yscale()
        if logstate == "linear":
            ax.set_yscale("log")
        else:
            ax.set_yscale("linear")
        self.canvas.draw()

    def toggle_rq4_scale(self, *args):
        """Toggle between plotting R and R * Q^4."""
        # should the y data be scaled by Q^4?
        is_yaxis_q_pow_4 = self.q_pow_4_button.isChecked()

        # scale the line data
        ax = self.canvas.ax
        for line in ax.get_lines():
            x = line.get_xdata()
            y = line.get_ydata()
            if is_yaxis_q_pow_4:
                line.set_ydata(y * x**4)
            else:
                line.set_ydata(y / x**4)

        # scale the error bar data
        for c in ax.collections:
            segments = c.get_segments()
            scaled_segments = []
            for segment in segments:
                if is_yaxis_q_pow_4:
                    segment[0][1] = segment[0][1] * segment[0][0] ** 4
                    segment[1][1] = segment[1][1] * segment[1][0] ** 4
                else:
                    segment[0][1] = segment[0][1] / segment[0][0] ** 4
                    segment[1][1] = segment[1][1] / segment[1][0] ** 4
                scaled_segments.append(segment)
            c.set_segments(scaled_segments)

        # update the axis labels
        if is_yaxis_q_pow_4:
            ax.set_ylabel("R $\\cdot$ Q$^4$")
        else:
            ax.set_ylabel("R")

        # update the axis limits
        ax.relim(visible_only=True)
        ax.autoscale_view(True, True, True)  # to autoscale error bars
        ax.autoscale()  # to autoscale lines
        self.canvas.draw()

    def toggle_lines(self, *args):
        """Toggle lines between points in the plot."""
        ax = self.canvas.ax
        if len(ax.lines) < 3:
            return
        linestyle = ax.lines[0].get_linestyle()
        if linestyle == "-":
            new_linestyle = ""
        else:
            new_linestyle = "-"
        for i in range(0, len(ax.lines), 3):
            ax.lines[i].set_linestyle(new_linestyle)
        settings = QtCore.QSettings(".quicknxs")
        settings.setValue(self.calling_function + "/linestyle", new_linestyle)
        self.canvas.draw()


class MplCanvas(FigureCanvas):
    """A canvas for matplotlib figures, used in the MPLWidget."""

    def __init__(self, parent=None, width=3, height=3, dpi=100, sharex=None, sharey=None, adjust={}):
        self.fig = Figure(figsize=(width, height), dpi=dpi, facecolor="None")
        self.ax = self.fig.add_subplot(111, sharex=sharex, sharey=sharey)
        self.fig.subplots_adjust(left=0.15, bottom=0.15, right=0.95, top=0.95)
        self.xtitle = ""
        self.ytitle = ""
        self.PlotTitle = ""
        self.grid_status = True
        self.xaxis_style = "linear"
        self.yaxis_style = "linear"
        self.format_labels()
        FigureCanvas.__init__(self, self.fig)
        FigureCanvas.setSizePolicy(self, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        FigureCanvas.updateGeometry(self)

    def format_labels(self):
        self.ax.set_title(self.PlotTitle)

    def sizeHint(self):
        w, h = self.get_width_height()
        w = max(w, self.height())
        h = max(h, self.width())
        return QtCore.QSize(w, h)

    def minimumSizeHint(self):
        return QtCore.QSize(40, 40)

    def get_default_filetype(self):
        return "png"


class MPLWidget(QtWidgets.QWidget):
    """A widget for displaying matplotlib plots, with a navigation toolbar."""

    cplot = None
    cbar = None

    def __init__(self, parent=None, with_toolbar=True, coordinates=False):
        QtWidgets.QWidget.__init__(self, parent)
        self.canvas = MplCanvas()
        self.canvas.ax2 = None
        self.vbox = QtWidgets.QVBoxLayout()
        self.vbox.addWidget(self.canvas)
        if with_toolbar:
            self.stacked_toolbars = QtWidgets.QStackedWidget(self.canvas)
            self.stacked_toolbars.setSizePolicy(QtWidgets.QSizePolicy.Maximum, QtWidgets.QSizePolicy.Maximum)
            toolbar_generic = NavigationToolbarGeneric(self.canvas, self)
            toolbar_generic.coordinates = coordinates
            toolbar_refl = NavigationToolbarReflectivity(self.canvas, self)
            toolbar_refl.coordinates = coordinates
            self.stacked_toolbars.addWidget(toolbar_generic)
            self.stacked_toolbars.addWidget(toolbar_refl)
            self.toolbar = self.stacked_toolbars.currentWidget()
            self.vbox.addWidget(self.stacked_toolbars)
        else:
            self.toolbar = None
        self.setLayout(self.vbox)

    def sync_toolbar_view(self, clear_history=False):
        """Ensure navigation toolbar state matches the current plot."""
        if not self.toolbar:
            return
        if clear_history:
            self.toolbar._views.clear()
            self.toolbar._positions.clear()
        self.toolbar.push_current()
        self.canvas.draw()
        self.toolbar.update()

    def leaveEvent(self, event):
        """Make sure the cursor is reset to it's default when leaving the widget.

        In some cases the zoom cursor does not reset when leaving the plot.
        """
        if self.toolbar:
            QtWidgets.QApplication.restoreOverrideCursor()
            self.toolbar._lastCursor = None
        return QtWidgets.QWidget.leaveEvent(self, event)

    def set_config(self, config):
        self.canvas.fig.subplots_adjust(**config)

    def get_config(self):
        spp = self.canvas.fig.subplotpars
        config = dict(left=spp.left, right=spp.right, bottom=spp.bottom, top=spp.top)
        return config

    def draw(self):
        """Convenience to redraw the graph."""
        self.canvas.fig.tight_layout()
        self.canvas.draw()

    def plot(self, *args, **opts):
        """Convenience wrapper for self.canvas.ax.plot."""
        result = self.canvas.ax.plot(*args, **opts)
        self.sync_toolbar_view()
        return result

    def semilogy(self, *args, **opts):
        """Convenience wrapper for self.canvas.ax.semilogy."""
        result = self.canvas.ax.semilogy(*args, **opts)
        self.sync_toolbar_view()
        return result

    def errorbar(self, *args, **opts):
        """Convenience wrapper for self.canvas.ax.errorbar."""
        if self.toolbar:
            # change to toolbar with reflectivity-specific options
            self.stacked_toolbars.setCurrentIndex(1)
            self.toolbar = self.stacked_toolbars.currentWidget()

        if "fmt" in opts:
            set_linestyle = False
        elif "linestyle" in opts:
            set_linestyle = False
        elif "ls" in opts:
            set_linestyle = False
        else:
            set_linestyle = True

        if set_linestyle:
            self.toolbar.calling_function = str(inspect.stack()[1][3])
            setting = QtCore.QSettings(".quicknxs")
            ls = setting.value(self.toolbar.calling_function + "/linestyle", "-")
            opts["ls"] = str(ls)

        result = self.canvas.ax.errorbar(*args, **opts)
        self.sync_toolbar_view()
        return result

    def pcolormesh(self, datax, datay, dataz, log=False, imin=None, imax=None, update=False, **opts):
        """Convenience wrapper for self.canvas.ax.plot."""
        if self.cplot is None or not update:
            if log:
                self.cplot = self.canvas.ax.pcolormesh(datax, datay, dataz, norm=LogNorm(imin, imax), **opts)
            else:
                self.cplot = self.canvas.ax.pcolormesh(datax, datay, dataz, **opts)
        else:
            self.update(datax, datay, dataz)
        self.sync_toolbar_view()
        return self.cplot

    def imshow(self, data, log=False, imin=None, imax=None, update=True, **opts):
        """Convenience wrapper for self.canvas.ax.plot."""
        if self.cplot is None or not update:
            if log:
                self.cplot = self.canvas.ax.imshow(data, norm=LogNorm(imin, imax), **opts)
            else:
                self.cplot = self.canvas.ax.imshow(data, **opts)
        else:
            self.update(data, **opts)
        self.sync_toolbar_view()
        return self.cplot

    def set_title(self, new_title, fontsize=None):
        return self.canvas.ax.set_title(new_title, fontsize=fontsize)

    def set_xlabel(self, label, fontsize=None):
        return self.canvas.ax.set_xlabel(label, fontsize=fontsize)

    def set_ylabel(self, label, fontsize=None):
        return self.canvas.ax.set_ylabel(label, fontsize=fontsize)

    def set_xticks_fontsize(self, fontsize):
        for label in self.canvas.ax.get_xticklabels():
            label.set_fontsize(fontsize)

    def set_yticks_fontsize(self, fontsize):
        for label in self.canvas.ax.get_yticklabels():
            label.set_fontsize(fontsize)

    def set_xscale(self, scale):
        try:
            return self.canvas.ax.set_xscale(scale)
        except ValueError:
            pass

    def set_yscale(self, scale):
        try:
            return self.canvas.ax.set_yscale(scale)
        except ValueError:
            pass

    def clear_fig(self):
        self.cplot = None
        self.cbar = None
        self.canvas.fig.clear()
        self.canvas.ax = self.canvas.fig.add_subplot(111, sharex=None, sharey=None)

    def clear(self):
        self.cplot = None
        self.canvas.ax.clear()
        if self.canvas.ax2 is not None:
            self.canvas.ax2.clear()

    def update(self, *data, **opts):
        self.cplot.set_data(*data)
        if "extent" in opts:
            self.cplot.set_extent(opts["extent"])

    def legend(self, *args, **opts):
        handles, labels = self.canvas.ax.get_legend_handles_labels()
        if labels:
            return self.canvas.ax.legend(*args, **opts)

    def adjust(self, **adjustment):
        result = self.canvas.fig.subplots_adjust(**adjustment)
        self.sync_toolbar_view()
        return result
