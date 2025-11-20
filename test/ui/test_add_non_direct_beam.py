"""UI tests for adding non-direct-beam runs to the direct beam table."""

# 3rd-party imports
import pytest

# local imports
from quicknxs.interfaces.configuration import Configuration
from quicknxs.interfaces.enums import DirectBeamTableColumn as DBTableCols
from quicknxs.interfaces.main_window import MainWindow


@pytest.mark.datarepo
def test_add_non_direct_beam_run_shows_warning(qtbot, data_server, mocker):
    """Test that adding a non-direct-beam run shows a warning message."""
    window_main = MainWindow()
    qtbot.addWidget(window_main)
    Configuration.setup_default_values()

    # Mock the report_message to capture the warning
    mock_report = mocker.patch.object(window_main.file_handler, "report_message")

    # Load a scattering run (not a direct beam) - REF_M_42112
    window_main.file_handler.open_file(data_server.path_to("REF_M_42112"))

    # Verify it's not a direct beam
    assert not window_main.data_manager._nexus_data.is_direct_beam()

    # Add it to the direct beam table
    window_main.actionAddDirectBeam.triggered.emit()

    # Check that the run was added to the table
    table = window_main.ui.directBeamTable
    assert table.rowCount() == 1
    assert table.item(0, DBTableCols.RUN_NUMBER).text() == "42112"

    # Verify that a warning message was shown (non-blocking, so pop_up=False)
    # report_message is called multiple times (for file loading too), so check for the warning call
    warning_calls = [call for call in mock_report.call_args_list if "not labeled as a direct beam" in str(call)]
    assert len(warning_calls) == 1
    # Check the warning message content
    warning_call = warning_calls[0]
    assert "42112" in warning_call[0][0]  # Run number in message
    assert "data_type PV" in warning_call[0][0]
    assert warning_call.kwargs.get("pop_up") == False  # Should be non-blocking


@pytest.mark.datarepo
def test_add_true_direct_beam_run_no_warning(qtbot, data_server, mocker):
    """Test that adding a true direct beam run does not show a warning."""
    window_main = MainWindow()
    qtbot.addWidget(window_main)
    Configuration.setup_default_values()

    # Mock the report_message to capture any messages
    mock_report = mocker.patch.object(window_main.file_handler, "report_message")

    # Load a true direct beam run - REF_M_42099
    window_main.file_handler.open_file(data_server.path_to("REF_M_42099"))

    # Verify it IS a direct beam
    assert window_main.data_manager._nexus_data.is_direct_beam()

    # Add it to the direct beam table
    window_main.actionAddDirectBeam.triggered.emit()

    # Check that the run was added to the table
    table = window_main.ui.directBeamTable
    assert table.rowCount() == 1
    assert table.item(0, DBTableCols.RUN_NUMBER).text() == "42099"

    # Verify that NO warning about non-direct-beam was shown
    # report_message is called for file loading, but not for the direct beam warning
    warning_calls = [call for call in mock_report.call_args_list if "not labeled as a direct beam" in str(call)]
    assert len(warning_calls) == 0  # No warning for true direct beam


@pytest.mark.datarepo
def test_non_direct_beam_can_normalize_scattering_data(qtbot, data_server):
    """Test that a non-direct-beam run can be used to normalize scattering data."""
    window_main = MainWindow()
    qtbot.addWidget(window_main)
    Configuration.setup_default_values()

    # Load a scattering run (REF_M_42112) and add it as "direct beam"
    window_main.file_handler.open_file(data_server.path_to("REF_M_42112"))
    window_main.actionAddDirectBeam.triggered.emit()

    # Load another scattering run (REF_M_42113) and add it to reduction
    window_main.file_handler.open_file(data_server.path_to("REF_M_42113"))
    window_main.actionAddRefl.triggered.emit()

    # Set the "direct beam" for this run
    window_main.data_manager._nexus_data.set_parameter("direct_beam", "42112")

    # Calculate reflectivity - this should work without errors
    window_main.data_manager.calculate_reflectivity()

    # Verify the reduction list has the correct direct beam set
    run_in_reduction = window_main.data_manager.reduction_list[0]
    assert (
        run_in_reduction.cross_sections[list(run_in_reduction.cross_sections.keys())[0]].configuration.direct_beam
        == "42112"
    )


@pytest.mark.datarepo
def test_add_duplicate_non_direct_beam_shows_error(qtbot, data_server, mocker):
    """Test that adding the same non-direct-beam run twice shows an error."""
    window_main = MainWindow()
    qtbot.addWidget(window_main)
    Configuration.setup_default_values()

    # Mock the report_message
    mock_report = mocker.patch.object(window_main.file_handler, "report_message")

    # Load a scattering run
    window_main.file_handler.open_file(data_server.path_to("REF_M_42112"))

    # Add it to the direct beam table (first time)
    window_main.actionAddDirectBeam.triggered.emit()
    assert window_main.ui.directBeamTable.rowCount() == 1

    # Reset the mock to clear the first warning
    mock_report.reset_mock()

    # Try to add the same run again
    window_main.actionAddDirectBeam.triggered.emit()

    # Verify that an error message was shown
    mock_report.assert_called_once()
    call_args = mock_report.call_args
    assert "already in the list" in call_args[0][0]
    assert call_args[1].get("pop_up") is True  # This should be a blocking error

    # Verify there's still only one entry
    assert window_main.ui.directBeamTable.rowCount() == 1


