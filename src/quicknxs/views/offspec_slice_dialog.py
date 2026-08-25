"""Dialog to let the user configure off-specular Qz slice parameters."""

from mantid.simpleapi import logger
from matplotlib.lines import Line2D
from numpy import float64
from numpy.typing import NDArray
from qtpy import QtCore, QtWidgets

from quicknxs.presenters.data_manager import DataManager
from quicknxs.views import load_ui
from quicknxs.views.widgets import MPLWidget


class OffSpecSliceDialog(QtWidgets.QDialog):
    """Dialog to define off-specular Qz slice parameters with plot preview."""

    INTENSITY_MIN = 1e-6  # starting value for the color scale
    INTENSITY_MAX = 1.0  # ending value for the color scale

    drawing = False

    def __init__(self, parent, data_manager: DataManager):
        QtWidgets.QDialog.__init__(self, parent)
        self.ui = load_ui("ui_offspec_slice_dialog.ui", base_instance=self)
        self.data_manager = data_manager
        self.rect_region = None

        # Load saved values from settings
        self.load_settings()

        # Connect signals to update slice width display
        self.ui.slice_qz_min.valueChanged.connect(self.update_slice_width)
        self.ui.slice_qz_max.valueChanged.connect(self.update_slice_width)

        # Connect signals to update plot region
        self.ui.slice_qz_min.valueChanged.connect(self.update_region)
        self.ui.slice_qz_max.valueChanged.connect(self.update_region)

        # Connect radio buttons to redraw plot
        self.ui.kizmkfzVSqz.toggled.connect(self.on_coordinate_system_changed)
        self.ui.qxVSqz.toggled.connect(self.on_coordinate_system_changed)
        self.ui.kizVSkfz.toggled.connect(self.on_coordinate_system_changed)

        # Set initial visibility of Qz range controls
        self.update_qz_range_visibility()

        # Update slice width display on initialization
        self.update_slice_width()

        # Draw the initial plot (deferred to avoid blocking)
        QtCore.QTimer.singleShot(0, self.draw_plot)

    def on_coordinate_system_changed(self):
        """Handle coordinate system change - update visibility and redraw plot."""
        self.update_qz_range_visibility()
        self.draw_plot()

    def update_qz_range_visibility(self):
        """Hide Qz range controls when ki_z vs kf_z is selected (no Qz axis)."""
        # ki_z vs kf_z doesn't have a Qz axis, so hide the Qz range controls
        has_qz_axis = not self.ui.kizVSkfz.isChecked()

        # Hide/show the Qz spinboxes
        self.ui.slice_qz_min.setVisible(has_qz_axis)
        self.ui.slice_qz_max.setVisible(has_qz_axis)

        # Hide/show the Qz labels (label_2 is "Qz min:", label_3 is "Qz max:")
        if hasattr(self.ui, "label_2"):
            self.ui.label_2.setVisible(has_qz_axis)
        if hasattr(self.ui, "label_3"):
            self.ui.label_3.setVisible(has_qz_axis)

        # Also hide/show the slice width display
        self.ui.slice_width_label.setVisible(has_qz_axis)
        if hasattr(self.ui, "label_4"):  # "Slice width:" label
            self.ui.label_4.setVisible(has_qz_axis)

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
        elif self.ui.qxVSqz.isChecked():
            plot.canvas.ax.set_xlim([qx_min, qx_max])
            plot.canvas.ax.set_ylim([qz_min, qz_max])
            plot.set_xlabel("Q$_x$ [Å$^{-1}$]", fontsize=14)
            plot.set_ylabel("Q$_z$ [Å$^{-1}$]", fontsize=14)
        elif self.ui.kizVSkfz.isChecked():
            plot.canvas.ax.set_xlim([ki_z_min, ki_z_max])
            plot.canvas.ax.set_ylim([kf_z_min, kf_z_max])
            plot.set_xlabel("k$_{i,z}$ [Å$^{-1}$]", fontsize=14)
            plot.set_ylabel("k$_{f,z}$ [Å$^{-1}$]", fontsize=14)

        # Draw the region rectangle (create it initially, then update_region will modify it)
        # Only draw if there's a Qz axis
        if not self.ui.kizVSkfz.isChecked():
            qz_min_val = self.ui.slice_qz_min.value()
            qz_max_val = self.ui.slice_qz_max.value()
            xlim = plot.canvas.ax.get_xlim()
            x_min_val, x_max_val = xlim[0], xlim[1]
            self.rect_region = Line2D(
                [x_min_val, x_max_val, x_max_val, x_min_val, x_min_val],
                [qz_min_val, qz_min_val, qz_max_val, qz_max_val, qz_min_val],
            )
            plot.canvas.ax.add_line(self.rect_region)

        # Show the plot
        if plot.cplot is not None:
            plot.cplot.set_clim([self.INTENSITY_MIN, self.INTENSITY_MAX])
        try:
            plot.draw()
        except Exception:
            pass  # Ignore drawing errors in headless environments
        self.drawing = False

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
            "shading": "nearest",
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
        """Update the horizontal lines showing the Qz slice region."""
        if self.drawing:
            return

        # Only update if plot has been initialized with data and rectangle exists
        if not self.data_manager.reduction_states or self.rect_region is None:
            return

        # Don't update region for ki_z vs kf_z (no Qz axis)
        if self.ui.kizVSkfz.isChecked():
            return

        qz_min = self.ui.slice_qz_min.value()
        qz_max = self.ui.slice_qz_max.value()

        # Get x-axis limits from plot
        xlim = self.ui.plot.canvas.ax.get_xlim()
        x_min, x_max = xlim[0], xlim[1]

        # Update rectangle data (matches smooth_dialog/binned_dialog pattern)
        self.rect_region.set_data([x_min, x_max, x_max, x_min, x_min], [qz_min, qz_min, qz_max, qz_max, qz_min])
        try:
            self.ui.plot.draw()
        except Exception:
            pass  # Ignore drawing errors in headless environments

    def load_settings(self):
        """Load parameter values from QSettings."""
        settings = QtCore.QSettings(".quicknxs")

        # Load Qz range
        if settings.contains("offspec_slice/qz_min"):
            self.ui.slice_qz_min.setValue(float(settings.value("offspec_slice/qz_min")))
        if settings.contains("offspec_slice/qz_max"):
            self.ui.slice_qz_max.setValue(float(settings.value("offspec_slice/qz_max")))

    def save_settings(self):
        """Save parameter values to QSettings."""
        settings = QtCore.QSettings(".quicknxs")

        # Save Qz range
        settings.setValue("offspec_slice/qz_min", self.ui.slice_qz_min.value())
        settings.setValue("offspec_slice/qz_max", self.ui.slice_qz_max.value())

    def update_slice_width(self):
        """Calculate and display the Qz slice width based on current settings."""
        qz_min = self.ui.slice_qz_min.value()
        qz_max = self.ui.slice_qz_max.value()

        width = qz_max - qz_min
        self.ui.slice_width_label.setText(f"{width:8.6f} 1/A")

    def get_parameters(self):
        """
        Get the slice parameters as a dictionary.

        Returns
        -------
        dict
            Dictionary containing off-specular slice parameters
        """
        return {
            "off_spec_slice_qz_min": self.ui.slice_qz_min.value(),
            "off_spec_slice_qz_max": self.ui.slice_qz_max.value(),
        }

    def accept(self):
        """Override accept to save settings before closing."""
        self.save_settings()
        super().accept()
