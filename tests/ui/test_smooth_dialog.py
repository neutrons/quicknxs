"""Tests for the Off-Specular Parameters dialog (combined smoothing and binning)"""

from unittest.mock import Mock, patch

import numpy as np
import pytest
from qtpy import QtCore, QtWidgets

from quicknxs.enums import OffSpecXAxis
from quicknxs.models.offspec_smoothing_memory import (
    DEFAULT_MINIMUM_RADIUS,
    DEFAULT_SIGMA_FRACTION,
    OffSpecRegion,
    OffSpecSmoothingMemory,
)
from quicknxs.views.smooth_dialog import OffSpecParametersDialog


@pytest.fixture
def mock_main_window(qtbot):
    """Create a minimal mock main window for testing UI components."""
    main_window = QtWidgets.QMainWindow()
    qtbot.addWidget(main_window)

    # Mock data_manager with minimal required attributes
    main_window.data_manager = Mock()
    main_window.data_manager.reduction_states = []  # Empty list for UI-only tests
    main_window.data_manager.reduction_list = []  # Empty list for UI-only tests

    return main_window


@pytest.fixture
def dialog_both(qtbot, mock_main_window):
    """Create an OffSpecParametersDialog instance with both smoothing and binning enabled."""
    with patch.object(OffSpecParametersDialog, "draw_plot"):
        dlg = OffSpecParametersDialog(
            mock_main_window, mock_main_window.data_manager, show_smoothing=True, show_binning=True
        )
        qtbot.addWidget(dlg)
        return dlg


@pytest.fixture
def dialog_smoothing_only(qtbot, mock_main_window):
    """Create an OffSpecParametersDialog instance with only smoothing enabled."""
    with patch.object(OffSpecParametersDialog, "draw_plot"):
        dlg = OffSpecParametersDialog(
            mock_main_window, mock_main_window.data_manager, show_smoothing=True, show_binning=False
        )
        qtbot.addWidget(dlg)
        return dlg


@pytest.fixture
def dialog_binning_only(qtbot, mock_main_window):
    """Create an OffSpecParametersDialog instance with only binning enabled."""
    with patch.object(OffSpecParametersDialog, "draw_plot"):
        dlg = OffSpecParametersDialog(
            mock_main_window, mock_main_window.data_manager, show_smoothing=False, show_binning=True
        )
        qtbot.addWidget(dlg)
        return dlg
    qtbot.addWidget(dlg)
    return dlg


def test_dialog_creation_both(dialog_both):
    """Test that the dialog is created successfully with both sections."""
    assert dialog_both is not None
    assert dialog_both.ui is not None
    assert dialog_both.show_smoothing is True
    assert dialog_both.show_binning is True


def test_dialog_creation_smoothing_only(dialog_smoothing_only):
    """Test that the dialog is created successfully with only smoothing."""
    assert dialog_smoothing_only is not None
    assert dialog_smoothing_only.ui is not None
    assert dialog_smoothing_only.show_smoothing is True
    assert dialog_smoothing_only.show_binning is False


def test_dialog_creation_binning_only(dialog_binning_only):
    """Test that the dialog is created successfully with only binning."""
    assert dialog_binning_only is not None
    assert dialog_binning_only.ui is not None
    assert dialog_binning_only.show_smoothing is False
    assert dialog_binning_only.show_binning is True


def test_dialog_shared_region_defaults(dialog_both):
    """Test that shared region parameters have reasonable defaults."""
    # Check X-axis defaults
    assert dialog_both.ui.offspec_x_min.value() == -0.015
    assert dialog_both.ui.offspec_x_max.value() == 0.015

    # Check Y-axis defaults
    assert dialog_both.ui.offspec_y_min.value() == 0.0
    assert dialog_both.ui.offspec_y_max.value() == 0.15


def test_dialog_binning_defaults(dialog_both):
    """Test that binning parameters have reasonable defaults."""
    # Check bin count defaults
    assert dialog_both.ui.offspec_bins_x.value() == 120
    assert dialog_both.ui.offspec_bins_y.value() == 120
    assert not dialog_both.ui.error_weighting_checkbox.isChecked()


