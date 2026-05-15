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

    # Mock data_handler with minimal required attributes
    main_window.data_handler = Mock()
    main_window.data_handler.reduction_states = []  # Empty list for UI-only tests
    main_window.data_handler.reduction_list = []  # Empty list for UI-only tests

    return main_window


@pytest.fixture
def dialog_both(qtbot, mock_main_window):
    """Create an OffSpecParametersDialog instance with both smoothing and binning enabled."""
    with patch.object(OffSpecParametersDialog, "draw_plot"):
        dlg = OffSpecParametersDialog(
            mock_main_window, mock_main_window.data_handler, show_smoothing=True, show_binning=True
        )
        qtbot.addWidget(dlg)
        return dlg


@pytest.fixture
def dialog_smoothing_only(qtbot, mock_main_window):
    """Create an OffSpecParametersDialog instance with only smoothing enabled."""
    with patch.object(OffSpecParametersDialog, "draw_plot"):
        dlg = OffSpecParametersDialog(
            mock_main_window, mock_main_window.data_handler, show_smoothing=True, show_binning=False
        )
        qtbot.addWidget(dlg)
        return dlg


@pytest.fixture
def dialog_binning_only(qtbot, mock_main_window):
    """Create an OffSpecParametersDialog instance with only binning enabled."""
    with patch.object(OffSpecParametersDialog, "draw_plot"):
        dlg = OffSpecParametersDialog(
            mock_main_window, mock_main_window.data_handler, show_smoothing=False, show_binning=True
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
    new_dialog = OffSpecParametersDialog(main_window, main_window.data_handler, show_smoothing=True, show_binning=True)
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
