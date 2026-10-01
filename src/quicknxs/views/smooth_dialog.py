"""Dialog to configure off-specular parameters (smoothing and/or binning)."""

import math

from mantid.simpleapi import logger
from matplotlib.lines import Line2D
from matplotlib.patches import Ellipse
from numpy import float64
from numpy.typing import NDArray
from qtpy import QtCore, QtWidgets

from quicknxs.enums import OffSpecXAxis
from quicknxs.models.offspec_smoothing_memory import OffSpecRegion, OffSpecSmoothingMemory, default_radii
from quicknxs.presenters.data_manager import DataManager
from quicknxs.views import load_ui
from quicknxs.views.widgets import MPLWidget

# (x, y) axis labels for each coordinate system
_AXIS_LABELS: dict[OffSpecXAxis, tuple[str, str]] = {
    OffSpecXAxis.DELTA_KZ_VS_QZ: ("k$_{i,z}$-k$_{f,z}$ [Å$^{-1}$]", "Q$_z$ [Å$^{-1}$]"),
    OffSpecXAxis.QX_VS_QZ: ("Q$_x$ [Å$^{-1}$]", "Q$_z$ [Å$^{-1}$]"),
    OffSpecXAxis.KZI_VS_KZF: ("k$_{i,z}$ [Å$^{-1}$]", "k$_{f,z}$ [Å$^{-1}$]"),
}


def _set_blocked(spin_box, value: float) -> None:
    """Set a spin box value without emitting valueChanged, so it doesn't count as a user edit."""
    spin_box.blockSignals(True)
    spin_box.setValue(value)
    spin_box.blockSignals(False)


