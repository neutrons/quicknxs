"""UI tests for adding non-direct-beam runs to the direct beam table."""

import pytest
from qtpy import QtWidgets
from qtpy.QtWidgets import QApplication

from quicknxs.enums import DirectBeamTableColumn as DBTableCols
from quicknxs.models.configuration import Configuration, OutputOptions
from quicknxs.models.processing_workflow import ProcessingWorkflow
from quicknxs.presenters.progress_reporter import ProgressReporter
from quicknxs.views.main_window import MainWindow


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
    assert not window_main.data_presenter._nexus_data.is_direct_beam()

    # Add it to the direct beam table
    window_main.actionAddDirectBeam.triggered.emit()

    # Check that the run was added to the table
    table = window_main.ui.directBeamTable
    assert table.rowCount() == 1
    assert table.item(0, DBTableCols.RUN_NUMBER).text() == "42112"

    # Verify that a warning message was shown (non-blocking, so pop_up=False)
    # report_message is called multiple times (for file loading too), so check for the warning call
    warning_calls = [call for call in mock_report.call_args_list if "labeled as a reflected beam" in str(call)]
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
    assert window_main.data_presenter._nexus_data.is_direct_beam()

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
    window_main.data_presenter._nexus_data.set_parameter("direct_beam", "42112")

    # Calculate reflectivity - this should work without errors
    window_main.data_presenter.calculate_reflectivity()

    # Verify the reduction list has the correct direct beam set
    run_in_reduction = window_main.data_presenter.reduction_list[0]
    assert (
        int(run_in_reduction.cross_sections[list(run_in_reduction.cross_sections.keys())[0]].configuration.direct_beam)
        == 42112
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
    assert not window_main.data_presenter._nexus_data.is_direct_beam()

    # Add it to the direct beam table
    window_main.actionAddDirectBeam.triggered.emit()

    # Click the radio button to make it active (simulate selecting it in the direct beam table)
    window_main.set_active_direct_beam(True, 0)

    # Check the plot title
    plot_title = window_main.ui.reflectivity_or_intensity_plot_title.text()
    assert plot_title == "Intensity", f"Expected 'Intensity' plot but got '{plot_title}'"

    # Also verify that the active data is indeed in the direct beam list
    assert window_main.data_presenter.find_active_direct_beam_id() is not None


@pytest.mark.datarepo
def test_true_direct_beam_displays_intensity_plot(qtbot, data_server):
    """Test that a true direct beam run displays an Intensity plot (baseline behavior)."""
    window_main = MainWindow()
    qtbot.addWidget(window_main)
    Configuration.setup_default_values()

    # Load a true direct beam run - REF_M_42099
    window_main.file_handler.open_file(data_server.path_to("REF_M_42099"))

    # Verify it IS a direct beam
    assert window_main.data_presenter._nexus_data.is_direct_beam()

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


@pytest.mark.datarepo
def test_non_direct_beam_saved_and_loaded(qtbot, data_server, tmp_path):
    """Test that non-direct beam runs are properly saved to and loaded from reduced files."""
    window_main = MainWindow()
    qtbot.addWidget(window_main)
    Configuration.setup_default_values()

    # Load run 42112 and add it as direct beam (not a true direct beam)
    window_main.file_handler.open_file(data_server.path_to("REF_M_42112"))
    window_main.actionAddDirectBeam.triggered.emit()

    # Load run 42113 and add it to the reduction table
    window_main.file_handler.open_file(data_server.path_to("REF_M_42113"))
    window_main.actionAddRefl.triggered.emit()

    output_dir = str(tmp_path)
    output_options = OutputOptions(
        output_directory=output_dir,
        format_5cols=True,
        format_numpy=False,
    )
    workflow = ProcessingWorkflow(window_main.data_presenter, output_options)
    workflow.execute()

    # Find the saved .dat file
    import glob

    dat_files = glob.glob(f"{output_dir}/*_Off_Off.dat")
    assert len(dat_files) > 0, "No reduced data file was created"

    saved_file = dat_files[0]

    # Read the file and check for the direct beam entry
    with open(saved_file, "r") as f:
        content = f.read()

    # Check that the direct beam section exists and contains our run
    assert "[Direct Beam Runs]" in content, "Direct Beam Runs section not found in saved file"

    # Debug: print the [Direct Beam Runs] section
    lines = content.split("\n")
    in_direct_beam_section = False
    db_section_lines = []
    for line in lines:
        if "[Direct Beam Runs]" in line:
            in_direct_beam_section = True
            db_section_lines.append(line)
        elif line.startswith("[") and in_direct_beam_section:
            # We've moved to a different section
            break
        elif in_direct_beam_section:
            db_section_lines.append(line)

    # The direct beam section should not be empty (should have at least header + data)
    assert len(db_section_lines) > 2, "Direct Beam Runs section is empty or only has headers. Content:\n" + "\n".join(
        db_section_lines[:10]
    )

    # Verify run 42112 is in the direct beam section
    # Note: The header sections are all commented with # by design
    found_42112 = any("42112" in line for line in db_section_lines)
    assert found_42112, "Run 42112 not found in [Direct Beam Runs] section. Section content:\n" + "\n".join(
        db_section_lines[:20]
    )

    # Now test LOADING the file back to verify it can be restored
    new_window = MainWindow()
    qtbot.addWidget(new_window)
    Configuration.setup_default_values()

    # Load the reduced file - this should restore both the direct beam and data runs
    new_window.data_presenter.load_data_from_reduced_file(saved_file, Configuration(), ProgressReporter())

    # Verify the direct beam list was loaded and contains run 42112
    assert len(new_window.data_presenter.direct_beam_list) > 0, "Direct beam list is empty after loading"
    db_numbers = [str(db.run_number) for db in new_window.data_presenter.direct_beam_list]
    assert "42112" in db_numbers, f"Run 42112 not in direct beam list after loading. Found: {db_numbers}"

    # Verify the reduction list was loaded and contains run 42113
    assert len(new_window.data_presenter.reduction_list) > 0, "Reduction list is empty after loading"
    refl_numbers = [str(r.run_number) for r in new_window.data_presenter.reduction_list]
    assert "42113" in refl_numbers, f"Run 42113 not in reduction list after loading. Found: {refl_numbers}"


@pytest.mark.datarepo
def test_marie_workflow_tab_switching_radio_buttons(qtbot, data_server):
    """Test Marie's exact workflow: switch between tabs and verify only one radio button is checked.

    This reproduces Marie's bug report: clicking between Direct Beam and Data tabs and changing
    which run is "Active" should not result in two radio buttons being checked.
    """
    window_main = MainWindow()
    qtbot.addWidget(window_main)
    Configuration.setup_default_values()

    # Load run 42112 and add to both tables
    window_main.file_handler.open_file(data_server.path_to("REF_M_42112"))
    window_main.actionAddDirectBeam.triggered.emit()
    window_main.actionAddRefl.triggered.emit()

    # Load run 42113 and add to both tables
    window_main.file_handler.open_file(data_server.path_to("REF_M_42113"))
    window_main.actionAddDirectBeam.triggered.emit()
    window_main.actionAddRefl.triggered.emit()

    # Simulate Marie's workflow: click between tabs and change active run
    for _ in range(5):  # Do this multiple times to exercise the bug
        # Select from Direct Beam table
        window_main.set_active_direct_beam(True, 0)
        # Process all pending Qt events to ensure signals are handled
        QApplication.processEvents()

        # Verify the correct button is checked in the Direct Beam table
        db_checked_indices = [
            i
            for i in range(window_main.ui.directBeamTable.rowCount())
            if window_main.ui.directBeamTable.cellWidget(i, 0)
            and window_main.ui.directBeamTable.cellWidget(i, 0).findChild(QtWidgets.QRadioButton).isChecked()
        ]
        assert 0 in db_checked_indices, (
            f"Expected direct beam row 0 to be checked, but checked rows are: {db_checked_indices}"
        )
        assert len(db_checked_indices) == 1, (
            f"Expected only 1 checked button in direct beam table, but found {len(db_checked_indices)}: {db_checked_indices}"
        )

        # Now select from Data table
        window_main.set_active_reduction_data(True, 1)
        # Process all pending Qt events to ensure signals are handled
        QApplication.processEvents()

        # Verify the correct button is checked in the Data table
        data_checked_indices = [
            i
            for i in range(window_main.file_handler.reduction_table.rowCount())
            if window_main.file_handler.reduction_table.cellWidget(i, 0)
            and window_main.file_handler.reduction_table.cellWidget(i, 0).findChild(QtWidgets.QRadioButton).isChecked()
        ]
        assert 1 in data_checked_indices, (
            f"Expected data row 1 to be checked, but checked rows are: {data_checked_indices}"
        )
        assert len(data_checked_indices) == 1, (
            f"Expected only 1 checked button in data table, but found {len(data_checked_indices)}: {data_checked_indices}"
        )


@pytest.mark.datarepo
def test_radio_button_indices_after_q_reordering(qtbot, data_server):
    """Test that radio button row indices are correct after runs are reordered by Q value."""
    window_main = MainWindow()
    qtbot.addWidget(window_main)
    Configuration.setup_default_values()

    # Step 1: Load run 42113 and add to Data tab
    window_main.file_handler.open_file(data_server.path_to("REF_M_42113"))
    window_main.actionAddRefl.triggered.emit()
    QApplication.processEvents()

    # Verify 42113 is in the table at row 0
    table = window_main.ui.reductionTable
    assert table.rowCount() == 1
    assert table.item(0, 1).text() == "42113"

    # Step 2: Load run 42112 and add to Data tab (will be inserted at row 0)
    window_main.file_handler.open_file(data_server.path_to("REF_M_42112"))
    window_main.actionAddRefl.triggered.emit()
    QApplication.processEvents()

    # Verify both runs are in the table, ordered by Q
    assert table.rowCount() == 2
    # Run 42112 should be at row 0 (lower Q), run 42113 at row 1 (higher Q)
    assert table.item(0, 1).text() == "42112"
    assert table.item(1, 1).text() == "42113"

    # Step 3: Click the Active radio button for run 42113
    radio_widget_row1 = table.cellWidget(1, 0)
    assert radio_widget_row1 is not None
    radio_button_row1 = radio_widget_row1.findChild(QtWidgets.QRadioButton)
    assert radio_button_row1 is not None

    # Simulate clicking the radio button
    radio_button_row1.setChecked(True)
    QApplication.processEvents()

    # Step 4: Verify that run 42113 is now the active run (not 42112)
    active_run_number = window_main.data_presenter._nexus_data.run_number
    assert active_run_number == "42113", (
        f"Expected active run to be 42113, but it is {active_run_number}. "
        "This indicates the radio button is using an outdated row index."
    )

    # Update references to radio buttons after reordering
    radio_widget_row0 = table.cellWidget(0, 0)
    radio_button_row0 = radio_widget_row0.findChild(QtWidgets.QRadioButton)
    radio_widget_row1 = table.cellWidget(1, 0)
    radio_button_row1 = radio_widget_row1.findChild(QtWidgets.QRadioButton)
    # Verify only row 1 is checked
    assert not radio_button_row0.isChecked(), "Row 0 (42112) should not be checked"
    assert radio_button_row1.isChecked(), "Row 1 (42113) should be checked"


if __name__ == "__main__":
    pytest.main([__file__])
