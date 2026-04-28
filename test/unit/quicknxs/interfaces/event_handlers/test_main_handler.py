import importlib
import logging
import os
import sys

import numpy as np
import pytest
from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QApplication
from qtpy import QtCore, QtWidgets

from quicknxs.enums import ReductionTableColumn
from quicknxs.exceptions import CrossSectionError, NormalizeToUnityQCutoffError
from quicknxs.models.configuration import Configuration
from quicknxs.models.data_set import CrossSectionData, NexusData
from quicknxs.presenters.main_presenter import MainPresenter
from quicknxs.views.main_window import MainWindow
from test.ui import ui_utilities

this_module_path = sys.modules[__name__].__file__


class DataPresenterMock(object):
    """Mock for DataPresenter to be used in MainWindowMock."""

    current_directory = os.path.dirname(this_module_path)


class MainWindowMock(object):
    """Mock for MainWindow to be used in MainPresenter tests."""

    ui = None
    main_window = None
    data_presenter = DataPresenterMock()


class TestMainPresenter(object):
    """Test MainPresenter class."""

    app = QApplication(sys.argv)
    application = MainWindow()
    handler = MainPresenter(application)

    @pytest.mark.datarepo
    @pytest.mark.skip(reason="WIP")
    def test_congruency_fail_report(self, data_server):
        # Selected subset of log names with an invalid one
        message = self.handler._congruency_fail_report(
            [data_server.path_to("REF_M_24945_event.nxs"), data_server.path_to("REF_M_24949_event.nxs")],
            log_names=["LambdaRequest", "NoLog"],
        )
        assert message == "NoLog is not a valid Log for comparison"

        # Valid subset of log name
        message = self.handler._congruency_fail_report(
            [data_server.path_to("REF_M_24945_event.nxs"), data_server.path_to("REF_M_24949_event.nxs")],
            log_names=["LambdaRequest", "frequency"],
        )
        assert message == ""

        # Old files
        message = self.handler._congruency_fail_report(
            [data_server.path_to("REF_M_24945_event.nxs"), data_server.path_to("REF_M_24949_event.nxs")]
        )
        assert "contain values for log S3Vheight that differ above tolerance 0.01" in message

        # New files
        message = self.handler._congruency_fail_report(
            [data_server.path_to("REF_M_38198.nxs.h5"), data_server.path_to("REF_M_38199.nxs.h5")]
        )
        assert "values for log DANGLE that differ above tolerance 0.01" in message

    @pytest.mark.parametrize(
        "error_type, error_msg",
        [
            (NormalizeToUnityQCutoffError, "Error in normalize to unity when stitching"),
            (RuntimeError, "Error in stitching"),
            (ValueError, "Error in stitching"),
        ],
    )
    def test_stitch_reflectivity_errors(self, mocker, error_type, error_msg):
        """Test that stitch_reflectivity catches errors in stitching and calls report_message."""
        # Mock exception raised in stitch_data_sets
        mocker.patch("quicknxs.interfaces.data_presenter.DataPresenter.stitch_data_sets", side_effect=error_type)
        # Mock call to function report_message
        mock_report_message = mocker.patch(
            "quicknxs.interfaces.event_handlers.main_presenter.MainPresenter.report_message"
        )
        self.handler.stitch_reflectivity()
        assert error_msg in mock_report_message.call_args[0][0]


def test_save_run_data(tmp_path, qtbot, mocker):
    """Test of method save_run_data."""
    mocker.patch(
        "quicknxs.interfaces.event_handlers.main_presenter.QtWidgets.QFileDialog.getExistingDirectory",
        return_value=tmp_path,
    )
    mocker.patch(
        "quicknxs.interfaces.event_handlers.main_presenter.QtWidgets.QInputDialog.getText",
        return_value=("test_save_run_data", True),
    )
    header = "col1 col2"
    mocker.patch(
        "quicknxs.interfaces.data_handling.data_set.CrossSectionData.get_tof_counts_table",
        return_value=(np.ones((5, 5)), header),
    )
    mocker.patch(
        "quicknxs.interfaces.event_handlers.main_presenter.MainPresenter.ask_question", side_effect=[False, True]
    )

    main_window = MainWindow()
    handler = MainPresenter(main_window)
    qtbot.addWidget(main_window)

    nexus_data = _get_nexus_data()
    # test save files
    handler.save_run_data(nexus_data)
    # test save and overwrite existing files
    handler.save_run_data(nexus_data)

    for xs in nexus_data.cross_sections.keys():
        save_file_path = tmp_path / f"test_save_run_data_{xs}.dat"
        assert os.path.exists(save_file_path)
        with open(save_file_path) as f:
            first_line = f.readline()
            assert header in first_line
            second_line = f.readline()
            assert len(second_line.split()) == 5


