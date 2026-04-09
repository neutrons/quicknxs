import pickle

import numpy as np
from matplotlib.collections import LineCollection
from matplotlib.lines import Line2D
from numpy.testing import assert_allclose
from PyQt5 import QtWidgets

from quicknxs.interfaces.main_window import MainWindow
from quicknxs.ui.mplwidget import (
    MPLWidget,
    NavigationToolbar,
    NavigationToolbarGeneric,
    NavigationToolbarReflectivity,
    _detect_plot_type,
)


def _refl_data():
    data = {}
    data["cross_sections"] = {"On_Off": None, "Off_Off": None}
    data["On_Off"] = np.array([[3.0, 12.0, 0.1], [4.0, 11.0, 0.1]])
    data["Off_Off"] = np.array([[1.5, 15.0, 0.1], [2.5, 14.0, 0.1]])
    return data


def _initialize_compare_plot(main_window: MainWindow):
    """Populate reflectivity data and draw the compare tab plot."""
    compare_widget = main_window.ui.compare_widget
    compare_widget.show_preview = True
    compare_widget.refl_data = _refl_data()
    compare_widget.draw()
    return compare_widget


def _toggle_toolbar_button(toolbar: NavigationToolbar, button_text: str):
    """Trigger a toolbar button by the button text."""
    for action in toolbar.findChildren(QtWidgets.QAction):
        if action.text() == button_text:
            action.trigger()
            break


def _compare_lines_data(lines: np.ndarray[Line2D], gold_data: dict, is_q4_plot: bool = False):
    """Assert that the data for the plotted line and upper and lower error bars are correct."""
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
    """Assert that the data for the vertical error bars are correct."""
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
    """Test the NavigationToolbar and its derived classes."""

    def test_toolbar_is_visible(self, qtbot):
        """Test that the plots have the correct toolbar."""
        main_window = MainWindow()
        qtbot.addWidget(main_window)
        toolbar = main_window.ui.xy_overview.toolbar
        assert isinstance(toolbar, NavigationToolbarGeneric)

    def test_compare_plot_toolbar(self, qtbot):
        """Test that the reflectivity toolbar is visible for the Compare tab plot."""
        main_window = MainWindow()
        qtbot.addWidget(main_window)
        compare_widget = _initialize_compare_plot(main_window)
        assert isinstance(compare_widget.comparePlot.toolbar, NavigationToolbarReflectivity)

    def test_reflectivity_toolbar_xlog(self, qtbot):
        """Test the XLog button of the reflectivity navigation toolbar."""
        main_window = MainWindow()
        qtbot.addWidget(main_window)
        compare_widget = _initialize_compare_plot(main_window)
        toolbar = compare_widget.comparePlot.toolbar
        assert compare_widget.comparePlot.canvas.ax.get_xscale() == "linear"
        _toggle_toolbar_button(toolbar, "XLog")
        assert compare_widget.comparePlot.canvas.ax.get_xscale() == "log"

    def test_reflectivity_toolbar_ylog(self, qtbot):
        """Test the YLog button of the reflectivity navigation toolbar."""
        main_window = MainWindow()
        qtbot.addWidget(main_window)
        compare_widget = _initialize_compare_plot(main_window)
        toolbar = compare_widget.comparePlot.toolbar
        assert compare_widget.comparePlot.canvas.ax.get_yscale() == "log"
        _toggle_toolbar_button(toolbar, "YLog")
        assert compare_widget.comparePlot.canvas.ax.get_yscale() == "linear"

    def test_reflectivity_toolbar_q4(self, qtbot):
        """Test the Q^4 button of the reflectivity navigation toolbar."""
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

    def test_reflectivity_toolbar_q4_with_nan(self, qtbot):
        """Q^4 toggle does not crash when errorbar data contains NaN (empty segments)."""
        w = MPLWidget()
        qtbot.addWidget(w)
        x = np.array([1.0, 2.0, 3.0, 4.0])
        y = np.array([10.0, np.nan, 30.0, 40.0])
        e = np.array([0.5, 1.0, np.nan, 2.0])
        w.errorbar(x, y, yerr=e)
        toolbar = w.toolbar
        # Toggle Q^4 on — should not raise
        _toggle_toolbar_button(toolbar, "RQ4")
        assert toolbar.q_pow_4_button.isChecked()
        # Toggle Q^4 off — should not raise
        _toggle_toolbar_button(toolbar, "RQ4")
        assert not toolbar.q_pow_4_button.isChecked()


