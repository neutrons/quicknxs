import pytest
from qtpy import QtWidgets

from quicknxs.interfaces.configuration import Configuration
from quicknxs.interfaces.main_window import MainWindow


@pytest.mark.datarepo
def test_table_data(qtbot, data_server):
    """Test that the direct beam table is populated with the correct data."""
    window_main = MainWindow()
    qtbot.addWidget(window_main)
    Configuration.setup_default_values()

    # add direct beam run
    window_main.file_handler.open_file(data_server.path_to("REF_M_42099"))
    window_main.actionAddDirectBeam.triggered.emit()

    # check that the direct beam table is populated with the correct data
    table = window_main.ui.directBeamTable
    assert table.rowCount() == 1
    assert table.item(0, 0).text() == "42099"
    assert table.item(0, 1).text() == "235.5"
    assert table.item(0, 2).text() == "21.0"


@pytest.mark.datarepo
def test_table_connections(qtbot, data_server):
    """Test that the direct beam table is connected to other UI elements.

    The table content should change when elements elsewhere are changed,
    and vice-versa (such as peak_position and peak_width).

    TODO: This test should also check that the table and overview plot limits are connected, if possible.
    """
    main_window = MainWindow()
    qtbot.addWidget(main_window)
    Configuration.setup_default_values()

    # Load direct beam run and add to the table
    main_window.file_handler.open_file(data_server.path_to("REF_M_42099"))
    main_window.actionAddDirectBeam.triggered.emit()

    # Get the direct beam table
    table: QtWidgets.QTableWidget = main_window.ui.directBeamTable
    assert table is not None
    assert table.rowCount() == 1

    assert main_window.ui.refXPos.value() == float(table.item(0, 1).text())
    assert main_window.ui.refXWidth.value() == float(table.item(0, 2).text())

    # Change the reference position and width in the table
    table.item(0, 1).setText("100")
    table.item(0, 2).setText("50")
    assert main_window.ui.refXPos.value() == float(table.item(0, 1).text())
    assert main_window.ui.refXWidth.value() == float(table.item(0, 2).text())

    # Change the reference position and width in the main window
    main_window.ui.refXPos.setValue(200)
    main_window.ui.refXWidth.setValue(100)
    main_window.file_handler.update_info()
    assert main_window.ui.refXPos.value() == float(table.item(0, 1).text())
    assert main_window.ui.refXWidth.value() == float(table.item(0, 2).text())


@pytest.mark.datarepo
def test_table_peak_position_change_triggers_plot_update(mocker, main_window_with_data_factory):
    """Test that changing the peak position in the direct beam table triggers a plot update."""
    # Mock plotting
    mock_plot_refl = mocker.patch(
        "quicknxs.interfaces.plotting.PlotManager.plot_reflectivity_or_intensity", return_value=True
    )

    main_window = main_window_with_data_factory()
    table: QtWidgets.QTableWidget = main_window.ui.directBeamTable

    reduction_list = main_window.data_manager.reduction_list
    mock_refl_run_with_db_42099 = mocker.patch.object(reduction_list[0], "calculate_reflectivity")
    mock_refl_run_with_db_42100 = mocker.patch.object(reduction_list[1], "calculate_reflectivity")

    # Get call count before
    plot_refl_call_count = mock_plot_refl.call_count

    # Update peak position in the direct beam table
    assert table.item(0, 0).text() == "42100"
    table.item(0, 1).setText("102.0")

    # Verify that the reflected run was updated and that the plot function was called
    mock_refl_run_with_db_42099.assert_not_called()
    mock_refl_run_with_db_42100.assert_called_once()
    assert mock_plot_refl.call_count == plot_refl_call_count + 1


if __name__ == "__main__":
    pytest.main([__file__])
