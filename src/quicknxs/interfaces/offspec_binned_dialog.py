# coding: utf-8
"""Dialog to let the user configure off-specular binned output parameters."""

from mantid.simpleapi import logger
from matplotlib.lines import Line2D
from numpy import float64
from numpy.typing import NDArray
from qtpy import QtCore, QtWidgets

from quicknxs.interfaces import load_ui
from quicknxs.interfaces.data_manager import DataManager
from quicknxs.ui.mplwidget import MPLWidget


class OffSpecBinnedDialog(QtWidgets.QDialog):
    """Dialog to define off-specular binned output parameters with plot preview."""

    INTENSITY_MIN = 1e-6  # starting value for the color scale
    INTENSITY_MAX = 1.0  # ending value for the color scale
    GRID_OFFSET = 0.05  # Starting percentage offset of the grid area inside the whole plot area

    drawing = False

    def __init__(self, parent, data_manager: DataManager):
        QtWidgets.QDialog.__init__(self, parent)
        self.ui = load_ui("ui_offspec_binned_dialog.ui", base_instance=self)
        self.data_manager = data_manager
        self.rect_region = None

        # Load saved values from settings
        self.load_settings()

        # Connect signals to update bin width display
        self.ui.offspec_bins_y.valueChanged.connect(self.update_bin_width)
        self.ui.offspec_y_min.valueChanged.connect(self.update_bin_width)
        self.ui.offspec_y_max.valueChanged.connect(self.update_bin_width)

        # Connect signals to update plot region
        self.ui.offspec_x_min.valueChanged.connect(self.update_region)
        self.ui.offspec_x_max.valueChanged.connect(self.update_region)
        self.ui.offspec_y_min.valueChanged.connect(self.update_region)
        self.ui.offspec_y_max.valueChanged.connect(self.update_region)

        # Connect radio buttons to update coordinate ranges and redraw plot
        self.ui.kizmkfzVSqz.toggled.connect(self.on_coordinate_system_changed)
        self.ui.qxVSqz.toggled.connect(self.on_coordinate_system_changed)
        self.ui.kizVSkfz.toggled.connect(self.on_coordinate_system_changed)

        # Update bin width display on initialization
        self.update_bin_width()

        # Draw the initial plot (deferred to avoid blocking)
        QtCore.QTimer.singleShot(0, self.draw_plot)

    def draw_plot(self):
        """Draw the off-specular data with the configured region overlay."""
        if self.drawing:
            return
        self.drawing = True

        # Skip drawing if widget isn't visible (e.g., in tests)
        if not self.isVisible():
            self.drawing = False
            return

        plot = self.ui.plot
        plot.clear()
        plot.set_xticks_fontsize(8)
        plot.set_yticks_fontsize(8)

        # Initialize limits
        qz_min, qz_max = 0.5, -0.1
        qx_min, qx_max = -0.001, 0.001
        ki_z_min, ki_z_max = 0.1, -0.1
        kf_z_min, kf_z_max = 0.1, -0.1
        k_diff_min, k_diff_max = 0.01, -0.01

        # Get first state from reduction_states
        if not self.data_manager.reduction_states:
            self.drawing = False
            return

        first_state = self.data_manager.reduction_states[0]

        # Plot data from all runs in the reduction list
        for item in self.data_manager.reduction_list:
            # Check if off_spec data exists
            if first_state not in item.cross_sections:
                continue
            if item.cross_sections[first_state].off_spec is None:
                continue

            offspec = item.cross_sections[first_state].off_spec
            Qx, Qz, ki_z, kf_z, I, _ = (offspec.Qx, offspec.Qz, offspec.ki_z, offspec.kf_z, offspec.S, offspec.dS)

            n_total = len(I[0])
            # P_0 and P_N are the number of points to cut in TOF on each side
            p_0 = item.cross_sections[first_state].configuration.cut_first_n_points
            p_n = n_total - item.cross_sections[first_state].configuration.cut_last_n_points

            Qx = Qx[:, p_0:p_n]
            Qz = Qz[:, p_0:p_n]
            ki_z = ki_z[:, p_0:p_n]
            kf_z = kf_z[:, p_0:p_n]
            I = I[:, p_0:p_n]

            # Extend the X and Y limits of the plotting area
            try:
                qz_max = max(Qz[I > 0].max(), qz_max)
                qz_min = min(Qz[I > 0].min(), qz_min)
                qx_min = min(qx_min, Qx[I > 0].min())
                qx_max = max(qx_max, Qx[I > 0].max())
                ki_z_min = min(ki_z_min, ki_z[I > 0].min())
                ki_z_max = max(ki_z_max, ki_z[I > 0].max())
                kf_z_min = min(kf_z_min, kf_z[I > 0].min())
                kf_z_max = max(kf_z_max, kf_z[I > 0].max())
                k_diff_min = min(k_diff_min, (ki_z - kf_z)[I > 0].min())
                k_diff_max = max(k_diff_max, (ki_z - kf_z)[I > 0].max())
            except Exception as exception:
                logger.error(f"Error extending plotting limits: {exception}")

            self._paint_intensities(ki_z, kf_z, Qx, Qz, I, plot)

        # Set plot limits and labels based on selected axis type
        if self.ui.kizmkfzVSqz.isChecked():
            plot.canvas.ax.set_xlim([k_diff_min, k_diff_max])
            plot.canvas.ax.set_ylim([qz_min, qz_max])
            plot.set_xlabel("k$_{i,z}$-k$_{f,z}$ [Å$^{-1}$]", fontsize=14)
            plot.set_ylabel("Q$_z$ [Å$^{-1}$]", fontsize=14)
            x1, x2, y1, y2 = self._grid_region_coordinates(k_diff_min, k_diff_max, qz_min, qz_max)
            coord_key = "k_diff"
        elif self.ui.qxVSqz.isChecked():
            plot.canvas.ax.set_xlim([qx_min, qx_max])
            plot.canvas.ax.set_ylim([qz_min, qz_max])
            plot.set_xlabel("Q$_x$ [Å$^{-1}$]", fontsize=14)
            plot.set_ylabel("Q$_z$ [Å$^{-1}$]", fontsize=14)
            x1, x2, y1, y2 = self._grid_region_coordinates(qx_min, qx_max, qz_min, qz_max)
            coord_key = "qx_qz"
        elif self.ui.kizVSkfz.isChecked():
            plot.canvas.ax.set_xlim([ki_z_min, ki_z_max])
            plot.canvas.ax.set_ylim([kf_z_min, kf_z_max])
            plot.set_xlabel("k$_{i,z}$ [Å$^{-1}$]", fontsize=14)
            plot.set_ylabel("k$_{f,z}$ [Å$^{-1}$]", fontsize=14)
            x1, x2, y1, y2 = self._grid_region_coordinates(ki_z_min, ki_z_max, kf_z_min, kf_z_max)
            coord_key = "ki_kf"

        # Update spinboxes with calculated default values
        # This matches smooth_dialog behavior - recalculate from data on each coordinate change
        self.ui.offspec_x_min.setValue(x1)
        self.ui.offspec_x_max.setValue(x2)
        self.ui.offspec_y_min.setValue(y1)
        self.ui.offspec_y_max.setValue(y2)

        # Draw the region rectangle
        # Create and add the rectangle directly (matches smooth_dialog pattern)
        self.rect_region = Line2D([x1, x1, x2, x2, x1], [y1, y2, y2, y1, y1])
        plot.canvas.ax.add_line(self.rect_region)

        # Show the plot
        if plot.cplot is not None:
            plot.cplot.set_clim([self.INTENSITY_MIN, self.INTENSITY_MAX])
        try:
            plot.draw()
        except Exception:
            pass  # Ignore drawing errors in headless environments
        self.drawing = False

    def _grid_region_coordinates(
        self, x_min: float, x_max: float, y_min: float, y_max: float
    ) -> tuple[float, float, float, float]:
        """
        Calculate the coordinates of box inside the plot area representing the grid region.

        Parameters
        ----------
        x_min, x_max : float
            Min/max values for X axis
        y_min, y_max : float
            Min/max values for Y axis

        Returns
        -------
        Coordinates of the grid region box (x1, x2, y1, y2)
        """
        x_offset = (x_max - x_min) * self.GRID_OFFSET
        y_offset = (y_max - y_min) * self.GRID_OFFSET
        return x_min + x_offset, x_max - x_offset, y_min + y_offset, y_max - y_offset

    def on_coordinate_system_changed(self):
        """Handle coordinate system radio button changes - recalculate ranges from data."""
        if self.drawing:
            return

        # Redraw the plot with new coordinate system, which recalculates ranges from data
        # This matches the behavior of smooth_dialog
        self.draw_plot()

    def _paint_intensities(
        self,
        ki_z: NDArray[float64],
        kf_z: NDArray[float64],
        Qx: NDArray[float64],
        Qz: NDArray[float64],
        I: NDArray[float64],
        plot: MPLWidget,
    ):
        """Color-paint the intensities versus appropriate X and Y coordinates."""
        common_args = {
            "log": True,
            "imin": self.INTENSITY_MIN,
            "imax": self.INTENSITY_MAX,
            "cmap": "jet",
            "shading": "gouraud",
        }

        if self.ui.kizmkfzVSqz.isChecked():
            x, y = (ki_z - kf_z), Qz
        elif self.ui.qxVSqz.isChecked():
            x, y = Qx, Qz
        elif self.ui.kizVSkfz.isChecked():
            x, y = ki_z, kf_z
        else:
            x, y = (ki_z - kf_z), Qz  # Default

        plot.pcolormesh(x, y, I, **common_args)

    def update_region(self):
        """Update the rectangle overlay showing the binning region."""
        if self.drawing:
            return

        # Only update if plot has been initialized with data and rectangle exists
        if not self.data_manager.reduction_states or self.rect_region is None:
            return

        x1 = self.ui.offspec_x_min.value()
        x2 = self.ui.offspec_x_max.value()
        y1 = self.ui.offspec_y_min.value()
        y2 = self.ui.offspec_y_max.value()

        # Update rectangle data (matches smooth_dialog updateSettings pattern)
        self.rect_region.set_data([x1, x1, x2, x2, x1], [y1, y2, y2, y1, y1])
        try:
            self.ui.plot.draw()
        except Exception:
            pass  # Ignore drawing errors in headless environments

    def load_settings(self):
        """Load parameter values from QSettings."""
        settings = QtCore.QSettings(".quicknxs")

        # Load X-axis range
        if settings.contains("offspec_binned/x_min"):
            self.ui.offspec_x_min.setValue(float(settings.value("offspec_binned/x_min")))
        if settings.contains("offspec_binned/x_max"):
            self.ui.offspec_x_max.setValue(float(settings.value("offspec_binned/x_max")))

        # Load Y-axis range
        if settings.contains("offspec_binned/y_min"):
            self.ui.offspec_y_min.setValue(float(settings.value("offspec_binned/y_min")))
        if settings.contains("offspec_binned/y_max"):
            self.ui.offspec_y_max.setValue(float(settings.value("offspec_binned/y_max")))

        # Load bin counts
        if settings.contains("offspec_binned/bins_x"):
            self.ui.offspec_bins_x.setValue(int(settings.value("offspec_binned/bins_x")))
        if settings.contains("offspec_binned/bins_y"):
            self.ui.offspec_bins_y.setValue(int(settings.value("offspec_binned/bins_y")))

        # Load error weighting
        if settings.contains("offspec_binned/error_weighting"):
            self.ui.error_weighting_checkbox.setChecked(settings.value("offspec_binned/error_weighting", type=bool))

    def save_settings(self):
        """Save parameter values to QSettings."""
        settings = QtCore.QSettings(".quicknxs")

        # Save X-axis range
        settings.setValue("offspec_binned/x_min", self.ui.offspec_x_min.value())
        settings.setValue("offspec_binned/x_max", self.ui.offspec_x_max.value())

        # Save Y-axis range
        settings.setValue("offspec_binned/y_min", self.ui.offspec_y_min.value())
        settings.setValue("offspec_binned/y_max", self.ui.offspec_y_max.value())

        # Save bin counts
        settings.setValue("offspec_binned/bins_x", self.ui.offspec_bins_x.value())
        settings.setValue("offspec_binned/bins_y", self.ui.offspec_bins_y.value())

        # Save error weighting
        settings.setValue("offspec_binned/error_weighting", self.ui.error_weighting_checkbox.isChecked())

    def update_bin_width(self):
        """Calculate and display the Qz bin width based on current settings."""
        bins_y = self.ui.offspec_bins_y.value()
        y_min = self.ui.offspec_y_min.value()
        y_max = self.ui.offspec_y_max.value()

        if bins_y > 0:
            width = (y_max - y_min) / bins_y
            self.ui.qz_bin_width_label.setText(f"{width:8.6f} 1/A")
        else:
            self.ui.qz_bin_width_label.setText("N/A")

    def get_parameters(self):
        """
        Get the binning parameters as a dictionary.

        Returns
        -------
        dict
            Dictionary containing off-specular binning parameters
        """
        from quicknxs.interfaces.configuration import Configuration

        # Determine coordinate system setting
        if self.ui.kizVSkfz.isChecked():
            off_spec_x_axis = Configuration.KZI_VS_KZF
        elif self.ui.qxVSqz.isChecked():
            off_spec_x_axis = Configuration.QX_VS_QZ
        else:
            off_spec_x_axis = Configuration.DELTA_KZ_VS_QZ

        return {
            "off_spec_x_axis": off_spec_x_axis,
            "off_spec_x_min": self.ui.offspec_x_min.value(),
            "off_spec_x_max": self.ui.offspec_x_max.value(),
            "off_spec_y_min": self.ui.offspec_y_min.value(),
            "off_spec_y_max": self.ui.offspec_y_max.value(),
            "off_spec_nxbins": self.ui.offspec_bins_x.value(),
            "off_spec_nybins": self.ui.offspec_bins_y.value(),
            "off_spec_err_weight": self.ui.error_weighting_checkbox.isChecked(),
        }

    def accept(self):
        """Override accept to save settings before closing."""
        self.save_settings()
        super().accept()
