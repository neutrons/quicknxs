"""Test that direct beam filenames are saved correctly in .dat files."""

import os
import tempfile

import pytest

from quicknxs.interfaces.configuration import Configuration
from quicknxs.interfaces.data_handling import quicknxs_io
from quicknxs.interfaces.main_window import MainWindow


@pytest.mark.datarepo
def test_direct_beam_filename_saved_correctly(qtbot, data_server):
    """Test that when saving reduced data, the direct beam filename matches the actual direct beam used.

    This test verifies the fix for the issue where:
    - User adds run 42099 as direct beam
    - User matches run 42113 to use 42099 as direct beam
    - When saving, the .dat file incorrectly showed filename REF_M_42116.nxs.h5

    The problem was that we were reading the filename from Mantid's workspace property
    'normalization_file_path' which can be incorrect. The fix is to get the filename
    from the direct_beam object itself (direct_beam.file_path).
    """
    window_main = MainWindow()
    qtbot.addWidget(window_main)
    Configuration.setup_default_values()

    # Step 1: Load 42112 and add to both reduction and direct beam lists
    window_main.file_handler.open_file(data_server.path_to("REF_M_42112"))
    window_main.actionAddRefl.triggered.emit()
    window_main.actionAddDirectBeam.triggered.emit()

    # Step 2: Load 42099 and add only to direct beam list
    window_main.file_handler.open_file(data_server.path_to("REF_M_42099"))
    window_main.actionAddDirectBeam.triggered.emit()

    # Verify we have 2 direct beams
    assert len(window_main.data_manager.direct_beam_list) == 2
    assert window_main.data_manager.direct_beam_list[0].number == "42112"
    assert window_main.data_manager.direct_beam_list[1].number == "42099"

    # Step 3: Load 42113 and add to reduction list
    window_main.file_handler.open_file(data_server.path_to("REF_M_42113"))
    window_main.actionAddRefl.triggered.emit()

    # Verify we have 2 data runs
    assert len(window_main.data_manager.reduction_list) == 2
    assert window_main.data_manager.reduction_list[0].number == "42112"
    assert window_main.data_manager.reduction_list[1].number == "42113"

    # Step 4: Match 42112 to itself
    window_main.data_manager.set_active_data_from_reduction_list(0)
    window_main.match_direct_beam_clicked()

    # Step 5: Match 42113 to 42099
    window_main.data_manager.set_active_data_from_reduction_list(1)
    # Set the direct beam configuration to 42099
    window_main.data_manager._nexus_data.set_parameter("direct_beam", 42099)
    window_main.file_handler.update_tables()

    # Step 6: Check what normalization_run values are set
    print("\n=== DEBUG: Checking normalization_run values ===")
    for i, data_set in enumerate(window_main.data_manager.reduction_list):
        print(f"Data run {data_set.number} has cross-sections: {list(data_set.cross_sections.keys())}")
        for pol in data_set.cross_sections.keys():
            try:
                if data_set.cross_sections[pol].reflectivity_workspace is not None:
                    run_object = data_set.cross_sections[pol].reflectivity_workspace.getRun()
                    normalization_run = run_object.getProperty("normalization_run").value
                    print(f"  {pol}: normalization_run = {normalization_run}")
            except Exception as e:
                print(f"  {pol}: Error getting normalization_run: {e}")

    # Step 7: Write the header
    with tempfile.TemporaryDirectory() as tmpdir:
        output_file = os.path.join(tmpdir, "test_output.dat")
        # Use the same approach as the actual save code
        quicknxs_io.write_reflectivity_header(
            peak_reduction_lists=window_main.data_manager.peak_reduction_lists,
            active_list_index=window_main.data_manager.active_reduction_list_index,
            direct_beam_list=window_main.data_manager.direct_beam_list,
            output_path=output_file,
            pol_state="Off_On",
            include_gisans=False,
            include_offspec=False,
        )

        # Read the output file and verify the direct beam filenames
        with open(output_file, "r") as f:
            content = f.read()

        print("\n=== DEBUG: Full .dat file content ===")
        print(content)
        print("\n=== END .dat file ===\n")

        # The file should contain the Direct Beam Runs section
        assert "[Direct Beam Runs]" in content

        # Check that run 42112 is in the direct beam section
        assert "42112" in content
        assert "REF_M_42112.nxs.h5" in content

        # Check that run 42099 is in the direct beam section with correct filename
        assert "42099" in content
        assert "REF_M_42099.nxs.h5" in content

        # CRITICAL: Verify that 42099's line doesn't have 42116's filename
        # Split into lines and check the direct beam section
        lines = content.split("\n")
        in_direct_beam_section = False
        direct_beam_lines = []

        for line in lines:
            if "[Direct Beam Runs]" in line:
                in_direct_beam_section = True
            elif in_direct_beam_section:
                if line.startswith("# ["):  # Start of next section
                    break
                # Data lines start with "#" followed by whitespace and then numbers for the fields
                # The header line starts with "#  " followed by column names (not numbers)
                # We can identify data lines by checking if they contain our run numbers or filenames
                if line.strip() and ("42099" in line or "42112" in line) and "REF_M_" in line:
                    direct_beam_lines.append(line)

        # Find the line for run 42099
        print(f"\n=== DEBUG: Found {len(direct_beam_lines)} data lines ===")
        for i, line in enumerate(direct_beam_lines):
            # Check if line contains 42099
            has_42099 = "42099" in line
            has_ref_42099 = "REF_M_42099" in line
            print(f"Line {i + 1}: has_42099={has_42099}, has_ref_42099={has_ref_42099}")
            print(f"  {line[:300]}...")  # Print first 300 chars

        run_42099_line = None
        for line in direct_beam_lines:
            print(
                f"Checking line: '42099' in line = {'42099' in line}, 'REF_M_42099' in line = {'REF_M_42099' in line}"
            )
            # Check if this line contains 42099 as the "number" field (not as part of other fields like "direct_beam")
            # The "number" field appears after several other fields in the table
            if "42099" in line and "REF_M_42099" in line:
                print("MATCH! Setting run_42099_line")
                run_42099_line = line
                break

        print(f"After loop: run_42099_line is None = {run_42099_line is None}")
        assert run_42099_line is not None, (
            f"Run 42099 should be in direct beam section. Found {len(direct_beam_lines)} data lines."
        )

        # Verify the filename in this line is REF_M_42099.nxs.h5, NOT REF_M_42116.nxs.h5
        assert "REF_M_42099.nxs.h5" in run_42099_line, (
            f"Run 42099 line should contain REF_M_42099.nxs.h5, but got: {run_42099_line}"
        )
        assert "REF_M_42116.nxs.h5" not in run_42099_line, (
            f"Run 42099 line should NOT contain REF_M_42116.nxs.h5, but got: {run_42099_line}"
        )

        # Also verify in the Data Runs section that 42113 exists
        # We don't need to parse it precisely - just verify the section exists and has the right data
        assert "[Data Runs]" in content, ".dat file should have Data Runs section"

        # Extract the Data Runs section
        data_section_start = content.find("[Data Runs]")
        data_section_end = content.find("[Peak 1 Runs]", data_section_start)
        if data_section_end == -1:
            data_section_end = content.find("[Global Options]", data_section_start)
        data_section = content[data_section_start:data_section_end]

        # Verify run 42113 is in the data section
        assert "42113" in data_section, "Run 42113 should be in Data Runs section"
        assert "REF_M_42113.nxs.h5" in data_section, "Run 42113 filename should be in Data Runs section"
