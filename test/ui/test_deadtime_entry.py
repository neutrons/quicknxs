# third party imports
import pytest
from qtpy.QtCore import Qt  # type: ignore

# local imports
from quicknxs.interfaces.main_window import MainWindow
from quicknxs.ui.deadtime_entry import DeadTimeEntryPoint  # Make sure to import your class correctly
from test.ui import ui_utilities


@pytest.fixture
def dead_time_entry_point(qtbot):
    widget = DeadTimeEntryPoint()
    qtbot.addWidget(widget)
    return widget


def test_initial_state(dead_time_entry_point):
    assert not dead_time_entry_point.applyCheckBox.isChecked()
    assert not dead_time_entry_point.settingsButton.isEnabled()


def test_checkbox_interaction(mocker, dead_time_entry_point, qtbot):
    # Mock modal dialog
    mocker.patch(
        "quicknxs.ui.deadtime_entry.DeadTimeEntryPoint.VerifyChangeCheckBox.ask_user_ok_to_reload_files",
        return_value=True,
    )
    # Simulate checking the checkbox
    qtbot.mouseClick(dead_time_entry_point.applyCheckBox, Qt.LeftButton)
    # Test if the checkbox is checked
    assert dead_time_entry_point.applyCheckBox.isChecked()
    # Test if the settings button is now enabled
    assert dead_time_entry_point.settingsButton.isEnabled()


def test_uncheck_checkbox(mocker, dead_time_entry_point, qtbot):
    # Mock modal dialog
    mocker.patch(
        "quicknxs.ui.deadtime_entry.DeadTimeEntryPoint.VerifyChangeCheckBox.ask_user_ok_to_reload_files",
        return_value=True,
    )
    # First, check the checkbox
    qtbot.mouseClick(dead_time_entry_point.applyCheckBox, Qt.LeftButton)
    # Now, uncheck it
    qtbot.mouseClick(dead_time_entry_point.applyCheckBox, Qt.LeftButton)
    # Test if the checkbox is unchecked
    assert not dead_time_entry_point.applyCheckBox.isChecked()
    # Test if the settings button is now disabled
    assert not dead_time_entry_point.settingsButton.isEnabled()


@pytest.mark.datarepo
def test_checkbox_change_reload_files(mocker, qtbot):
    # Mock modal dialog
    mocker.patch(
        "quicknxs.ui.deadtime_entry.DeadTimeEntryPoint.VerifyChangeCheckBox.ask_user_ok_to_reload_files",
        return_value=True,
    )
    mock_reload_files = mocker.patch("quicknxs.interfaces.main_window.MainWindow.reload_all_files")
    # Initialize main window
    main_window = MainWindow()
    qtbot.addWidget(main_window)
    # Add run to the reduction table
    ui_utilities.setText(main_window.numberSearchEntry, str(40785), press_enter=True)
    ui_utilities.set_current_file_by_run_number(main_window, 40785)
    main_window.actionAddPlot.triggered.emit()
    # Simulate checking the deadtime settings checkbox
    qtbot.mouseClick(main_window.ui.deadtime_entry.applyCheckBox, Qt.LeftButton)
    # Test if file reload was triggered
    mock_reload_files.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__])
