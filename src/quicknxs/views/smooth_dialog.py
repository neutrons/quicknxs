"""Dialog to configure off-specular parameters (smoothing and/or binning)."""

import math

from mantid.simpleapi import logger
from matplotlib.lines import Line2D
from matplotlib.patches import Ellipse
from numpy import float64
from numpy.typing import NDArray
from qtpy import QtCore, QtWidgets

from quicknxs.enums import OffSpecXAxis
from quicknxs.models.off_specular import finest_intervals
from quicknxs.presenters.data_manager import DataManager
from quicknxs.views import load_ui
from quicknxs.views.widgets import MPLWidget


class OffSpecParametersDialog(QtWidgets.QDialog):
    """Combined dialog for off-specular smoothing and binning parameters."""

    INTENSITY_MIN = 1e-6  # starting value for the color scale
    INTENSITY_MAX = 1.0  # ending value for the color scale
    GRID_OFFSET = 0.05  # Starting percentage offset of the grid area inside the whole plot area

    drawing = False

    def __init__(self, parent, data_manager: DataManager, show_smoothing: bool = False, show_binning: bool = False):
        """
        Initialize the combined off-specular parameters dialog.

        Parameters
        ----------
        parent : QWidget
            Parent widget
        data_manager : DataManager
            Data manager instance
        show_smoothing : bool
            Whether to show smoothing parameters
        show_binning : bool
            Whether to show binning parameters
        """
        QtWidgets.QDialog.__init__(self, parent)
        self.ui = load_ui("ui_smooth_dialog.ui", base_instance=self)
        self.data_manager = data_manager
        self.show_smoothing = show_smoothing
        self.show_binning = show_binning
        self.rect_region = None
        self.sigma_1 = None
        self.sigma_2 = None
        self.sigma_3 = None

        # Show/hide sections based on what's requested
        self._configure_visibility()

        # Load saved values from settings
        self.load_settings()

        # Connect signals for binning
        if show_binning:
            self.ui.offspec_bins_y.valueChanged.connect(self.update_bin_width)
            self.ui.offspec_y_min.valueChanged.connect(self.update_bin_width)
            self.ui.offspec_y_max.valueChanged.connect(self.update_bin_width)

        # Connect signals for smoothing
        if show_smoothing:
            self.ui.sigmaX.valueChanged.connect(self.update_settings)
            self.ui.sigmaY.valueChanged.connect(self.update_settings)
            self.ui.sigmasCoupled.toggled.connect(self.update_sigma_coupling)
            self.ui.rSigmas.valueChanged.connect(self.update_settings)
            self.ui.autoGridBins.toggled.connect(self.update_auto_grid_state)
            # Recompute the automatic smoothing grid when the region changes
            self.ui.offspec_x_min.valueChanged.connect(self.update_auto_bins)
            self.ui.offspec_x_max.valueChanged.connect(self.update_auto_bins)
            self.ui.offspec_y_min.valueChanged.connect(self.update_auto_bins)
            self.ui.offspec_y_max.valueChanged.connect(self.update_auto_bins)

        # Connect plot interaction for region selection (common to both binning and smoothing)
        self.ui.plot.canvas.mpl_connect("motion_notify_event", self.plot_select)
        self.ui.plot.canvas.mpl_connect("button_press_event", self.plot_select)

        # Connect signals to update plot region
        self.ui.offspec_x_min.valueChanged.connect(self.update_region)
        self.ui.offspec_x_max.valueChanged.connect(self.update_region)
        self.ui.offspec_y_min.valueChanged.connect(self.update_region)
        self.ui.offspec_y_max.valueChanged.connect(self.update_region)

        # Connect radio buttons to update coordinate ranges and redraw plot
        self.ui.kizmkfzVSqz.toggled.connect(self.on_coordinate_system_changed)
        self.ui.qxVSqz.toggled.connect(self.on_coordinate_system_changed)
        self.ui.kizVSkfz.toggled.connect(self.on_coordinate_system_changed)

        # Update bin width display on initialization if binning is shown
        if show_binning:
            self.update_bin_width()

        # Apply the auto-grid state (and compute the grid if auto is enabled)
        if show_smoothing:
            self.update_auto_grid_state()

        # Draw the initial plot (deferred to avoid blocking)
        QtCore.QTimer.singleShot(0, self.draw_plot)

    def _configure_visibility(self):
        """Show/hide dialog sections based on which options are selected."""
        # Smoothing-specific controls
        if hasattr(self.ui, "smoothing_group"):
            self.ui.smoothing_group.setVisible(self.show_smoothing)

        # Binning group contains bins (needed for both) and error weighting (binning only)
        # Show binning_group if either smoothing or binning is enabled
        if hasattr(self.ui, "binning_group"):
            self.ui.binning_group.setVisible(self.show_smoothing or self.show_binning)

        # Error weighting checkbox is only for binning
        if hasattr(self.ui, "error_weighting_checkbox"):
            self.ui.error_weighting_checkbox.setVisible(self.show_binning)

        # Update dialog title
        if self.show_smoothing and self.show_binning:
            self.setWindowTitle("Off-Specular Parameters (Smoothing & Binning)")
        elif self.show_smoothing:
            self.setWindowTitle("Off-Specular Parameters (Smoothing)")
        elif self.show_binning:
            self.setWindowTitle("Off-Specular Parameters (Binning)")

    def _grid_region_coordinates(
        self, x_min: float, x_max: float, y_min: float, y_max: float
    ) -> tuple[float, float, float, float]:
        """
        Calculate the coordinates of box inside the plot area representing the grid region.

        Parameters
        ----------
        x_min: float
            k_diff_min, qx_min or ki_z_min
        x_max: float
            k_diff_max, qx_max or ki_z_max
        y_min: float
            qz_min or kf_z_min
        y_max: float
            qz_max or kf_z_max

        Returns
        -------
        tuple
            Coordinates of the grid region box (x1, x2, y1, y2)
        """
        x_offset = (x_max - x_min) * self.GRID_OFFSET
        y_offset = (y_max - y_min) * self.GRID_OFFSET
        return x_min + x_offset, x_max - x_offset, y_min + y_offset, y_max - y_offset

    def _paint_intensities(
        self,
        ki_z: NDArray[float64],
        kf_z: NDArray[float64],
        Qx: NDArray[float64],
        Qz: NDArray[float64],
        I: NDArray[float64],
        plot: MPLWidget,
    ):
        """
        Color-paint the intensities versus appropriate X and Y coordinates.

        Parameters
        ----------
        ki_z : NDArray[float64]
            Array of z-component of incident wave vector
        kf_z : NDArray[float64]
            Array of z-component of final wave vector
        Qx : NDArray[float64]
            Array of x-component of momentum transfer
        Qz : NDArray[float64]
            Array of z-component of momentum transfer
        I : NDArray[float64]
            Intensity array
        plot : MPLWidget
            The plot object to draw on
        """
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

    def draw_plot(self):
        """Draw the off-specular data with the configured region overlay."""
        if self.drawing:
            return
        self.drawing = True

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
        Qzmax = 0.001

        # Get first state from reduction_states
        if not self.data_manager.reduction_states:
            self.drawing = False
            return

        first_state = self.data_manager.reduction_states[0]

        # Plot data from all runs in the reduction list
        for item in self.data_manager.reduction_list:
            # Check if off_spec data exists
            if first_state not in item.cross_sections:
                logger.warning(f"Cross section state '{first_state}' not found in item, skipping plot")
                continue
            if item.cross_sections[first_state].off_spec is None:
                logger.warning(f"No off-specular data available for state '{first_state}', skipping plot")
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
                Qzmax = max(ki_z.max() * 2.0, Qzmax)
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
        if self.ui.qxVSqz.isChecked():
            plot.canvas.ax.set_xlim([qx_min, qx_max])
            plot.canvas.ax.set_ylim([qz_min, qz_max])
            plot.set_xlabel("Q$_x$ [Å$^{-1}$]", fontsize=14)
            plot.set_ylabel("Q$_z$ [Å$^{-1}$]", fontsize=14)
            x1, x2, y1, y2 = self._grid_region_coordinates(qx_min, qx_max, qz_min, qz_max)
            sigma_pos = (0.0, Qzmax / 3.0)
            sigma_y_enabled = True
        elif self.ui.kizVSkfz.isChecked():
            plot.canvas.ax.set_xlim([ki_z_min, ki_z_max])
            plot.canvas.ax.set_ylim([kf_z_min, kf_z_max])
            plot.set_xlabel("k$_{i,z}$ [Å$^{-1}$]", fontsize=14)
            plot.set_ylabel("k$_{f,z}$ [Å$^{-1}$]", fontsize=14)
            x1, x2, y1, y2 = self._grid_region_coordinates(ki_z_min, ki_z_max, kf_z_min, kf_z_max)
            sigma_pos = (Qzmax / 6.0, Qzmax / 6.0)
            sigma_y_enabled = True
        else:
            # Default: k_i,z - k_f,z vs Q_z
            plot.canvas.ax.set_xlim([k_diff_min, k_diff_max])
            plot.canvas.ax.set_ylim([qz_min, qz_max])
            plot.set_xlabel("k$_{i,z}$-k$_{f,z}$ [Å$^{-1}$]", fontsize=14)
            plot.set_ylabel("Q$_z$ [Å$^{-1}$]", fontsize=14)
            x1, x2, y1, y2 = self._grid_region_coordinates(k_diff_min, k_diff_max, qz_min, qz_max)
            sigma_pos = (0.0, Qzmax / 3.0)
            sigma_y_enabled = False

        # Update spinboxes with calculated default values
        self.ui.offspec_x_min.setValue(x1)
        self.ui.offspec_x_max.setValue(x2)
        self.ui.offspec_y_min.setValue(y1)
        self.ui.offspec_y_max.setValue(y2)

        # Draw the region rectangle
        self.rect_region = Line2D([x1, x1, x2, x2, x1], [y1, y2, y2, y1, y1])
        plot.canvas.ax.add_line(self.rect_region)

        # Configure smoothing-specific elements if smoothing is enabled
        if self.show_smoothing:
            # Calculate sigma values
            sigma_percentage = 0.005
            min_sigma_size = 0.0001
            sigma_x = max((x2 - x1) * sigma_percentage, min_sigma_size)
            sigma_y = max((y2 - y1) * sigma_percentage, min_sigma_size)

            self.ui.sigmaX.setValue(sigma_x)
            self.ui.sigmaY.setValue(sigma_y)
            self.ui.sigmaY.setEnabled(sigma_y_enabled)

            # Set sigma coupling based on coordinate system
            if self.ui.kizmkfzVSqz.isChecked():
                self.ui.sigmasCoupled.setChecked(True)
            elif self.ui.qxVSqz.isChecked():
                self.ui.sigmasCoupled.setChecked(False)
            else:
                self.ui.sigmasCoupled.setChecked(True)

            # Create sigma ellipses
            sigma_ang = 0.0
            self.sigma_1 = Ellipse(
                sigma_pos, self.ui.sigmaX.value() * 2, self.ui.sigmaY.value() * 2, angle=sigma_ang, fill=False
            )
            self.sigma_2 = Ellipse(
                sigma_pos, self.ui.sigmaX.value() * 4, self.ui.sigmaY.value() * 4, angle=sigma_ang, fill=False
            )
            self.sigma_3 = Ellipse(
                sigma_pos, self.ui.sigmaX.value() * 6, self.ui.sigmaY.value() * 6, angle=sigma_ang, fill=False
            )
            plot.canvas.ax.add_artist(self.sigma_1)
            plot.canvas.ax.add_artist(self.sigma_2)
            plot.canvas.ax.add_artist(self.sigma_3)

        # Show the plot
        if plot.cplot is not None:
            plot.cplot.set_clim([self.INTENSITY_MIN, self.INTENSITY_MAX])
        plot.draw()

        if self.show_smoothing:
            self.update_sigma_coupling()

        self.drawing = False

    def on_coordinate_system_changed(self):
        """Handle coordinate system radio button changes - recalculate ranges from data."""
        if self.drawing:
            return
        if self.show_smoothing:
            self.update_auto_bins()
        self.draw_plot()

    def _selected_axes(self) -> OffSpecXAxis:
        """Return the coordinate system currently selected by the radio buttons."""
        if self.ui.kizVSkfz.isChecked():
            return OffSpecXAxis.KZI_VS_KZF
        if self.ui.qxVSqz.isChecked():
            return OffSpecXAxis.QX_VS_QZ
        return OffSpecXAxis.DELTA_KZ_VS_QZ

    def update_auto_grid_state(self):
        """Enable or disable manual grid editing based on the Auto checkbox."""
        auto = self.ui.autoGridBins.isChecked()
        self.ui.smooth_grid_x.setEnabled(not auto)
        self.ui.smooth_grid_y.setEnabled(not auto)
        if auto:
            self.update_auto_bins()

    def update_auto_bins(self):
        """Set the smoothing grid size from the typical x/y intervals in the raw data.

        For each axis the number of bins is the region extent divided by the
        typical interval present in the off-specular data (the median of the
        adjacent-point differences), clamped to the spinbox range. Does
        nothing when the Auto checkbox is unchecked or no data is loaded.
        """
        if not self.show_smoothing or not self.ui.autoGridBins.isChecked():
            return
        if not self.data_manager.reduction_states:
            return

        x_range = (self.ui.offspec_x_min.value(), self.ui.offspec_x_max.value())
        y_range = (self.ui.offspec_y_min.value(), self.ui.offspec_y_max.value())
        intervals = finest_intervals(
            self.data_manager.reduction_list,
            self.data_manager.reduction_states[0],
            axes=self._selected_axes(),
            x_range=x_range,
            y_range=y_range,
        )
        if intervals is None:
            return

        for spinbox, (low, high), interval in (
            (self.ui.smooth_grid_x, x_range, intervals[0]),
            (self.ui.smooth_grid_y, y_range, intervals[1]),
        ):
            extent = high - low
            if extent <= 0 or interval <= 0:
                continue
            n_bins = min(max(math.ceil(extent / interval), spinbox.minimum()), spinbox.maximum())
            spinbox.blockSignals(True)
            spinbox.setValue(n_bins)
            spinbox.blockSignals(False)

    def update_region(self):
        """Update the rectangle overlay showing the region."""
        if self.drawing:
            return

        # Only update if plot has been initialized with data and rectangle exists
        if self.rect_region is None:
            return

        x1 = self.ui.offspec_x_min.value()
        x2 = self.ui.offspec_x_max.value()
        y1 = self.ui.offspec_y_min.value()
        y2 = self.ui.offspec_y_max.value()

        # Update rectangle data
        self.rect_region.set_data([x1, x1, x2, x2, x1], [y1, y2, y2, y1, y1])
        self.ui.plot.draw()

    def update_settings(self):
        """Update smoothing sigma visualization (only called when smoothing is enabled)."""
        if self.drawing or not self.show_smoothing:
            return
        self.drawing = True

        # Redraw indicators (only if they exist)
        if self.rect_region is not None:
            x1 = self.ui.offspec_x_min.value()
            x2 = self.ui.offspec_x_max.value()
            y1 = self.ui.offspec_y_min.value()
            y2 = self.ui.offspec_y_max.value()
            self.rect_region.set_data([x1, x1, x2, x2, x1], [y1, y2, y2, y1, y1])

        if self.sigma_1:
            self.sigma_1.width = 2 * self.ui.sigmaX.value()
            self.sigma_1.height = 2 * self.ui.sigmaY.value()
            self.sigma_2.width = 4 * self.ui.sigmaX.value()
            self.sigma_2.height = 4 * self.ui.sigmaY.value()
            self.sigma_3.width = 6 * self.ui.sigmaX.value()
            self.sigma_3.height = 6 * self.ui.sigmaY.value()

        self.ui.plot.draw()

        self.drawing = False

    def update_sigma_coupling(self):
        """Update sigma coupling state and UI element states."""
        if not self.show_smoothing:
            return

        if self.ui.sigmasCoupled.isChecked():
            self.ui.sigmaY.setEnabled(False)
            self.ui.sigmaY.setValue(self.ui.sigmaX.value())
        else:
            self.ui.sigmaY.setEnabled(True)

        self.update_settings()

    def plot_select(self, event):
        """Handle plot clicks to adjust the selection region."""
        if event.button == 1 and event.xdata is not None:
            x = event.xdata
            y = event.ydata
            x1 = self.ui.offspec_x_min.value()
            x2 = self.ui.offspec_x_max.value()
            y1 = self.ui.offspec_y_min.value()
            y2 = self.ui.offspec_y_max.value()
            if x < x1 or abs(x - x1) < abs(x - x2):
                x1 = x
            else:
                x2 = x
            if y < y1 or abs(y - y1) < abs(y - y2):
                y1 = y
            else:
                y2 = y
            self.drawing = True
            self.ui.offspec_x_min.setValue(x1)
            self.ui.offspec_x_max.setValue(x2)
            self.ui.offspec_y_min.setValue(y1)
            self.ui.offspec_y_max.setValue(y2)
            self.drawing = False

            # Update visualization: rectangle only for binning, rectangle + sigmas for smoothing
            if self.show_smoothing:
                self.update_settings()  # Updates both rectangle and sigma ellipses
            else:
                self.update_region()  # Updates only rectangle

    def load_settings(self):
        """Load parameter values from QSettings."""
        settings = QtCore.QSettings(".quicknxs")

        # Load shared region parameters
        if settings.contains("offspec_binned/x_min"):
            self.ui.offspec_x_min.setValue(float(settings.value("offspec_binned/x_min")))
        if settings.contains("offspec_binned/x_max"):
            self.ui.offspec_x_max.setValue(float(settings.value("offspec_binned/x_max")))
        if settings.contains("offspec_binned/y_min"):
            self.ui.offspec_y_min.setValue(float(settings.value("offspec_binned/y_min")))
        if settings.contains("offspec_binned/y_max"):
            self.ui.offspec_y_max.setValue(float(settings.value("offspec_binned/y_max")))

        # Load binning-specific parameters
        if self.show_binning:
            if settings.contains("offspec_binned/bins_x"):
                self.ui.offspec_bins_x.setValue(int(settings.value("offspec_binned/bins_x")))
            if settings.contains("offspec_binned/bins_y"):
                self.ui.offspec_bins_y.setValue(int(settings.value("offspec_binned/bins_y")))
            if settings.contains("offspec_binned/error_weighting"):
                self.ui.error_weighting_checkbox.setChecked(
                    settings.value("offspec_binned/error_weighting", False, type=bool)
                )

        # Load smoothing-specific parameters
        if self.show_smoothing:
            if settings.contains("offspec_smoothing/sigma_x"):
                self.ui.sigmaX.setValue(float(settings.value("offspec_smoothing/sigma_x")))
            if settings.contains("offspec_smoothing/sigma_y"):
                self.ui.sigmaY.setValue(float(settings.value("offspec_smoothing/sigma_y")))
            if settings.contains("offspec_smoothing/r_sigmas"):
                self.ui.rSigmas.setValue(float(settings.value("offspec_smoothing/r_sigmas")))
            if settings.contains("offspec_smoothing/sigmas_coupled"):
                self.ui.sigmasCoupled.setChecked(settings.value("offspec_smoothing/sigmas_coupled", True, type=bool))
            if settings.contains("offspec_smoothing/grid_x"):
                self.ui.smooth_grid_x.setValue(int(settings.value("offspec_smoothing/grid_x")))
            if settings.contains("offspec_smoothing/grid_y"):
                self.ui.smooth_grid_y.setValue(int(settings.value("offspec_smoothing/grid_y")))
            if settings.contains("offspec_smoothing/auto_grid"):
                self.ui.autoGridBins.setChecked(settings.value("offspec_smoothing/auto_grid", True, type=bool))

        # Load coordinate system
        if settings.contains("offspec_binned/coordinate_system"):
            coord_sys = settings.value("offspec_binned/coordinate_system")
            if coord_sys == OffSpecXAxis.KZI_VS_KZF:
                self.ui.kizVSkfz.setChecked(True)
            elif coord_sys == OffSpecXAxis.QX_VS_QZ:
                self.ui.qxVSqz.setChecked(True)
            else:
                self.ui.kizmkfzVSqz.setChecked(True)

    def save_settings(self):
        """Save parameter values to QSettings."""
        settings = QtCore.QSettings(".quicknxs")

        # Save shared region parameters
        settings.setValue("offspec_binned/x_min", self.ui.offspec_x_min.value())
        settings.setValue("offspec_binned/x_max", self.ui.offspec_x_max.value())
        settings.setValue("offspec_binned/y_min", self.ui.offspec_y_min.value())
        settings.setValue("offspec_binned/y_max", self.ui.offspec_y_max.value())

        # Save coordinate system
        if self.ui.kizVSkfz.isChecked():
            coord_sys = OffSpecXAxis.KZI_VS_KZF
        elif self.ui.qxVSqz.isChecked():
            coord_sys = OffSpecXAxis.QX_VS_QZ
        else:
            coord_sys = OffSpecXAxis.DELTA_KZ_VS_QZ
        settings.setValue("offspec_binned/coordinate_system", coord_sys)

        # Save bins parameters (common to both binning and smoothing)
        settings.setValue("offspec_binned/bins_x", self.ui.offspec_bins_x.value())
        settings.setValue("offspec_binned/bins_y", self.ui.offspec_bins_y.value())

        # Save binning-specific parameters
        if self.show_binning:
            settings.setValue("offspec_binned/error_weighting", self.ui.error_weighting_checkbox.isChecked())

        # Save smoothing-specific parameters
        if self.show_smoothing:
            settings.setValue("offspec_smoothing/sigma_x", self.ui.sigmaX.value())
            settings.setValue("offspec_smoothing/sigma_y", self.ui.sigmaY.value())
            settings.setValue("offspec_smoothing/r_sigmas", self.ui.rSigmas.value())
            settings.setValue("offspec_smoothing/sigmas_coupled", self.ui.sigmasCoupled.isChecked())
            settings.setValue("offspec_smoothing/grid_x", self.ui.smooth_grid_x.value())
            settings.setValue("offspec_smoothing/grid_y", self.ui.smooth_grid_y.value())
            settings.setValue("offspec_smoothing/auto_grid", self.ui.autoGridBins.isChecked())

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
        Get the parameters as a dictionary.

        Returns
        -------
        dict
            Dictionary containing off-specular parameters
        """
        params = {}

        # Determine coordinate system setting
        params["off_spec_x_axis"] = self._selected_axes()

        # Shared region parameters
        params["off_spec_x_min"] = self.ui.offspec_x_min.value()
        params["off_spec_x_max"] = self.ui.offspec_x_max.value()
        params["off_spec_y_min"] = self.ui.offspec_y_min.value()
        params["off_spec_y_max"] = self.ui.offspec_y_max.value()

        # Bins parameters (common to both binning and smoothing)
        params["off_spec_nxbins"] = self.ui.offspec_bins_x.value()
        params["off_spec_nybins"] = self.ui.offspec_bins_y.value()

        # Binning-specific parameters
        if self.show_binning:
            params["off_spec_err_weight"] = self.ui.error_weighting_checkbox.isChecked()

        # Smoothing-specific parameters
        if self.show_smoothing:
            params["off_spec_sigmas"] = self.ui.rSigmas.value()
            params["off_spec_sigmax"] = self.ui.sigmaX.value()
            params["off_spec_sigmay"] = self.ui.sigmaY.value()
            params["off_spec_smooth_nxbins"] = self.ui.smooth_grid_x.value()
            params["off_spec_smooth_nybins"] = self.ui.smooth_grid_y.value()

        return params

    def accept(self):
        """Override accept to save settings before closing."""
        self.save_settings()
        super().accept()
