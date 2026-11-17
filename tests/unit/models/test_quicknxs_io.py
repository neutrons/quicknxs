import os

import mantid.simpleapi as api
import numpy as np
import pytest

from quicknxs.models.configuration import Configuration
from quicknxs.models.data_set import CrossSectionData, NexusData
from quicknxs.models.quicknxs_io import (
    _assign_config_value,
    _sort_keys_with_file_last,
    determine_which_files_to_sum,
    read_reduced_file,
    write_reflectivity_data,
    write_reflectivity_header,
)


class TestDataLoader:
    """Test the data loading functionality from quicknxs_io module."""

    @pytest.fixture(autouse=True)
    def _data_dir(self, data_server):
        r"""Pass the data_file fixture."""
        self.file = data_server.path_to

    @pytest.fixture(autouse=True)
    def _reset_config(self):
        """Reset configuration to defaults after each test."""
        yield
        Configuration.setup_default_values()

    def test_simple_load(self):
        file_path = self.file("REF_M_28613+28614+28615+28616+28617+28618+28619_Specular_++.dat")
        db_list, data_list, _, _ = read_reduced_file(file_path)
        assert len(db_list) == 7
        assert len(data_list) == 7
        assert data_list[0][2].peak_position == 179.5
        assert data_list[0][2].direct_beam == 28610

    def test_load_no_db(self):
        file_path = self.file("REF_M_29160_Specular_++.dat")
        db_list, data_list, _, _ = read_reduced_file(file_path)
        assert len(db_list) == 0
        assert len(data_list) == 1

    def test_load_from_ar(self):
        file_path = self.file("REF_M_29526_Off_Off_combined_autoreduced.dat")
        db_list, data_list, _, _ = read_reduced_file(file_path)
        assert len(db_list) == 4
        assert len(data_list) == 4

    def test_load_from_quicknxs(self):
        file_path = self.file("REF_M_29526_quicknxs.dat")
        db_list, data_list, _, _ = read_reduced_file(file_path)
        assert len(db_list) == 4
        assert len(data_list) == 4
        assert Configuration.lock_direct_beam_y is False

    def test_load_from_mismatch(self):
        file_path = self.file("REF_M_29782_empty_db.dat")
        db_list, data_list, _, _ = read_reduced_file(file_path)
        assert len(db_list) == 5
        assert len(data_list) == 6
        assert data_list[4][2].direct_beam is None

    def test_load_global_options(self):
        file_path = self.file("REF_M_29526_global_options.dat")
        db_list, data_list, _, _ = read_reduced_file(file_path)
        assert len(db_list) == 4
        assert len(data_list) == 4
        assert Configuration.lock_direct_beam_y is True

    def test_load_multiple_peaks(self):
        file_path = self.file("REF_M_42536+42537_peak1_Specular_Off_Off.dat")
        db_list, data_list, additional_peaks_list, _ = read_reduced_file(file_path)
        assert len(db_list) == 2
        assert len(data_list) == 2
        # test that there are two additional peaks, both with run numbers 42536 and 42537
        assert len(additional_peaks_list) == 4
        assert len(additional_peaks_list[0]) == 5  # Now includes slice_value as 5th element
        assert len(additional_peaks_list[1]) == 5
        assert additional_peaks_list[0][0] == additional_peaks_list[1][0] == 2
        assert additional_peaks_list[2][0] == additional_peaks_list[3][0] == 3
        assert additional_peaks_list[0][1] == additional_peaks_list[2][1] == 42536
        assert additional_peaks_list[1][1] == additional_peaks_list[3][1] == 42537

    def test_load_summed_runs_in_file_column(self, tmp_path):
        """Test loading reduced file where number column contains '+' for summed runs."""
        # Create a reduced file with summed run numbers in both number and File columns
        test_file = tmp_path / "test_summed.dat"
        test_file.write_text(
            """# Datafile created by QuickNXS 4.16.0.dev2
# Datafile created using Mantid 6.14.0
# Date: 2025-01-20 10:30:00
# Type: Specular
# Input file indices: 42112+42113,42116
# Extracted states: +
#
# [Direct Beam Runs]
#    DB_ID        P0        PN     x_pos   x_width     y_pos   y_width    bg_pos  bg_width      dpix       tth    number      File
#        0         0         0     179.5        19       144        46        39        56       180         0     42110  /SNS/REF_M/IPTS-30794/nexus/REF_M_42110.nxs.h5
#
# [Data Runs]
#    scale        P0        PN     x_pos   x_width     y_pos   y_width    bg_pos  bg_width       fan      dpix       tth    number     DB_ID      File
#        1         5        10     212.6        19     117.3      65.3        39        56     False       180    2.2255  42112+42113      0  /SNS/REF_M/IPTS-30794/nexus/REF_M_42112.nxs.h5
#   3.7201         5        10     214.9        22     121.8      56.3        39        56     False       180    4.1776     42116         0  /SNS/REF_M/IPTS-30794/nexus/REF_M_42116.nxs.h5
#
# [Peak 1 Runs]
#    scale        P0        PN     x_pos   x_width     y_pos   y_width    bg_pos  bg_width       fan      dpix       tth    number     DB_ID      File
#        1         5        10     212.6        19     117.3      65.3        39        56     False       180    2.2255  42112+42113      0  /SNS/REF_M/IPTS-30794/nexus/REF_M_42112.nxs.h5
#   3.7201         5        10     214.9        22     121.8      56.3        39        56     False       180    4.1776     42116         0  /SNS/REF_M/IPTS-30794/nexus/REF_M_42116.nxs.h5
#
# [Global Options]
# name           value
# sample_length  10.0
#
# [Data]
#     Qz [1/A]	    R [a.u.]	   dR [a.u.]	   dQz [1/A]	 theta [rad]
2.263373e-02      	1.986968e-02      	1.427452e-04      	1.252235e-03      	1.445378e-02
"""
        )

        # Read the file
        direct_beam_runs, data_runs, additional_peaks, has_scaling_error = read_reduced_file(str(test_file))

        # Check direct beam
        assert len(direct_beam_runs) == 1
        assert direct_beam_runs[0][0] == 42110

        # Peak 1 Runs replaces Data Runs, so data_runs contains Peak 1 data
        assert len(data_runs) == 2

        # First entry: summed files (42112+42113)
        assert data_runs[0][0] == 42112  # run number (first of summed)
        assert "42112.nxs.h5+/SNS/REF_M/IPTS-30794/nexus/REF_M_42113.nxs.h5" in data_runs[0][1]
        assert data_runs[0][1].count("+") == 1  # Only one "+" separator
        assert data_runs[0][1].count("42112") == 1  # No duplicates
        assert data_runs[0][1].count("42113") == 1  # No duplicates

        # Second entry: single file (42116)
        assert data_runs[1][0] == 42116
        assert "42116.nxs.h5" in data_runs[1][1]
        assert "+" not in data_runs[1][1]

        # additional_peaks should be empty (only Peak 2, 3, ... go there)
        assert len(additional_peaks) == 0


