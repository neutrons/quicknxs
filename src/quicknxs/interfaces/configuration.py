# pylint: disable=invalid-name, line-too-long, too-few-public-methods, too-many-instance-attributes, wrong-import-order, bare-except
"""
Application configuration, including reduction options
"""

import logging

from .data_handling.instrument import Instrument

# TODO extract to file based parameter setting


class Configuration(object):
    """
    Hold reduction options
    """

    # Choice of axes for off-specular binning
    QX_VS_QZ = 0
    KZI_VS_KZF = 1
    DELTA_KZ_VS_QZ = 3

    # Global variables

    wl_bandwidth = 3.2
    use_constant_q = False
    sample_size = 10
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
    # Note: not exposed in the UI, but can be modified in ~/.config/.refredm.conf
    nbr_events_min = 100

    def __init__(self, settings=None):
        self.instrument = Instrument()
        # Number of TOF bins
        self.tof_bins = 400
        self.tof_range = [0, 0]
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
        self.use_roi = True
        self.set_direct_pixel = False
        self.direct_pixel_overwrite = 0
        self.set_direct_angle_offset = False
        self.direct_angle_offset_overwrite = 0
        self.use_dangle = False

        # Update the specular peak range after finding the peak
        # within the ROI
        self.update_peak_range = False

        # Use background specified in the meta data, if available
        self.use_roi_bck = False
        self.use_tight_bck = False
        self.bck_offset = 5

        # Options to override the range
        self.force_peak_roi = False
        self.peak_position = 130
        self.peak_width = 20

        self.force_low_res_roi = False
        self.low_res_position = 130
        self.low_res_width = 20

        self.force_bck_roi = True
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

        if settings is not None:
            try:
                self.from_q_settings(settings)
            except:
                logging.error("Could not process application settings")

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

    def to_q_settings(self, settings):
        """
        Save configuration to QSettings
        :param settings QSettings: QSettings object
        """
        settings.setValue("use_roi", self.use_roi)
        settings.setValue("tof_bins", self.tof_bins)
        settings.setValue("tof_range", ",".join([str(x) for x in self.tof_range]))
        settings.setValue("tof_bin_type", self.tof_bin_type)
        settings.setValue("update_peak_range", self.update_peak_range)
        settings.setValue("use_roi_bck", self.use_roi_bck)
        settings.setValue("use_tight_bck", self.use_tight_bck)
        settings.setValue("bck_offset", self.bck_offset)
        settings.setValue("wl_bandwidth", self.wl_bandwidth)

        settings.setValue("force_peak_roi", self.force_peak_roi)
        settings.setValue("peak_roi", ",".join([str(x) for x in self.peak_roi]))
        settings.setValue("force_low_res_roi", self.force_low_res_roi)
        settings.setValue("low_res_roi", ",".join([str(x) for x in self.low_res_roi]))
        settings.setValue("force_bck_roi", self.force_bck_roi)
        settings.setValue("bck_roi", ",".join([str(x) for x in self.bck_roi]))

        settings.setValue("subtract_background", self.subtract_background)
        settings.setValue("scaling_factor", self.scaling_factor)
        settings.setValue("scaling_error", self.scaling_error)
        settings.setValue("cut_first_n_points", self.cut_first_n_points)
        settings.setValue("cut_last_n_points", self.cut_last_n_points)

        # Normalize to unity when stitching
        settings.setValue("normalize_to_unity", self.normalize_to_unity)
        settings.setValue("total_reflectivity_q_cutoff", self.total_reflectivity_q_cutoff)
        settings.setValue("global_stitching", self.global_stitching)
        settings.setValue("polynomial_stitching", self.polynomial_stitching)
        settings.setValue("polynomial_stitching_degree", self.polynomial_stitching_degree)
        settings.setValue("polynomial_stitching_points", self.polynomial_stitching_points)

        settings.setValue("normalize_x_tof", self.normalize_x_tof)
        settings.setValue("x_wl_map", self.x_wl_map)
        settings.setValue("angle_map", self.angle_map)
        settings.setValue("log_1d", self.log_1d)
        settings.setValue("log_2d", self.log_2d)

        settings.setValue("use_constant_q", self.use_constant_q)
        settings.setValue("use_dangle", self.use_dangle)
        settings.setValue("set_direct_pixel", self.set_direct_pixel)
        settings.setValue("direct_pixel_overwrite", self.direct_pixel_overwrite)
        settings.setValue("set_direct_angle_offset", self.set_direct_angle_offset)
        settings.setValue("direct_angle_offset_overwrite", self.direct_angle_offset_overwrite)
        settings.setValue("sample_size", self.sample_size)
        settings.setValue("do_final_rebin", self.do_final_rebin_global)
        settings.setValue("final_rebin_step", self.final_rebin_step_global)
        settings.setValue("do_final_rebin_run", self.do_final_rebin_run)
        settings.setValue("final_rebin_step_run", self.final_rebin_step_run)
        settings.setValue("lock_direct_beam_y", self.lock_direct_beam_y)

        # Dead time options
        settings.setValue("apply_deadtime", self.apply_deadtime)
        settings.setValue("paralyzable_deadtime", self.paralyzable_deadtime)
        settings.setValue("deadtime_value", self.deadtime_value)
        settings.setValue("deadtime_tof_step", self.deadtime_tof_step)

        # Number of events below which we throw away a workspace
        settings.setValue("nbr_events_min", self.nbr_events_min)

        # Off-specular options
        settings.setValue("off_spec_x_axis", self.off_spec_x_axis)
        settings.setValue("off_spec_slice", self.off_spec_slice)
        settings.setValue("off_spec_qz_list", ",".join([str(x) for x in self.off_spec_qz_list]))
        settings.setValue("off_spec_err_weight", self.off_spec_err_weight)
        settings.setValue("off_spec_nxbins", self.off_spec_nxbins)
        settings.setValue("off_spec_nybins", self.off_spec_nybins)
        settings.setValue("off_spec_slice_qz_min", self.off_spec_slice_qz_min)
        settings.setValue("off_spec_slice_qz_max", self.off_spec_slice_qz_max)

        # Off-specular smoothing
        settings.setValue("apply_smoothing", self.apply_smoothing)
        settings.setValue("off_spec_sigmas", self.off_spec_sigmas)
        settings.setValue("off_spec_sigmax", self.off_spec_sigmax)
        settings.setValue("off_spec_sigmay", self.off_spec_sigmay)
        settings.setValue("off_spec_x_min", self.off_spec_x_min)
        settings.setValue("off_spec_x_max", self.off_spec_x_max)
        settings.setValue("off_spec_y_min", self.off_spec_y_min)
        settings.setValue("off_spec_y_max", self.off_spec_y_max)

        # GISANS options
        settings.setValue("gisans_wl_min", self.gisans_wl_min)
        settings.setValue("gisans_wl_max", self.gisans_wl_max)
        settings.setValue("gisans_wl_npts", self.gisans_wl_npts)
        settings.setValue("gisans_qy_npts", self.gisans_qy_npts)
        settings.setValue("gisans_qz_npts", self.gisans_qz_npts)
        settings.setValue("gisans_use_pf", self.gisans_use_pf)
        settings.setValue("gisans_slice", self.gisans_slice)
        settings.setValue("gisans_slice_qz_min", self.gisans_slice_qz_min)
        settings.setValue("gisans_slice_qz_max", self.gisans_slice_qz_max)

    def from_q_settings(self, settings):
        """Retrieve configuration from QSettings"""

        def _verify_true(parameter, default):
            """Utility function to read a bool"""
            _value = settings.value(parameter, str(default))
            return str(_value).lower() == "true"

        self.use_roi = _verify_true("use_roi", self.use_roi)
        # self.tof_bins = int(settings.value('tof_bins', self.tof_bins))
        self.tof_range = [float(x) for x in settings.value("tof_range", [0, 0]).split(",")]
        self.tof_bin_type = int(settings.value("tof_bin_type", self.tof_bin_type))
        self.update_peak_range = _verify_true("update_peak_range", self.update_peak_range)
        self.use_roi_bck = _verify_true("use_roi_bck", self.use_roi_bck)
        self.use_tight_bck = _verify_true("use_tight_bck", self.use_tight_bck)
        self.bck_offset = int(settings.value("bck_offset", self.bck_offset))
        Configuration.wl_bandwidth = float(settings.value("wl_bandwidth", self.wl_bandwidth))

        self.force_peak_roi = _verify_true("force_peak_roi", self.force_peak_roi)
        self.force_low_res_roi = _verify_true("force_low_res_roi", self.force_low_res_roi)
        self.force_bck_roi = _verify_true("force_bck_roi", self.force_bck_roi)

        default = ",".join([str(x) for x in self.peak_roi])
        self.peak_roi = [int(x) for x in settings.value("peak_roi", default).split(",")]
        default = ",".join([str(x) for x in self.low_res_roi])
        self.low_res_roi = [int(x) for x in settings.value("low_res_roi", default).split(",")]
        default = ",".join([str(x) for x in self.bck_roi])
        self.bck_roi = [int(x) for x in settings.value("bck_roi", default).split(",")]

        self.subtract_background = _verify_true("subtract_background", self.subtract_background)
        self.scaling_factor = float(settings.value("scaling_factor", self.scaling_factor))
        self.scaling_error = float(settings.value("scaling_error", self.scaling_error))
        self.cut_first_n_points = int(settings.value("cut_first_n_points", self.cut_first_n_points))
        self.cut_last_n_points = int(settings.value("cut_last_n_points", self.cut_last_n_points))

        # Normalize to unity when stitching
        Configuration.normalize_to_unity = _verify_true("normalize_to_unity", self.normalize_to_unity)
        Configuration.total_reflectivity_q_cutoff = float(
            settings.value("total_reflectivity_q_cutoff", self.total_reflectivity_q_cutoff)
        )
        Configuration.global_stitching = _verify_true("global_stitching", self.global_stitching)
        Configuration.polynomial_stitching = _verify_true("polynomial_stitching", self.polynomial_stitching)
        Configuration.polynomial_stitching_degree = int(
            settings.value("polynomial_stitching_degree", self.polynomial_stitching_degree)
        )
        Configuration.polynomial_stitching_points = int(
            settings.value("polynomial_stitching_points", self.polynomial_stitching_points)
        )

        self.normalize_x_tof = _verify_true("normalize_x_tof", self.normalize_x_tof)
        self.x_wl_map = _verify_true("x_wl_map", self.x_wl_map)
        self.angle_map = _verify_true("angle_map", self.angle_map)
        self.log_1d = _verify_true("log_1d", self.log_1d)
        self.log_2d = _verify_true("log_2d", self.log_2d)

        Configuration.use_constant_q = _verify_true("use_constant_q", self.use_constant_q)
        self.use_dangle = _verify_true("use_dangle", self.use_dangle)
        self.set_direct_pixel = _verify_true("set_direct_pixel", self.set_direct_pixel)
        self.direct_pixel_overwrite = float(settings.value("direct_pixel_overwrite", self.direct_pixel_overwrite))
        self.set_direct_angle_offset = _verify_true("set_direct_angle_offset", self.set_direct_angle_offset)
        self.direct_angle_offset_overwrite = float(
            settings.value("direct_angle_offset_overwrite", self.direct_angle_offset_overwrite)
        )
        Configuration.sample_size = float(settings.value("sample_size", self.sample_size))
        Configuration.do_final_rebin_global = _verify_true("do_final_rebin", self.do_final_rebin_global)
        Configuration.final_rebin_step_global = float(settings.value("final_rebin_step", self.final_rebin_step_global))
        self.do_final_rebin_run = _verify_true("do_final_rebin_run", self.do_final_rebin_run)
        self.final_rebin_step_run = float(settings.value("final_rebin_step_run", self.final_rebin_step_run))
        Configuration.lock_direct_beam_y = _verify_true("lock_direct_beam_y", self.lock_direct_beam_y)

        # Dead time options
        Configuration.apply_deadtime = _verify_true("apply_deadtime", self.apply_deadtime)
        Configuration.paralyzable_deadtime = _verify_true("paralyzable_deadtime", self.paralyzable_deadtime)
        Configuration.deadtime_value = float(settings.value("deadtime_value", self.deadtime_value))
        Configuration.deadtime_tof_step = float(settings.value("deadtime_tof_step", self.deadtime_tof_step))

        # Number of events below which we throw away a workspace
        Configuration.nbr_events_min = int(settings.value("nbr_events_min", self.nbr_events_min))

        # Off-specular options
        self.off_spec_x_axis = int(settings.value("off_spec_x_axis", self.off_spec_x_axis))
        self.off_spec_slice = _verify_true("off_spec_slice", self.off_spec_slice)
        default = ",".join([str(x) for x in self.off_spec_qz_list])
        try:
            self.off_spec_qz_list = [float(x) for x in settings.value("off_spec_qz_list", default).split(",")]
        except:
            self.off_spec_qz_list = []
        self.off_spec_err_weight = _verify_true("off_spec_err_weight", self.off_spec_err_weight)
        self.off_spec_nxbins = int(settings.value("off_spec_nxbins", self.off_spec_nxbins))
        self.off_spec_nybins = int(settings.value("off_spec_nybins", self.off_spec_nybins))
        self.off_spec_slice_qz_min = float(settings.value("off_spec_slice_qz_min", self.off_spec_slice_qz_min))
        self.off_spec_slice_qz_max = float(settings.value("off_spec_slice_qz_max", self.off_spec_slice_qz_max))

        # Off-specular smoothing
        self.apply_smoothing = _verify_true("apply_smoothing", self.apply_smoothing)
        self.off_spec_sigmas = int(settings.value("off_spec_sigmas", self.off_spec_sigmas))
        self.off_spec_sigmax = float(settings.value("off_spec_sigmax", self.off_spec_sigmax))
        self.off_spec_sigmay = float(settings.value("off_spec_sigmay", self.off_spec_sigmay))
        self.off_spec_x_min = float(settings.value("off_spec_x_min", self.off_spec_x_min))
        self.off_spec_x_max = float(settings.value("off_spec_x_max", self.off_spec_x_max))
        self.off_spec_y_min = float(settings.value("off_spec_y_min", self.off_spec_y_min))
        self.off_spec_y_max = float(settings.value("off_spec_y_max", self.off_spec_y_max))

        # GISANS options
        self.gisans_wl_min = float(settings.value("gisans_wl_min", self.gisans_wl_min))
        self.gisans_wl_max = float(settings.value("gisans_wl_max", self.gisans_wl_max))
        self.gisans_wl_npts = int(settings.value("gisans_wl_npts", self.gisans_wl_npts))
        self.gisans_qy_npts = int(settings.value("gisans_qy_npts", self.gisans_qy_npts))
        self.gisans_qz_npts = int(settings.value("gisans_qz_npts", self.gisans_qz_npts))
        self.gisans_use_pf = _verify_true("gisans_use_pf", self.gisans_use_pf)

        self.gisans_slice = _verify_true("gisans_slice", self.gisans_slice)
        self.gisans_slice_qz_min = float(settings.value("gisans_slice_qz_min", self.gisans_slice_qz_min))
        self.gisans_slice_qz_max = float(settings.value("gisans_slice_qz_max", self.gisans_slice_qz_max))

    @classmethod
    def setup_default_values(cls):
        cls.QX_VS_QZ = 0
        cls.KZI_VS_KZF = 1
        cls.DELTA_KZ_VS_QZ = 3
        cls.wl_bandwidth = 3.2
        cls.use_constant_q = False
        cls.sample_size = 10
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
