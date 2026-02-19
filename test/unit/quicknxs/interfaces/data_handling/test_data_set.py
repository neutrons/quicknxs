import numpy as np
import pytest

from quicknxs.interfaces.configuration import Configuration
from quicknxs.interfaces.data_handling.data_set import CrossSectionData, CrossSectionError


def _get_cross_section_data():
    """Get instance of CrossSectionData for testing."""
    config = Configuration()
    config.peak_position = 3
    config.peak_width = 1
    config.low_res_position = 2
    config.low_res_width = 2
    xs = CrossSectionData("On_Off", config)
    pixel_counts = [[0, 0, 1, 1, 0, 0], [0, 1, 3, 4, 1, 0], [0, 1, 2, 4, 1, 0], [0, 0, 1, 1, 0, 0]]
    pixel_counts = np.array(pixel_counts).astype(float)
    xs.data = np.array([pixel_counts, pixel_counts, pixel_counts]).T
    xs.raw_error = np.ones_like(xs.data)
    xs.tof_edges = np.array([0.1, 0.2, 0.3, 0.4])
    xs.proton_charge = 8.03e5
    xs.dist_mod_det = 2.96
    return xs


class TestCrossSectionError:
    """Tests for the CrossSectionError Exception class"""

    def test_exception_initialization(self, data_server):
        """Test that exception initializes and loads workspaces"""
        file_path = data_server.path_to("REF_M_40785")
        error = CrossSectionError(file_path)

        assert str(error) == f"No valid cross-sections found in file: {file_path}"
        assert len(error.xs_list) == 1
        assert len(error.diagnostic_data) == 1
        assert len(error.sample_logs) == 1

    def test_diagnostic_data_extraction(self, data_server):
        """Test that diagnostic data is properly extracted"""
        file_path = data_server.path_to("REF_M_40785")
        error = CrossSectionError(file_path)

        assert len(error.diagnostic_data) == 1
        data = error.diagnostic_data[0]

        assert "cross_section_id" in data
        assert "event_count" in data
        assert "lambda_center" in data
        assert "direct_pixel" in data
        assert "proton_charge" in data
        assert "sample_angle" in data
        assert "dangle" in data
        assert "dangle0" in data
        assert "counting_time" in data
        assert "count_rate" in data

        assert data["cross_section_id"] == "Run 40785"
        assert data["event_count"] == 32336
        assert data["lambda_center"] == pytest.approx(5.35)
        assert data["direct_pixel"] == pytest.approx(202.0)
        assert data["proton_charge"] == pytest.approx(73.91540313888889)
        assert data["sample_angle"] == pytest.approx(0.12236576869484063)
        assert data["dangle"] == pytest.approx(0.9501975886666632)
        assert data["dangle0"] == pytest.approx(1.2963305700000323)
        assert data["counting_time"] == pytest.approx(980.662088115)
        expected_rate = data["event_count"] / data["counting_time"]
        assert data["count_rate"] == pytest.approx(expected_rate, rel=1e-6)

    def test_sample_logs_extraction(self, data_server):
        """Test that sample logs are properly extracted"""
        file_path = data_server.path_to("REF_M_40785")
        error = CrossSectionError(file_path)

        assert len(error.sample_logs) == 1
        log_data = error.sample_logs[0]

        assert "run_id" in log_data
        assert "logs" in log_data
        assert log_data["run_id"] == 40785

        assert isinstance(log_data["logs"], list)
        assert len(log_data["logs"]) > 0

        for log_entry in log_data["logs"]:
            assert isinstance(log_entry, tuple)
            assert len(log_entry) == 2
            assert isinstance(log_entry[0], str)
            assert isinstance(log_entry[1], str)

        property_names = [log[0] for log in log_data["logs"]]
        assert property_names == sorted(property_names)

    def test_multiple_workspaces(self, data_server):
        """Test that exception handles multiple workspaces correctly"""
        file_path = data_server.path_to("REF_M_40785") + "+" + data_server.path_to("REF_M_40786")
        error = CrossSectionError(file_path)

        assert len(error.xs_list) == 2
        assert len(error.diagnostic_data) == 2
        assert len(error.sample_logs) == 2

        run_ids = [data["cross_section_id"] for data in error.diagnostic_data]
        assert "Run 40785" in run_ids
        assert "Run 40786" in run_ids

        data_40785 = (
            error.diagnostic_data[0]
            if "40785" in error.diagnostic_data[0]["cross_section_id"]
            else error.diagnostic_data[1]
        )
        assert data_40785["event_count"] == 32336
        assert data_40785["lambda_center"] == pytest.approx(5.35)

        data_40786 = (
            error.diagnostic_data[0]
            if "40786" in error.diagnostic_data[0]["cross_section_id"]
            else error.diagnostic_data[1]
        )
        assert data_40786["event_count"] == 1987764
        assert data_40786["lambda_center"] == pytest.approx(5.35)


if __name__ == "__main__":
    pytest.main([__file__])
