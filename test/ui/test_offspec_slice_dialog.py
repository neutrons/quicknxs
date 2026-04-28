"""Tests for the Off-Specular Qz Slice Parameters dialog"""

from unittest.mock import Mock

import pytest
from qtpy import QtCore

from quicknxs.interfaces.offspec_slice_dialog import OffSpecSliceDialog


@pytest.fixture
def dialog(qtbot):
    """Create an OffSpecSliceDialog instance for testing."""
    # Create minimal mock data_presenter for UI-only tests
    data_presenter = Mock()
    data_presenter.reduction_states = []  # Empty list for UI-only tests
    data_presenter.reduction_list = []  # Empty list for UI-only tests

    # No parent needed for UI-only tests
    dlg = OffSpecSliceDialog(None, data_presenter)
    qtbot.addWidget(dlg)
    return dlg


def test_dialog_creation(dialog):
    """Test that the dialog is created successfully."""
    assert dialog is not None
    assert dialog.ui is not None


def test_dialog_default_values(dialog):
    """Test that the dialog has reasonable default values."""
    # Check Qz range defaults
    assert dialog.ui.slice_qz_min.value() == 0.05
    assert dialog.ui.slice_qz_max.value() == 0.07


def test_dialog_slice_width_calculation(dialog):
    """Test that the slice width is calculated correctly."""
    # Set known values
    dialog.ui.slice_qz_min.setValue(0.05)
    dialog.ui.slice_qz_max.setValue(0.07)

    # Trigger update
    dialog.update_slice_width()

    # Check calculated width (0.07 - 0.05 = 0.02)
    expected_text = "0.020000 1/A"
    assert dialog.ui.slice_width_label.text() == expected_text


def test_dialog_get_parameters(dialog):
    """Test that get_parameters returns the correct dictionary."""
    # Set some values
    dialog.ui.slice_qz_min.setValue(0.04)
    dialog.ui.slice_qz_max.setValue(0.08)

    params = dialog.get_parameters()

    assert params["off_spec_slice_qz_min"] == 0.04
    assert params["off_spec_slice_qz_max"] == 0.08


def test_dialog_settings_persistence(dialog, qtbot):
    """Test that settings are saved and loaded correctly."""
    # Set custom values
    dialog.ui.slice_qz_min.setValue(0.03)
    dialog.ui.slice_qz_max.setValue(0.09)

    # Save settings
    dialog.save_settings()

    # Create a new dialog with mock data_presenter to test loading
    data_presenter = Mock()
    data_presenter.reduction_states = []
    data_presenter.reduction_list = []
    new_dialog = OffSpecSliceDialog(None, data_presenter)
    qtbot.addWidget(new_dialog)

    # Check that values were loaded
    assert new_dialog.ui.slice_qz_min.value() == 0.03
    assert new_dialog.ui.slice_qz_max.value() == 0.09


def test_dialog_accept_saves_settings(dialog, qtbot):
    """Test that accepting the dialog saves settings."""
    # Set custom values
    dialog.ui.slice_qz_min.setValue(0.055)
    dialog.ui.slice_qz_max.setValue(0.085)

    # Accept the dialog (this should save settings)
    dialog.accept()

    # Check that settings were saved
    settings = QtCore.QSettings(".quicknxs")
    assert settings.contains("offspec_slice/qz_min")
    assert float(settings.value("offspec_slice/qz_min")) == 0.055
    assert settings.contains("offspec_slice/qz_max")
    assert float(settings.value("offspec_slice/qz_max")) == 0.085


def test_dialog_slice_width_updates_on_value_change(dialog, qtbot):
    """Test that slice width label updates when values change."""
    # Set initial values
    dialog.ui.slice_qz_min.setValue(0.05)
    dialog.ui.slice_qz_max.setValue(0.07)

    # Check initial width
    assert "0.020000" in dialog.ui.slice_width_label.text()

    # Change max value
    dialog.ui.slice_qz_max.setValue(0.10)

    # Check updated width (0.10 - 0.05 = 0.05)
    assert "0.050000" in dialog.ui.slice_width_label.text()

    # Change min value
    dialog.ui.slice_qz_min.setValue(0.02)

    # Check updated width (0.10 - 0.02 = 0.08)
    assert "0.080000" in dialog.ui.slice_width_label.text()


def test_dialog_parameter_ranges(dialog):
    """Test that parameter ranges are properly configured."""
    # Test Qz min spinbox
    assert dialog.ui.slice_qz_min.minimum() == -1.0
    assert dialog.ui.slice_qz_min.maximum() == 10.0
    assert dialog.ui.slice_qz_min.singleStep() == 0.005

    # Test Qz max spinbox
    assert dialog.ui.slice_qz_max.minimum() == -1.0
    assert dialog.ui.slice_qz_max.maximum() == 10.0
    assert dialog.ui.slice_qz_max.singleStep() == 0.005