def test_dialog_smoothing_defaults(dialog_both):
    """Test that smoothing parameters have reasonable defaults."""
    # Check sigma defaults
    assert dialog_both.ui.sigmaX.value() == 0.0005
    assert dialog_both.ui.sigmaY.value() == 0.0005

    # Check r_sigmas default
    assert dialog_both.ui.rSigmas.value() == 3.0

    # Check coupling defaults
    assert dialog_both.ui.sigmasCoupled.isChecked()


def _fake_reduction_item(state):
    """Build a mock reduction item with numpy off-specular data (units: 1/A)."""
    shape = (10, 20)
    ki_z = np.linspace(0.05, 0.10, shape[0] * shape[1]).reshape(shape)
    off_spec = Mock()
    off_spec.ki_z = ki_z
    off_spec.kf_z = ki_z * 0.5
    off_spec.Qz = np.linspace(0.1, 0.3, shape[0] * shape[1]).reshape(shape)
    off_spec.Qx = np.linspace(-0.001, 0.001, shape[0] * shape[1]).reshape(shape)
    off_spec.S = np.ones(shape)
    off_spec.dS = np.ones(shape)

    cross_section = Mock()
    cross_section.off_spec = off_spec
    cross_section.configuration.cut_first_n_points = 0
    cross_section.configuration.cut_last_n_points = 0

    item = Mock()
    item.cross_sections = {state: cross_section}
    return item


def test_initial_draw_ellipses_match_coupled_sigmas(qtbot, mock_main_window):
    """Test that draw_plot builds the sigma ellipses from the coupled sigma values.

    The Y range is larger than the X range, so the range-derived sigma_y differs
    from sigma_x; in coupled mode the ellipses must use the coupled value.
    """
    state = "Off_Off"
    mock_main_window.data_manager.reduction_states = [state]
    mock_main_window.data_manager.reduction_list = [_fake_reduction_item(state)]

    with patch.object(OffSpecParametersDialog, "draw_plot"):
        dlg = OffSpecParametersDialog(
            mock_main_window, mock_main_window.data_manager, show_smoothing=True, show_binning=False
        )
        qtbot.addWidget(dlg)

    # Coupled mode already active in the default coordinate system, so draw_plot's
    # own setChecked(True) is a no-op and emits no toggled signal
    dlg.ui.kizmkfzVSqz.setChecked(True)
    dlg.ui.sigmasCoupled.setChecked(True)

    dlg.draw_plot()

    sigma_x = dlg.ui.sigmaX.value()
    assert dlg.ui.sigmaY.value() == sigma_x
    assert dlg.sigma_1.width == pytest.approx(2 * sigma_x)
    assert dlg.sigma_1.height == pytest.approx(2 * sigma_x)
    assert dlg.sigma_3.height == pytest.approx(6 * sigma_x)


def test_sigma_y_follows_sigma_x_when_coupled(dialog_smoothing_only):
    """Test that sigmaY tracks every sigmaX change while sigmasCoupled is checked."""
    dialog_smoothing_only.ui.sigmasCoupled.setChecked(True)

    dialog_smoothing_only.ui.sigmaX.setValue(0.002)
    assert dialog_smoothing_only.ui.sigmaY.value() == 0.002
    assert not dialog_smoothing_only.ui.sigmaY.isEnabled()

    dialog_smoothing_only.ui.sigmaX.setValue(0.0007)
    assert dialog_smoothing_only.ui.sigmaY.value() == 0.0007


def test_sigma_y_independent_when_uncoupled(dialog_smoothing_only):
    """Test that sigmaY keeps its own value when sigmasCoupled is unchecked."""
    dialog_smoothing_only.ui.sigmasCoupled.setChecked(False)
    dialog_smoothing_only.ui.sigmaY.setValue(0.004)

    dialog_smoothing_only.ui.sigmaX.setValue(0.001)

    assert dialog_smoothing_only.ui.sigmaY.value() == 0.004
    assert dialog_smoothing_only.ui.sigmaY.isEnabled()


def test_dialog_bin_width_calculation(dialog_binning_only):
    """Test that the Qz bin width is calculated correctly."""
    # Set known values
    dialog_binning_only.ui.offspec_y_min.setValue(0.0)
    dialog_binning_only.ui.offspec_y_max.setValue(0.12)
    dialog_binning_only.ui.offspec_bins_y.setValue(100)

    # Trigger update
    dialog_binning_only.update_bin_width()

    # Check calculated width (0.12 / 100 = 0.0012)
    expected_text = "0.001200 1/A"
    assert dialog_binning_only.ui.qz_bin_width_label.text() == expected_text


