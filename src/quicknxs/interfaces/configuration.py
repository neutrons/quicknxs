# pylint: disable=invalid-name, line-too-long, too-few-public-methods, too-many-instance-attributes, wrong-import-order, bare-except
"""Application configuration, including reduction options"""

from quicknxs.interfaces.data_handling.instrument import Instrument

# TODO: extract to file based parameter setting
# TODO: add docstring for Configuration attributes


class Configuration(object):
    """Hold reduction options"""

    # Choice of axes for off-specular binning
    QX_VS_QZ = 0
    KZI_VS_KZF = 1
    DELTA_KZ_VS_QZ = 3

    ### Global variables
    sample_size = 10
    use_constant_q = False
    wl_bandwidth = 3.2
    # Final Q rebin global options
    do_final_rebin_global = True
    final_rebin_step_global = -0.01
    # Normalize to unity when stitching
    normalize_to_unity = True
    total_reflectivity_q_cutoff = 0.01
    # Use all cross-sections when stitching
    global_stitching = False
    # Use a polynomial curve fit when stitching
    polynomial_stitching = False
    polynomial_stitching_degree = 3
    polynomial_stitching_points = 3
    # Dead time options
    apply_deadtime = False
    paralyzable_deadtime = True
    deadtime_value = 4.2
    deadtime_tof_step = 100
    # Direct beam uses the same low res roi as the data run
    lock_direct_beam_y = False
    # Number of events below which we throw away a workspace
    nbr_events_min = 100
    # Peak finder options
    use_roi = True
    update_peak_range = False
    use_peak_finder = False
    use_low_res_finder = False
    use_roi_bck = False
    use_tight_bck = False
    bck_offset = 5
    force_bck_roi = True

    @classmethod
    def setup_default_values(cls):
        """Initialize class variables - only used for testing purposes"""
        cls.QX_VS_QZ = 0
        cls.KZI_VS_KZF = 1
        cls.DELTA_KZ_VS_QZ = 3
        cls.sample_size = 10
        cls.use_constant_q = False
        cls.wl_bandwidth = 3.2
        cls.do_final_rebin_global = True
        cls.final_rebin_step_global = -0.01
        cls.normalize_to_unity = True
        cls.total_reflectivity_q_cutoff = 0.01
        cls.global_stitching = False
        cls.polynomial_stitching = False
        cls.polynomial_stitching_degree = 3
        cls.polynomial_stitching_points = 3
        cls.apply_deadtime = False
        cls.paralyzable_deadtime = True
        cls.deadtime_value = 4.2
        cls.deadtime_tof_step = 100
        cls.lock_direct_beam_y = False
        cls.nbr_events_min = 100
        cls.use_roi = True
        cls.update_peak_range = False
        cls.use_peak_finder = False
        cls.use_low_res_finder = False
        cls.use_roi_bck = False
        cls.use_tight_bck = False
        cls.bck_offset = 5
        cls.force_bck_roi = True

    # TODO: settings may not be needed anymore
    def __init__(self, settings=None):
        self.instrument = Instrument()
        # Number of TOF bins
        self.tof_bins = 400
        self.tof_range = None
        # Bin type:
        #    0 = Constant bin width
        #    1 = Constant Q bin width
        #    2 = Constant 1/wavelength bin width
        self.tof_bin_type = 0

        # Threshold under which we skip a cross-section, as fraction of the max count
        self.count_threshold = 0.01
        self.tof_overwrite = None

        # Reduction parameters
        # Use region of interest specified in meta data
        self.set_direct_pixel = False
        self.direct_pixel_overwrite = 0
        self.set_direct_angle_offset = False
        self.direct_angle_offset_overwrite = 0
        self.use_dangle = False

        # Options to override the range
        self.peak_position = 130
        self.peak_width = 20

        self.low_res_position = 130
        self.low_res_width = 20

        self.bck_position = 30
        self.bck_width = 20

        # Subtract background
        self.subtract_background = True
        # Overall scaling factor
        self.scaling_factor = 1.0
        # Error in the scaling factor
        self.scaling_error = 0.0

        # Cut first and last N points
        self.cut_first_n_points = 1
        self.cut_last_n_points = 1

        # Final Rebin run options
        self.do_final_rebin_run = False
        self.final_rebin_step_run = -0.01

        # UI elements
        self.normalize_x_tof = False
        self.x_wl_map = False
        self.angle_map = False
        self.log_1d = True
        self.log_2d = True

        # Off-specular options
        self.off_spec_x_axis = Configuration.DELTA_KZ_VS_QZ
        self.off_spec_slice = False
        self.off_spec_qz_list = []
        self.off_spec_slice_qz_min = 0.05
        self.off_spec_slice_qz_max = 0.07
        self.off_spec_err_weight = False
        self.off_spec_nxbins = 450
        self.off_spec_nybins = 200
        # Off-specular smoothing
        self.apply_smoothing = False
        self.off_spec_sigmas = 3
        self.off_spec_sigmax = 0.0005
        self.off_spec_sigmay = 0.0005
        self.off_spec_x_min = -0.015
        self.off_spec_x_max = 0.015
        self.off_spec_y_min = 0.0
        self.off_spec_y_max = 0.15

        # GISANS options
        self.gisans_wl_min = 2.0
        self.gisans_wl_max = 8.0
        self.gisans_wl_npts = 2
        self.gisans_qy_npts = 50
        self.gisans_qz_npts = 50
        self.gisans_use_pf = False
        self.gisans_slice = False
        self.gisans_slice_qz_min = 0.015
        self.gisans_slice_qz_max = 0.035

        # Reduction options
        self.match_direct_beam = False
        self.normalization = None

    @property
    def peak_roi(self):
        peak_min = int(round(float(self.peak_position) - (float(self.peak_width) / 2.0)))
        peak_max = int(round(float(self.peak_position) + (float(self.peak_width) / 2.0)))
        return [peak_min, peak_max]

    @peak_roi.setter
    def peak_roi(self, value):
        self.peak_position = (value[1] + value[0]) / 2.0
        self.peak_width = value[1] - value[0]

    @property
    def low_res_roi(self):
        peak_min = int(round(float(self.low_res_position) - (float(self.low_res_width) / 2.0)))
        peak_max = int(round(float(self.low_res_position) + (float(self.low_res_width) / 2.0)))
        return [peak_min, peak_max]

    @low_res_roi.setter
    def low_res_roi(self, value):
        self.low_res_position = (value[1] + value[0]) / 2.0
        self.low_res_width = value[1] - value[0]

    @property
    def bck_roi(self):
        peak_min = int(round(float(self.bck_position) - (float(self.bck_width) / 2.0)))
        peak_max = int(round(float(self.bck_position) + (float(self.bck_width) / 2.0)))
        return [peak_min, peak_max]

    @bck_roi.setter
    def bck_roi(self, value):
        self.bck_position = (value[1] + value[0]) / 2.0
        self.bck_width = value[1] - value[0]


def get_direct_beam_low_res_roi(data_conf, direct_beam_conf):
    """
    Get the direct beam low res ROI either from the data run or from the direct beam depending on
    the configuration `lock_direct_beam_y`

    Parameters
    ----------
    data_conf: Configuration
        Configuration for the data run
    direct_beam_conf: Configuration
        Configuration for the direct beam run

    Returns
    -------
    [int, int]
        The pixel range of the direct beam ROI in the low res direction (y)
    """

    def _as_ints(a):
        return [int(round(a[0])), int(round(a[1]))]

    if data_conf.lock_direct_beam_y:
        # use same low res ROI as the data run
        direct_beam_low_res_roi = _as_ints(data_conf.low_res_roi)
    else:
        # use ROI from the direct beam table
        direct_beam_low_res_roi = _as_ints(direct_beam_conf.low_res_roi)
    return direct_beam_low_res_roi
