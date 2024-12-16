# package imports
import numpy as np
from qtpy import QtWidgets, QtCore

from reflectivity_ui.interfaces.configuration import Configuration
from reflectivity_ui.interfaces.data_handling.data_manipulation import NormalizeToUnityQCutoffError
from reflectivity_ui.interfaces.data_handling.data_set import NexusData, CrossSectionData
from reflectivity_ui.interfaces.main_window import MainWindow
from reflectivity_ui.interfaces.event_handlers.main_handler import MainHandler

# 3rd-party imports
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer
import pytest

# standard imports
import os
import sys

from test.ui import ui_utilities

this_module_path = sys.modules[__name__].__file__


class DataManagerMock(object):
    current_directory = os.path.dirname(this_module_path)


class MainWindowMock(object):
    ui = None
    main_window = None
    data_manager = DataManagerMock()


class TestMainHandler(object):

    app = QApplication(sys.argv)
    application = MainWindow()
    handler = MainHandler(application)

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
        """Test that stitch_reflectivity catches errors in stitching and calls report_message"""
        # Mock exception raised in stitch_data_sets
        mocker.patch("reflectivity_ui.interfaces.data_manager.DataManager.stitch_data_sets", side_effect=error_type)
        # Mock call to function report_message
        mock_report_message = mocker.patch(
            "reflectivity_ui.interfaces.event_handlers.main_handler.MainHandler.report_message"
        )
        self.handler.stitch_reflectivity()
        assert error_msg in mock_report_message.call_args[0][0]


def test_save_run_data(tmp_path, qtbot, mocker):
    """Test of method save_run_data"""
    mocker.patch(
        "reflectivity_ui.interfaces.event_handlers.main_handler.QtWidgets.QFileDialog.getExistingDirectory",
        return_value=tmp_path,
    )
    mocker.patch(
        "reflectivity_ui.interfaces.event_handlers.main_handler.QtWidgets.QInputDialog.getText",
        return_value=("test_save_run_data", True),
    )
    header = "col1 col2"
    mocker.patch(
        "reflectivity_ui.interfaces.data_handling.data_set.CrossSectionData.get_tof_counts_table",
        return_value=(np.ones((5, 5)), header),
    )
    mocker.patch(
        "reflectivity_ui.interfaces.event_handlers.main_handler.MainHandler.ask_question", side_effect=[False, True]
    )

    main_window = MainWindow()
    handler = MainHandler(main_window)
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
    """Test of helper function ask_question"""
    main_window = MainWindow()
    handler = MainHandler(main_window)
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
    """Test function reload_all_files"""
    main_window = MainWindow()
    handler = MainHandler(main_window)
    data_manager = main_window.data_manager
    qtbot.addWidget(main_window)
    selected_row = 0

    # Add one direct beam run and two data runs
    ui_utilities.setText(main_window.numberSearchEntry, str(40786), press_enter=True)
    ui_utilities.set_current_file_by_run_number(main_window, 40786)
    main_window.actionNorm.triggered.emit()
    ui_utilities.set_current_file_by_run_number(main_window, 40785)
    main_window.actionAddPlot.triggered.emit()
    ui_utilities.set_current_file_by_run_number(main_window, 40782)
    main_window.actionAddPlot.triggered.emit()

    # Select/plot the first data run
    main_window.reduction_cell_activated(selected_row, 0)

    # Test that reloading all files does not change the active run
    assert main_window.ui.reductionTable.rowCount() == 2
    assert len(data_manager.reduction_list) == 2
    assert data_manager._nexus_data == data_manager.reduction_list[selected_row]
    handler.reload_all_files()
    assert main_window.ui.reductionTable.rowCount() == 2
    assert len(main_window.data_manager.reduction_list) == 2
    assert data_manager._nexus_data == data_manager.reduction_list[selected_row]


@pytest.mark.datarepo
def test_reload_all_files_two_data_tabs(qtbot):
    """Test function reload_all_files"""
    main_window = MainWindow()
    handler = MainHandler(main_window)
    data_manager = main_window.data_manager
    qtbot.addWidget(main_window)
    selected_row = 0

    # Add one direct beam run and two data runs
    ui_utilities.setText(main_window.numberSearchEntry, str(40786), press_enter=True)
    ui_utilities.set_current_file_by_run_number(main_window, 40786)
    main_window.actionNorm.triggered.emit()
    ui_utilities.set_current_file_by_run_number(main_window, 40785)
    main_window.actionAddPlot.triggered.emit()
    ui_utilities.set_current_file_by_run_number(main_window, 40782)
    main_window.actionAddPlot.triggered.emit()

    # Add second peak data tab
    main_window.addDataTable()

    # Select/plot the first data run
    main_window.reduction_cell_activated(selected_row, 0)

    # Test that reloading all files does not change the active run and data tab
    assert main_window.ui.reductionTable.rowCount() == 2
    assert len(data_manager.reduction_list) == 2
    assert len(data_manager.peak_reduction_lists[2]) == 2
    assert data_manager.active_reduction_list_index == 1
    assert data_manager._nexus_data == data_manager.reduction_list[selected_row]
    handler.reload_all_files()
    assert main_window.ui.reductionTable.rowCount() == 2
    assert len(data_manager.reduction_list) == 2
    assert len(data_manager.peak_reduction_lists[2]) == 2
    assert data_manager.active_reduction_list_index == 1
    assert data_manager._nexus_data == data_manager.reduction_list[selected_row]


def _get_nexus_data():
    """Data for testing"""
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
    """Test property reduction_table which is computed based on the selected tab in the UI"""
    main_window = MainWindow()
    handler = MainHandler(main_window)
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


if __name__ == "__main__":
    pytest.main([__file__])