def test_ask_question(qtbot):
    """Test of helper function ask_question."""
    main_window = MainWindow()
    handler = MainPresenter(main_window)
    qtbot.addWidget(main_window)

    def dialog_click_button(button_type):
        # click button in the popup dialog
        dialog = QApplication.activeModalWidget()
        button = dialog.button(button_type)
        qtbot.mouseClick(button, QtCore.Qt.LeftButton, delay=1)

    QTimer.singleShot(200, lambda: dialog_click_button(QtWidgets.QMessageBox.Ok))
    answer = handler.ask_question("OK or Cancel?")
    assert answer is True

    QTimer.singleShot(200, lambda: dialog_click_button(QtWidgets.QMessageBox.Cancel))
    answer = handler.ask_question("OK or Cancel?")
    assert answer is False


@pytest.mark.datarepo
def test_reload_all_files(qtbot):
    """Test function reload_all_files."""
    main_window = MainWindow()
    handler = MainPresenter(main_window)
    data_presenter = main_window.data_presenter
    qtbot.addWidget(main_window)
    selected_row = 0

    # Add one direct beam run and two data runs
    ui_utilities.setText(main_window.numberSearchEntry, str(40786), press_enter=True)
    ui_utilities.set_current_file_by_run_number(main_window, 40786)
    main_window.actionAddDirectBeam.triggered.emit()
    ui_utilities.set_current_file_by_run_number(main_window, 40785)
    main_window.actionAddRefl.triggered.emit()
    ui_utilities.set_current_file_by_run_number(main_window, 40782)
    main_window.actionAddRefl.triggered.emit()

    # Select/plot the first data run
    main_window.set_active_reduction_data(True, selected_row)

    # Test that reloading all files does not change the active run
    assert main_window.ui.reductionTable.rowCount() == 2
    assert len(data_presenter.reduction_list) == 2
    assert data_presenter._nexus_data == data_presenter.reduction_list[selected_row]
    handler.reload_all_files()
    assert main_window.ui.reductionTable.rowCount() == 2
    assert len(main_window.data_presenter.reduction_list) == 2
    assert data_presenter._nexus_data == data_presenter.reduction_list[selected_row]


@pytest.mark.datarepo
def test_reload_all_files_two_data_tabs(qtbot):
    """Test function reload_all_files."""
    main_window = MainWindow()
    handler = MainPresenter(main_window)
    data_presenter = main_window.data_presenter
    qtbot.addWidget(main_window)
    selected_row = 0

    # Add one direct beam run and two data runs
    ui_utilities.setText(main_window.numberSearchEntry, str(40786), press_enter=True)
    ui_utilities.set_current_file_by_run_number(main_window, 40786)
    main_window.actionAddDirectBeam.triggered.emit()
    ui_utilities.set_current_file_by_run_number(main_window, 40785)
    main_window.actionAddRefl.triggered.emit()
    ui_utilities.set_current_file_by_run_number(main_window, 40782)
    main_window.actionAddRefl.triggered.emit()

    # Add second peak data tab
    main_window.addDataTable()

    # Select/plot the first data run
    main_window.set_active_reduction_data(True, selected_row)

    # Test that reloading all files does not change the active run and data tab
    assert main_window.ui.reductionTable.rowCount() == 2
    assert len(data_presenter.reduction_list) == 2
    assert len(data_presenter.peak_reduction_lists[2]) == 2
    assert data_presenter.active_reduction_list_index == 1
    assert data_presenter._nexus_data == data_presenter.reduction_list[selected_row]
    handler.reload_all_files()
    assert main_window.ui.reductionTable.rowCount() == 2
    assert len(data_presenter.reduction_list) == 2
    assert len(data_presenter.peak_reduction_lists[2]) == 2
    assert data_presenter.active_reduction_list_index == 1
    assert data_presenter._nexus_data == data_presenter.reduction_list[selected_row]


