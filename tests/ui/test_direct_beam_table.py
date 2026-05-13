import pytest
from qtpy import QtWidgets

from quicknxs.enums import DirectBeamTableColumn as DBTableCols
from quicknxs.enums import ReductionTableColumn
from quicknxs.models.configuration import Configuration
from quicknxs.views.main_window import MainWindow


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
    assert table.item(0, DBTableCols.RUN_NUMBER).text() == "42099"
    assert table.item(0, DBTableCols.PEAK_POSITION).text() == "235.5"
    assert table.item(0, DBTableCols.PEAK_WIDTH).text() == "21.0"


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

    assert main_window.ui.refXPos.value() == float(table.item(0, DBTableCols.PEAK_POSITION).text())
    assert main_window.ui.refXWidth.value() == float(table.item(0, DBTableCols.PEAK_WIDTH).text())

    # Change the reference position and width in the table
    table.item(0, DBTableCols.PEAK_POSITION).setText("100")
    table.item(0, DBTableCols.PEAK_WIDTH).setText("50")
    assert main_window.ui.refXPos.value() == float(table.item(0, DBTableCols.PEAK_POSITION).text())
    assert main_window.ui.refXWidth.value() == float(table.item(0, DBTableCols.PEAK_WIDTH).text())

    # Change the reference position and width in the main window
    main_window.ui.refXPos.setValue(200)
    main_window.ui.refXWidth.setValue(100)
    main_window.file_handler.update_overview_run_info_from_active_run()
    assert main_window.ui.refXPos.value() == float(table.item(0, DBTableCols.PEAK_POSITION).text())
    assert main_window.ui.refXWidth.value() == float(table.item(0, DBTableCols.PEAK_WIDTH).text())


@pytest.mark.datarepo
def test_table_peak_position_change_triggers_plot_update(mocker, main_window_with_data_factory):
    """Test that changing the peak position in the direct beam table triggers a plot update."""
    # Mock plotting
    mock_plot_refl = mocker.patch("quicknxs.views.plotting.PlotView.plot_reflectivity_or_intensity", return_value=True)

    main_window = main_window_with_data_factory()
    table: QtWidgets.QTableWidget = main_window.ui.directBeamTable

    reduction_list = main_window.data_presenter.reduction_list
    mock_refl_run_with_db_42099 = mocker.patch.object(reduction_list[0], "calculate_reflectivity")
    mock_refl_run_with_db_42100 = mocker.patch.object(reduction_list[1], "calculate_reflectivity")

    # Get call count before
    plot_refl_call_count = mock_plot_refl.call_count

    # Update peak position in the direct beam table
    assert table.item(0, DBTableCols.RUN_NUMBER).text() == "42100"
    table.item(0, DBTableCols.PEAK_POSITION).setText("102.0")

    # Verify that the reflected run was updated and that the plot function was called
    mock_refl_run_with_db_42099.assert_not_called()
    mock_refl_run_with_db_42100.assert_called_once()
    assert mock_plot_refl.call_count == plot_refl_call_count + 1


@pytest.mark.datarepo
def test_peak_position_updates_direct_pixel(qtbot, data_server):
    """Test that updating the peak position in the direct beam table updates the direct pixel value."""
    main_window = MainWindow()
    qtbot.addWidget(main_window)
    Configuration.setup_default_values()

    # Load direct beam run and add to the table
    main_window.file_handler.open_file(data_server.path_to("REF_M_42099"))
    main_window.actionAddDirectBeam.triggered.emit()

    # Load reflected runs and add to the reduction list
    main_window.file_handler.open_file(data_server.path_to("REF_M_42112"))
    main_window.actionAddRefl.triggered.emit()
    main_window.file_handler.open_file(data_server.path_to("REF_M_42113"))
    main_window.actionAddRefl.triggered.emit()

    # assert that main_window.data_presenter.load() was called and data is loaded
    assert len(main_window.data_presenter.direct_beam_list) == 1
    assert len(main_window.data_presenter.reduction_list) == 2

    # Assert reflected runs are using the direct beam
    refl_run0 = main_window.data_presenter.reduction_list[0]
    assert str(refl_run0.get_parameter("direct_beam")) == str(main_window.data_presenter.direct_beam_list[0].run_number)
    refl_run1 = main_window.data_presenter.reduction_list[1]
    assert str(refl_run1.get_parameter("direct_beam")) == str(main_window.data_presenter.direct_beam_list[0].run_number)

    # Verify that the column DPix is initially populated with the value from the DAS
    table_reduction: QtWidgets.QTableWidget = main_window.ui.reductionTable
    dpix_item0 = table_reduction.item(0, ReductionTableColumn.DPIX)
    assert float(dpix_item0.text()) == refl_run0.get_main_cross_section_data().direct_pixel
    dpix_item1 = table_reduction.item(1, ReductionTableColumn.DPIX)
    assert float(dpix_item1.text()) == refl_run1.get_main_cross_section_data().direct_pixel

    # Enable set_direct_pixel for one of the reflected runs
    refl_run0.set_parameter("set_direct_pixel", True)

    # Update peak position in the direct beam table
    table: QtWidgets.QTableWidget = main_window.ui.directBeamTable
    table.item(0, DBTableCols.PEAK_POSITION).setText("300.0")

    # Verify that the direct pixel in the direct beam object is updated
    direct_beam = main_window.data_presenter.direct_beam_list[0]
    direct_beam_peak_position = direct_beam.get_parameter("peak_position")
    assert direct_beam_peak_position == 300.0

    # Verify that the direct pixel in the reflected run is updated
    assert refl_run0.get_parameter("direct_pixel_overwrite") == direct_beam_peak_position
    assert refl_run1.get_parameter("direct_pixel_overwrite") == direct_beam_peak_position

    # Verify that the column DPix is only updated for the reflected run with set_direct_pixel enabled
    table_reduction: QtWidgets.QTableWidget = main_window.ui.reductionTable
    dpix_item0 = table_reduction.item(0, ReductionTableColumn.DPIX)
    assert float(dpix_item0.text()) == direct_beam_peak_position
    dpix_item1 = table_reduction.item(1, ReductionTableColumn.DPIX)
    assert float(dpix_item1.text()) == refl_run1.get_main_cross_section_data().direct_pixel  # should be unchanged


if __name__ == "__main__":
    pytest.main([__file__])
