#!/usr/bin/env python
# pylint: disable=invalid-name, too-many-instance-attributes
"""
    Plotting widget taken from QuickNXS

    #TODO: refactor this or replace it with a standard solution
"""
from __future__ import absolute_import, division, print_function, unicode_literals

import os
import inspect
import tempfile
from PyQt5 import QtCore, QtGui, QtWidgets, QtPrintSupport
import matplotlib.cm
import matplotlib.colors
from reflectivity_ui.config import plotting

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5 import NavigationToolbar2QT
from matplotlib.cbook import Stack
from matplotlib.colors import LogNorm, Normalize
from matplotlib.figure import Figure
import numpy as np

try:
    import matplotlib.backends.qt5_editor.figureoptions as figureoptions
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


class NavigationToolbar(NavigationToolbar2QT):
    """
    A small change to the original navigation toolbar.
    """

    _auto_toggle = False

    def __init__(self, canvas, parent, coordinates=False):
        NavigationToolbar2QT.__init__(self, canvas, parent, coordinates)
        self.setIconSize(QtCore.QSize(20, 20))
        self.calling_function = None
        self._init_toolbar()

    def _init_toolbar(self):
        # add the extra default toolbar functions for quicknxs print, & lines
        if not hasattr(self, "_actions"):
            self._actions = {}

        icon = getIcon("document-print.png")
        a = self.addAction(icon, "Print", self.print_figure)
        a.setToolTip("Print the figure with the default printer")

        icon = getIcon("toggle-log.png")
        self.addSeparator()
        a = self.addAction(icon, "Log", self.toggle_log)
        a.setToolTip("Toggle logarithmic scale")

        icon = QtGui.QIcon()
        self.addSeparator()
        a = self.addAction(icon, "SaveData", self.save_data)
        a.setToolTip("Save XYE data to file")

        # TODO find appropriate icon
        icon = QtGui.QIcon()
        self.addSeparator()
        a = self.addAction(icon, "Lines", self.toggle_lines)
        a.setToolTip("Toggle lines between points")
        for action in self.findChildren(QtWidgets.QAction):
            if action.text() == "Lines":
                action.setVisible(False)
                break
        self.buttons = {}

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

    def print_figure(self):
        """
        Save the plot to a temporary png file and show a preview dialog also used for printing.
        """
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

    def toggle_lines(self, *args):
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
        settings = QtCore.QSettings(".refredm")
        settings.setValue(self.calling_function + "/linestyle", new_linestyle)
        self.canvas.draw()

    def save_data(self):
        ax = self.canvas.ax

        if hasattr(ax, "get_array") == False:
            if np.mod(len(ax.lines), 3) == 1:
                data_to_save = ax.lines[0].get_xydata()
            if np.mod(len(ax.lines), 3) == 0:
                data_to_save = np.empty((0, 3), float)
                for i in range(0, int(len(ax.lines)), 3):
                    xdata_from_plot = ax.lines[i].get_xdata()
                    ydata_from_plot = ax.lines[i].get_ydata()
                    err_from_plot = (ax.lines[i + 2].get_ydata() - ax.lines[i + 1].get_ydata()) / 2.0
                    data_to_save = np.append(
                        data_to_save, np.array([xdata_from_plot, ydata_from_plot, err_from_plot]).transpose(), axis=0
                    )
        else:
            data_to_save = ax.get_array()

        fname = QtWidgets.QFileDialog.getSaveFileName(self, "Choose a filename to save to")

        if type(fname[0]) == str:
            try:
                np.savetxt(fname[0], data_to_save)
            except Exception as e:
                QtWidgets.QMessageBox.critical(
                    self, "Error saving file", str(e), QtWidgets.QMessageBox.Ok, QtWidgets.QMessageBox.NoButton
                )

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


class MplCanvas(FigureCanvas):
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
    cplot = None
    cbar = None

    def __init__(self, parent=None, with_toolbar=True, coordinates=False):
        QtWidgets.QWidget.__init__(self, parent)
        self.canvas = MplCanvas()
        self.canvas.ax2 = None
        self.vbox = QtWidgets.QVBoxLayout()
        self.vbox.addWidget(self.canvas)
        if with_toolbar:
            self.toolbar = NavigationToolbar(self.canvas, self)
            self.toolbar.coordinates = coordinates
            self.vbox.addWidget(self.toolbar)
        else:
            self.toolbar = None
        self.setLayout(self.vbox)

    def leaveEvent(self, event):
        """
        Make sure the cursor is reset to it's default when leaving the widget.
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
        """
        Convenience to redraw the graph.
        """
        self.canvas.fig.tight_layout()
        self.canvas.draw()

    def plot(self, *args, **opts):
        """
        Convenience wrapper for self.canvas.ax.plot
        """
        return self.canvas.ax.plot(*args, **opts)

    def semilogy(self, *args, **opts):
        """
        Convenience wrapper for self.canvas.ax.semilogy
        """
        return self.canvas.ax.semilogy(*args, **opts)

    def errorbar(self, *args, **opts):
        """
        Convenience wrapper for self.canvas.ax.semilogy
        """
        for action in self.toolbar.findChildren(QtWidgets.QAction):
            if action.text() == "Lines":
                action.setVisible(True)
                break

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
            setting = QtCore.QSettings(".refredm")
            ls = setting.value(self.toolbar.calling_function + "/linestyle", "-")
            opts["ls"] = str(ls)

        return self.canvas.ax.errorbar(*args, **opts)

    def pcolormesh(self, datax, datay, dataz, log=False, imin=None, imax=None, update=False, **opts):
        """
        Convenience wrapper for self.canvas.ax.plot
        """
        if self.cplot is None or not update:
            if log:
                self.cplot = self.canvas.ax.pcolormesh(datax, datay, dataz, norm=LogNorm(imin, imax), **opts)
            else:
                self.cplot = self.canvas.ax.pcolormesh(datax, datay, dataz, **opts)
        else:
            self.update(datax, datay, dataz)
        return self.cplot

    def imshow(self, data, log=False, imin=None, imax=None, update=True, **opts):
        """
        Convenience wrapper for self.canvas.ax.plot
        """
        if self.cplot is None or not update:
            if log:
                self.cplot = self.canvas.ax.imshow(data, norm=LogNorm(imin, imax), **opts)
            else:
                self.cplot = self.canvas.ax.imshow(data, **opts)
        else:
            self.update(data, **opts)
        return self.cplot

    def set_title(self, new_title):
        return self.canvas.ax.title.set_text(new_title)

    def set_xlabel(self, label):
        return self.canvas.ax.set_xlabel(label)

    def set_ylabel(self, label):
        return self.canvas.ax.set_ylabel(label)

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
        return self.canvas.ax.legend(*args, **opts)

    def adjust(self, **adjustment):
        return self.canvas.fig.subplots_adjust(**adjustment)