def _get_nexus_data():
    """Data for testing."""
    config = Configuration()
    nexus_data = NexusData("file/path", config)
    off_off = CrossSectionData("Off_Off", config)
    off_off.tof_edges = np.arange(0.1, 0.4, 20)
    off_off.dist_mod_det = 1.0
    on_off = CrossSectionData("On_Off", config)
    on_off.tof_edges = np.arange(0.1, 0.4, 20)
    on_off.dist_mod_det = 1.0
    nexus_data.cross_sections["Off_Off"] = off_off
    nexus_data.cross_sections["On_Off"] = on_off
    return nexus_data


def test_reduction_table(qtbot):
    """Test property reduction_table which is computed based on the selected tab in the UI."""
    main_window = MainWindow()
    handler = MainPresenter(main_window)
    data_tab_widget = main_window.ui.tabWidget
    qtbot.addWidget(main_window)

    # Add second data tab
    main_window.addDataTable()
    main_data_table_widget = data_tab_widget.widget(handler.MAIN_DATA_TAB_INDEX).findChild(QtWidgets.QTableWidget)
    second_data_table_widget = data_tab_widget.widget(2).findChild(QtWidgets.QTableWidget)

    # Test that the main data tab is active by default
    assert handler.reduction_table == main_data_table_widget

    # When the direct beam tab is active, `reduction_table` should return the main data table widget
    data_tab_widget.setCurrentIndex(handler.DIRECT_BEAM_TAB_INDEX)
    assert handler.reduction_table == main_data_table_widget

    # When one of the data tabs is active, `reduction_table` should return the corresponding data table widget
    data_tab_widget.setCurrentIndex(handler.MAIN_DATA_TAB_INDEX)
    assert handler.reduction_table == main_data_table_widget
    data_tab_widget.setCurrentIndex(2)
    assert handler.reduction_table == second_data_table_widget


@pytest.mark.datarepo
def test_reduction_table_dpix(qtbot):
    """Test that changing the DPIX column in the reduction table updates configuration.direct_pixel_overwrite."""
    main_window = MainWindow()
    data_presenter = main_window.data_presenter
    qtbot.addWidget(main_window)

    # Load a data file and add it to the reduction table
    ui_utilities.setText(main_window.numberSearchEntry, str(40785), press_enter=True)
    ui_utilities.set_current_file_by_run_number(main_window, 40785)
    main_window.actionAddRefl.triggered.emit()

    # Verify the run was added to the reduction table
    assert main_window.ui.reductionTable.rowCount() == 1
    assert len(data_presenter.reduction_list) == 1

    # Get the nexus data from the reduction list
    nexus_data = data_presenter.reduction_list[0]
    active_cross_section_name = data_presenter.active_cross_section.name
    active_cross_section = nexus_data.cross_sections[active_cross_section_name]

    # check the "Set Direct Pixel" checkbox
    if not main_window.ui.set_dirpix_checkbox.isChecked():
        main_window.ui.set_dirpix_checkbox.click()

    # Set a new value in the DPIX column
    initial_dpix = active_cross_section.configuration.direct_pixel_overwrite
    new_dpix_value = initial_dpix + 10.5
    main_window.ui.reductionTable.item(0, ReductionTableColumn.DPIX).setText(str(new_dpix_value))

    # Verify that the configuration was updated
    assert active_cross_section.configuration.direct_pixel_overwrite == new_dpix_value

    # Verify the value propagates to all cross sections in the nexus data
    for xs in nexus_data.cross_sections.values():
        assert xs.configuration.direct_pixel_overwrite == new_dpix_value


class MockCrossSectionError(CrossSectionError):
    """Mock exception class to make testing work without a real file"""

    def __init__(self):
        pass


