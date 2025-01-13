import numpy as np
import pytest
from PyQt5 import QtWidgets
from numpy.testing import assert_allclose
from matplotlib.collections import LineCollection
from matplotlib.lines import Line2D

from quicknxs.interfaces.main_window import MainWindow
from quicknxs.ui.mplwidget import NavigationToolbarGeneric, NavigationToolbarReflectivity, NavigationToolbar


def _refl_data():
    data = {}
    data["cross_sections"] = {"On_Off": None, "Off_Off": None}
    data["On_Off"] = np.array([[3.0, 12.0, 0.1], [4.0, 11.0, 0.1]])
    data["Off_Off"] = np.array([[1.5, 15.0, 0.1], [2.5, 14.0, 0.1]])
    return data


def _initialize_compare_plot(main_window: MainWindow):
    """Populate reflectivity data and draw the compare tab plot"""
    compare_widget = main_window.ui.compare_widget
    compare_widget.show_preview = True
    compare_widget.refl_data = _refl_data()
    compare_widget.draw()
    return compare_widget


def _toggle_toolbar_button(toolbar: NavigationToolbar, button_text: str):
    """Trigger a toolbar button by the button text"""
    for action in toolbar.findChildren(QtWidgets.QAction):
        if action.text() == button_text:
            action.trigger()
            break


def _compare_lines_data(lines: np.ndarray[Line2D], gold_data: dict, is_q4_plot: bool = False):
    """Assert that the data for the plotted line and upper and lower error bars are correct"""
    for ics, cross_section in enumerate(gold_data["cross_sections"].keys()):
        gold_x, gold_y, gold_yerr = gold_data[cross_section].T
        plot_line = lines[3 * ics]
        plot_err_lo = lines[3 * ics + 1]
        plot_err_hi = lines[3 * ics + 2]
        # check x data
        assert_allclose(plot_line.get_xdata(), gold_x)
        assert_allclose(plot_err_lo.get_xdata(), gold_x)
        assert_allclose(plot_err_hi.get_xdata(), gold_x)
        # check y data
        y_factor = 1
        if is_q4_plot:
            y_factor = gold_x**4
        assert_allclose(plot_line.get_ydata(), gold_y * y_factor)
        assert_allclose(plot_err_lo.get_ydata(), (gold_y - gold_yerr) * y_factor)
        assert_allclose(plot_err_hi.get_ydata(), (gold_y + gold_yerr) * y_factor)


def _compare_error_bar_data(collections: np.ndarray[LineCollection], gold_data: dict, is_q4_plot: bool = False):
    """Assert that the data for the vertical error bars are correct"""
    for ics, cross_section in enumerate(gold_data["cross_sections"].keys()):
        gold_x, gold_y, gold_yerr = gold_data[cross_section].T
        plot_err_bar = collections[ics]
        # check error bars
        for iseg, segment in enumerate(plot_err_bar.get_segments()):
            bar_x, bar_y = segment.T
            y_factor = 1
            if is_q4_plot:
                y_factor = gold_x[iseg] ** 4
            assert_allclose(bar_x, gold_x[iseg])
            assert_allclose(bar_y[0], (gold_y[iseg] - gold_yerr[iseg]) * y_factor)
            assert_allclose(bar_y[1], (gold_y[iseg] + gold_yerr[iseg]) * y_factor)


class TestNavigationToolbar:
    def test_toolbar_is_visible(self, qtbot):
        """Test that the plots have the correct toolbar"""
        main_window = MainWindow()
        qtbot.addWidget(main_window)
        toolbar = main_window.ui.xy_overview.toolbar
        assert isinstance(toolbar, NavigationToolbarGeneric)

    def test_compare_plot_toolbar(self, qtbot):
        """Test that the reflectivity toolbar is visible for the Compare tab plot"""
        main_window = MainWindow()
        qtbot.addWidget(main_window)
        compare_widget = _initialize_compare_plot(main_window)
        assert isinstance(compare_widget.comparePlot.toolbar, NavigationToolbarReflectivity)

    def test_reflectivity_toolbar_xlog(self, qtbot):
        """Test the XLog button of the reflectivity navigation toolbar"""
        main_window = MainWindow()
        qtbot.addWidget(main_window)
        compare_widget = _initialize_compare_plot(main_window)
        toolbar = compare_widget.comparePlot.toolbar
        assert compare_widget.comparePlot.canvas.ax.get_xscale() == "linear"
        _toggle_toolbar_button(toolbar, "XLog")
        assert compare_widget.comparePlot.canvas.ax.get_xscale() == "log"

    def test_reflectivity_toolbar_ylog(self, qtbot):
        """Test the YLog button of the reflectivity navigation toolbar"""
        main_window = MainWindow()
        qtbot.addWidget(main_window)
        compare_widget = _initialize_compare_plot(main_window)
        toolbar = compare_widget.comparePlot.toolbar
        assert compare_widget.comparePlot.canvas.ax.get_yscale() == "log"
        _toggle_toolbar_button(toolbar, "YLog")
        assert compare_widget.comparePlot.canvas.ax.get_yscale() == "linear"

    def test_reflectivity_toolbar_q4(self, qtbot):
        """Test the Q^4 button of the reflectivity navigation toolbar"""
        main_window = MainWindow()
        qtbot.addWidget(main_window)
        compare_widget = _initialize_compare_plot(main_window)
        toolbar = compare_widget.comparePlot.toolbar
        gold_data = _refl_data()
        assert compare_widget.comparePlot.canvas.ax.get_ylabel() == "R"
        # check positions of lines and error bar caps
        lines = compare_widget.comparePlot.canvas.ax.get_lines()
        assert len(lines) == 6
        _compare_lines_data(lines, gold_data)
        # check positions of error bars
        collections = compare_widget.comparePlot.canvas.ax.collections
        assert len(collections) == 2
        _compare_error_bar_data(collections, gold_data)
        # toggle Q^4 button
        _toggle_toolbar_button(toolbar, "RQ4")
        assert compare_widget.comparePlot.canvas.ax.get_ylabel() == "R $\\cdot$ Q$^4$"
        # check that the plot data has been scaled by Q^4
        _compare_lines_data(lines, gold_data, is_q4_plot=True)
        _compare_error_bar_data(collections, gold_data, is_q4_plot=True)