class OffSpecParametersDialog(QtWidgets.QDialog):
    """Combined dialog for off-specular smoothing and binning parameters."""

    INTENSITY_MIN = 1e-6  # starting value for the color scale
    INTENSITY_MAX = 1.0  # ending value for the color scale
    GRID_OFFSET = 0.05  # Starting percentage offset of the grid area inside the whole plot area

    drawing = False

    def __init__(
        self,
        parent,
        data_manager: DataManager,
        show_smoothing: bool = False,
        show_binning: bool = False,
        memory: OffSpecSmoothingMemory | None = None,
    ):
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
        memory : OffSpecSmoothingMemory | None
            Settings remembered from earlier in the session. A new one is used if None.
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

        # Shared with the main window. Edits go to a copy that is only saved on OK.
        self.memory = OffSpecSmoothingMemory() if memory is None else memory
        self._state = self.memory.snapshot()

        self._clear_edits()

        # Cached off-specular data. The dialog is modal, so it can't change while open.
        self._plot_runs: list[tuple[NDArray[float64], ...]] | None = None
        self._extents: dict[OffSpecXAxis, OffSpecRegion] = {}
        self._qz_max = 0.001
        # Mean tan(theta_i) of the runs, for converting radii to Qx
        self._tan_theta: float | None = None
        # Default (dk, Qz) radii for this visit
        self._default_radii = (0.0, 0.0)

        # Always open on (ki_z-kf_z) vs Qz
        self.ui.kizmkfzVSqz.setChecked(True)
        # Coordinate system the spin boxes are showing
        self._active_axis = self._current_axis()

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
            self.ui.sigmaX.valueChanged.connect(self.update_sigma_coupling)
            self.ui.sigmaY.valueChanged.connect(self.update_settings)
            self.ui.sigmasCoupled.toggled.connect(self.update_sigma_coupling)
            self.ui.rSigmas.valueChanged.connect(self.update_settings)
            # Track user edits so only changed values get remembered
            self.ui.sigmaX.valueChanged.connect(self._on_radius_x_edited)
            self.ui.sigmaY.valueChanged.connect(self._on_radius_y_edited)
            self.ui.sigmasCoupled.toggled.connect(self._on_coupled_edited)

        # Connect plot interaction for region selection (common to both binning and smoothing)
        self.ui.plot.canvas.mpl_connect("motion_notify_event", self.plot_select)
        self.ui.plot.canvas.mpl_connect("button_press_event", self.plot_select)

        # Connect signals to update plot region
        self.ui.offspec_x_min.valueChanged.connect(self.update_region)
        self.ui.offspec_x_max.valueChanged.connect(self.update_region)
        self.ui.offspec_y_min.valueChanged.connect(self.update_region)
        self.ui.offspec_y_max.valueChanged.connect(self.update_region)
        for spin_box in (self.ui.offspec_x_min, self.ui.offspec_x_max, self.ui.offspec_y_min, self.ui.offspec_y_max):
            spin_box.valueChanged.connect(self._on_region_edited)

        # Connect radio buttons to update coordinate ranges and redraw plot
        self.ui.kizmkfzVSqz.toggled.connect(self.on_coordinate_system_changed)
        self.ui.qxVSqz.toggled.connect(self.on_coordinate_system_changed)
        self.ui.kizVSkfz.toggled.connect(self.on_coordinate_system_changed)

        # Update bin width display on initialization if binning is shown
        if show_binning:
            self.update_bin_width()

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

    def _current_axis(self) -> OffSpecXAxis:
        """Return the selected coordinate system."""
        if self.ui.qxVSqz.isChecked():
            return OffSpecXAxis.QX_VS_QZ
        if self.ui.kizVSkfz.isChecked():
            return OffSpecXAxis.KZI_VS_KZF
        return OffSpecXAxis.DELTA_KZ_VS_QZ

    def _current_region(self) -> OffSpecRegion:
        """Return the region shown in the spin boxes."""
        return OffSpecRegion(
            self.ui.offspec_x_min.value(),
            self.ui.offspec_x_max.value(),
            self.ui.offspec_y_min.value(),
            self.ui.offspec_y_max.value(),
        )

    def _default_region(self, axis: OffSpecXAxis) -> OffSpecRegion:
        """Return the default region for `axis`, based on the data extents."""
        extent = self._extents[axis]
        x_min, x_max, y_min, y_max = self._grid_region_coordinates(
            extent.x_min, extent.x_max, extent.y_min, extent.y_max
        )
        return OffSpecRegion(x_min, x_max, y_min, y_max)

    def _paint_intensities(
        self,
        ki_z: NDArray[float64],
        kf_z: NDArray[float64],
        Qx: NDArray[float64],
        Qz: NDArray[float64],
        I: NDArray[float64],
        plot: MPLWidget,
        axis: OffSpecXAxis,
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
        axis : OffSpecXAxis
            Coordinate system to plot
        """
        common_args = {
            "log": True,
            "imin": self.INTENSITY_MIN,
            "imax": self.INTENSITY_MAX,
            "cmap": "jet",
            "shading": "gouraud",
        }

        if axis == OffSpecXAxis.QX_VS_QZ:
            x, y = Qx, Qz
        elif axis == OffSpecXAxis.KZI_VS_KZF:
            x, y = ki_z, kf_z
        else:
            x, y = (ki_z - kf_z), Qz

        plot.pcolormesh(x, y, I, **common_args)

    def _collect_extents(self) -> None:
        """Read the off-specular data once and cache the arrays, extents and ellipse anchor."""
        self._plot_runs = []
        self._extents = {}
        self._qz_max = 0.001
        self._tan_theta = None
        tan_thetas = []

        # Get first state from reduction_states
        if not self.data_manager.reduction_states:
            return

        # Initialize limits (these also bound the plotted range)
        qz_min, qz_max = 0.5, -0.1
        qx_min, qx_max = -0.001, 0.001
        ki_z_min, ki_z_max = 0.1, -0.1
        kf_z_min, kf_z_max = 0.1, -0.1
        k_diff_min, k_diff_max = 0.01, -0.01

        first_state = self.data_manager.reduction_states[0]

        # Collect data from all runs in the reduction list
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
                self._qz_max = max(ki_z.max() * 2.0, self._qz_max)
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
                tan_thetas.append(math.tan(math.radians(item.cross_sections[first_state].scattering_angle)))
            except Exception as exception:
                logger.error(f"Error extending plotting limits: {exception}")

            self._plot_runs.append((ki_z, kf_z, Qx, Qz, I))

        self._extents = {
            OffSpecXAxis.DELTA_KZ_VS_QZ: OffSpecRegion(k_diff_min, k_diff_max, qz_min, qz_max),
            OffSpecXAxis.QX_VS_QZ: OffSpecRegion(qx_min, qx_max, qz_min, qz_max),
            OffSpecXAxis.KZI_VS_KZF: OffSpecRegion(ki_z_min, ki_z_max, kf_z_min, kf_z_max),
        }
        if tan_thetas:
            self._tan_theta = sum(tan_thetas) / len(tan_thetas)

        # 0.25% of the blue box as it is when the dialog opens, so later box edits don't change it
        axis = OffSpecXAxis.DELTA_KZ_VS_QZ
        region = self._state.region_for(axis, self._default_region(axis))
        self._default_radii = default_radii(region, self._state.coupled_for(axis))

    def _apply_axis_state(self, axis: OffSpecXAxis) -> None:
        """Set the spin boxes to the remembered state for `axis`.

        Signals are blocked, so this doesn't count as a user edit.
        """
        self._clear_edits()

        region = self._state.region_for(axis, self._default_region(axis))
        coupled = self._state.coupled_for(axis)

        for spin_box, value in (
            (self.ui.offspec_x_min, region.x_min),
            (self.ui.offspec_x_max, region.x_max),
            (self.ui.offspec_y_min, region.y_min),
            (self.ui.offspec_y_max, region.y_max),
        ):
            _set_blocked(spin_box, value)

        if not self.show_smoothing:
            return

        if axis == OffSpecXAxis.QX_VS_QZ and not (self._tan_theta and self._tan_theta > 0.0):
            logger.warning("No incident angle available, Qx radii are shown without conversion")
        sigma_x, sigma_y = self._state.radii_for(
            axis, self._default_radii, self._tan_theta, self.ui.sigmaX.minimum(), self.ui.sigmaX.maximum()
        )
        if coupled:
            sigma_y = sigma_x
        _set_blocked(self.ui.sigmaX, sigma_x)
        _set_blocked(self.ui.sigmaY, sigma_y)
        _set_blocked(self.ui.rSigmas, self._state.r_sigmas_for(self.ui.rSigmas.value()))

        self.ui.sigmasCoupled.blockSignals(True)
        self.ui.sigmasCoupled.setChecked(coupled)
        self.ui.sigmasCoupled.blockSignals(False)
        self.ui.sigmaY.setEnabled(not coupled)

    def _paint(self, axis: OffSpecXAxis) -> None:
        """Redraw the plot from the cached data and the current spin box values."""
        plot = self.ui.plot
        plot.clear()
        plot.set_xticks_fontsize(8)
        plot.set_yticks_fontsize(8)

        for ki_z, kf_z, Qx, Qz, I in self._plot_runs or ():
            self._paint_intensities(ki_z, kf_z, Qx, Qz, I, plot, axis)

        # Set plot limits and labels based on selected axis type
        extent = self._extents[axis]
        plot.canvas.ax.set_xlim([extent.x_min, extent.x_max])
        plot.canvas.ax.set_ylim([extent.y_min, extent.y_max])
        x_label, y_label = _AXIS_LABELS[axis]
        plot.set_xlabel(x_label, fontsize=14)
        plot.set_ylabel(y_label, fontsize=14)

        # Draw the region rectangle
        region = self._current_region()
        self.rect_region = Line2D(
            [region.x_min, region.x_min, region.x_max, region.x_max, region.x_min],
            [region.y_min, region.y_max, region.y_max, region.y_min, region.y_min],
        )
        plot.canvas.ax.add_line(self.rect_region)

        # Configure smoothing-specific elements if smoothing is enabled
        if self.show_smoothing:
            # Draw the ellipses near the specular ridge
            if axis == OffSpecXAxis.KZI_VS_KZF:
                sigma_pos = (self._qz_max / 6.0, self._qz_max / 6.0)
            else:
                sigma_pos = (0.0, self._qz_max / 3.0)

            # Create sigma ellipses
            sigma_ang = 0.0
            sigma_x = self.ui.sigmaX.value()
            sigma_y = self.ui.sigmaY.value()
            self.sigma_1 = Ellipse(sigma_pos, sigma_x * 2, sigma_y * 2, angle=sigma_ang, fill=False)
            self.sigma_2 = Ellipse(sigma_pos, sigma_x * 4, sigma_y * 4, angle=sigma_ang, fill=False)
            self.sigma_3 = Ellipse(sigma_pos, sigma_x * 6, sigma_y * 6, angle=sigma_ang, fill=False)
            plot.canvas.ax.add_artist(self.sigma_1)
            plot.canvas.ax.add_artist(self.sigma_2)
            plot.canvas.ax.add_artist(self.sigma_3)

        # Show the plot
        if plot.cplot is not None:
            plot.cplot.set_clim([self.INTENSITY_MIN, self.INTENSITY_MAX])
        plot.draw()

    def draw_plot(self):
        """Draw the off-specular data with the configured region overlay."""
        if self.drawing:
            return
        self.drawing = True
        try:
            if self._plot_runs is None:
                self._collect_extents()

            if not self._extents:
                # No data, leave the plot empty
                plot = self.ui.plot
                plot.clear()
                plot.set_xticks_fontsize(8)
                plot.set_yticks_fontsize(8)
                return

            self._active_axis = self._current_axis()
            self._apply_axis_state(self._active_axis)
            self._paint(self._active_axis)
        finally:
            self.drawing = False

    def on_coordinate_system_changed(self, checked: bool = True):
        """Save the edits in the current coordinate system and show the new one.

        `toggled` also fires for the button being unchecked, which is ignored.
        """
        if not checked or self.drawing:
            return
        new_axis = self._current_axis()
        if new_axis == self._active_axis:
            return
        self._store_current_state(self._active_axis)
        self._active_axis = new_axis
        self.draw_plot()

    def _store_current_state(self, axis: OffSpecXAxis) -> None:
        """Save the user's edits for `axis` to the working copy.

        Only edited values are saved, so a region the user never touched stays based on
        the data and isn't carried over to the next dataset. Moving the region doesn't
        change the radii.
        """
        if self._region_edited:
            self._state.store_region(axis, self._current_region())

        if self.show_smoothing:
            coupled = self.ui.sigmasCoupled.isChecked()
            if self._coupled_edited:
                self._state.store_coupled(axis, coupled)
            if self._radius_x_edited or self._radius_y_edited:
                self._state.store_radii(
                    axis,
                    self.ui.sigmaX.value(),
                    self.ui.sigmaY.value(),
                    self._default_radii,
                    self._tan_theta,
                    edited_x=self._radius_x_edited,
                    edited_y=self._radius_y_edited,
                    coupled=coupled,
                )
            self._state.store_r_sigmas(self.ui.rSigmas.value())

        self._clear_edits()

    def _clear_edits(self) -> None:
        """Reset the edit flags."""
        self._region_edited = False
        self._radius_x_edited = False
        self._radius_y_edited = False
        self._coupled_edited = False

    # These slots only record that an edit happened. They don't check `drawing`, because
    # clicking the plot changes the region while `drawing` is set.

    def _on_region_edited(self):
        """Called when the user moves the region."""
        self._region_edited = True

    def _on_radius_x_edited(self):
        """Called when the user edits sigmaX."""
        self._radius_x_edited = True

    def _on_radius_y_edited(self):
        """Called when the user edits sigmaY."""
        self._radius_y_edited = True

    def _on_coupled_edited(self):
        """Called when the user toggles uniform radii."""
        self._coupled_edited = True

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
            self.ui.sigmaY.blockSignals(True)
            self.ui.sigmaY.setValue(self.ui.sigmaX.value())
            self.ui.sigmaY.blockSignals(False)
            # Only user actions get here, and the y now shown should be the one remembered
            self._radius_y_edited = True
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
        """Load the binning parameters from QSettings.

        The region, radii, uniformity and coordinate system are only kept for the session,
        so they aren't saved here.
        """
        settings = QtCore.QSettings(".quicknxs")

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

    def save_settings(self):
        """Save the binning parameters to QSettings."""
        settings = QtCore.QSettings(".quicknxs")

        # Save bins parameters (common to both binning and smoothing)
        settings.setValue("offspec_binned/bins_x", self.ui.offspec_bins_x.value())
        settings.setValue("offspec_binned/bins_y", self.ui.offspec_bins_y.value())

        # Save binning-specific parameters
        if self.show_binning:
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
        Get the parameters as a dictionary.

        Returns
        -------
        dict
            Dictionary containing off-specular parameters
        """
        params = {}

        # Determine coordinate system setting
        params["off_spec_x_axis"] = self._current_axis()

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

        return params

    def accept(self):
        """Save the edits to the session memory and close.

        No `reject` override is needed: edits only go to the working copy, so Cancel,
        Escape or closing the window just drops them.
        """
        self._store_current_state(self._active_axis)
        self.memory.copy_from(self._state)
        self.save_settings()
        super().accept()