@pytest.fixture
def mock_nexus_data(tmp_path, temp_workspace_name):
    """Generate mock Nexus data for testing."""

    def mock_nexus_data_function(run_number: int):
        # create reflectivity workspace
        ws = api.CreateWorkspace([0.0, 1.0], [12.0, 14.0], OutputWorkspace=temp_workspace_name())
        api.AddSampleLog(ws, LogName="Filename", LogText=os.path.join(tmp_path, f"run{run_number}.nxs.h5"))
        api.AddSampleLog(ws, LogName="DIRPIX", LogText="105.0", LogType="Number Series")
        api.AddSampleLog(ws, LogName="normalization_dirpix", LogText="105.0")
        api.AddSampleLog(ws, LogName="normalization_file_path", LogText="/test/file/path")
        api.AddSampleLog(ws, LogName="normalization_run", LogText="30001")
        api.AddSampleLog(ws, LogName="constant_q_binning", LogText="True")
        api.AddSampleLog(ws, LogName="specular_pixel", LogText="80.0", LogType="Number")
        api.AddSampleLog(ws, LogName="two_theta", LogText="5.0", LogType="Number")
        api.AddSampleLog(ws, LogName="SampleDetDis", LogText="105.0", LogType="Number Series")

        # create nexus data object
        config = Configuration()
        nexus_data = NexusData("file/path", config)
        off_off = CrossSectionData("Off_Off", config)
        off_off._reflectivity_workspace = str(ws)
        on_off = CrossSectionData("On_Off", config)
        on_off._reflectivity_workspace = str(ws)
        nexus_data.cross_sections["Off_Off"] = off_off
        nexus_data.cross_sections["On_Off"] = on_off
        nexus_data.run_number = run_number

        return nexus_data

    return mock_nexus_data_function