@pytest.mark.parametrize(
    "error_type",
    [
        (MockCrossSectionError),
        (RuntimeError),
    ],
)
def test_open_file_insufficient_event_count_error(error_type, mocker, qtbot):
    mock_show_diag = mocker.patch("quicknxs.interfaces.event_handlers.main_presenter.MainPresenter._show_diagnostic")
    mocker.patch("quicknxs.interfaces.data_presenter.DataPresenter.load", side_effect=error_type)
    mocker.patch("os.path.isfile", return_value=True)
    mock_report_message = mocker.patch("quicknxs.interfaces.event_handlers.main_presenter.MainPresenter.report_message")

    main_window = MainWindow()
    qtbot.addWidget(main_window)
    handler = MainPresenter(main_window)

    handler.open_file("test/file/path")

    if error_type is RuntimeError:
        mock_show_diag.assert_not_called()
        assert mock_report_message.call_count == 2
        assert "Error loading file(s)" in mock_report_message.call_args[0][0]
    else:
        mock_show_diag.assert_called_once()
        mock_report_message.assert_any_call("Loading file(s) test/file/path")


def test_logging_default_level(monkeypatch):
    """Test that the default logging level is INFO if the environment variable is not set or invalid."""
    monkeypatch.delenv("QUICKNXS_LOGLEVEL", raising=False)

    import quicknxs.main  # noqa

    assert logging.getLogger().getEffectiveLevel() == logging.INFO


def test_logging_level_environment_variable(monkeypatch):
    """Test that the logging level is set according to the environment variable."""
    monkeypatch.setenv("QUICKNXS_LOGLEVEL", "DEBUG")
    import quicknxs.main as gui_module

    importlib.reload(gui_module)

    assert logging.getLogger().getEffectiveLevel() == logging.DEBUG

    monkeypatch.setenv("QUICKNXS_LOGLEVEL", "INVALID_LEVEL")
    importlib.reload(gui_module)

    assert logging.getLogger().getEffectiveLevel() == logging.INFO


def test_logging_handlers():
    """Test that the logging handlers are set up correctly."""
    logger = logging.getLogger()
    handlers = logger.handlers

    # Check that there are two handlers: one for file and one for console
    assert any(isinstance(h, logging.handlers.TimedRotatingFileHandler) for h in handlers)
    assert any(isinstance(h, logging.StreamHandler) for h in handlers)

    # Check that the file handler is set to rotate at midnight and keep 15 backups
    file_handler = next(h for h in handlers if isinstance(h, logging.handlers.TimedRotatingFileHandler))
    assert file_handler.when == "MIDNIGHT"
    assert file_handler.backupCount == 15


def test_logging_changes_from_gui(qtbot, monkeypatch):
    """Test that changing the log level from the GUI updates the logging level."""
    monkeypatch.setenv("QUICKNXS_LOGLEVEL", "WARNING")
    import quicknxs.main as gui_module

    importlib.reload(gui_module)

    main_window = MainWindow()
    handler = MainPresenter(main_window)
    qtbot.addWidget(main_window)

    # Initial log level should be WARNING
    assert handler.get_log_level() == "WARN"
    assert logging.getLogger().getEffectiveLevel() == logging.WARNING

    # Change log level to DEBUG using the handler method
    handler.change_log_level("DEBUG")
    assert handler.get_log_level() == "DBUG"
    assert logging.getLogger().getEffectiveLevel() == logging.DEBUG


@pytest.mark.datarepo
def test_stitch_reflectivity_updates_reduction_table(mocker, qtbot):
    """Test that stitch_reflectivity updates the reduction table scale factor column"""
    scale0 = 2.1111
    scale1 = 5.4444

    def _mock_stitch_data_sets(*args, **kwargs):
        # simulate stitching updating the scale factors
        data_presenter.reduction_list[0].set_parameter("scaling_factor", scale0)
        data_presenter.reduction_list[1].set_parameter("scaling_factor", scale1)

    mocker.patch("quicknxs.interfaces.plotting.PlotView.plot_reflectivity_or_intensity", return_value=True)
    mocker.patch("quicknxs.interfaces.data_presenter.DataPresenter.stitch_data_sets", new=_mock_stitch_data_sets)

    main_window = MainWindow()
    handler = MainPresenter(main_window)
    data_presenter = main_window.data_presenter
    qtbot.addWidget(main_window)

    # Add two data runs
    ui_utilities.setText(main_window.numberSearchEntry, str(42112), press_enter=True)
    ui_utilities.set_current_file_by_run_number(main_window, 42112)
    main_window.actionAddRefl.triggered.emit()
    ui_utilities.set_current_file_by_run_number(main_window, 42113)
    main_window.actionAddRefl.triggered.emit()

    handler.stitch_reflectivity()

    assert handler.reduction_table.item(0, ReductionTableColumn.SCALE_FACTOR).text() == str(scale0)
    assert handler.reduction_table.item(1, ReductionTableColumn.SCALE_FACTOR).text() == str(scale1)


