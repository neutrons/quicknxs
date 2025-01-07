import numpy as np
import pytest

from quicknxs.interfaces.configuration import Configuration
from quicknxs.interfaces.data_handling.data_set import CrossSectionData


def _get_cross_section_data():
    """Get instance of CrossSectionData for testing"""
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


class TestCrossSectionData(object):
    def test_r_scaling_factor(self):
        config = Configuration()
        xs = CrossSectionData("On_Off", config)
        xs._r = 0.8
        xs._dr = 0.1
        setattr(xs.configuration, "scaling_factor", 0.35)
        setattr(xs.configuration, "scaling_error", 0.01)

        assert xs.r == pytest.approx(0.28, rel=1e-6)
        assert xs.dr == pytest.approx(0.035902646, rel=1e-6)

    def test_get_tof_counts_table(self, mocker):
        """Test of method get_tof_counts_table"""
        mocker.patch("quicknxs.interfaces.data_handling.data_set.CrossSectionData.prepare_plot_data")
        rel_tol = 1e-6
        xs = _get_cross_section_data()
        data_table, header = xs.get_tof_counts_table()
        assert len(data_table) == 3
        assert data_table[0][0] == pytest.approx(0.15, rel_tol)  # tof
        assert data_table[0][1] == pytest.approx(2.0046381e-4, rel_tol)  # wavelength
        assert data_table[0][2] == pytest.approx(13.0 / xs.proton_charge, rel_tol)  # counts normalized
        assert data_table[0][3] == pytest.approx(2.0 / xs.proton_charge, rel_tol)  # counts normalized error
        assert data_table[0][4] == pytest.approx(13.0, rel_tol)  # counts
        assert data_table[0][5] == pytest.approx(2.0, rel_tol)  # counts error
        assert data_table[0][6] == 4  # size of ROI


if __name__ == "__main__":
    pytest.main([__file__])
