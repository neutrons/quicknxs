# local imports
from quicknxs.interfaces.configuration import Configuration
from quicknxs.interfaces.main_window import MainWindow

# standard imports
import unittest.mock as mock

# third-party imports
import pytest
from qtpy import QtCore, QtWidgets


def test_show_deadtime_settings_default_values(mocker, qtbot):
    """Test showing the deadtime settings dialog and keeping the default values"""
    mock_reload_files = mocker.patch("quicknxs.interfaces.main_window.MainWindow.reload_all_files")
    main_window = MainWindow()
    qtbot.addWidget(main_window)
    Configuration.setup_default_values()

    def display_deadtime_settings():
        # open the deadtime settings dialog and close without changing values
        dialog = QtWidgets.QApplication.activeModalWidget()
        # press Enter to accept (click Ok)
        qtbot.keyClick(dialog, QtCore.Qt.Key_Enter, delay=1)

    QtCore.QTimer.singleShot(200, display_deadtime_settings)
    main_window.open_deadtime_settings()

    assert Configuration.paralyzable_deadtime == True
    assert Configuration.deadtime_value == 4.2
    assert Configuration.deadtime_tof_step == 100
    mock_reload_files.assert_not_called()


def test_show_deadtime_settings_updated_values(mocker, qtbot):
    """Test showing the deadtime settings dialog and updating the values"""
    mocker.patch("quicknxs.ui.deadtime_settings.DeadTimeSettingsView.ask_user_ok_to_reload_files", return_value=True)
    mock_reload_files = mocker.patch("quicknxs.interfaces.main_window.MainWindow.reload_all_files")

    new_paralyzable = False
    new_dead_time = 5.0
    new_tof_step = 200

    main_window = MainWindow()
    qtbot.addWidget(main_window)

    def update_deadtime_settings():
        # update the values in the deadtime settings dialog and close the dialog
        dialog = QtWidgets.QApplication.activeModalWidget()
        paralyzable_checkbox = dialog.findChild(QtWidgets.QCheckBox)
        paralyzable_checkbox.setChecked(new_paralyzable)
        deadtime_spinbox = dialog.findChild(QtWidgets.QDoubleSpinBox, "dead_time_value")
        deadtime_spinbox.setValue(new_dead_time)
        tof_spinbox = dialog.findChild(QtWidgets.QDoubleSpinBox, "dead_time_tof")
        tof_spinbox.setValue(new_tof_step)
        # press Enter to accept (click Ok)
        qtbot.keyClick(dialog, QtCore.Qt.Key_Enter, delay=1)

    QtCore.QTimer.singleShot(200, update_deadtime_settings)
    main_window.open_deadtime_settings()

    assert Configuration.paralyzable_deadtime == new_paralyzable
    assert Configuration.deadtime_value == new_dead_time
    assert Configuration.deadtime_tof_step == new_tof_step
    mock_reload_files.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__])