def test_show_diagnostic(mocker, qtbot):
    """Test that _show_diagnostic creates DiagnosticData and DiagnosticWidget, shows the widget, and updates the file list."""
    main_window = MainWindow()
    handler = MainPresenter(main_window)
    qtbot.addWidget(main_window)

    mock_diag_data_cls = mocker.patch("quicknxs.interfaces.event_handlers.main_presenter.DiagnosticData")
    mock_diag_widget_cls = mocker.patch("quicknxs.interfaces.event_handlers.main_presenter.DiagnosticWidget")
    mock_update_file_list = mocker.patch(
        "quicknxs.interfaces.event_handlers.main_presenter.MainPresenter.update_file_list"
    )

    error = CrossSectionError(file_path=None, message="test diagnostic message")
    handler._show_diagnostic(error)

    mock_diag_data_cls.assert_called_once_with(file_path=error.file_path, message=str(error))
    mock_diag_widget_cls.assert_called_once_with(parent=main_window)
    mock_diag_widget_cls.return_value.show.assert_called_once_with(mock_diag_data_cls.return_value)
    mock_update_file_list.assert_called_once()


def test_get_tab_index_for_reduction_table(qtbot):
    """Test that get_tab_index_for_reduction_table returns the correct tab index for each table widget."""
    main_window = MainWindow()
    handler = MainPresenter(main_window)
    data_tab_widget = main_window.ui.tabWidget
    qtbot.addWidget(main_window)

    main_data_table = data_tab_widget.widget(handler.MAIN_DATA_TAB_INDEX).findChild(QtWidgets.QTableWidget)

    # With only the default tabs, the main data table should map to MAIN_DATA_TAB_INDEX
    assert handler.get_tab_index_for_reduction_table(main_data_table) == handler.MAIN_DATA_TAB_INDEX

    # Add a second data tab and verify each table maps to the correct index
    main_window.addDataTable()
    second_tab_index = 2
    second_data_table = data_tab_widget.widget(second_tab_index).findChild(QtWidgets.QTableWidget)

    assert handler.get_tab_index_for_reduction_table(main_data_table) == handler.MAIN_DATA_TAB_INDEX
    assert handler.get_tab_index_for_reduction_table(second_data_table) == second_tab_index