def test_dialog_get_parameters_both(dialog_both):
    """Test that get_parameters returns correct dictionary with both sections."""
    # Set region values
    dialog_both.ui.offspec_x_min.setValue(-0.01)
    dialog_both.ui.offspec_x_max.setValue(0.02)
    dialog_both.ui.offspec_y_min.setValue(0.01)
    dialog_both.ui.offspec_y_max.setValue(0.20)

    # Set binning values
    dialog_both.ui.offspec_bins_x.setValue(100)
    dialog_both.ui.offspec_bins_y.setValue(150)
    dialog_both.ui.error_weighting_checkbox.setChecked(True)

    # Set smoothing values - uncouple sigmas first to set different values
    dialog_both.ui.sigmasCoupled.setChecked(False)
    dialog_both.ui.sigmaX.setValue(0.001)
    dialog_both.ui.sigmaY.setValue(0.002)
    dialog_both.ui.rSigmas.setValue(4.0)

    params = dialog_both.get_parameters()

    # Check shared region parameters
    assert params["off_spec_x_min"] == -0.01
    assert params["off_spec_x_max"] == 0.02
    assert params["off_spec_y_min"] == 0.01
    assert params["off_spec_y_max"] == 0.20

    # Check binning parameters
    assert params["off_spec_nxbins"] == 100
    assert params["off_spec_nybins"] == 150
    assert params["off_spec_err_weight"] is True

    # Check smoothing parameters
    assert params["off_spec_sigmax"] == 0.001
    assert params["off_spec_sigmay"] == 0.002
    assert params["off_spec_sigmas"] == 4.0


def test_dialog_get_parameters_smoothing_only(dialog_smoothing_only):
    """Test that get_parameters returns correct dictionary with only smoothing."""
    # Set region values
    dialog_smoothing_only.ui.offspec_x_min.setValue(-0.01)
    dialog_smoothing_only.ui.offspec_x_max.setValue(0.02)
    dialog_smoothing_only.ui.offspec_y_min.setValue(0.01)
    dialog_smoothing_only.ui.offspec_y_max.setValue(0.20)

    # Set smoothing values - uncouple sigmas first to set different values
    dialog_smoothing_only.ui.sigmasCoupled.setChecked(False)
    dialog_smoothing_only.ui.sigmaX.setValue(0.001)
    dialog_smoothing_only.ui.sigmaY.setValue(0.002)
    dialog_smoothing_only.ui.rSigmas.setValue(4.0)

    params = dialog_smoothing_only.get_parameters()

    # Check shared region parameters
    assert params["off_spec_x_min"] == -0.01
    assert params["off_spec_x_max"] == 0.02
    assert params["off_spec_y_min"] == 0.01
    assert params["off_spec_y_max"] == 0.20

    # Check smoothing parameters
    assert params["off_spec_sigmax"] == 0.001
    assert params["off_spec_sigmay"] == 0.002
    assert params["off_spec_sigmas"] == 4.0

    # Bins are common to both smoothing and binning, so they should be present
    assert "off_spec_nxbins" in params
    assert "off_spec_nybins" in params

    # Error weighting is binning-specific and should not be present
    assert "off_spec_err_weight" not in params


def test_dialog_get_parameters_binning_only(dialog_binning_only):
    """Test that get_parameters returns correct dictionary with only binning."""
    # Set region values
    dialog_binning_only.ui.offspec_x_min.setValue(-0.01)
    dialog_binning_only.ui.offspec_x_max.setValue(0.02)
    dialog_binning_only.ui.offspec_y_min.setValue(0.01)
    dialog_binning_only.ui.offspec_y_max.setValue(0.20)

    # Set binning values
    dialog_binning_only.ui.offspec_bins_x.setValue(100)
    dialog_binning_only.ui.offspec_bins_y.setValue(150)
    dialog_binning_only.ui.error_weighting_checkbox.setChecked(True)

    params = dialog_binning_only.get_parameters()

    # Check shared region parameters
    assert params["off_spec_x_min"] == -0.01
    assert params["off_spec_x_max"] == 0.02
    assert params["off_spec_y_min"] == 0.01
    assert params["off_spec_y_max"] == 0.20

    # Check binning parameters
    assert params["off_spec_nxbins"] == 100
    assert params["off_spec_nybins"] == 150
    assert params["off_spec_err_weight"] is True

    # Smoothing-specific parameters should not be present
    assert "off_spec_sigmax" not in params
    assert "off_spec_sigmay" not in params
    assert "off_spec_sigmas" not in params


