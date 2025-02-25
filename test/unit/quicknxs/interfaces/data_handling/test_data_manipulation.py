# package imports
# 3rd-party imports
import copy

import mantid.simpleapi as api
import numpy as np
import pytest

from quicknxs.interfaces.configuration import Configuration
from quicknxs.interfaces.data_handling.data_manipulation import (
    NormalizeToUnityQCutoffError,
    _get_polynomial_fit_stitching_scaling_factor,
    _get_stitching_overlap_region,
    smart_stitch_reflectivity,
)
from quicknxs.interfaces.data_handling.data_set import NexusData
from quicknxs.interfaces.data_manager import DataManager

mock_reduced_file_str = (
    "# Datafile created by QuickNXS 3.1.0.dev2\n"
    "# Datafile created using Mantid 6.6.0\n"
    "# Date: 2023-07-05 13:31:21\n"
    "# Type: Specular\n"
    "# Input file indices: 42112,42116,42113\n"
    "# Extracted states: -+\n"
    "#\n"
    "# [Direct Beam Runs]\n"
    "#    DB_ID        P0        PN     x_pos   x_width     y_pos   y_width    bg_pos  bg_width      dpix       tth    number      File\n"  # noqa: E501
    "#        1         0         0       195        12     126.5       155        55        24       194         0     42099  quicknxs-data/REF_M_42099.nxs.h5\n"  # noqa: E501
    "#        2         0         0       195        12       127       154        55        24       194         0     42100  quicknxs-data/REF_M_42100.nxs.h5\n"  # noqa: E501
    "#        3         0         0       195        12       127       154        55        24       194         0     42100  quicknxs-data/REF_M_42100.nxs.h5\n"  # noqa: E501
    "#\n"
    "# [Data Runs]\n"
    "#    scale        P0        PN     x_pos   x_width     y_pos   y_width    bg_pos  bg_width       fan      dpix       tth    number     DB_ID      File\n"  # noqa: E501
    "#        1        15        10       167        12     163.5      72.9        55        24     False       194  0.00653668     42112         1  quicknxs-data/REF_M_42112.nxs.h5\n"  # noqa: E501
    "# 0.183654        15        10     189.3        12     162.2      68.3        55        24     False       194  0.799577     42116           2  quicknxs-data/REF_M_42116.nxs.h5\n"  # noqa: E501
    "#   0.1375        15        10     167.5        12     159.9      67.4        55        24     False       194  0.798876     42113           3  quicknxs-data/REF_M_42113.nxs.h5\n"  # noqa: E501
    "#\n"
    "# [Global Options]\n"
    "# name           value\n"
    "# sample_length  10.0\n"
    "#\n"
    "# [Data]\n"
    "#     Qz [1/A]	    R [a.u.]	   dR [a.u.]	   dQz [1/A]"
)


@pytest.fixture
def mocker_file_open(mocker):
    mocked_reduced_file = mocker.mock_open(read_data=mock_reduced_file_str)
    mocker.patch("builtins.open", mocked_reduced_file)


@pytest.fixture
def stitching_config():
    settings = {
        "use_dangle": True,
        "normalize_to_unity": False,
        "total_reflectivity_q_cutoff": 0.008,
        "do_final_rebin_global": False,
        "final_rebin_step_global": -0.01,
        "match_direct_beam": True,
    }
    Configuration.setup_default_values()
    config = Configuration()
    for key in settings:
        setattr(config, key, settings[key])
    return config


