"""Dialog to configure off-specular parameters (smoothing and/or binning)."""

from mantid.simpleapi import logger
from matplotlib.lines import Line2D
from matplotlib.patches import Ellipse
from numpy import float64
from numpy.typing import NDArray
from qtpy import QtCore, QtWidgets

from quicknxs.enums import OffSpecXAxis
from quicknxs.models.offspec_smoothing_memory import OffSpecRegion, OffSpecSmoothingMemory
from quicknxs.presenters.data_manager import DataManager
from quicknxs.views import load_ui
from quicknxs.views.widgets import MPLWidget

# Axis labels per coordinate system, as (horizontal, vertical)
_AXIS_LABELS: dict[OffSpecXAxis, tuple[str, str]] = {
    OffSpecXAxis.DELTA_KZ_VS_QZ: ("k$_{i,z}$-k$_{f,z}$ [Å$^{-1}$]", "Q$_z$ [Å$^{-1}$]"),
    OffSpecXAxis.QX_VS_QZ: ("Q$_x$ [Å$^{-1}$]", "Q$_z$ [Å$^{-1}$]"),
    OffSpecXAxis.KZI_VS_KZF: ("k$_{i,z}$ [Å$^{-1}$]", "k$_{f,z}$ [Å$^{-1}$]"),
}


