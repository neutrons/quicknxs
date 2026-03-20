"""Tests for the ReductionDialog class."""

from quicknxs.interfaces.reduction_dialog import ReductionDialog


class TestReductionDialog:
    """Test the Reduction Dialog functionality."""

    def test_dialog_initialization(self, qtbot):
        """Test that the dialog initializes with default values."""
        # Create a minimal parent widget
        parent = None
        dialog = ReductionDialog(parent)
        qtbot.addWidget(dialog)

        # Check that the dialog was created
        assert dialog is not None
        assert dialog.windowTitle() == "Reduction Options"

    def test_intensity_smoothing_checkbox_exists(self, qtbot):
        """Test that the intensity smoothing checkbox is present."""
        dialog = ReductionDialog(None)
        qtbot.addWidget(dialog)

        # Check that the checkbox exists
        assert hasattr(dialog.ui, "intensitySmoothingCheckbox")
        assert dialog.ui.intensitySmoothingCheckbox is not None

    def test_intensity_smoothing_default_value(self, qtbot):
        """Test that intensity smoothing defaults to False."""
        dialog = ReductionDialog(None)
        qtbot.addWidget(dialog)

        # Default should be unchecked (False)
        assert dialog.ui.intensitySmoothingCheckbox.isChecked() is False

    def test_get_options_includes_apply_smoothing(self, qtbot):
        """Test that get_options returns apply_smoothing value."""
        dialog = ReductionDialog(None)
        qtbot.addWidget(dialog)

        # Check unchecked state
        dialog.ui.intensitySmoothingCheckbox.setChecked(False)
        dialog.accept()
        options = dialog.get_options()

        assert options is not None
        assert "apply_smoothing" in options
        assert options["apply_smoothing"] is False

    def test_apply_smoothing_true_when_checked(self, qtbot):
        """Test that apply_smoothing is True when checkbox is checked."""
        dialog = ReductionDialog(None)
        qtbot.addWidget(dialog)

        # Set checkbox to checked
        dialog.ui.intensitySmoothingCheckbox.setChecked(True)
        dialog.accept()
        options = dialog.get_options()

        assert options is not None
        assert options["apply_smoothing"] is True

    def test_settings_persistence(self, qtbot, qsettings_tmp_path):
        """Test that the intensity smoothing setting persists across dialog instances."""
        # qsettings_tmp_path fixture configures QSettings to use a temporary location.

        # Create first dialog and set checkbox
        dialog1 = ReductionDialog(None)
        qtbot.addWidget(dialog1)
        dialog1.ui.intensitySmoothingCheckbox.setChecked(True)
        dialog1.accept()

        # Create second dialog and check if setting persisted
        dialog2 = ReductionDialog(None)
        qtbot.addWidget(dialog2)

        # The checkbox should be checked based on saved settings
        assert dialog2.ui.intensitySmoothingCheckbox.isChecked() is True