def test_only_binning_settings_are_persisted(dialog_both, qtbot):
    """Region, radii, uniformity and coordinate system live in the session memory only.

    Bins and error weighting keep their QSettings behaviour, which is outside the scope of
    the session memory.
    """
    dialog_both.ui.offspec_x_min.setValue(-0.02)
    dialog_both.ui.offspec_bins_x.setValue(200)
    dialog_both.ui.offspec_bins_y.setValue(250)
    dialog_both.ui.error_weighting_checkbox.setChecked(True)
    dialog_both.ui.sigmasCoupled.setChecked(False)
    dialog_both.ui.sigmaX.setValue(0.003)
    dialog_both.ui.sigmaY.setValue(0.004)
    dialog_both.ui.rSigmas.setValue(5.0)
    dialog_both.ui.qxVSqz.setChecked(True)

    dialog_both.save_settings()

    settings = QtCore.QSettings(".quicknxs")
    for key in ("offspec_binned/bins_x", "offspec_binned/bins_y", "offspec_binned/error_weighting"):
        assert settings.contains(key), key
    for key in (
        "offspec_binned/x_min",
        "offspec_binned/x_max",
        "offspec_binned/y_min",
        "offspec_binned/y_max",
        "offspec_binned/coordinate_system",
        "offspec_smoothing/sigma_x",
        "offspec_smoothing/sigma_y",
        "offspec_smoothing/r_sigmas",
        "offspec_smoothing/sigmas_coupled",
    ):
        assert not settings.contains(key), key

    main_window = dialog_both.parent()
    new_dialog = OffSpecParametersDialog(main_window, main_window.data_manager, show_smoothing=True, show_binning=True)
    qtbot.addWidget(new_dialog)

    assert new_dialog.ui.offspec_bins_x.value() == 200
    assert new_dialog.ui.offspec_bins_y.value() == 250
    assert new_dialog.ui.error_weighting_checkbox.isChecked() is True
    # Nothing else carried over into the new session
    assert new_dialog.ui.offspec_x_min.value() == -0.015
    assert new_dialog.ui.sigmaX.value() == 0.0005
    assert new_dialog.ui.rSigmas.value() == 3.0
    assert new_dialog.ui.kizmkfzVSqz.isChecked()


def test_opens_on_the_default_system_despite_a_legacy_setting(mock_main_window, qtbot):
    """Configuration files from earlier versions still hold the last coordinate system."""
    QtCore.QSettings(".quicknxs").setValue("offspec_binned/coordinate_system", OffSpecXAxis.QX_VS_QZ)

    with patch.object(OffSpecParametersDialog, "draw_plot"):
        dlg = OffSpecParametersDialog(mock_main_window, mock_main_window.data_manager, show_smoothing=True)
    qtbot.addWidget(dlg)

    assert dlg.ui.kizmkfzVSqz.isChecked()
    assert dlg._active_axis == OffSpecXAxis.DELTA_KZ_VS_QZ


########################################################################################
# Session memory: what the dialog remembers between coordinate systems and between visits
########################################################################################

STATE = "Off_Off"
DELTA_KZ = OffSpecXAxis.DELTA_KZ_VS_QZ
QX = OffSpecXAxis.QX_VS_QZ
KIZ_KFZ = OffSpecXAxis.KZI_VS_KZF

# Default region boxes for `_fake_reduction_item`, one per coordinate system: the data
# extents, bounded from outside by the seed values of `_collect_extents`, inset by 5%.
DEFAULT_REGION = {
    DELTA_KZ: (0.012, 0.048, 0.11, 0.29),
    QX: (-0.0009, 0.0009, 0.11, 0.29),
    KIZ_KFZ: (0.0525, 0.0975, 0.02625, 0.04875),
}
WIDTH = {axis: box[1] - box[0] for axis, box in DEFAULT_REGION.items()}
HEIGHT = {axis: box[3] - box[2] for axis, box in DEFAULT_REGION.items()}
COUPLED_BY_DEFAULT = {DELTA_KZ: True, QX: False, KIZ_KFZ: True}
# sigmaX and sigmaY show six decimals, so a radius read back is only exact to within this
DISPLAY_RESOLUTION = 1e-6