class TestDataWriter:
    """Test the data writing functionality from quicknxs_io module."""

    def test_save_multiple_peaks(self, tmp_path, temp_workspace_name):
        """Test saving session with multiple peaks and different direct beams."""
        output_path = tmp_path / "test_REF_M_save_data_output.dat"
        pol_state = "On_Off"
        col_names = ["Qz [1/A]", "R [a.u.]", "dR [a.u.]", "dQz [1/A]", "theta [rad]"]
        output_data = np.array(
            [
                [2.26337261e-02, 5.39473109e-03, 7.23757965e-05, 1.25223308e-03, 1.44538147e-02],
                [2.28600633e-02, 5.25972758e-03, 6.96006058e-05, 1.26563639e-03, 1.44538147e-02],
                [2.30886640e-02, 5.11775592e-03, 6.69761737e-05, 1.27919979e-03, 1.44538147e-02],
                [2.33195506e-02, 4.99204401e-03, 6.49017474e-05, 1.29292564e-03, 1.44538147e-02],
            ]
        )

        # Helper to create mock data with specific direct beam
        def create_mock_with_db(run_number, db_number):
            ws = api.CreateWorkspace([0.0, 1.0], [12.0, 14.0], OutputWorkspace=temp_workspace_name())
            api.AddSampleLog(ws, LogName="Filename", LogText=os.path.join(tmp_path, f"run{run_number}.nxs.h5"))
            api.AddSampleLog(ws, LogName="DIRPIX", LogText="105.0", LogType="Number Series")
            api.AddSampleLog(ws, LogName="normalization_dirpix", LogText="105.0")
            api.AddSampleLog(ws, LogName="normalization_file_path", LogText=f"/test/db_{db_number}.nxs.h5")
            api.AddSampleLog(ws, LogName="normalization_run", LogText=str(db_number))
            api.AddSampleLog(ws, LogName="constant_q_binning", LogText="True")
            api.AddSampleLog(ws, LogName="specular_pixel", LogText="80.0", LogType="Number")
            api.AddSampleLog(ws, LogName="two_theta", LogText="5.0", LogType="Number")
            api.AddSampleLog(ws, LogName="SampleDetDis", LogText="105.0", LogType="Number Series")

            config = Configuration()
            nexus_data = NexusData("file/path", config)
            off_off = CrossSectionData("Off_Off", config)
            off_off._reflectivity_workspace = str(ws)
            on_off = CrossSectionData("On_Off", config)
            on_off._reflectivity_workspace = str(ws)
            nexus_data.cross_sections["Off_Off"] = off_off
            nexus_data.cross_sections["On_Off"] = on_off
            nexus_data.run_number = run_number
            return nexus_data

        # Create direct beams
        db_30001 = create_mock_with_db(30001, 30001)
        db_30004 = create_mock_with_db(30004, 30004)
        direct_beam_list = [db_30001, db_30004]

        # Peak 1: run 30002 uses DB 30001, run 30003 uses DB 30004
        peak1_run1 = create_mock_with_db(30002, 30001)
        peak1_run2 = create_mock_with_db(30003, 30004)

        # Peak 2: same runs with same direct beams
        peak2_run1 = create_mock_with_db(30002, 30001)
        peak2_run2 = create_mock_with_db(30003, 30004)

        peak_reduction_lists = {
            1: [peak1_run1, peak1_run2],
            2: [peak2_run1, peak2_run2],
        }
        active_list_index = 1

        # write reflectivity data to file
        write_reflectivity_header(
            peak_reduction_lists,
            active_list_index,
            direct_beam_list,
            output_path,
            pol_state,
        )
        write_reflectivity_data(output_path, output_data, col_names)

        # test loading saved file
        db_list, data_list, additional_peaks_list, has_scaling_error = read_reduced_file(output_path)

        # Verify both direct beams are saved
        assert len(db_list) == 2
        db_numbers = [db[0] for db in db_list]
        assert 30001 in db_numbers
        assert 30004 in db_numbers

        # Verify data runs are correctly matched to their direct beams
        assert len(data_list) == 2
        assert data_list[0][2].direct_beam == 30001  # run 30002 uses DB 30001
        assert data_list[1][2].direct_beam == 30004  # run 30003 uses DB 30004

        # Verify additional peak has same direct beam matching
        assert len(additional_peaks_list) == 2
        assert has_scaling_error is True

    def test_save_and_load_slice(self, tmp_path, mock_nexus_data):
        """Test that slice attribute is saved and loaded correctly."""
        output_path = tmp_path / "test_slice_save_load.dat"
        pol_state = "On_Off"
        col_names = ["Qz [1/A]", "R [a.u.]", "dR [a.u.]", "dQz [1/A]", "theta [rad]"]
        output_data = np.array(
            [
                [2.26337261e-02, 5.39473109e-03, 7.23757965e-05, 1.25223308e-03, 1.44538147e-02],
                [2.28600633e-02, 5.25972758e-03, 6.96006058e-05, 1.26563639e-03, 1.44538147e-02],
            ]
        )

        # Create mock data with different slice values
        nexus_db = mock_nexus_data(30001)
        nexus_db.slice = 0

        nexus_1 = mock_nexus_data(30002)
        nexus_1.slice = 1

        nexus_2 = mock_nexus_data(30003)
        nexus_2.slice = 2

        direct_beam_list = [nexus_db]
        peak_reduction_lists = {1: [nexus_1, nexus_2]}
        active_list_index = 1

        # Write reflectivity data to file
        write_reflectivity_header(
            peak_reduction_lists,
            active_list_index,
            direct_beam_list,
            output_path,
            pol_state,
        )
        write_reflectivity_data(output_path, output_data, col_names)

        # Test loading saved file
        db_list, data_list, _, _ = read_reduced_file(output_path)

        # Check direct beam - should only be written once since both data runs reference the same direct beam
        assert len(db_list) == 1
        assert db_list[0][3] == 0  # slice_value is 4th element in tuple

        # Check data runs slices
        assert len(data_list) == 2
        assert data_list[0][3] == 1  # first run has slice=1
        assert data_list[1][3] == 2  # second run has slice=2