@pytest.fixture
def stitching_reduction_list():
    """List of NexusData objects for testing of stitching"""

    class _MockCrossSectionData(object):
        """Test class to use instead of CrossSectionData, which requires EventWorkspaces"""

        def __init__(self, xs: str, config: Configuration, data_x: list, data_y: list, ws_name: str):
            self.name = xs
            self.configuration = copy.deepcopy(config)
            data_e = [0.1 * y for y in data_y]
            workspace = api.CreateWorkspace(DataX=data_x, DataY=data_y, DataE=data_e, OutputWorkspace=ws_name)
            self.ws = workspace
            self.q = self.ws.readX(0)[:].copy()
            self._r = np.ma.masked_equal(self.ws.readY(0)[:].copy(), 0)
            self._dr = self.ws.readE(0)[:].copy()

    configuration = Configuration()
    configuration.cut_first_n_points = 0
    configuration.cut_last_n_points = 0

    # create curve 1
    data_x = [1.0, 2.0, 3.0, 4.0]
    xs1_on_on = _MockCrossSectionData("On_On", configuration, data_x, [5.0, 5.0, 5.0, 5.0], "run1_on_on")
    xs1_on_off = _MockCrossSectionData("On_Off", configuration, data_x, [7.0, 7.0, 7.0, 7.0], "run1_on_off")
    curve1 = NexusData("path", configuration)
    curve1.cross_sections = {"On_On": xs1_on_on, "On_Off": xs1_on_off}

    # create curve 2
    data_x = [4.0, 5.0, 6.0, 7.0]
    xs2_on_on = _MockCrossSectionData("On_On", configuration, data_x, [3.0, 3.0, 3.0, 3.0], "run2_on_on")
    xs2_on_off = _MockCrossSectionData("On_Off", configuration, data_x, [2.0, 2.0, 2.0, 2.0], "run2_on_off")
    curve2 = NexusData("path", configuration)
    curve2.cross_sections = {"On_On": xs2_on_on, "On_Off": xs2_on_off}

    # create curve 3
    data_x = [7.0, 8.0, 9.0, 10.0]
    xs3_on_on = _MockCrossSectionData("On_On", configuration, data_x, [1.0, 1.0, 1.0, 1.0], "run3_on_on")
    xs3_on_off = _MockCrossSectionData("On_Off", configuration, data_x, [1.0, 1.0, 1.0, 1.0], "run3_on_off")
    curve3 = NexusData("path", configuration)
    curve3.cross_sections = {"On_On": xs3_on_on, "On_Off": xs3_on_off}

    return [curve1, curve2, curve3]