class TestActiveDataChangedSyncsFileList:
    """Test that the active run is synced between the reduction/direct beam tables and the file list in the UI."""

    def test_select_run_from_reduction_table(self, main_window_with_mock_runs):
        """Test that switching the active run in the reduction table updates the file list selection."""
        main_window = main_window_with_mock_runs
        data_presenter = main_window.data_presenter

        # Switch active run to row 0 and verify the file list highlights run 40785
        main_window.set_active_reduction_data(True, 0)
        assert data_presenter._nexus_data == data_presenter.reduction_list[0]
        assert main_window.ui.file_list.currentItem() is not None
        assert main_window.ui.file_list.currentItem().text() == "REF_M_40785.nxs.h5"

        # Switch active run to row 1 and verify the file list highlights run 40782
        main_window.set_active_reduction_data(True, 1)
        assert data_presenter._nexus_data == data_presenter.reduction_list[1]
        assert main_window.ui.file_list.currentItem() is not None
        assert main_window.ui.file_list.currentItem().text() == "REF_M_40782.nxs.h5+REF_M_40785.nxs.h5"

    def test_select_run_from_direct_beam_table(self, main_window_with_mock_runs):
        """Test that switching the active run in the direct beam table updates the file list selection."""
        main_window = main_window_with_mock_runs
        data_presenter = main_window.data_presenter

        # Switch active to the direct beam run and verify the file list highlights run 40786
        main_window.set_active_direct_beam(True, 0)
        assert data_presenter._nexus_data == data_presenter.direct_beam_list[0]
        assert main_window.ui.file_list.currentItem() is not None
        assert main_window.ui.file_list.currentItem().text() == "REF_M_40786.nxs.h5"

        # Switch to the data run and verify the file list highlights run 40787
        main_window.set_active_direct_beam(True, 1)
        assert data_presenter._nexus_data == data_presenter.direct_beam_list[1]
        assert main_window.ui.file_list.currentItem() is not None
        assert main_window.ui.file_list.currentItem().text() == "REF_M_40787.nxs.h5"

    def test_select_run_from_file_list(self, main_window_with_mock_runs):
        """Test that selecting a file in the list updates the active run radio button"""
        main_window = main_window_with_mock_runs
        data_presenter = main_window.data_presenter
        handler = main_window.file_handler

        def _checked_row():
            """Return the row index of the checked radio button, or None if none is checked."""
            for i in range(handler.reduction_table.rowCount()):
                cell = handler.reduction_table.cellWidget(i, ReductionTableColumn.ACTIVE)
                if cell is not None and cell.radio_button.isChecked():
                    return i
            return None

        # Click on the first data run in the file list and verify that the correct row is checked
        item = main_window.ui.file_list.findItems("40785", QtCore.Qt.MatchContains)[0]
        main_window.ui.file_list.setCurrentItem(item)
        assert data_presenter._nexus_data == data_presenter.reduction_list[0]
        assert _checked_row() == 0

        # Click on the second data run in the file list and verify that the correct row is checked
        item = main_window.ui.file_list.findItems("REF_M_40782.nxs.h5+REF_M_40785.nxs.h5", QtCore.Qt.MatchContains)[0]
        main_window.ui.file_list.setCurrentItem(item)
        assert data_presenter._nexus_data == data_presenter.reduction_list[1]
        assert _checked_row() == 1

    def test_switching_between_data_and_direct_beam_tabs(self, main_window_with_mock_runs):
        """Test that switching between the direct beam and data tabs updates the file list selection."""
        main_window = main_window_with_mock_runs
        data_presenter = main_window.data_presenter
        data_tab_widget = main_window.ui.tabWidget

        # Switch to the direct beam tab and verify the file list highlights the active direct beam run (40786)
        data_tab_widget.setCurrentIndex(main_window.file_handler.DIRECT_BEAM_TAB_INDEX)
        assert data_presenter._nexus_data == data_presenter.direct_beam_list[0]
        assert main_window.ui.file_list.currentItem() is not None
        assert main_window.ui.file_list.currentItem().text() == "REF_M_40786.nxs.h5"

        # Switch to the main data tab and verify the file list highlights the active data run (40785)
        data_tab_widget.setCurrentIndex(main_window.file_handler.MAIN_DATA_TAB_INDEX)
        assert data_presenter._nexus_data == data_presenter.reduction_list[0]
        assert main_window.ui.file_list.currentItem() is not None
        assert main_window.ui.file_list.currentItem().text() == "REF_M_40785.nxs.h5"

    def test_switching_between_multiple_data_tabs(self, main_window_with_mock_runs):
        """Test that the file list syncs correctly when the active data comes from a secondary reduction tab.

        Switching the active reduction list to tab 2 and calling active_data_changed() directly
        verifies the file list sync without triggering the full tab-change event cycle.
        """
        main_window = main_window_with_mock_runs
        data_presenter = main_window.data_presenter
        data_tab_widget = main_window.ui.tabWidget

        # Add a second data tab; the runs from tab 1 are deep-copied into it
        main_window.addDataTable()
        assert len(data_presenter.peak_reduction_lists[2]) == 3

        # Make the second tab the active list and verify the first run is active
        data_tab_widget.setCurrentIndex(2)
        assert main_window.ui.file_list.currentItem() is not None
        assert main_window.ui.file_list.currentItem().text() == "REF_M_40785.nxs.h5"

        # Switch to the second run in tab 2 (40782) and verify the file list updates
        main_window.set_active_reduction_data(True, 1)
        assert main_window.ui.file_list.currentItem() is not None
        assert main_window.ui.file_list.currentItem().text() == "REF_M_40782.nxs.h5+REF_M_40785.nxs.h5"


if __name__ == "__main__":
    pytest.main([__file__])
