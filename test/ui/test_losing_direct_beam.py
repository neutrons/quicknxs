# local imports
# third party imports
import pytest

from quicknxs.interfaces.main_window import MainWindow
from test.ui import ui_utilities

# standard library imports


def test_losing_direct_beam(qtbot):
    r"""Test that reduction list runs do not lose their direct beam when the user clicks another run in the file list"""
    main_window = MainWindow()
    qtbot.addWidget(main_window)

    def _get_reduction_list_run_direct_beam(reduction_list_index, xs):
        r"""Get the direct beam for the given reduction list run and cross-section
        Returns
        -------
        int
            the run number of the direct beam
        """
        return (
            main_window.data_manager.reduction_list[reduction_list_index].cross_sections[xs].configuration.normalization
        )

    direct_beam_run = 40786

    # load file list
    ui_utilities.setText(main_window.numberSearchEntry, str(direct_beam_run), press_enter=True)

    # select run in the file list
    ui_utilities.set_current_file_by_run_number(main_window, direct_beam_run)
    # add run to direct beams
    main_window.actionNorm.triggered.emit()

    # select run in the file list
    ui_utilities.set_current_file_by_run_number(main_window, 40785)
    # add run to the reduction list
    main_window.actionAddPlot.triggered.emit()

    assert _get_reduction_list_run_direct_beam(0, "On_Off") == direct_beam_run
    assert _get_reduction_list_run_direct_beam(0, "Off_Off") == direct_beam_run

    # select different run in the file list
    ui_utilities.set_current_file_by_run_number(main_window, 40782)

    assert _get_reduction_list_run_direct_beam(0, "On_Off") == direct_beam_run
    assert _get_reduction_list_run_direct_beam(0, "Off_Off") == direct_beam_run


if __name__ == "__main__":
    pytest.main([__file__])
