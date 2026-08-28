"""Tests for the Off-Specular Parameters dialog (combined smoothing and binning)"""

from unittest.mock import Mock, patch

import pytest
from qtpy import QtWidgets

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


def test_dialog_settings_persistence(dialog_both, qtbot):
    """Test that settings are saved and loaded correctly."""
    # Set custom values for region
    dialog_both.ui.offspec_x_min.setValue(-0.02)
    dialog_both.ui.offspec_x_max.setValue(0.03)
    dialog_both.ui.offspec_y_min.setValue(0.02)
    dialog_both.ui.offspec_y_max.setValue(0.25)

    # Set custom values for binning
    dialog_both.ui.offspec_bins_x.setValue(200)
    dialog_both.ui.offspec_bins_y.setValue(250)
    dialog_both.ui.error_weighting_checkbox.setChecked(True)

    # Set custom values for smoothing - uncouple first to set different values
    dialog_both.ui.sigmasCoupled.setChecked(False)
    dialog_both.ui.sigmaX.setValue(0.003)
    dialog_both.ui.sigmaY.setValue(0.004)
    dialog_both.ui.rSigmas.setValue(5.0)

    # Save settings
    dialog_both.save_settings()

    # Create a new dialog to test loading
    main_window = dialog_both.parent()
    new_dialog = OffSpecParametersDialog(main_window, main_window.data_manager, show_smoothing=True, show_binning=True)
    qtbot.addWidget(new_dialog)

    # Check that region values were loaded
    assert new_dialog.ui.offspec_x_min.value() == -0.02
    assert new_dialog.ui.offspec_x_max.value() == 0.03
    assert new_dialog.ui.offspec_y_min.value() == 0.02
    assert new_dialog.ui.offspec_y_max.value() == 0.25

    # Check that binning values were loaded
    assert new_dialog.ui.offspec_bins_x.value() == 200
    assert new_dialog.ui.offspec_bins_y.value() == 250
    assert new_dialog.ui.error_weighting_checkbox.isChecked() is True

    # Check that smoothing values were loaded
    assert new_dialog.ui.sigmaX.value() == 0.003
    assert new_dialog.ui.sigmaY.value() == 0.004
    assert new_dialog.ui.rSigmas.value() == 5.0

    # Check that coupling states were loaded
    assert new_dialog.ui.sigmasCoupled.isChecked() is False


@pytest.fixture
def dialog_with_auto_grid(qtbot, mock_main_window, mocker):
    """Dialog with data available and finest_intervals mocked to known values."""
    mock_main_window.data_manager.reduction_states = ["Off_Off"]
    intervals = mocker.patch("quicknxs.views.smooth_dialog.finest_intervals", return_value=(0.001, 0.0005))
    # Patch for the dialog's lifetime: the real draw_plot would reset the region
    # spinboxes from the (mocked, empty) data on every axis change
    mocker.patch.object(OffSpecParametersDialog, "draw_plot")
    dlg = OffSpecParametersDialog(
        mock_main_window, mock_main_window.data_manager, show_smoothing=True, show_binning=False
    )
    qtbot.addWidget(dlg)
    # Fixed region so the expected bin counts are deterministic
    dlg.ui.offspec_x_min.setValue(-0.015)
    dlg.ui.offspec_x_max.setValue(0.015)
    dlg.ui.offspec_y_min.setValue(0.0)
    dlg.ui.offspec_y_max.setValue(0.15)
    return dlg, intervals


def test_auto_grid_defaults(dialog_with_auto_grid):
    """Auto grid is on by default and locks the spinboxes."""
    dlg, _ = dialog_with_auto_grid
    assert dlg.ui.autoGridBins.isChecked()
    assert not dlg.ui.smooth_grid_x.isEnabled()
    assert not dlg.ui.smooth_grid_y.isEnabled()


def test_auto_grid_computes_bins_from_intervals(dialog_with_auto_grid):
    """Bins are region extent / finest interval, per axis."""
    dlg, _ = dialog_with_auto_grid
    # x: 0.03 / 0.001 = 30, y: 0.15 / 0.0005 = 300
    assert dlg.ui.smooth_grid_x.value() == 30
    assert dlg.ui.smooth_grid_y.value() == 300


def test_auto_grid_recomputes_on_axis_change(dialog_with_auto_grid):
    dlg, intervals = dialog_with_auto_grid
    intervals.return_value = (0.003, 0.001)
    dlg.ui.qxVSqz.setChecked(True)
    assert dlg.ui.smooth_grid_x.value() == 10  # 0.03 / 0.003
    assert dlg.ui.smooth_grid_y.value() == 150  # 0.15 / 0.001


def test_auto_grid_clamps_to_spinbox_maximum(dialog_with_auto_grid):
    dlg, intervals = dialog_with_auto_grid
    intervals.return_value = (1e-9, 1e-9)
    dlg.update_auto_bins()
    assert dlg.ui.smooth_grid_x.value() == dlg.ui.smooth_grid_x.maximum() == 5000
    assert dlg.ui.smooth_grid_y.value() == dlg.ui.smooth_grid_y.maximum() == 5000


def test_manual_grid_when_auto_unchecked(dialog_with_auto_grid):
    """Unchecking Auto enables editing and stops automatic recomputation."""
    dlg, intervals = dialog_with_auto_grid
    dlg.ui.autoGridBins.setChecked(False)
    assert dlg.ui.smooth_grid_x.isEnabled()
    assert dlg.ui.smooth_grid_y.isEnabled()
    dlg.ui.smooth_grid_x.setValue(77)
    intervals.return_value = (0.003, 0.001)
    dlg.ui.qxVSqz.setChecked(True)
    assert dlg.ui.smooth_grid_x.value() == 77


def test_auto_grid_without_data_keeps_values(qtbot, mock_main_window):
    """With no data loaded the spinboxes keep their stored values."""
    with patch.object(OffSpecParametersDialog, "draw_plot"):
        dlg = OffSpecParametersDialog(
            mock_main_window, mock_main_window.data_manager, show_smoothing=True, show_binning=False
        )
        qtbot.addWidget(dlg)
    assert dlg.ui.smooth_grid_x.value() >= 1  # unchanged stored/default value, no crash


def test_get_parameters_includes_smooth_grid(dialog_with_auto_grid):
    dlg, _ = dialog_with_auto_grid
    params = dlg.get_parameters()
    assert params["off_spec_smooth_nxbins"] == dlg.ui.smooth_grid_x.value()
    assert params["off_spec_smooth_nybins"] == dlg.ui.smooth_grid_y.value()


def test_auto_grid_settings_round_trip(dialog_with_auto_grid, qtbot, mocker):
    """Auto state and manual grid values persist through QSettings."""
    dlg, intervals = dialog_with_auto_grid
    dlg.ui.autoGridBins.setChecked(False)
    dlg.ui.smooth_grid_x.setValue(111)
    dlg.ui.smooth_grid_y.setValue(222)
    dlg.save_settings()

    with patch.object(OffSpecParametersDialog, "draw_plot"):
        new_dlg = OffSpecParametersDialog(
            dlg.parent(), dlg.parent().data_manager, show_smoothing=True, show_binning=False
        )
        qtbot.addWidget(new_dlg)
    assert new_dlg.ui.autoGridBins.isChecked() is False
    assert new_dlg.ui.smooth_grid_x.value() == 111
    assert new_dlg.ui.smooth_grid_y.value() == 222