class TestBackwardsCompatibility(TestDataLoader):
    """Test backwards compatibility for loading files without slice column."""

    def test_load_file_without_slice_backwards_compatibility(self):
        """Test that files without slice column load with slice=0 for backwards compatibility."""
        # Use existing test file that doesn't have slice column
        file_path = self.file("REF_M_28613+28614+28615+28616+28617+28618+28619_Specular_++.dat")
        db_list, data_list, _, _ = read_reduced_file(file_path)

        # All entries should have slice=0 (default)
        for db_entry in db_list:
            assert db_entry[3] == 0  # slice_value is 4th element in tuple

        for data_entry in data_list:
            assert data_entry[3] == 0  # slice_value is 4th element in tuple


@pytest.fixture
def config_teardown():
    yield
    Configuration.setup_default_values()


class TestConfig:
    """Test reading and writing instance and class configuration options"""

    def test_write_and_read_full_config(self, tmp_path, mock_nexus_data, config_teardown):
        """Test writing and reading full configuration, including global and instance attributes."""

        # Modify instance-level config
        conf = Configuration()
        Configuration.sample_size = 42
        conf.scaling_factor = 3.14
        conf.cut_first_n_points = 5
        conf.off_spec_slice_qz_min = 0.05
        conf.gisans_qz_npts = 77
        conf.off_spec_qz_list = [0.05, 0.07]
        conf.tof_range = [1123.9234, 1234.5678]

        # Modify global (class-level) config
        Configuration.use_constant_q = True
        Configuration.final_rebin_step_global = -0.02
        Configuration.normalize_to_unity = False

        # Use mock NexusData object
        nexus = mock_nexus_data(30001)
        nexus.cross_sections["On_Off"].configuration = conf
        nexus.cross_sections["Off_Off"].configuration = conf

        output_path = tmp_path / "test_config_roundtrip.dat"
        write_reflectivity_header(
            {1: [nexus]},
            active_list_index=1,
            direct_beam_list=[nexus],
            output_path=output_path,
            pol_state="On_Off",
        )

        # Read back from file
        _, data_list, _, _ = read_reduced_file(output_path)

        # === Assert instance values ===
        instance_conf = data_list[0][2]
        assert instance_conf.sample_size == 42
        assert instance_conf.scaling_factor == 3.14
        assert instance_conf.cut_first_n_points == 5
        assert instance_conf.off_spec_slice_qz_min == 0.05
        assert instance_conf.tof_range == [1123.9234, 1234.5678]
        # These should not have changed
        assert instance_conf.gisans_qz_npts == 50
        assert instance_conf.off_spec_qz_list == []

        # === Assert global values ===
        assert Configuration.use_constant_q is True
        assert Configuration.final_rebin_step_global == -0.02
        assert Configuration.normalize_to_unity is False

        output_path = tmp_path / "GISANS_test_config_roundtrip.dat"
        # Modify GISANS-specific configuration
        write_reflectivity_header(
            {1: [nexus]},
            active_list_index=1,
            direct_beam_list=[nexus],
            output_path=output_path,
            pol_state="On_Off",
            include_gisans=True,
        )

        # Read back GISANS-specific configuration
        _, data_list, _, _ = read_reduced_file(output_path)
        instance_conf = data_list[0][2]
        assert instance_conf.gisans_qz_npts == 77

        output_path = tmp_path / "OffSpec_test_config_roundtrip.dat"
        # Modify OffSpec-specific configuration
        write_reflectivity_header(
            {1: [nexus]},
            active_list_index=1,
            direct_beam_list=[nexus],
            output_path=output_path,
            pol_state="On_Off",
            include_offspec=True,
        )

        # Read back OffSpec-specific configuration
        _, data_list, _, _ = read_reduced_file(output_path)
        instance_conf = data_list[0][2]
        assert instance_conf.off_spec_slice_qz_min == 0.05
        assert instance_conf.off_spec_qz_list == [0.05, 0.07]


