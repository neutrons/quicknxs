# local imports
# standard imports
import os

# 3rd-party imports
import mantid.simpleapi as api
import numpy as np
import pytest

from quicknxs.interfaces.configuration import Configuration
from quicknxs.interfaces.data_handling.data_set import CrossSectionData, NexusData
from quicknxs.interfaces.data_handling.quicknxs_io import (
    _assign_config_value,
    _sort_keys_with_file_last,
    read_reduced_file,
    write_reflectivity_data,
    write_reflectivity_header,
)


class TestDataLoader(object):
    """Test the data loading functionality from quicknxs_io module."""

    @pytest.fixture(autouse=True)
    def _data_dir(self, data_server):
        r"""Pass the data_file fixture."""
        self.file = data_server.path_to

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
        assert len(additional_peaks_list[0]) == 4
        assert len(additional_peaks_list[1]) == 4
        assert additional_peaks_list[0][0] == additional_peaks_list[1][0] == 2
        assert additional_peaks_list[2][0] == additional_peaks_list[3][0] == 3
        assert additional_peaks_list[0][1] == additional_peaks_list[2][1] == 42536
        assert additional_peaks_list[1][1] == additional_peaks_list[3][1] == 42537


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
        nexus_data.number = run_number

        return nexus_data

    return mock_nexus_data_function


class TestDataWriter(object):
    """Test the data writing functionality from quicknxs_io module."""

    def test_save_multiple_peaks(self, tmp_path, mock_nexus_data):
        """Test saving session with multiple peaks."""
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
        direct_beam_list = [mock_nexus_data(30001)]
        peak_reduction_lists = {
            1: [mock_nexus_data(30002), mock_nexus_data(30003)],
            2: [mock_nexus_data(30002), mock_nexus_data(30003)],
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
        assert len(db_list) == 2
        assert len(data_list) == 2
        assert len(additional_peaks_list) == 2
        assert has_scaling_error is True


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


if __name__ == "__main__":
    pytest.main([__file__])
