"""Tests for the Off-Specular Binned Parameters dialog"""

import pytest
from qtpy import QtCore

from quicknxs.interfaces.offspec_binned_dialog import OffSpecBinnedDialog


@pytest.fixture
def dialog(qtbot, main_window_with_data_factory):
    """Create an OffSpecBinnedDialog instance for testing."""
    main_window = main_window_with_data_factory()

    # Clear any saved settings to test default values
    # This must be done AFTER creating main_window, since initialize_instrument()
    # writes Configuration defaults to QSettings
    settings = QtCore.QSettings(".quicknxs")
    settings.remove("offspec_binned/x_min")
    settings.remove("offspec_binned/x_max")
    settings.remove("offspec_binned/y_min")
    settings.remove("offspec_binned/y_max")
    settings.remove("offspec_binned/bins_x")
    settings.remove("offspec_binned/bins_y")
    settings.sync()  # Force write

    dlg = OffSpecBinnedDialog(main_window, main_window.data_manager)
    qtbot.addWidget(dlg)
    return dlg


def test_dialog_creation(dialog):
    """Test that the dialog is created successfully."""
    assert dialog is not None
    assert dialog.ui is not None


def test_dialog_default_values(dialog):
    """Test that the dialog has reasonable default values."""
    # Check X-axis defaults
    assert dialog.ui.offspec_x_min.value() == -0.015
    assert dialog.ui.offspec_x_max.value() == 0.015

    # Check Y-axis defaults
    assert dialog.ui.offspec_y_min.value() == 0.0
    assert dialog.ui.offspec_y_max.value() == 0.15

    # Check bin count defaults
    assert dialog.ui.offspec_bins_x.value() == 120
    assert dialog.ui.offspec_bins_y.value() == 120


def test_dialog_bin_width_calculation(dialog):
    """Test that the Qz bin width is calculated correctly."""
    # Set known values
    dialog.ui.offspec_y_min.setValue(0.0)
    dialog.ui.offspec_y_max.setValue(0.12)
    dialog.ui.offspec_bins_y.setValue(100)

    # Trigger update
    dialog.update_bin_width()

    # Check calculated width (0.12 / 100 = 0.0012)
    expected_text = "0.001200 1/A"
    assert dialog.ui.qz_bin_width_label.text() == expected_text


def test_dialog_get_parameters(dialog):
    """Test that get_parameters returns the correct dictionary."""
    # Set some values
    dialog.ui.offspec_x_min.setValue(-0.01)
    dialog.ui.offspec_x_max.setValue(0.02)
    dialog.ui.offspec_y_min.setValue(0.01)
    dialog.ui.offspec_y_max.setValue(0.20)
    dialog.ui.offspec_bins_x.setValue(100)
    dialog.ui.offspec_bins_y.setValue(150)

    params = dialog.get_parameters()

    assert params["off_spec_x_min"] == -0.01
    assert params["off_spec_x_max"] == 0.02
    assert params["off_spec_y_min"] == 0.01
    assert params["off_spec_y_max"] == 0.20
    assert params["off_spec_nxbins"] == 100
    assert params["off_spec_nybins"] == 150


def test_dialog_settings_persistence(dialog, qtbot):
    """Test that settings are saved and loaded correctly."""
    # Clear any existing settings
    settings = QtCore.QSettings(".quicknxs")
    settings.remove("offspec_binned")

    # Set custom values
    dialog.ui.offspec_x_min.setValue(-0.02)
    dialog.ui.offspec_x_max.setValue(0.03)
    dialog.ui.offspec_y_min.setValue(0.02)
    dialog.ui.offspec_y_max.setValue(0.25)
    dialog.ui.offspec_bins_x.setValue(200)
    dialog.ui.offspec_bins_y.setValue(250)

    # Save settings
    dialog.save_settings()

    # Create a new dialog to test loading
    main_window = dialog.parent()
    new_dialog = OffSpecBinnedDialog(main_window, main_window.data_manager)
    qtbot.addWidget(new_dialog)

    # Check that values were loaded
    assert new_dialog.ui.offspec_x_min.value() == -0.02
    assert new_dialog.ui.offspec_x_max.value() == 0.03
    assert new_dialog.ui.offspec_y_min.value() == 0.02
    assert new_dialog.ui.offspec_y_max.value() == 0.25
    assert new_dialog.ui.offspec_bins_x.value() == 200
    assert new_dialog.ui.offspec_bins_y.value() == 250

    # Cleanup
    settings.remove("offspec_binned")


def test_dialog_accept_saves_settings(dialog, qtbot):
    """Test that accepting the dialog saves settings."""
    # Clear any existing settings
    settings = QtCore.QSettings(".quicknxs")
    settings.remove("offspec_binned")

    # Set custom values
    dialog.ui.offspec_x_min.setValue(-0.025)
    dialog.ui.offspec_bins_y.setValue(180)

    # Accept the dialog (this should save settings)
    dialog.accept()

    # Check that settings were saved
    assert settings.contains("offspec_binned/x_min")
    assert float(settings.value("offspec_binned/x_min")) == -0.025
    assert settings.contains("offspec_binned/bins_y")
    assert int(settings.value("offspec_binned/bins_y")) == 180

    # Cleanup
    settings.remove("offspec_binned")


def test_dialog_bin_width_updates_on_value_change(dialog, qtbot):
    """Test that bin width label updates when values change."""
    # Set initial values
    dialog.ui.offspec_y_min.setValue(0.0)
    dialog.ui.offspec_y_max.setValue(0.15)
    dialog.ui.offspec_bins_y.setValue(100)

    initial_text = dialog.ui.qz_bin_width_label.text()

    # Change Y max
    dialog.ui.offspec_y_max.setValue(0.20)

    # Check that label updated
    new_text = dialog.ui.qz_bin_width_label.text()
    assert new_text != initial_text
    assert new_text == "0.002000 1/A"


def test_dialog_parameter_ranges(dialog):
    """Test that parameter spinboxes have appropriate ranges."""
    # X-axis ranges
    assert dialog.ui.offspec_x_min.minimum() == -10.0
    assert dialog.ui.offspec_x_min.maximum() == 10.0
    assert dialog.ui.offspec_x_max.minimum() == -10.0
    assert dialog.ui.offspec_x_max.maximum() == 10.0

    # Y-axis ranges
    assert dialog.ui.offspec_y_min.minimum() == -1.0
    assert dialog.ui.offspec_y_min.maximum() == 10.0
    assert dialog.ui.offspec_y_max.minimum() == -1.0
    assert dialog.ui.offspec_y_max.maximum() == 10.0

    # Bin count ranges
    assert dialog.ui.offspec_bins_x.minimum() == 1
    assert dialog.ui.offspec_bins_x.maximum() == 1000
    assert dialog.ui.offspec_bins_y.minimum() == 1
    assert dialog.ui.offspec_bins_y.maximum() == 1000
