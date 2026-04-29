import pytest

from quicknxs.views.main_window import MainWindow
from tests.ui import ui_utilities


def _populate_reduction_and_direct_beam_tables(main_window):
    # load file list
    ui_utilities.setText(main_window.numberSearchEntry, str(42100), press_enter=True)

    # select run in the file list
    ui_utilities.set_current_file_by_run_number(main_window, 42100)
    # add run to direct beams
    main_window.actionAddDirectBeam.triggered.emit()

    ui_utilities.set_current_file_by_run_number(main_window, 42112)
    main_window.actionAddRefl.triggered.emit()

    ui_utilities.set_current_file_by_run_number(main_window, 42113)
    main_window.actionAddRefl.triggered.emit()


@pytest.mark.datarepo
def test_plot_reflectivity_or_intensity(qtbot):
    """Test that the plot title is updated depending on the type of the active run."""
    main_window = MainWindow()
    qtbot.addWidget(main_window)
    _populate_reduction_and_direct_beam_tables(main_window)

    # select a sample run
    main_window.set_active_reduction_data(True, 0)
    assert main_window.ui.reflectivity_or_intensity_plot_title.text() == "Reflectivity"

    # select a direct beam run
    main_window.set_active_direct_beam(True, 0)
    assert main_window.ui.reflectivity_or_intensity_plot_title.text() == "Intensity"
