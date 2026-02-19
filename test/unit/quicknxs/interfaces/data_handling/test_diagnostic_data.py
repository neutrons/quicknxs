import pytest

from quicknxs.interfaces.data_handling.diagnostic_data import DiagnosticData

class TestDiagnosticData:
    """Tests for the DiagnosticData class"""

    def test_exception_initialization(self, data_server):
        """Test that DiagnosticData initializes and loads workspaces"""
        file_path = data_server.path_to("REF_M_40785")
        diag = DiagnosticData(file_path)

        assert str(diag) == f"No valid cross-sections found in file: {file_path}"
        assert len(diag.xs_list) == 1
        assert len(diag.diagnostic_data) == 1
        assert len(diag.sample_logs) == 1

    def test_diagnostic_data_extraction(self, data_server):
        """Test that diagnostic data is properly extracted"""
        file_path = data_server.path_to("REF_M_40785")
        diag = DiagnosticData(file_path)

        assert len(diag.diagnostic_data) == 1
        data = diag.diagnostic_data[0]

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
        diag = DiagnosticData(file_path)

        assert len(diag.sample_logs) == 1
        log_data = diag.sample_logs[0]

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
        """Test that DiagnosticData handles multiple workspaces correctly"""
        file_path = data_server.path_to("REF_M_40785") + "+" + data_server.path_to("REF_M_40786")
        diag = DiagnosticData(file_path)

        assert len(diag.xs_list) == 2
        assert len(diag.diagnostic_data) == 2
        assert len(diag.sample_logs) == 2

        run_ids = [data["cross_section_id"] for data in diag.diagnostic_data]
        assert "Run 40785" in run_ids
        assert "Run 40786" in run_ids

        data_40785 = (
            diag.diagnostic_data[0]
            if "40785" in diag.diagnostic_data[0]["cross_section_id"]
            else diag.diagnostic_data[1]
        )
        assert data_40785["event_count"] == 32336
        assert data_40785["lambda_center"] == pytest.approx(5.35)

        data_40786 = (
            diag.diagnostic_data[0]
            if "40786" in diag.diagnostic_data[0]["cross_section_id"]
            else diag.diagnostic_data[1]
        )
        assert data_40786["event_count"] == 1987764
        assert data_40786["lambda_center"] == pytest.approx(5.35)

if __name__ == "__main__":
    pytest.main([__file__])