@pytest.mark.datarepo
def test_non_direct_beam_displays_intensity_plot(qtbot, data_server):
    """Test that a non-direct-beam run in the direct beam table displays an Intensity plot."""
    window_main = MainWindow()
    qtbot.addWidget(window_main)
    Configuration.setup_default_values()

    # Load a scattering run (not a direct beam) - REF_M_42113
    window_main.file_handler.open_file(data_server.path_to("REF_M_42113"))

    # Verify it's not a direct beam
    assert not window_main.data_manager._nexus_data.is_direct_beam()

    # Add it to the direct beam table
    window_main.actionAddDirectBeam.triggered.emit()

    # Click the radio button to make it active (simulate selecting it in the direct beam table)
    window_main.set_active_direct_beam(True, 0)

    # Check the plot title
    plot_title = window_main.ui.reflectivity_or_intensity_plot_title.text()
    assert plot_title == "Intensity", f"Expected 'Intensity' plot but got '{plot_title}'"

    # Also verify that the active data is indeed in the direct beam list
    assert window_main.data_manager.find_active_direct_beam_id() is not None


@pytest.mark.datarepo
def test_true_direct_beam_displays_intensity_plot(qtbot, data_server):
    """Test that a true direct beam run displays an Intensity plot (baseline behavior)."""
    window_main = MainWindow()
    qtbot.addWidget(window_main)
    Configuration.setup_default_values()

    # Load a true direct beam run - REF_M_42099
    window_main.file_handler.open_file(data_server.path_to("REF_M_42099"))

    # Verify it IS a direct beam
    assert window_main.data_manager._nexus_data.is_direct_beam()

    # Add it to the direct beam table
    window_main.actionAddDirectBeam.triggered.emit()

    # Click the radio button to make it active
    window_main.set_active_direct_beam(True, 0)

    # Check the plot title
    plot_title = window_main.ui.reflectivity_or_intensity_plot_title.text()
    assert plot_title == "Intensity", f"Expected 'Intensity' plot but got '{plot_title}'"


@pytest.mark.datarepo
def test_run_in_both_tables_shows_correct_plot_by_context(qtbot, data_server):
    """Test that a run in both tables shows different plots depending on which table it's selected from."""
    window_main = MainWindow()
    qtbot.addWidget(window_main)
    Configuration.setup_default_values()

    # Load a scattering run - REF_M_42113
    window_main.file_handler.open_file(data_server.path_to("REF_M_42113"))

    # Add it to the direct beam table
    window_main.actionAddDirectBeam.triggered.emit()

    # Also add it to the reduction/data table
    window_main.actionAddRefl.triggered.emit()

    # Select from direct beam table - should show "Intensity"
    window_main.set_active_direct_beam(True, 0)
    plot_title = window_main.ui.reflectivity_or_intensity_plot_title.text()
    assert plot_title == "Intensity", (
        f"When selected from Direct Beam table, expected 'Intensity' but got '{plot_title}'"
    )

    # Select from reduction/data table - should show "Reflectivity"
    window_main.set_active_reduction_data(True, 0)
    plot_title = window_main.ui.reflectivity_or_intensity_plot_title.text()
    assert plot_title == "Reflectivity", (
        f"When selected from Data table, expected 'Reflectivity' but got '{plot_title}'"
    )


@pytest.mark.datarepo
def test_only_one_radio_button_selected_in_reduction_table(qtbot, data_server):
    """Test that only one radio button can be selected at a time in the reduction table."""
    window_main = MainWindow()
    qtbot.addWidget(window_main)
    Configuration.setup_default_values()

    # Load and add first run to reduction table
    window_main.file_handler.open_file(data_server.path_to("REF_M_42112"))
    window_main.actionAddRefl.triggered.emit()

    # Load and add second run to reduction table
    window_main.file_handler.open_file(data_server.path_to("REF_M_42113"))
    window_main.actionAddRefl.triggered.emit()

    # Get the reduction table
    table = window_main.ui.reductionTable

    # Count how many radio buttons are checked
    checked_count = 0
    for row in range(table.rowCount()):
        widget = table.cellWidget(row, 0)  # Active column is column 0
        if widget and hasattr(widget, "radio_button"):
            if widget.radio_button.isChecked():
                checked_count += 1

    assert checked_count == 1, f"Expected exactly 1 radio button to be checked, but found {checked_count}"


@pytest.mark.datarepo
def test_radio_button_exclusivity_with_dual_table_runs(qtbot, data_server):
    """Test Marie's scenario: run in both tables, switching between them."""
    window_main = MainWindow()
    qtbot.addWidget(window_main)
    Configuration.setup_default_values()

    # Load 42112 and add to both Direct Beam and Data tables
    window_main.file_handler.open_file(data_server.path_to("REF_M_42112"))
    window_main.actionAddDirectBeam.triggered.emit()
    window_main.actionAddRefl.triggered.emit()

    # Load 42113 and add to Data table
    window_main.file_handler.open_file(data_server.path_to("REF_M_42113"))
    window_main.actionAddRefl.triggered.emit()

    # Now switch between selecting from direct beam and reduction tables
    # Select 42112 from direct beam table
    window_main.set_active_direct_beam(True, 0)

    # Select 42113 from reduction table (row 1)
    window_main.set_active_reduction_data(True, 1)

    # Select 42112 from reduction table (row 0)
    window_main.set_active_reduction_data(True, 0)

    # Check that only ONE radio button is checked in the reduction table
    table = window_main.ui.reductionTable
    checked_count = 0
    checked_rows = []
    for row in range(table.rowCount()):
        widget = table.cellWidget(row, 0)
        if widget and hasattr(widget, "radio_button"):
            if widget.radio_button.isChecked():
                checked_count += 1
                checked_rows.append(row)

    assert checked_count == 1, (
        f"Expected exactly 1 radio button in reduction table, but found {checked_count} checked at rows {checked_rows}"
    )


if __name__ == "__main__":
    pytest.main([__file__])