def test_assign_list_value():
    conf = Configuration()
    conf.off_spec_qz_list = []  # default empty
    _assign_config_value(conf, "off_spec_qz_list", "[0.01, 0.02, 0.03]")
    assert conf.off_spec_qz_list == [0.01, 0.02, 0.03]


def test_fallback_int_to_float():
    conf = Configuration()
    conf.cut_first_n_points = 1  # int by default
    _assign_config_value(conf, "cut_first_n_points", "3.0")
    assert conf.cut_first_n_points == 3.0  # now float, not int


def test_assign_unknown_key_ignored(caplog):
    conf = Configuration()
    _assign_config_value(conf, "nonexistent_option", "123")
    assert not hasattr(conf, "nonexistent_option")
    assert "nonexistent_option" not in conf.__dict__


def test_sort_keys_with_file_last():
    keys = ["x", "a", "File", "z"]
    sorted_keys = _sort_keys_with_file_last(keys)
    assert sorted_keys[-1] == "File"
    assert set(sorted_keys[:-1]) == {"a", "x", "z"}


def test_determine_which_files_to_sum_with_summed_format():
    """Test determine_which_files_to_sum with summed format (run_number_str='42112+42113')."""
    run_file = "/SNS/REF_M/IPTS-12345/nexus/REF_M_42112.nxs.h5"
    data_file_indices = "42112"
    run_number_str = "42112+42113"

    result = determine_which_files_to_sum(run_file, data_file_indices, run_number_str)

    # Should return string with both file paths joined by "+"
    expected = "/SNS/REF_M/IPTS-12345/nexus/REF_M_42112.nxs.h5+/SNS/REF_M/IPTS-12345/nexus/REF_M_42113.nxs.h5"
    assert result == expected
    assert "+" in result
    # Verify both file paths are present
    paths = result.split("+")
    assert len(paths) == 2
    assert "REF_M_42112.nxs.h5" in paths[0]
    assert "REF_M_42113.nxs.h5" in paths[1]