def _default_radius(extent: float) -> float:
    """The radius a view shows before the user chooses one."""
    return max(DEFAULT_SIGMA_FRACTION * extent, DEFAULT_MINIMUM_RADIUS)


_RADIO_BUTTON = {DELTA_KZ: "kizmkfzVSqz", QX: "qxVSqz", KIZ_KFZ: "kizVSkfz"}


@pytest.fixture
def data_window(mock_main_window):
    """Main window mock whose reduction list holds one run with off-specular data."""
    mock_main_window.data_manager.reduction_states = [STATE]
    mock_main_window.data_manager.reduction_list = [_fake_reduction_item(STATE)]
    return mock_main_window


@pytest.fixture
def open_dialog(qtbot, data_window):
    """Open the smoothing dialog on the fake data, the way the main window does."""

    def _open(memory: OffSpecSmoothingMemory | None = None) -> OffSpecParametersDialog:
        # Patched only while constructing, so the deferred first draw is a no op and cannot
        # fire later in the test and wipe the edits it is making
        with patch.object(OffSpecParametersDialog, "draw_plot"):
            dlg = OffSpecParametersDialog(data_window, data_window.data_manager, show_smoothing=True, memory=memory)
        qtbot.addWidget(dlg)
        dlg.draw_plot()
        return dlg

    return _open


def _switch(dlg: OffSpecParametersDialog, axis: OffSpecXAxis) -> None:
    """Select a coordinate system with its radio button, as the user would."""
    getattr(dlg.ui, _RADIO_BUTTON[axis]).setChecked(True)
    assert dlg._active_axis == axis


def _region(dlg: OffSpecParametersDialog) -> tuple[float, float, float, float]:
    return (
        dlg.ui.offspec_x_min.value(),
        dlg.ui.offspec_x_max.value(),
        dlg.ui.offspec_y_min.value(),
        dlg.ui.offspec_y_max.value(),
    )


class TestDefaults:
    """What a first visit in the session shows."""

    @pytest.mark.parametrize("axis", [DELTA_KZ, QX, KIZ_KFZ])
    def test_region_is_derived_from_the_data(self, open_dialog, axis):
        dlg = open_dialog()
        _switch(dlg, axis)
        assert _region(dlg) == pytest.approx(DEFAULT_REGION[axis])

    @pytest.mark.parametrize("axis", [DELTA_KZ, QX, KIZ_KFZ])
    def test_radii_are_a_quarter_percent_of_the_box_but_not_below_the_floor(self, open_dialog, axis):
        dlg = open_dialog()
        _switch(dlg, axis)

        expected_x = _default_radius(WIDTH[axis])
        expected_y = expected_x if COUPLED_BY_DEFAULT[axis] else _default_radius(HEIGHT[axis])
        assert dlg.ui.sigmaX.value() == pytest.approx(expected_x, abs=DISPLAY_RESOLUTION)
        assert dlg.ui.sigmaY.value() == pytest.approx(expected_y, abs=DISPLAY_RESOLUTION)

    @pytest.mark.parametrize("axis", [DELTA_KZ, QX, KIZ_KFZ])
    def test_uniformity_follows_the_agreed_table(self, open_dialog, axis):
        dlg = open_dialog()
        _switch(dlg, axis)
        assert dlg.ui.sigmasCoupled.isChecked() is COUPLED_BY_DEFAULT[axis]
        assert dlg.ui.sigmaY.isEnabled() is not COUPLED_BY_DEFAULT[axis]

    def test_ellipses_are_drawn_from_the_radii(self, open_dialog):
        dlg = open_dialog()
        sigma_x, sigma_y = dlg.ui.sigmaX.value(), dlg.ui.sigmaY.value()
        assert (dlg.sigma_1.width, dlg.sigma_1.height) == pytest.approx((2 * sigma_x, 2 * sigma_y))
        assert (dlg.sigma_3.width, dlg.sigma_3.height) == pytest.approx((6 * sigma_x, 6 * sigma_y))

    def test_the_data_is_read_once_however_often_the_view_changes(self, open_dialog):
        dlg = open_dialog()
        with patch.object(dlg, "_collect_extents") as collect:
            _switch(dlg, QX)
            _switch(dlg, KIZ_KFZ)
            _switch(dlg, DELTA_KZ)
        collect.assert_not_called()