class TestSaveData:
    """Test save_data() across all plot types and output formats."""

    # -- helpers --

    @staticmethod
    def _make_widget(qtbot):
        w = MPLWidget()
        qtbot.addWidget(w)
        return w

    @staticmethod
    def _mock_dialog(monkeypatch, path, filter_str="ASCII data (*.dat)"):
        monkeypatch.setattr(
            QtWidgets.QFileDialog,
            "getSaveFileName",
            staticmethod(lambda *_a, **_kw: (path, filter_str)),
        )

    # -- plot type detection --

    def test_detect_empty(self, qtbot):
        w = self._make_widget(qtbot)
        assert _detect_plot_type(w.canvas.ax) == "empty"

    def test_detect_errorbar(self, qtbot):
        w = self._make_widget(qtbot)
        w.errorbar([1, 2], [3, 4], yerr=[0.1, 0.2])
        assert _detect_plot_type(w.canvas.ax) == "errorbar"

    def test_detect_imshow(self, qtbot):
        w = self._make_widget(qtbot)
        w.imshow(np.ones((5, 5)), extent=[0, 1, 0, 1])
        assert _detect_plot_type(w.canvas.ax) == "imshow"

    def test_detect_pcolormesh(self, qtbot):
        w = self._make_widget(qtbot)
        x = np.arange(4)
        y = np.arange(3)
        z = np.ones((2, 3))
        w.pcolormesh(x, y, z)
        assert _detect_plot_type(w.canvas.ax) == "pcolormesh"

    def test_detect_line(self, qtbot):
        w = self._make_widget(qtbot)
        w.plot([1, 2, 3], [4, 5, 6])
        assert _detect_plot_type(w.canvas.ax) == "line"

    def test_detect_imshow_with_overlays(self, qtbot):
        w = self._make_widget(qtbot)
        w.imshow(np.ones((5, 5)), extent=[0, 1, 0, 1])
        w.canvas.ax.axvline(0.5, color="red")
        w.canvas.ax.axhline(0.5, color="green")
        assert _detect_plot_type(w.canvas.ax) == "imshow"

    # -- errorbar saves --

    def test_save_errorbar_dat(self, qtbot, tmp_path, monkeypatch):
        w = self._make_widget(qtbot)
        x = np.array([1.0, 2.0, 3.0])
        y = np.array([10.0, 20.0, 30.0])
        e = np.array([0.5, 1.0, 1.5])
        w.errorbar(x, y, yerr=e)
        out = str(tmp_path / "test.dat")
        self._mock_dialog(monkeypatch, out)
        w.toolbar.save_data()
        loaded = np.loadtxt(out)
        assert_allclose(loaded[:, 0], x)
        assert_allclose(loaded[:, 1], y)
        assert_allclose(loaded[:, 2], e)

    def test_save_errorbar_npz(self, qtbot, tmp_path, monkeypatch):
        w = self._make_widget(qtbot)
        x = np.array([1.0, 2.0])
        y = np.array([10.0, 20.0])
        e = np.array([0.5, 1.0])
        w.errorbar(x, y, yerr=e)
        out = str(tmp_path / "test.npz")
        self._mock_dialog(monkeypatch, out, "Numpy archive (*.npz)")
        w.toolbar.save_data()
        data = np.load(out, allow_pickle=True)
        assert str(data["plot_type"]) == "errorbar"
        assert_allclose(data["x_0"], x)
        assert_allclose(data["y_0"], y)
        assert_allclose(data["error_0"], e)

    def test_save_errorbar_pkl(self, qtbot, tmp_path, monkeypatch):
        w = self._make_widget(qtbot)
        w.errorbar([1, 2], [3, 4], yerr=[0.1, 0.2])
        out = str(tmp_path / "test.pkl")
        self._mock_dialog(monkeypatch, out, "Pickle (*.pkl)")
        w.toolbar.save_data()
        with open(out, "rb") as f:
            payload = pickle.load(f)
        assert payload["plot_type"] == "errorbar"
        assert "figure" in payload
        assert len(payload["data"]["datasets"]) == 1

    # -- imshow saves --

    def test_save_imshow_dat(self, qtbot, tmp_path, monkeypatch):
        w = self._make_widget(qtbot)
        arr = np.array([[1.0, 2.0], [3.0, 4.0]])
        w.imshow(arr, extent=[0, 1, 0, 1], update=False)
        out = str(tmp_path / "test.dat")
        self._mock_dialog(monkeypatch, out)
        w.toolbar.save_data()
        loaded = np.loadtxt(out)
        assert_allclose(loaded, arr)

    def test_save_imshow_npz(self, qtbot, tmp_path, monkeypatch):
        w = self._make_widget(qtbot)
        arr = np.array([[1.0, 2.0], [3.0, 4.0]])
        w.imshow(arr, extent=[0, 10, 0, 20], update=False)
        out = str(tmp_path / "test.npz")
        self._mock_dialog(monkeypatch, out, "Numpy archive (*.npz)")
        w.toolbar.save_data()
        data = np.load(out)
        assert str(data["plot_type"]) == "imshow"
        assert_allclose(data["extent"], [0, 10, 0, 20])

    # -- pcolormesh saves (flat shading, 1D edge arrays) --

    def test_save_pcolormesh_flat_dat(self, qtbot, tmp_path, monkeypatch):
        w = self._make_widget(qtbot)
        x_edges = np.array([0.0, 1.0, 2.0, 3.0])
        y_edges = np.array([0.0, 1.0, 2.0])
        z = np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])
        w.pcolormesh(x_edges, y_edges, z)
        out = str(tmp_path / "test.dat")
        self._mock_dialog(monkeypatch, out)
        w.toolbar.save_data()
        text = open(out).read()
        assert "shading: flat" in text
        rows = np.loadtxt(out)
        assert rows.shape == (6, 3)
        # x_centers=[0.5,1.5,2.5], y_centers=[0.5,1.5]
        assert_allclose(rows[0], [0.5, 0.5, 1.0])
        assert_allclose(rows[1], [0.5, 1.5, 4.0])
        assert_allclose(rows[4], [2.5, 0.5, 3.0])
        assert_allclose(rows[5], [2.5, 1.5, 6.0])

    def test_save_pcolormesh_flat_npz(self, qtbot, tmp_path, monkeypatch):
        w = self._make_widget(qtbot)
        x_edges = np.array([0.0, 1.0, 2.0, 3.0])
        y_edges = np.array([0.0, 1.0, 2.0])
        z = np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])
        w.pcolormesh(x_edges, y_edges, z)
        out = str(tmp_path / "test.npz")
        self._mock_dialog(monkeypatch, out, "Numpy archive (*.npz)")
        w.toolbar.save_data()
        data = np.load(out)
        assert str(data["plot_type"]) == "pcolormesh"
        assert str(data["shading"]) == "flat"
        assert_allclose(data["z_data_0"], z)
        assert len(data["x_edges_0"]) == len(x_edges)
        assert len(data["y_edges_0"]) == len(y_edges)

    # -- pcolormesh saves (gouraud shading, 2D node grids) --

    def test_detect_pcolormesh_gouraud(self, qtbot):
        w = self._make_widget(qtbot)
        x2d = np.array([[0, 1, 3], [0.5, 1.5, 3.5], [1, 2, 4]], dtype=float)
        y2d = np.array([[0, 0.1, 0.3], [1, 1.1, 1.3], [2, 2.1, 2.3]], dtype=float)
        z2d = np.array([[1, 2, 3], [4, 5, 6], [7, 8, 9]], dtype=float)
        w.pcolormesh(x2d, y2d, z2d, shading="gouraud")
        assert _detect_plot_type(w.canvas.ax) == "pcolormesh"

    def test_save_pcolormesh_gouraud_dat(self, qtbot, tmp_path, monkeypatch):
        """Gouraud xyz output must have ALL z_data points with per-cell coords."""
        w = self._make_widget(qtbot)
        # Irregular grid: each row has different x values
        x2d = np.array([[0, 1, 3], [0.5, 1.5, 3.5], [1, 2, 4]], dtype=float)
        y2d = np.array([[0, 0.1, 0.3], [1, 1.1, 1.3], [2, 2.1, 2.3]], dtype=float)
        z2d = np.array([[1, 2, 3], [4, 5, 6], [7, 8, 9]], dtype=float)
        w.pcolormesh(x2d, y2d, z2d, shading="gouraud")
        out = str(tmp_path / "test.dat")
        self._mock_dialog(monkeypatch, out)
        w.toolbar.save_data()
        text = open(out).read()
        assert "shading: gouraud" in text
        assert "grid: 3 3" in text
        rows = np.loadtxt(out)
        # 3 rows × 3 cols = 9 data lines, each with true (x, y, z)
        assert rows.shape == (9, 3)
        # Row 0: x2d[0,:], y2d[0,:], z2d[0,:]
        assert_allclose(rows[0], [0.0, 0.0, 1.0])
        assert_allclose(rows[1], [1.0, 0.1, 2.0])
        assert_allclose(rows[2], [3.0, 0.3, 3.0])
        # Row 1: x2d[1,:], y2d[1,:], z2d[1,:]
        assert_allclose(rows[3], [0.5, 1.0, 4.0])
        # Last: x2d[2,2], y2d[2,2], z2d[2,2]
        assert_allclose(rows[8], [4.0, 2.3, 9.0])

    def test_save_pcolormesh_gouraud_npz(self, qtbot, tmp_path, monkeypatch):
        w = self._make_widget(qtbot)
        x2d = np.array([[0, 1, 3], [0.5, 1.5, 3.5], [1, 2, 4]], dtype=float)
        y2d = np.array([[0, 0.1, 0.3], [1, 1.1, 1.3], [2, 2.1, 2.3]], dtype=float)
        z2d = np.array([[1, 2, 3], [4, 5, 6], [7, 8, 9]], dtype=float)
        w.pcolormesh(x2d, y2d, z2d, shading="gouraud")
        out = str(tmp_path / "test.npz")
        self._mock_dialog(monkeypatch, out, "Numpy archive (*.npz)")
        w.toolbar.save_data()
        data = np.load(out)
        assert str(data["plot_type"]) == "pcolormesh"
        assert str(data["shading"]) == "gouraud"
        assert_allclose(data["z_data_0"], z2d)
        assert_allclose(data["x_grid_0"], x2d)
        assert_allclose(data["y_grid_0"], y2d)

    # -- line saves --

    def test_save_line_dat(self, qtbot, tmp_path, monkeypatch):
        w = self._make_widget(qtbot)
        x = np.array([1.0, 2.0, 3.0])
        y = np.array([4.0, 5.0, 6.0])
        w.plot(x, y)
        out = str(tmp_path / "test.dat")
        self._mock_dialog(monkeypatch, out)
        w.toolbar.save_data()
        loaded = np.loadtxt(out)
        assert_allclose(loaded[:, 0], x)
        assert_allclose(loaded[:, 1], y)

    # -- error handling --

    def test_save_empty_plot_shows_error(self, qtbot, monkeypatch):
        w = self._make_widget(qtbot)
        errors = []
        monkeypatch.setattr(
            QtWidgets.QMessageBox,
            "critical",
            staticmethod(lambda *_a, **_kw: errors.append(_a)),
        )
        w.toolbar.save_data()
        assert len(errors) == 1
        assert "empty" in errors[0][2].lower()

    # -- overlay filtering --

    def test_save_imshow_with_overlays_npz(self, qtbot, tmp_path, monkeypatch):
        w = self._make_widget(qtbot)
        arr = np.array([[10.0, 20.0], [30.0, 40.0]])
        w.imshow(arr, extent=[0, 1, 0, 1], update=False)
        w.canvas.ax.axvline(0.5, color="red")
        w.canvas.ax.axhline(0.5, color="green")
        out = str(tmp_path / "test.npz")
        self._mock_dialog(monkeypatch, out, "Numpy archive (*.npz)")
        w.toolbar.save_data()
        data = np.load(out)
        assert str(data["plot_type"]) == "imshow"

    # -- imshow origin --

    def test_save_imshow_origin_lower(self, qtbot, tmp_path, monkeypatch):
        w = self._make_widget(qtbot)
        arr = np.array([[1.0, 2.0], [3.0, 4.0]])
        w.imshow(arr, extent=[0, 10, 0, 20], origin="lower", update=False)
        out = str(tmp_path / "test.dat")
        self._mock_dialog(monkeypatch, out)
        w.toolbar.save_data()
        text = open(out).read()
        assert "origin: lower" in text

    def test_save_imshow_origin_upper(self, qtbot, tmp_path, monkeypatch):
        w = self._make_widget(qtbot)
        arr = np.array([[1.0, 2.0], [3.0, 4.0]])
        w.imshow(arr, extent=[0, 10, 0, 20], origin="upper", update=False)
        out = str(tmp_path / "test.dat")
        self._mock_dialog(monkeypatch, out)
        w.toolbar.save_data()
        text = open(out).read()
        assert "origin: upper" in text

    def test_save_imshow_origin_npz(self, qtbot, tmp_path, monkeypatch):
        w = self._make_widget(qtbot)
        arr = np.array([[1.0, 2.0], [3.0, 4.0]])
        w.imshow(arr, extent=[0, 10, 0, 20], origin="lower", update=False)
        out = str(tmp_path / "test.npz")
        self._mock_dialog(monkeypatch, out, "Numpy archive (*.npz)")
        w.toolbar.save_data()
        data = np.load(out, allow_pickle=True)
        assert str(data["origin"]) == "lower"

    # -- round-trip tests --

    def test_roundtrip_errorbar_dat(self, qtbot, tmp_path, monkeypatch):
        """Write errorbar .dat, read back, verify X/Y/E match."""
        w = self._make_widget(qtbot)
        x = np.array([1.0, 2.0, 3.0])
        y = np.array([10.0, 20.0, 30.0])
        e = np.array([0.5, 1.0, 1.5])
        w.errorbar(x, y, yerr=e)
        out = str(tmp_path / "rt.dat")
        self._mock_dialog(monkeypatch, out)
        w.toolbar.save_data()
        loaded = np.loadtxt(out)
        assert_allclose(loaded[:, 0], x)
        assert_allclose(loaded[:, 1], y)
        assert_allclose(loaded[:, 2], e)

    def test_roundtrip_line_dat(self, qtbot, tmp_path, monkeypatch):
        """Write line .dat, read back, verify X/Y match."""
        w = self._make_widget(qtbot)
        x = np.array([0.5, 1.5, 2.5, 3.5])
        y = np.array([10.0, 20.0, 15.0, 25.0])
        w.plot(x, y)
        out = str(tmp_path / "rt.dat")
        self._mock_dialog(monkeypatch, out)
        w.toolbar.save_data()
        loaded = np.loadtxt(out)
        assert_allclose(loaded[:, 0], x)
        assert_allclose(loaded[:, 1], y)

    def test_roundtrip_imshow_dat(self, qtbot, tmp_path, monkeypatch):
        """Write imshow .dat, read back with extent+origin, verify array."""
        w = self._make_widget(qtbot)
        arr = np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])
        extent = [0, 30, 0, 20]
        w.imshow(arr, extent=extent, origin="lower", update=False)
        out = str(tmp_path / "rt.dat")
        self._mock_dialog(monkeypatch, out)
        w.toolbar.save_data()
        # Read back and verify
        loaded = np.loadtxt(out)
        assert_allclose(loaded, arr)
        text = open(out).read()
        assert "origin: lower" in text
        assert "xmin=0" in text
        assert "xmax=30" in text

    def test_roundtrip_pcolormesh_flat_dat(self, qtbot, tmp_path, monkeypatch):
        """Write flat pcolormesh .dat, read back as xyz, reconstruct z grid."""
        w = self._make_widget(qtbot)
        x_edges = np.array([0.0, 1.0, 2.0, 3.0])
        y_edges = np.array([0.0, 1.0, 2.0])
        z = np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])
        w.pcolormesh(x_edges, y_edges, z)
        out = str(tmp_path / "rt.dat")
        self._mock_dialog(monkeypatch, out)
        w.toolbar.save_data()
        rows = np.loadtxt(out)
        xs = np.unique(rows[:, 0])
        ys = np.unique(rows[:, 1])
        z_rt = rows[:, 2].reshape(len(xs), len(ys)).T
        assert_allclose(z_rt, z)

    def test_roundtrip_pcolormesh_gouraud_dat(self, qtbot, tmp_path, monkeypatch):
        """Write gouraud pcolormesh .dat, read back using grid dims, verify all arrays."""
        w = self._make_widget(qtbot)
        x2d = np.array([[0, 1, 3], [0.5, 1.5, 3.5], [1, 2, 4]], dtype=float)
        y2d = np.array([[0, 0.1, 0.3], [1, 1.1, 1.3], [2, 2.1, 2.3]], dtype=float)
        z2d = np.array([[1, 2, 3], [4, 5, 6], [7, 8, 9]], dtype=float)
        w.pcolormesh(x2d, y2d, z2d, shading="gouraud")
        out = str(tmp_path / "rt.dat")
        self._mock_dialog(monkeypatch, out)
        w.toolbar.save_data()
        # Reconstruct using grid dimensions from header
        import re

        text = open(out).read()
        m = re.search(r"grid: (\d+) (\d+)", text)
        ny, nx = int(m.group(1)), int(m.group(2))
        rows = np.loadtxt(out)
        x_rt = rows[:, 0].reshape(ny, nx)
        y_rt = rows[:, 1].reshape(ny, nx)
        z_rt = rows[:, 2].reshape(ny, nx)
        assert_allclose(x_rt, x2d)
        assert_allclose(y_rt, y2d)
        assert_allclose(z_rt, z2d)

    def test_roundtrip_all_npz(self, qtbot, tmp_path, monkeypatch):
        """Verify .npz round-trip for all plot types."""
        # errorbar
        w = self._make_widget(qtbot)
        w.errorbar([1, 2], [3, 4], yerr=[0.1, 0.2])
        out = str(tmp_path / "eb.npz")
        self._mock_dialog(monkeypatch, out, "Numpy archive (*.npz)")
        w.toolbar.save_data()
        d = np.load(out, allow_pickle=True)
        assert str(d["plot_type"]) == "errorbar"
        assert_allclose(d["x_0"], [1, 2])

        # imshow
        w2 = self._make_widget(qtbot)
        arr = np.array([[5.0, 6.0], [7.0, 8.0]])
        w2.imshow(arr, extent=[0, 1, 0, 1], origin="lower", update=False)
        out2 = str(tmp_path / "im.npz")
        self._mock_dialog(monkeypatch, out2, "Numpy archive (*.npz)")
        w2.toolbar.save_data()
        d2 = np.load(out2, allow_pickle=True)
        assert str(d2["plot_type"]) == "imshow"
        assert str(d2["origin"]) == "lower"
        assert_allclose(d2["data"], arr)

        # pcolormesh gouraud (irregular grid)
        w3 = self._make_widget(qtbot)
        x2d = np.array([[0, 1.5], [0.5, 2.0]], dtype=float)
        y2d = np.array([[0, 0.1], [1, 1.1]], dtype=float)
        z2d = np.array([[10, 20], [30, 40]], dtype=float)
        w3.pcolormesh(x2d, y2d, z2d, shading="gouraud")
        out3 = str(tmp_path / "pm.npz")
        self._mock_dialog(monkeypatch, out3, "Numpy archive (*.npz)")
        w3.toolbar.save_data()
        d3 = np.load(out3)
        assert str(d3["plot_type"]) == "pcolormesh"
        assert str(d3["shading"]) == "gouraud"
        assert_allclose(d3["z_data_0"], z2d)
        assert_allclose(d3["x_grid_0"], x2d)
        assert_allclose(d3["y_grid_0"], y2d)

    # -- metadata preservation --

    def test_errorbar_yscale_in_dat(self, qtbot, tmp_path, monkeypatch):
        """Log y-scale is written to the .dat header."""
        w = self._make_widget(qtbot)
        w.errorbar([1, 2], [3, 4], yerr=[0.1, 0.2])
        w.canvas.ax.set_yscale("log")
        out = str(tmp_path / "test.dat")
        self._mock_dialog(monkeypatch, out)
        w.toolbar.save_data()
        text = open(out).read()
        assert "yscale: log" in text

    def test_errorbar_yscale_in_npz(self, qtbot, tmp_path, monkeypatch):
        w = self._make_widget(qtbot)
        w.errorbar([1, 2], [3, 4], yerr=[0.1, 0.2])
        w.canvas.ax.set_yscale("log")
        out = str(tmp_path / "test.npz")
        self._mock_dialog(monkeypatch, out, "Numpy archive (*.npz)")
        w.toolbar.save_data()
        data = np.load(out, allow_pickle=True)
        assert str(data["yscale"]) == "log"

    def test_imshow_lognorm_in_dat(self, qtbot, tmp_path, monkeypatch):
        """LogNorm and cmap are written to the imshow .dat header."""
        w = self._make_widget(qtbot)
        w.imshow(np.ones((3, 3)) + 1, log=True, imin=0.1, imax=10, update=False)
        out = str(tmp_path / "test.dat")
        self._mock_dialog(monkeypatch, out)
        w.toolbar.save_data()
        text = open(out).read()
        assert "norm: LogNorm" in text
        assert "cmap:" in text

    def test_pcolormesh_lognorm_in_dat(self, qtbot, tmp_path, monkeypatch):
        """LogNorm and cmap are written to the pcolormesh .dat header."""
        w = self._make_widget(qtbot)
        x = np.array([0.0, 1.0, 2.0, 3.0])
        y = np.array([0.0, 1.0, 2.0])
        z = np.ones((2, 3)) + 1
        w.pcolormesh(x, y, z, log=True, imin=0.1, imax=10)
        out = str(tmp_path / "test.dat")
        self._mock_dialog(monkeypatch, out)
        w.toolbar.save_data()
        text = open(out).read()
        assert "norm: LogNorm" in text
        assert "norm_vmin: 0.1" in text
        assert "norm_vmax: 10" in text

    def test_errorbar_labels_in_dat(self, qtbot, tmp_path, monkeypatch):
        """Dataset labels from legend are preserved in the .dat header."""
        w = self._make_widget(qtbot)
        w.errorbar([1, 2], [3, 4], yerr=[0.1, 0.2], label="Active")
        w.errorbar([2, 3], [5, 6], yerr=[0.2, 0.3], label="43279")
        out = str(tmp_path / "test.dat")
        self._mock_dialog(monkeypatch, out)
        w.toolbar.save_data()
        text = open(out).read()
        assert "Dataset 0: Active" in text
        assert "Dataset 1: 43279" in text

    def test_save_errorbar_with_nan_dat(self, qtbot, tmp_path, monkeypatch):
        """Errorbar data with NaN values (empty matplotlib segments) saves without error."""
        w = self._make_widget(qtbot)
        x = np.array([1.0, 2.0, 3.0, 4.0])
        y = np.array([10.0, np.nan, 30.0, 40.0])
        e = np.array([0.5, 1.0, 1.5, np.nan])
        w.errorbar(x, y, yerr=e)
        out = str(tmp_path / "test.dat")
        self._mock_dialog(monkeypatch, out)
        w.toolbar.save_data()
        loaded = np.loadtxt(out)
        assert_allclose(loaded[:, 0], x)
        # Valid points should have correct data; NaN points produce NaN error
        assert_allclose(loaded[0, 1], 10.0)
        assert_allclose(loaded[2, 1], 30.0)
        assert loaded.shape[0] == 4

    def test_pcolormesh_title_labels_in_dat(self, qtbot, tmp_path, monkeypatch):
        """Title and axis labels are written to the pcolormesh .dat header."""
        w = self._make_widget(qtbot)
        x2d = np.array([[0, 1], [0, 1]], dtype=float)
        y2d = np.array([[0, 0], [1, 1]], dtype=float)
        z2d = np.array([[1, 2], [3, 4]], dtype=float)
        w.pcolormesh(x2d, y2d, z2d, shading="gouraud")
        w.canvas.ax.set_title("Off_Off")
        w.canvas.ax.set_xlabel(r"k$_{i,z}$-k$_{f,z}$ [\u00c5$^{-1}$]")
        w.canvas.ax.set_ylabel(r"Q$_z$ [\u00c5$^{-1}$]")
        out = str(tmp_path / "test.dat")
        self._mock_dialog(monkeypatch, out)
        w.toolbar.save_data()
        text = open(out).read()
        assert "title: Off_Off" in text
        assert "xlabel: k$" in text
        assert "ylabel: Q$" in text