def test_determine_which_files_to_sum_with_single_run():
    """Test determine_which_files_to_sum with single run number."""
    run_file = "/SNS/REF_M/IPTS-12345/nexus/REF_M_42116.nxs.h5"
    data_file_indices = "42116"
    run_number_str = "42116"

    result = determine_which_files_to_sum(run_file, data_file_indices, run_number_str)

    # Should return the original file path (no summing)
    assert result == "/SNS/REF_M/IPTS-12345/nexus/REF_M_42116.nxs.h5"
    assert "+" not in result


def test_determine_which_files_to_sum_legacy_with_plus():
    """Test determine_which_files_to_sum with legacy format (no run_number_str, plus in data_file_indices)."""
    run_file = "/SNS/REF_M/IPTS-12345/nexus/REF_M_42112.nxs.h5"
    data_file_indices = "42112+42113"
    run_number_str = None

    result = determine_which_files_to_sum(run_file, data_file_indices, run_number_str)

    # Should return the original file path (legacy behavior doesn't modify for single matching run)
    # The legacy code only returns run_file when the run is in the file
    assert result == "/SNS/REF_M/IPTS-12345/nexus/REF_M_42112.nxs.h5"


def test_determine_which_files_to_sum_with_mixed_format():
    """Test determine_which_files_to_sum with mixed comma-separated format."""
    run_file = "/SNS/REF_M/IPTS-12345/nexus/REF_M_42112.nxs.h5"
    data_file_indices = "42112+42113,42116"
    run_number_str = "42112+42113"

    result = determine_which_files_to_sum(run_file, data_file_indices, run_number_str)

    # With run_number_str provided, should process the summed part
    expected = "/SNS/REF_M/IPTS-12345/nexus/REF_M_42112.nxs.h5+/SNS/REF_M/IPTS-12345/nexus/REF_M_42113.nxs.h5"
    assert result == expected
    paths = result.split("+")
    assert len(paths) == 2


def test_determine_which_files_to_sum_with_range_format():
    """Test determine_which_files_to_sum with range format (colon)."""
    run_file = "/SNS/REF_M/IPTS-12345/nexus/REF_M_42112.nxs.h5"
    data_file_indices = "42112:42115"
    run_number_str = None

    result = determine_which_files_to_sum(run_file, data_file_indices, run_number_str)

    # Should handle colon as range - expands to all files in range
    assert "+" in result
    paths = result.split("+")
    assert len(paths) == 4  # 42112, 42113, 42114, 42115
    assert "REF_M_42112.nxs.h5" in result
    assert "REF_M_42113.nxs.h5" in result
    assert "REF_M_42114.nxs.h5" in result
    assert "REF_M_42115.nxs.h5" in result


if __name__ == "__main__":
    pytest.main([__file__])


OFFSPEC_COL_NAMES = [
    "Qx [1/A]",
    "Qz [1/A]",
    "ki_z [1/A]",
    "kf_z [1/A]",
    "ki_z-kf_z [1/A]",
    "I [a.u.]",
    "dI [a.u.]",
]