class TestSwitchingCoordinateSystem:
    """Bogdan's rule: radii carry over as a percentage of the box, so the spot keeps its size."""

    def test_the_radius_is_rescaled_to_the_new_box(self, open_dialog):
        dlg = open_dialog()
        dlg.ui.sigmaX.setValue(0.001)

        _switch(dlg, QX)

        assert dlg.ui.sigmaX.value() == pytest.approx(0.001 * WIDTH[QX] / WIDTH[DELTA_KZ], abs=DISPLAY_RESOLUTION)
        # The vertical fraction was not touched while the radii were coupled
        assert dlg.ui.sigmaY.value() == pytest.approx(_default_radius(HEIGHT[QX]), abs=DISPLAY_RESOLUTION)

    @pytest.mark.parametrize("detour", [QX, KIZ_KFZ])
    def test_coming_back_restores_the_radius_exactly(self, open_dialog, detour):
        """Showing a view never re-derives a fraction, so a round trip cannot drift."""
        dlg = open_dialog()
        dlg.ui.sigmaX.setValue(0.000123)

        _switch(dlg, detour)
        _switch(dlg, DELTA_KZ)

        assert dlg.ui.sigmaX.value() == 0.000123
        assert dlg.ui.sigmaY.value() == 0.000123

    def test_a_vertical_radius_survives_a_detour_through_a_uniform_view(self, open_dialog):
        dlg = open_dialog()
        _switch(dlg, QX)
        dlg.ui.sigmaY.setValue(0.002)

        _switch(dlg, DELTA_KZ)
        _switch(dlg, QX)

        assert dlg.ui.sigmaY.value() == pytest.approx(0.002, abs=DISPLAY_RESOLUTION)

    def test_editing_the_vertical_radius_does_not_nudge_the_horizontal_one(self, open_dialog):
        """The untouched horizontal radius must stay a per-view default.

        Re-reading it from its spin box would turn the Qx default, which sits on the floor,
        into a chosen fraction twenty times larger than the default fraction, and every
        other view would inherit a radius twenty times too big.
        """
        dlg = open_dialog()
        _switch(dlg, QX)

        dlg.ui.sigmaY.setValue(0.002)
        _switch(dlg, DELTA_KZ)

        assert dlg.ui.sigmaX.value() == pytest.approx(_default_radius(WIDTH[DELTA_KZ]), abs=DISPLAY_RESOLUTION)

    def test_editing_one_radius_marks_only_that_radius(self, open_dialog):
        """The other radius must not be re-read, or its rounding would nudge its fraction."""
        dlg = open_dialog()
        _switch(dlg, QX)

        dlg.ui.sigmaY.setValue(0.002)

        assert dlg._radius_y_edited is True
        assert dlg._radius_x_edited is False

    def test_a_mirrored_vertical_radius_is_not_an_edit(self, open_dialog):
        """While coupled, sigmaY copies sigmaX with signals blocked."""
        dlg = open_dialog()

        dlg.ui.sigmaX.setValue(0.001)

        assert dlg.ui.sigmaY.value() == 0.001
        assert dlg._radius_x_edited is True
        assert dlg._radius_y_edited is False

    def test_uniformity_is_remembered_per_view(self, open_dialog):
        dlg = open_dialog()
        dlg.ui.sigmasCoupled.setChecked(False)

        _switch(dlg, KIZ_KFZ)
        assert dlg.ui.sigmasCoupled.isChecked(), "another view keeps its own default"

        _switch(dlg, DELTA_KZ)
        assert not dlg.ui.sigmasCoupled.isChecked()