def _set_blocked(spin_box, value: float) -> None:
    """Write a value into a spin box without emitting its change signal.

    A programmatic write must not look like a user edit, because only a real edit may
    re-derive the remembered smoothing fractions.
    """
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
            Region, uniformity and smoothing radii carried over from earlier visits in
            this session. A fresh memory is used when none is supplied, which makes the
            dialog behave as if it were being opened for the first time.
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

        # Session memory shared with the main window, and a private working copy of it.
        # Everything during the visit goes to the working copy, which is committed only
        # on OK, so cancelling or closing the dialog leaves the session memory untouched.
        self.memory = OffSpecSmoothingMemory() if memory is None else memory
        self._state = self.memory.snapshot()

        # What the user changed in the active coordinate system since it was shown
        self._clear_edits()

        # Off-specular data and its extents, read once and reused on every repaint.
        # The dialog is modal, so the reduction list cannot change while it is open.
        self._plot_runs: list[tuple[NDArray[float64], ...]] | None = None
        self._extents: dict[OffSpecXAxis, OffSpecRegion] = {}
        self._qz_max = 0.001

        # Always open on the (ki_z - kf_z) vs Qz view, whichever view was used last
        self.ui.kizmkfzVSqz.setChecked(True)
        # Coordinate system the spin boxes currently belong to
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
            # Record user edits, so that only what the user changed gets remembered
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
        """Return the coordinate system the radio buttons currently select."""
        if self.ui.qxVSqz.isChecked():
            return OffSpecXAxis.QX_VS_QZ
        if self.ui.kizVSkfz.isChecked():
            return OffSpecXAxis.KZI_VS_KZF
        return OffSpecXAxis.DELTA_KZ_VS_QZ

    def _current_region(self) -> OffSpecRegion:
        """Return the region box as the spin boxes currently show it."""
        return OffSpecRegion(
            self.ui.offspec_x_min.value(),
            self.ui.offspec_x_max.value(),
            self.ui.offspec_y_min.value(),
            self.ui.offspec_y_max.value(),
        )

    def _default_region(self, axis: OffSpecXAxis) -> OffSpecRegion:
        """Return the region derived from the data extents, used until the user picks one."""
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
            Coordinate system to paint against
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
        """Read the off-specular data once and cache what every repaint needs.

        Fills `_plot_runs` with the trimmed arrays to paint, `_extents` with the data
        extents of each coordinate system, and `_qz_max` with the anchor for the sigma
        ellipses. Switching coordinate system then reuses the cache instead of walking
        the reduction list again; the dialog is modal, so the data cannot change
        underneath it.
        """
        self._plot_runs = []
        self._extents = {}
        self._qz_max = 0.001

        # Get first state from reduction_states
        if not self.data_manager.reduction_states:
            return

        # Initialize limits. These seeds also bound the plotted range from outside when
        # the data itself is narrower, so they are kept as they were.
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
            except Exception as exception:
                logger.error(f"Error extending plotting limits: {exception}")

            self._plot_runs.append((ki_z, kf_z, Qx, Qz, I))

        self._extents = {
            OffSpecXAxis.DELTA_KZ_VS_QZ: OffSpecRegion(k_diff_min, k_diff_max, qz_min, qz_max),
            OffSpecXAxis.QX_VS_QZ: OffSpecRegion(qx_min, qx_max, qz_min, qz_max),
            OffSpecXAxis.KZI_VS_KZF: OffSpecRegion(ki_z_min, ki_z_max, kf_z_min, kf_z_max),
        }

    def _apply_axis_state(self, axis: OffSpecXAxis) -> None:
        """Show the remembered region, uniformity and radii for a coordinate system.

        Writes spin boxes only; painting is left to `_paint`. Every write blocks the
        widget's change signal, so showing a coordinate system never looks like a user
        edit and therefore never re-derives the remembered smoothing fractions.
        """
        # A freshly shown coordinate system has no edits yet
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

        # Scale against the region as the spin boxes rounded it, so that the box and the
        # smoothing spot drawn inside it stay consistent with each other.
        sigma_x, sigma_y = self._state.radii_for(
            self._current_region(), self.ui.sigmaX.minimum(), self.ui.sigmaX.maximum()
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
        """Repaint the plot for a coordinate system from the cache and the spin boxes.

        Reads the region and the radii from the widgets rather than deciding them, so it
        can be called after any change without disturbing what is on display.
        """
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
            # Anchor the ellipses on the specular ridge of the active coordinate system
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
                # No data to work from: leave an empty plot behind
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
        """Switch coordinate system, carrying what the user changed over to the new one.

        Parameters
        ----------
        checked : bool
            State of the radio button that emitted ``toggled``. The signal also fires for
            the button being switched off, which is ignored so the switch happens once.
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
        """Record what the user changed in the coordinate system being left.

        Writes to the working copy only; nothing reaches the session memory until the
        dialog is accepted. Only actual edits are recorded. In particular a region the
        user never touched stays derived from the data, so reducing a different dataset
        later in the session does not inherit a box that was drawn for this one.

        Moving the region leaves the radii where they are, as agreed, but it changes what
        fraction of the box they cover, so it re-derives both fractions. Editing a radius
        re-derives only that radius's fraction, so the other one is never re-read from its
        spin box and nudged by rounding. The fraction is what the next coordinate system
        is scaled by.
        """
        region = self._current_region()

        if self._region_edited:
            self._state.store_region(axis, region)

        if self.show_smoothing:
            coupled = self.ui.sigmasCoupled.isChecked()
            if self._coupled_edited:
                self._state.store_coupled(axis, coupled)
            update_x = self._region_edited or self._radius_x_edited
            update_y = self._region_edited or self._radius_y_edited
            if update_x or update_y:
                self._state.store_fractions(
                    self.ui.sigmaX.value(),
                    self.ui.sigmaY.value(),
                    region,
                    coupled,
                    update_x=update_x,
                    update_y=update_y,
                )
            self._state.store_r_sigmas(self.ui.rSigmas.value())

        self._clear_edits()

    def _clear_edits(self) -> None:
        """Forget which values the user changed in the active coordinate system."""
        self._region_edited = False
        self._radius_x_edited = False
        self._radius_y_edited = False
        self._coupled_edited = False

    # The slots below only note that an edit happened. They are deliberately not guarded
    # by `drawing`: a click on the plot writes the region while `drawing` is set, and that
    # is a user edit like any other. Programmatic writes block signals instead.

    def _on_region_edited(self):
        """Note that the user moved the region box."""
        self._region_edited = True

    def _on_radius_x_edited(self):
        """Note that the user changed the horizontal smoothing radius."""
        self._radius_x_edited = True

    def _on_radius_y_edited(self):
        """Note that the user changed the vertical smoothing radius.

        While the radii are coupled, `update_sigma_coupling` writes sigmaY with signals
        blocked, so a mirrored value never lands here: only a genuine edit does.
        """
        self._radius_y_edited = True

    def _on_coupled_edited(self):
        """Note that the user changed whether the radii are uniform."""
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

        The region, the smoothing radii, their uniformity and the coordinate system are
        deliberately not persisted between application runs: they live in the session
        memory instead, and a new session starts from defaults derived from the data.
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
        """Save the binning parameters to QSettings. See `load_settings` for what is not saved."""
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
        """Commit this visit to the session memory, save the binning settings, and close.

        There is no matching override of ``reject``: the visit was only ever recorded in
        the working copy, so cancelling, pressing Escape or closing the window simply
        discards it.
        """
        self._store_current_state(self._active_axis)
        self.memory.copy_from(self._state)
        self.save_settings()
        super().accept()
