"""UI integration tests for adding non-direct-beam runs to the direct beam table."""

# local imports
# 3rd-party imports
import pytest

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
    assert window_main.data_manager._nexus_data.is_direct_beam() == False

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
    assert window_main.data_manager._nexus_data.is_direct_beam() == True

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
    try:
        window_main.data_manager.calculate_reflectivity()
        success = True
    except Exception as e:
        success = False
        pytest.fail(f"Reflectivity calculation failed: {e}")

    assert success

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


if __name__ == "__main__":
    pytest.main([__file__])