def _data_column_names(file_path) -> list[str]:
    """Return the column names from the line following ``# [Data]``."""
    lines = file_path.read_text().splitlines()
    names_line = lines[lines.index("# [Data]") + 1]
    return [name.strip() for name in names_line.lstrip("#").split("\t")]


def test_write_raw_offspec_names_every_column(tmp_path):
    """Raw off-specular data (one [pixel][TOF][column] array per run) has 7 columns, all of them named."""
    output_path = tmp_path / "OffSpec_Off_Off.dat"
    n_pixel, n_tof = 2, 3
    data = [np.arange(n_pixel * n_tof * 7, dtype=float).reshape(n_pixel, n_tof, 7) for _ in range(2)]
    write_reflectivity_data(output_path, data, OFFSPEC_COL_NAMES, as_5col=False)

    assert _data_column_names(output_path) == OFFSPEC_COL_NAMES
    written = np.loadtxt(output_path)
    assert written.shape == (2 * n_pixel * n_tof, len(OFFSPEC_COL_NAMES))


@pytest.mark.parametrize(("as_5col", "n_expected"), [(True, 5), (False, 4)])
def test_write_reflectivity_column_names_match_data(tmp_path, as_5col, n_expected):
    """For 2D reflectivity data, the number of column names equals the number of columns written."""
    output_path = tmp_path / "Specular_Off_Off.dat"
    col_names = ["Qz [1/A]", "R [a.u.]", "dR [a.u.]", "dQz [1/A]", "theta [rad]"]
    write_reflectivity_data(output_path, np.ones((3, 5)), col_names, as_5col=as_5col)

    assert _data_column_names(output_path) == col_names[:n_expected]
    assert np.loadtxt(output_path).shape == (3, n_expected)


@pytest.mark.parametrize(("kwargs", "expected"), [({}, "Specular"), ({"data_type": "OffSpec"}, "OffSpec")])
def test_header_states_data_type(tmp_path, mock_nexus_data, kwargs, expected):
    """The ``# Type:`` header line names the kind of data in the file, and the file still loads."""
    output_path = tmp_path / "header_type.dat"
    write_reflectivity_header(
        {1: [mock_nexus_data(30002)]},
        1,
        [mock_nexus_data(30001)],
        output_path,
        "Off_Off",
        include_offspec=True,
        **kwargs,
    )
    write_reflectivity_data(output_path, [np.zeros((2, 3, 7))], OFFSPEC_COL_NAMES)

    type_lines = [line for line in output_path.read_text().splitlines() if line.startswith("# Type:")]
    assert type_lines == [f"# Type: {expected}"]
    _, data_list, _, _ = read_reduced_file(str(output_path))
    assert len(data_list) == 1


def test_write_raw_offspec_separates_runs(tmp_path):
    """Runs are separated by two blank lines and pixels within a run by one.

    Plotting tools (e.g. gnuplot) join consecutive blank-line-separated scans into one surface, and treat
    a double blank line as the end of that surface. Without it, the last pixel of one run is joined to the
    first pixel of the next run. This is the convention of the Off-Specular preview data export.
    """
    output_path = tmp_path / "OffSpec_Off_Off.dat"
    n_pixel = 3
    data = [np.ones((n_pixel, n_tof, 7)) for n_tof in (4, 2, 5)]
    write_reflectivity_data(output_path, data, OFFSPEC_COL_NAMES)

    text = output_path.read_text().split("# [Data]\n")[1].split("\n", 1)[1]  # drop the column names
    runs = [run for run in text.split("\n\n\n") if run.strip()]
    assert len(runs) == len(data)
    for run, expected in zip(runs, data):
        pixels = [pixel for pixel in run.split("\n\n") if pixel.strip()]
        assert len(pixels) == n_pixel
        assert all(len(pixel.strip().splitlines()) == expected.shape[1] for pixel in pixels)
    assert np.loadtxt(output_path).shape == (n_pixel * (4 + 2 + 5), 7)