class TestRegion:
    """The blue box: moving it keeps the radii, and changes the percentage that carries over."""

    def test_moving_the_region_keeps_the_radius(self, open_dialog):
        dlg = open_dialog()
        dlg.ui.sigmaX.setValue(0.001)

        dlg.ui.offspec_x_max.setValue(0.066)

        assert dlg.ui.sigmaX.value() == 0.001
        assert dlg.ui.sigmaY.value() == 0.001

    def test_the_new_percentage_is_what_carries_over(self, open_dialog):
        dlg = open_dialog()
        dlg.ui.sigmaX.setValue(0.001)
        dlg.ui.offspec_x_max.setValue(0.066)
        new_width = 0.066 - DEFAULT_REGION[DELTA_KZ][0]

        _switch(dlg, QX)

        assert dlg.ui.sigmaX.value() == pytest.approx(0.001 / new_width * WIDTH[QX], abs=DISPLAY_RESOLUTION)

    def test_an_edited_region_is_remembered_per_view(self, open_dialog):
        dlg = open_dialog()
        dlg.ui.offspec_x_min.setValue(0.02)

        _switch(dlg, QX)
        assert _region(dlg) == pytest.approx(DEFAULT_REGION[QX])

        _switch(dlg, DELTA_KZ)
        assert dlg.ui.offspec_x_min.value() == 0.02

    def test_a_click_on_the_plot_moves_the_region_and_keeps_the_radius(self, open_dialog):
        dlg = open_dialog()
        radius = dlg.ui.sigmaX.value()

        dlg.plot_select(Mock(button=1, xdata=0.015, ydata=0.12))

        moved = (0.015, DEFAULT_REGION[DELTA_KZ][1], 0.12, DEFAULT_REGION[DELTA_KZ][3])
        assert _region(dlg) == pytest.approx(moved)
        assert dlg.ui.sigmaX.value() == radius

        _switch(dlg, QX)
        _switch(dlg, DELTA_KZ)
        assert _region(dlg) == pytest.approx(moved)


class TestSessionMemory:
    """Carrying the visit over to the next time the dialog is opened."""

    def test_ok_commits_and_reopening_restores(self, open_dialog):
        memory = OffSpecSmoothingMemory()
        first = open_dialog(memory)
        first.ui.sigmaX.setValue(0.001)
        first.ui.offspec_x_min.setValue(0.02)
        first.ui.rSigmas.setValue(5.0)
        first.accept()

        second = open_dialog(memory)

        assert second.ui.offspec_x_min.value() == 0.02
        assert second.ui.sigmaX.value() == pytest.approx(0.001, abs=DISPLAY_RESOLUTION)
        assert second.ui.rSigmas.value() == 5.0

    def test_reopening_always_starts_in_the_default_view(self, open_dialog):
        memory = OffSpecSmoothingMemory()
        first = open_dialog(memory)
        _switch(first, QX)
        first.ui.offspec_x_min.setValue(-0.0005)
        first.accept()

        second = open_dialog(memory)
        assert second.ui.kizmkfzVSqz.isChecked()
        assert second._active_axis == DELTA_KZ

        _switch(second, QX)
        assert second.ui.offspec_x_min.value() == -0.0005

    def test_an_untouched_region_is_not_remembered(self, open_dialog):
        """Otherwise the next dataset reduced in the session would inherit this box."""
        memory = OffSpecSmoothingMemory()
        dlg = open_dialog(memory)
        _switch(dlg, QX)
        _switch(dlg, DELTA_KZ)

        dlg.accept()

        assert memory.regions == {}
        assert memory.coupled == {}
        assert memory.fraction_x is None

    def test_cancel_leaves_the_session_memory_untouched(self, open_dialog):
        memory = OffSpecSmoothingMemory()
        memory.store_fractions(0.0005, 0.0005, OffSpecRegion(*DEFAULT_REGION[DELTA_KZ]), coupled=True)
        before = memory.snapshot()

        dlg = open_dialog(memory)
        _switch(dlg, QX)
        dlg.ui.offspec_x_min.setValue(-0.0005)
        dlg.ui.sigmaY.setValue(0.002)
        _switch(dlg, KIZ_KFZ)
        dlg.ui.sigmasCoupled.setChecked(False)
        dlg.reject()

        assert memory == before

    def test_the_session_memory_is_the_one_the_main_window_holds(self, open_dialog):
        """Committing must write into the caller's object rather than rebinding it."""
        memory = OffSpecSmoothingMemory()
        dlg = open_dialog(memory)
        dlg.ui.offspec_x_min.setValue(0.02)

        dlg.accept()

        assert dlg.memory is memory
        assert DELTA_KZ in memory.regions