class TestDataManipulation(object):
    @pytest.mark.datarepo
    def test_smart_stitch_reflectivity(self, data_server, mocker_file_open, stitching_config):
        manager = DataManager(data_server.directory)
        manager.load_data_from_reduced_file(data_server.directory, stitching_config)
        if len(manager.reduction_list) < 1:
            raise IOError("Files missing.")
        scaling_factors, scaling_errors = smart_stitch_reflectivity(manager.reduction_list, "Off_On", False, 0.008)
        assert scaling_factors == pytest.approx([1.0, 0.1809, 0.1556], abs=0.001)
        assert scaling_errors == pytest.approx([0.0, 0.003, 0.005], abs=0.001)

    @pytest.mark.parametrize(
        "normalize_to_unity, global_fit, polynom_degree, expected_scaling_factors, expected_scaling_errors",
        [
            (False, False, None, [1.0, 1.66667, 5.0], [0.0, 0.23570, 1.00000]),
            (True, False, None, [0.2, 0.33333, 1.0], [0.02, 0.057735, 0.22361]),
            (False, True, None, [1.0, 2.4, 6.0], [0.0, 0.24403, 0.85988]),
            (True, True, None, [0.2, 0.48, 1.2], [0.02, 0.068455, 0.20970]),
            (False, False, 3, [1.0, 1.66667, 5.0], [0.0, 0.2, 1.0]),
            (True, False, 3, [0.2, 0.33333, 1.0], [0.02, 0.06, 0.2]),
            (False, True, 3, [1.0, 2.4, 6.0], [0.0, 0.2, 0.9]),
            (True, True, 3, [0.2, 0.48, 1.2], [0.02, 0.07, 0.2]),
        ],
    )
    def test_smart_stitch_parameters(
        self,
        stitching_reduction_list,
        normalize_to_unity,
        global_fit,
        polynom_degree,
        expected_scaling_factors,
        expected_scaling_errors,
    ):
        """Test all combinations of the smart_stitch_reflectivity parameters `normalize_to_unity` and `global_fit`

        The fixture stitching_reduction_list has three runs with two cross-sections each: `On_On` and `On_Off`.
        When `global_fit` is True, both cross-sections are used to calculate the scaling factors.
        """
        q_cutoff = 1.5
        scaling_factors, scaling_errors = smart_stitch_reflectivity(
            stitching_reduction_list, "On_On", normalize_to_unity, q_cutoff, global_fit, polynom_degree
        )
        assert scaling_factors == pytest.approx(expected_scaling_factors, abs=0.001)
        # higher tolerance because the polynomial fit to a constant value is ill-conditioned
        assert scaling_errors == pytest.approx(expected_scaling_errors, rel=0.2)
        # Delete workspaces
        api.mtd.clear()

    def test_get_stitching_overlap_region(self):
        """Test of helper function _get_stitching_overlap_region"""
        x1 = [1, 2, 3, 4, 5]
        x2 = [3, 4, 5, 6, 7]
        x3 = [7, 8, 9, 10, 11]
        y = [1, 1, 1, 1]
        ws1 = api.CreateWorkspace(x1, y)
        ws2 = api.CreateWorkspace(x2, y)
        ws3 = api.CreateWorkspace(x3, y)

        # with overlap
        xmin, xmax = _get_stitching_overlap_region(ws1, ws2, 1)
        assert (xmin, xmax) == pytest.approx((2, 6))

        # without overlap
        xmin, xmax = _get_stitching_overlap_region(ws1, ws3, 1)
        assert (xmin, xmax) == pytest.approx((5, 7))

        # wrong order
        with pytest.raises(ValueError) as error_info:
            xmin, xmax = _get_stitching_overlap_region(ws2, ws1, 1)
        assert str(error_info.value) == "x-range for ws_lo must not be higher than x-range for ws_hi"

        # delete workspaces
        api.mtd.clear()

    def test_get_polynomial_fit_stitching_scaling_factor(self):
        """Test of helper function _get_polynomial_fit_stitching_scaling_factor

        Tests stitching of two parts of a parabola x^2 with no overlap in the x-range
        """
        rng = np.random.default_rng(745841)

        x1 = np.arange(0, 10)
        y1 = x1**2 + rng.normal(0.0, 0.001)
        ws1 = api.CreateWorkspace(x1, y1)

        expected_scale_factor = 3.2
        x2 = np.arange(12, 20)
        y2 = x2**2 / expected_scale_factor + rng.normal(0.0, 0.001)
        ws2 = api.CreateWorkspace(x2, y2)

        # test expected output
        fit_output = _get_polynomial_fit_stitching_scaling_factor(ws1, ws2, 3, 3)
        assert fit_output["scale_factor_value"] == pytest.approx(expected_scale_factor, abs=1e-3)
        assert fit_output["scale_factor_error"] == pytest.approx(0.26968, abs=1e-3)
        assert fit_output["polynomial_coeff"] == pytest.approx([0.0, 0.0, 1.0, 0.0], abs=1e-2)

        # test exception due to not enough points
        with pytest.raises(RuntimeError) as error_info:
            _get_polynomial_fit_stitching_scaling_factor(ws1, ws2, 5, 3)
        assert "Levenberg-Marquardt minimizer failed to initialize" in str(error_info.value)

    def test_smart_stitch_normalize_to_unity_error(self, stitching_reduction_list):
        """Test that error is raised when the normalize to unity Q cutoff is too low"""
        q_cutoff = 0.5
        with pytest.raises(NormalizeToUnityQCutoffError):
            smart_stitch_reflectivity(stitching_reduction_list, "On_On", True, q_cutoff)


if __name__ == "__main__":
    pytest.main([__file__])
