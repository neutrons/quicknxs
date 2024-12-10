"""
    Loader for event nexus files.
    Uses Mantid Framework
"""
# pylint: disable=invalid-name, too-many-instance-attributes, line-too-long, multiple-statements, bare-except, wrong-import-order, \
# too-many-locals, too-few-public-methods, wrong-import-position, too-many-public-methods


# local imports
from reflectivity_ui.interfaces.configuration import get_direct_beam_low_res_roi
from reflectivity_ui.interfaces.data_handling.filepath import FilePath
from reflectivity_ui.interfaces.data_handling.data_info import DataInfo
from reflectivity_ui.interfaces.data_handling.gisans import GISANS
from reflectivity_ui.interfaces.data_handling.off_specular import OffSpecular

# 3rd-party imports
import numpy as np

# standard imports
from collections import OrderedDict
import copy
import logging
import math
import sys
import traceback
import time
from typing import Union

import mantid.simpleapi as api
from mantid.dataobjects import Workspace2D

# Set Mantid logging level to warnings
api.ConfigService.setLogLevel(3)

# Parameters needed for some calculations.
H_OVER_M_NEUTRON = 3.956034e-7  # h/m_n [m^2/s]

# Number of events under which we throw away a workspace
# TODO: This should be a parameter
N_EVENTS_CUTOFF = 100

# If there's an empty reflectivity curve, add a small value to it so that it can be plotted.
REFLECTIVITY_THRESHOLD_VALUE = 1e-6


def _is_empty_reflectivity_curve(input_workspace: Union[str, Workspace2D]) -> bool:
    r"""
    Check that the reflectivity values are not all zero.

    Parameters
    ----------
    input_workspace
        Reflectivity workspace with only one spectrum.

    Returns
    -------
    True if all reflectivity values are zero, False otherwise.
    """
    workspace = api.mtd[str(input_workspace)]
    return np.all(workspace.readY(0) < REFLECTIVITY_THRESHOLD_VALUE)


def _shift_empty_reflectivity_curve(
    input_workspace: Union[str, Workspace2D], shift=REFLECTIVITY_THRESHOLD_VALUE
) -> None:
    r"""
    Shift the reflectivity values by a small amount so that it can be plotted.

    Parameters
    ----------
    input_workspace
        Reflectivity workspace with only one spectrum.
    """
    workspace = api.mtd[str(input_workspace)]
    workspace.dataY(0)[:] += shift
    workspace.dataE(0)[:] += shift**2  # arbitrary small error


def getIxyt(nxs_data):
    """
    Return [x, y, TOF] array
    @param nxs_data: Mantid workspace
    """
    _tof_axis = nxs_data.readX(0)[:].copy()
    nbr_tof = len(_tof_axis)

    sz_y_axis = int(nxs_data.getInstrument().getNumberParameter("number-of-y-pixels")[0])  # 256
    sz_x_axis = int(nxs_data.getInstrument().getNumberParameter("number-of-x-pixels")[0])  # 304

    _y_axis = np.zeros((sz_x_axis, sz_y_axis, nbr_tof - 1))
    _y_error_axis = np.zeros((sz_x_axis, sz_y_axis, nbr_tof - 1))

    for x in range(sz_x_axis):
        for y in range(sz_y_axis):
            _index = int(sz_y_axis * x + y)
            _y_axis[x, y, :] = nxs_data.readY(_index)[:]
            _y_error_axis[x, y, :] = nxs_data.readE(_index)[:]

    return _y_axis, _y_error_axis


class NexusData(object):
    """
    Read a nexus file with multiple cross-section data.
    """

    def __init__(self, file_path, configuration):
        # type: (unicode, Configuration) -> None
        """
        @brief Structure to read in one or more Nexus data files
        @param file_path: absolute path to one or more files. If more than one, paths are concatenated with the
        plus symbol '+'
        @param configuration: reduction configurations
        """
        self.file_path = FilePath(file_path).path  # sort the paths if more than one
        self.number = ""  # can be a singe number (e.g. '1234') or a composite (e.g '1234:1239+1245')
        self.configuration = configuration
        self.cross_sections = {}
        self.main_cross_section = None

    def get_highest_cross_section(self, n_points=10):
        """
        Get the cross-section with the largest signal at the
        lower end of its Q range.
        :param int n_points: number of points to average over
        """
        n_events = 0
        large_xs = None
        for xs in self.cross_sections:
            if self.cross_sections[xs].raw_r is not None:
                _r = self.cross_sections[xs].raw_r
                _dr = self.cross_sections[xs].raw_dr
                npts = min(len(_r), n_points)
                _n_events = np.sum(_r[:npts] / _dr[:npts] ** 2) / np.sum(1 / _dr[:npts] ** 2)
                if _n_events > n_events:
                    n_events = _n_events
                    large_xs = xs
        return large_xs

    def get_q_range(self):
        """
        Return the Q range for the cross-sections
        """
        q_min = None
        q_max = None
        for xs in self.cross_sections:
            if self.cross_sections[xs].q is not None:
                if q_min is None:
                    q_min = self.cross_sections[xs].q.min()
                    q_max = self.cross_sections[xs].q.max()
                else:
                    q_min = min(q_min, self.cross_sections[xs].q.min())
                    q_max = max(q_max, self.cross_sections[xs].q.max())
        return q_min, q_max

    def get_reflectivity_workspace_group(self):
        ws_list = [self.cross_sections[xs]._reflectivity_workspace for xs in self.cross_sections]
        wsg = api.GroupWorkspaces(InputWorkspaces=ws_list)
        return wsg

    def set_parameter(self, param, value):
        """
        Loop through the cross-section data sets and update
        a parameter.
        """
        has_changed = False
        try:
            for xs in self.cross_sections:
                if hasattr(self.cross_sections[xs].configuration, param):
                    if not getattr(self.cross_sections[xs].configuration, param) == value:
                        setattr(self.cross_sections[xs].configuration, param, value)
                        has_changed = True
        except:
            logging.error("Could not set parameter %s %s", param, value)
        return has_changed

    def calculate_reflectivity(self, direct_beam=None, configuration=None, ws_suffix: str = ""):
        """
        Loop through the cross-section data sets and update
        the reflectivity.

        Parameters
        ----------
        direct_beam: CrossSectionData | None
            Direct beam data
        configuration: Configuration | None
            The configuration
        ws_suffix: str
            String to add to reflectivity workspace name

        Example
        -------
        `ws_suffix` is used when reducing multiple ROIs for the same run and cross-section, to
        differentiate the workspace names in the Mantid data service

        peak_index = 2
        # update the active reduction list
        data_manager.set_active_reduction_list_index(peak_index)
        # get the first data set of the active reduction list
        nexus_data = data_manager.reduction_list[0]
        # calculate the reflectivity for this data set
        nexus_data.calculate_reflectivity(ws_suffix=str(peak_index))
        """
        if configuration is not None:
            self.configuration = copy.deepcopy(configuration)

        if self.configuration is None:
            return

        # If a direct beam object was passed, use it.
        apply_norm = direct_beam is not None  # and not self.is_direct_beam
        if not apply_norm:
            direct_beam = CrossSectionData("none", self.configuration, "none")

        logging.info(
            "%s Reduction with DB: %s [config: %s]", self.number, direct_beam.number, self.configuration.normalization
        )
        angle_offset = 0  # Offset from dangle0, in radians

        def _as_ints(a):
            return [int(round(a[0])), int(round(a[1])) - 1]

        output_ws = "r%s" % self.number

        ws_norm = None
        if apply_norm and direct_beam._event_workspace is not None:
            ws_norm = direct_beam._event_workspace

        ws_list = [self.cross_sections[xs]._event_workspace for xs in self.cross_sections]
        conf = self.cross_sections[self.main_cross_section].configuration
        wsg = api.GroupWorkspaces(InputWorkspaces=ws_list)

        _dirpix = conf.direct_pixel_overwrite if conf.set_direct_pixel else None
        _dangle0 = conf.direct_angle_offset_overwrite if conf.set_direct_angle_offset else None

        direct_beam_low_res_roi = get_direct_beam_low_res_roi(conf, direct_beam.configuration)

        # The reduced data workspace may be a group or a single
        # workspace depending on the InputWorkspace parameter
        ws = api.MagnetismReflectometryReduction(
            InputWorkspace=wsg,
            NormalizationWorkspace=ws_norm,
            SignalPeakPixelRange=_as_ints(conf.peak_roi),
            SubtractSignalBackground=conf.subtract_background,
            SignalBackgroundPixelRange=_as_ints(conf.bck_roi),
            ApplyNormalization=apply_norm,
            NormPeakPixelRange=_as_ints(direct_beam.configuration.peak_roi),
            SubtractNormBackground=conf.subtract_background,
            NormBackgroundPixelRange=_as_ints(direct_beam.configuration.bck_roi),
            CutLowResDataAxis=True,
            LowResDataAxisPixelRange=_as_ints(conf.low_res_roi),
            CutLowResNormAxis=True,
            LowResNormAxisPixelRange=direct_beam_low_res_roi,
            CutTimeAxis=True,
            FinalRebin=conf.do_final_rebin,
            QMin=0.001,
            QStep=conf.final_rebin_step,
            RoundUpPixel=False,
            AngleOffset=angle_offset,
            UseWLTimeAxis=False,
            TimeAxisStep=conf.tof_bins,
            UseSANGLE=not conf.use_dangle,
            TimeAxisRange=conf.tof_range,
            SpecularPixel=conf.peak_position,
            ConstantQBinning=conf.use_constant_q,
            ConstQTrim=0.1,
            CropFirstAndLastPoints=False,
            CleanupBadData=conf.do_final_rebin,
            AcceptNullReflectivity=True,  # return empty reflectivity curves (all intensities are zero)
            ErrorWeightedBackground=False,
            SampleLength=conf.sample_size,
            DAngle0Overwrite=_dangle0,
            DirectPixelOverwrite=_dirpix,
            OutputWorkspace=output_ws,
        )

        # If there's an empty reflectivity curve, add a small value to it so that it can be plotted.
        _xs_ws = [ws] if isinstance(ws, Workspace2D) else ws
        for i in range(len(ws_list)):
            if _is_empty_reflectivity_curve(_xs_ws[i]):
                _shift_empty_reflectivity_curve(_xs_ws[i])

        # FOR COMPATIBILITY WITH QUICKNXS #
        _ws = ws[0] if len(ws_list) > 1 else ws
        run_object = _ws.getRun()
        peak_min = run_object.getProperty("scatt_peak_min").value
        peak_max = run_object.getProperty("scatt_peak_max").value + 1.0
        low_res_min = run_object.getProperty("scatt_low_res_min").value
        low_res_max = run_object.getProperty("scatt_low_res_max").value + 1.0
        norm_x_min = run_object.getProperty("norm_peak_min").value
        norm_x_max = run_object.getProperty("norm_peak_max").value + 1.0
        norm_y_min = run_object.getProperty("norm_low_res_min").value
        norm_y_max = run_object.getProperty("norm_low_res_max").value + 1.0
        tth = run_object.getProperty("two_theta").value * math.pi / 360.0
        quicknxs_scale = (float(norm_x_max) - float(norm_x_min)) * (float(norm_y_max) - float(norm_y_min))
        quicknxs_scale /= (float(peak_max) - float(peak_min)) * (float(low_res_max) - float(low_res_min))
        logging.warning("Scale size = %s", str(quicknxs_scale))
        logging.warning("Alpha_i = %s", str(tth))
        _scale = 0.005 / math.sin(tth) if tth > 0.0002 else 1.0
        quicknxs_scale *= _scale

        ws = api.Scale(
            InputWorkspace=output_ws, OutputWorkspace=output_ws, factor=quicknxs_scale, Operation="Multiply"
        )
        _ws = ws if len(ws_list) > 1 else [ws]
        for xs in _ws:
            # add suffix to avoid overwriting ws in mantid data service, needed for multiple peaks
            api.RenameWorkspace(str(xs), str(xs) + ws_suffix)
            xs_id = xs.getRun().getProperty("cross_section_id").value
            self.cross_sections[xs_id].q = xs.readX(0)[:].copy()
            self.cross_sections[xs_id]._r = np.ma.masked_equal(xs.readY(0)[:].copy(), 0)
            self.cross_sections[xs_id]._dr = np.ma.masked_equal(xs.readE(0)[:].copy(), 0)
            self.cross_sections[xs_id]._reflectivity_workspace = str(xs)

    def calculate_gisans(self, direct_beam, progress=None):
        """
        Compute GISANS
        """
        has_errors = False
        detailed_msg = ""
        if progress is not None:
            progress(1, "Computing GISANS", out_of=100.0)
        for i, xs in enumerate(self.cross_sections):
            try:
                self.cross_sections[xs].gisans(direct_beam=direct_beam)
            except:
                has_errors = True
                detailed_msg += "Could not calculate GISANS reflectivity for %s\n  %s\n\n" % (
                    xs,
                    traceback.format_exc(),
                )
                logging.error("Could not calculate GISANS reflectivity for %s", xs)
            if progress:
                progress(i, message="Computed GISANS %s" % xs, out_of=len(self.cross_sections))
        if has_errors:
            raise RuntimeError(detailed_msg)
        if progress is not None:
            progress(100, "Complete", out_of=100.0)

    def is_offspec_available(self):
        """
        Verify whether we have off-specular data calculated for all cross-sections
        """
        for xs in self.cross_sections:
            if self.cross_sections[xs].off_spec is None:
                return False
        return True

    def is_gisans_available(self):
        """
        Verify whether we have GISANS data calculated for all cross-sections
        """
        for xs in self.cross_sections:
            if self.cross_sections[xs].gisans_data is None:
                return False
        return True

    def calculate_offspec(self, direct_beam=None):
        """
        Loop through the cross-section data sets and update
        the reflectivity.
        """
        has_errors = False
        detailed_msg = ""
        for xs in self.cross_sections:
            try:
                self.cross_sections[xs].offspec(direct_beam=direct_beam)
            except Exception:
                has_errors = True
                detailed_msg += "Could not calculate off-specular reflectivity for %s\n  %s\n\n" % (
                    xs,
                    traceback.format_exc(),
                )
                logging.error(detailed_msg)
        if has_errors:
            raise RuntimeError(detailed_msg)

    def update_configuration(self, configuration):
        """
        Loop through the cross-section data sets and update
        the reflectivity.
        """
        for xs in self.cross_sections:
            try:
                self.cross_sections[xs].update_configuration(configuration)
            except:
                logging.error("Could not update configuration for %s", xs)

    def update_calculated_values(self):
        """
        Loop through the cross-section data sets and update.
        """
        for xs in self.cross_sections:
            self.cross_sections[xs].update_calculated_values()

    def load(self, update_parameters=True, progress=None):
        """
        Load cross-sections from a nexus file.
        :param function progress: call-back function to track progress
        :param bool update_parameters: if True, we will find peak ranges
        """
        # sanity check
        if self.file_path is None:
            raise RuntimeError("self.file_path is None")

        self.cross_sections = OrderedDict()
        if progress is not None:
            progress(5, "Filtering data...", out_of=100.0)

        try:
            xs_list = self.configuration.instrument.load_data(self.file_path, self.configuration)
            logging.info("%s loaded: %s xs", self.file_path, len(xs_list))
        except RuntimeError as run_err:
            logging.error("Could not load file(s) {}\n   {}".format(str(self.file_path), run_err))
            return self.cross_sections

        progress_value = 0
        # Keep track of cross-section with max counts so we can use it to
        # select peak regions
        _max_counts = 0
        _max_xs = None
        _loaded_with_getDI = False
        for ws in xs_list:
            # Get the unique name for the cross-section, determined by the filtering
            channel = ws.getRun().getProperty("cross_section_id").value
            if ws.getRun().hasProperty("loaded_with_getDI"):
                _loaded_with_getDI = True
            if progress is not None:
                progress_value += int(100.0 / len(xs_list))
                progress(progress_value, "Loading %s..." % str(channel), out_of=100.0)

            # Get rid of empty workspaces
            logging.info("Loading %s: %s events", str(channel), ws.getNumberEvents())
            if ws.getNumberEvents() < N_EVENTS_CUTOFF:
                logging.warning("Too few events for %s: %s", channel, ws.getNumberEvents())
                continue

            name = ws.getRun().getProperty("cross_section_id").value
            cross_section = CrossSectionData(name, self.configuration, entry_name=channel, workspace=ws)
            self.cross_sections[name] = cross_section
            self.number = cross_section.number  # e.g '1234:1238+1239' if more than one run made up this cross section
            if cross_section.total_counts > _max_counts:
                _max_counts = cross_section.total_counts
                _max_xs = name

        # Now that we know which cross section has the most data,
        # use that one to get the reduction parameters
        self.main_cross_section = _max_xs
        self.cross_sections[_max_xs].get_reduction_parameters(update_parameters=update_parameters)

        # Push the configuration (reduction options and peak regions) from the
        # cross-section with the most data to all other cross-sections.
        for xs in self.cross_sections:
            if xs == _max_xs:
                continue
            self.cross_sections[xs].update_configuration(self.cross_sections[_max_xs].configuration)

        if progress is not None:
            progress(100, "Complete", out_of=100.0)
            if _loaded_with_getDI:
                progress(100, "WARNING: Analyzer/polarizer states not available - loaded with getDI", out_of=100.0)

        return self.cross_sections

    def is_direct_beam(self):
        """Returns True if the main cross-section is a direct beam"""
        return self.cross_sections[self.main_cross_section].is_direct_beam


class CrossSectionData(object):
    """
    Data object to hold loaded reflectivity data
    """

    # Instrument specific attributes filled out by the instrument object
    dist_sam_det = 0
    dist_mod_det = 0
    dist_mod_mon = 0
    dist_mod_mon = 0
    dist_mod_mon = 0
    dangle = 0
    dangle0 = 0
    det_size_x = 0.0007
    det_size_y = 0.0007
    lambda_center = 0

    def __init__(self, name, configuration, entry_name="entry", workspace=None):
        self.name = name
        self.entry_name = entry_name
        self.cross_section_label = entry_name
        self.measurement_type = "polarized"
        self.configuration = copy.deepcopy(configuration)
        self.number = ""  # can be singe number (e.g. '1234') or a composite (e.g '1234:1239+1245')
        self.q = None
        self._r = None
        self._dr = None
        self._event_workspace = None
        # Flag to tell us whether we succeeded in using the meta data ROI
        self.use_roi_actual = True
        # Flag to tell us whether we found this data to be a direct beam data set
        self.is_direct_beam = False
        self._active_area_x = None
        self._active_area_y = None
        self.logs = {}
        self.log_minmax = {}
        self.log_units = {}
        self.proton_charge = 0
        self.total_counts = 0
        self.total_time = 0

        self.experiment = ""
        self.merge_warnings = ""
        self.tof_edges = None

        # Data used for plotting
        self.data = None
        self.xydata = None
        self.xtofdata = None
        self.raw_error = None

        self.meta_data_roi_peak = None
        self.meta_data_roi_bck = None
        self._direct_pixel = 0
        self._angle_offset = 0
        self.scattering_angle = 0
        self._reflectivity_workspace = None

        # Offset data
        self.off_spec = None

        # GISANS data
        self.gisans_data = None

        if workspace:
            self.collect_info(workspace)

    # Properties for easy data access #
    # return the size of the data stored in memory for this dataset
    # pylint: disable=missing-docstring
    @property
    def event_workspace(self):
        if str(self._event_workspace) in api.mtd:
            return api.mtd[self._event_workspace]
        return None

    @property
    def reflectivity_workspace(self):
        if str(self._reflectivity_workspace) in api.mtd:
            return api.mtd[self._reflectivity_workspace]
        return None

    @property
    def dpix(self):
        logging.error("CrossSectionData.dpix is deprecated")
        return self.direct_pixel

    @property
    def dangle0(self):
        logging.error("CrossSectionData.dangle0 is deprecated")
        return self.angle_offset

    @property
    def direct_pixel(self):
        if self.configuration.set_direct_pixel:
            return self.configuration.direct_pixel_overwrite
        return self._direct_pixel

    @direct_pixel.setter
    def direct_pixel(self, value):
        self._direct_pixel = value

    @property
    def angle_offset(self):
        if self.configuration.set_direct_angle_offset:
            return self.configuration.direct_angle_offset_overwrite
        return self._angle_offset

    @angle_offset.setter
    def angle_offset(self, value):
        self._angle_offset = value

    @property
    def xdata(self):
        return self.xydata.mean(axis=0)

    @property
    def ydata(self):
        return self.xydata.mean(axis=1)

    @property
    def tofdata(self):
        return self.xtofdata.mean(axis=0)

    # coordinates corresponding to the data items
    @property
    def x(self):
        return np.arange(self.xydata.shape[1])

    @property
    def y(self):
        return np.arange(self.xydata.shape[0])

    @property
    def xy(self):
        return np.meshgrid(self.x, self.y)

    @property
    def tof(self):
        return (self.tof_edges[:-1] + self.tof_edges[1:]) / 2.0

    @property
    def xtof(self):
        return np.meshgrid(self.tof, self.x)

    @property
    def r(self):
        if self._r is None:
            return None
        return self._r * self.configuration.scaling_factor

    @property
    def raw_r(self):
        return self._r

    @property
    def raw_dr(self):
        return self._dr

    @property
    def dr(self):
        if self._dr is None:
            return None
        return np.sqrt(
            (self._dr * self.configuration.scaling_factor) ** 2 + (self.configuration.scaling_error * self._r) ** 2
        )

    @property
    def wavelength_range(self):
        """
        Returns the wavelength range
        """
        # TODO: use the skipped points to trim the wl band.
        # The following would work, but not if we perform a final rebin.
        # We should use the final Q binning to determine the wl range.
        # That's because we cut points in Q, but it has to be consistent
        # throughout the application even when wavelength is plotted.
        # PN = len(self.tof)-self.configuration.cut_first_n_points-1
        # P0 = self.configuration.cut_last_n_points

        wl_min = H_OVER_M_NEUTRON / self.dist_mod_det * self.tof[0] * 1.0e4
        wl_max = H_OVER_M_NEUTRON / self.dist_mod_det * self.tof[-1] * 1.0e4
        return wl_min, wl_max

    @property
    def wavelength(self):
        h = 6.626e-34  # m^2 kg s^-1
        m = 1.675e-27  # kg
        v_n = self.dist_mod_det / self.tof * 1e6  # m/s
        return h / m / v_n * 1e10  # A

    @property
    def active_area_x(self):
        if self._active_area_x is None:
            return (0, self.xydata.shape[0])
        return self._active_area_x

    @active_area_x.setter
    def active_area_x(self, value):
        self._active_area_x = value

    @property
    def active_area_y(self):
        if self._active_area_y is None:
            return (0, self.xydata.shape[1])
        return self._active_area_y

    @active_area_y.setter
    def active_area_y(self, value):
        self._active_area_y = value

    # pylint: enable=missing-docstring
    # Properties for easy data access #
    def collect_info(self, workspace):
        """
        Extract meta data from DASLogs.

        TODO: get average of values post filtering so that it truly represents the data
        """
        self._event_workspace = str(workspace)
        data = workspace.getRun()
        self.logs = {}
        self.log_minmax = {}
        self.log_units = {}

        for motor in data.keys():
            if motor in ["proton_charge", "frequency", "Veto_pulse"]:
                continue
            item = data[motor]
            try:
                self.log_units[motor] = str(item.units)
                if item.type == "string":
                    pass
                    # self.logs[motor] = item.value
                    # self.log_minmax[motor] = (item.value, item.value)
                elif item.type == "number":
                    self.logs[motor] = np.float64(item.value)
                    self.log_minmax[motor] = (np.float64(item.value), np.float64(item.value))
                else:
                    stats = item.getStatistics()
                    self.logs[motor] = np.float64(stats.mean)
                    self.log_minmax[motor] = (np.float64(stats.minimum), np.float64(stats.maximum))
            except:
                logging.error("Error reading DASLogs %s", motor)

        self.proton_charge = data["gd_prtn_chrg"].value
        self.total_counts = workspace.getNumberEvents()
        self.total_time = data["duration"].value

        self.experiment = str(data["experiment_identifier"].value)
        self.number = workspace.getRun().getProperty("run_numbers").value
        self.merge_warnings = ""

        # Retrieve instrument-specific information
        self.configuration.instrument.get_info(workspace, self)

    def process_configuration(self):
        """
        Process loaded data
        :param bool update_parameters: If true, we will determine reduction parameters
        """
        self.scattering_angle = self.configuration.instrument.scattering_angle_from_data(self)

        # Determine binning
        # TODO: only the TOF binning is implemented
        if self.configuration.tof_overwrite is not None:
            tof_edges = self.configuration.tof_overwrite
        else:
            if self.configuration.tof_bin_type == 1:  # constant Q
                tof_edges = 1.0 / np.linspace(
                    1.0 / self.configuration.tof_range[0],
                    1.0 / self.configuration.tof_range[1],
                    self.configuration.tof_bins + 1,
                )
            elif self.configuration.tof_bin_type == 2:  # constant 1/wavelength
                tof_edges = self.configuration.tof_range[0] * (
                    (
                        (self.configuration.tof_range[1] / self.configuration.tof_range[0])
                        ** (1.0 / self.configuration.tof_bins)
                    )
                    ** np.arange(self.configuration.tof_bins + 1)
                )
            else:
                tof_edges = np.arange(
                    self.configuration.tof_range[0], self.configuration.tof_range[1], self.configuration.tof_bins
                )
        self.tof_edges = tof_edges

    def prepare_plot_data(self):
        """
        Bin events to be used for plotting and in-app calculations
        """
        workspace = api.mtd[self._event_workspace]
        if self.xtofdata is None:
            t_0 = time.time()
            binning_ws = api.CreateWorkspace(DataX=self.tof_edges, DataY=np.zeros(len(self.tof_edges) - 1))
            data_rebinned = api.RebinToWorkspace(WorkspaceToRebin=workspace, WorkspaceToMatch=binning_ws)
            Ixyt, Ixyt_error = getIxyt(data_rebinned)

            # Create projections for the 2D datasets
            Ixy = Ixyt.sum(axis=2)
            Ixt = Ixyt.sum(axis=1)
            # Store the data
            self.data = Ixyt.astype(float)  # 3D dataset
            self.raw_error = Ixyt_error.astype(float)  # 3D dataset
            self.xydata = Ixy.transpose().astype(float)  # 2D dataset
            self.xtofdata = Ixt.astype(float)  # 2D dataset
            logging.info("Plot data generated: %s sec", time.time() - t_0)

    def get_reduction_parameters(self, update_parameters=True):
        """
        Determine reduction parameter
        :param bool update_parameters: if True, we will find peak ranges
        """
        workspace = api.mtd[self._event_workspace]
        data_info = DataInfo(workspace, self.name, self.configuration)
        self.configuration.tof_range = data_info.tof_range
        if update_parameters:
            # data_info = DataInfo(workspace, self.name, self.configuration)
            self.use_roi_actual = data_info.use_roi_actual
            self.is_direct_beam = data_info.is_direct_beam

            self.meta_data_roi_peak = data_info.roi_peak
            self.meta_data_roi_bck = data_info.roi_background

            if not self.configuration.force_peak_roi:
                self.configuration.peak_roi = data_info.peak_range

            if not self.configuration.force_low_res_roi:
                self.configuration.low_res_roi = data_info.low_res_range

            if self.configuration.force_bck_roi:
                self.configuration.bck_roi = data_info.background
        self.configuration.bck_roi = data_info.background
        self.process_configuration()

    def get_counts_vs_TOF(self):
        """
        Used for normalization, returns ROI counts vs TOF.
        """
        self.prepare_plot_data()
        # Calculate ROI intensities and normalize by number of points
        raw_data = self.data[
            self.configuration.peak_roi[0] : self.configuration.peak_roi[1],
            self.configuration.low_res_roi[0] : self.configuration.low_res_roi[1],
            :,
        ]
        size_roi = float(
            (self.configuration.low_res_roi[1] - self.configuration.low_res_roi[0])
            * (self.configuration.peak_roi[1] - self.configuration.peak_roi[0])
        )
        summed_raw = raw_data.sum(axis=0).sum(axis=0)

        # Remove the background
        bck = self.get_background_vs_TOF()

        return (summed_raw / math.fabs(size_roi) - bck) / self.proton_charge

    def get_tof_counts_table(self):
        """
        Get a table of TOF vs counts in the region-of-interest (ROI)

        The table columns are:
        - TOF
        - wavelength
        - counts normalized by proton charge
        - error in counts normalized by proton charge
        - counts
        - error in counts
        - size of the ROI
        """
        self.prepare_plot_data()
        # Calculate ROI intensities and normalize by number of points
        data_roi = self.data[
            self.configuration.peak_roi[0] : self.configuration.peak_roi[1],
            self.configuration.low_res_roi[0] : self.configuration.low_res_roi[1],
            :,
        ]
        counts_roi = data_roi.sum(axis=(0, 1))
        raw_error_roi = self.raw_error[
            self.configuration.peak_roi[0] : self.configuration.peak_roi[1],
            self.configuration.low_res_roi[0] : self.configuration.low_res_roi[1],
            :,
        ]
        counts_roi_error = np.linalg.norm(raw_error_roi, axis=(0, 1))  # square root of sum of squares
        if self.proton_charge > 0.0:
            counts_roi_normalized = counts_roi / self.proton_charge
            counts_roi_normalized_error = counts_roi_error / self.proton_charge
        else:
            counts_roi_normalized = counts_roi
            counts_roi_normalized_error = counts_roi_error
        size_roi = len(counts_roi) * [
            float(
                (self.configuration.low_res_roi[1] - self.configuration.low_res_roi[0])
                * (self.configuration.peak_roi[1] - self.configuration.peak_roi[0])
            )
        ]
        data_table = np.vstack(
            (
                self.tof,
                self.wavelength,
                counts_roi_normalized,
                counts_roi_normalized_error,
                counts_roi,
                counts_roi_error,
                size_roi,
            )
        ).T
        header = "tof wavelength counts_normalized counts_normalized_error counts counts_error size_roi"
        return data_table, header

    def get_background_vs_TOF(self):
        """
        Returns the background counts vs TOF
        """
        # Find the background pixels to use, excluding the peak if there's an overlap.
        dims = self.data.shape
        indices = [
            (i >= self.configuration.bck_roi[0] and i < self.configuration.bck_roi[1])
            and not (i >= self.configuration.peak_roi[0] and i < self.configuration.peak_roi[1])
            for i in range(dims[0])
        ]
        indices = np.asarray(indices)
        n_bins = len(indices[indices == True])
        raw_bck = self.data[indices, self.configuration.low_res_roi[0] : self.configuration.low_res_roi[1], :]
        summed_bck = raw_bck.sum(axis=0).sum(axis=0)
        size_bck = float(n_bins * (self.configuration.low_res_roi[1] - self.configuration.low_res_roi[0]))

        return summed_bck / math.fabs(size_bck)

    def update_calculated_values(self):
        """
        Update parameters that are calculated from the configuration
        """
        self.scattering_angle = self.configuration.instrument.scattering_angle_from_data(self)

    def update_configuration(self, configuration):
        """
        Update configuration
        """
        if configuration is not None:
            self.configuration = copy.deepcopy(configuration)
            self.update_calculated_values()
            self.process_configuration()

            # We want to keep consistency between the specular calculations
            # and the off-spec and GISANS ones. So clear the off-spec and GISANS
            # to force a recalculation.
            # TODO: This is a problem when switching beteewn the Off-spec and GISANS tabs
            self.off_spec = None
            self.gisans_data = None

    def reflectivity(self, direct_beam=None, configuration=None):
        """
        Compute reflectivity
        """
        self.q = None
        self._r = None
        self._dr = None
        if configuration is not None:
            self.configuration = copy.deepcopy(configuration)

        if self.configuration is None:
            return

        # If a direct beam object was passed, use it.
        apply_norm = direct_beam is not None  # and not self.is_direct_beam
        if not apply_norm:
            direct_beam = CrossSectionData("none", self.configuration, "none")

        logging.info(
            "%s:%s Reduction with DB: %s [config: %s]",
            self.number,
            self.entry_name,
            direct_beam.number,
            self.configuration.normalization,
        )
        angle_offset = 0  # Offset from dangle0, in radians

        def _as_ints(a):
            return [int(round(a[0])), int(round(a[1]))]

        output_ws = "r%s_%s" % (self.number, str(self.entry_name))

        ws_norm = None
        if apply_norm and direct_beam._event_workspace is not None:
            ws_norm = direct_beam._event_workspace

        logging.info(
            "Calc: %s %s %s",
            str(_as_ints(self.configuration.peak_roi)),
            str(_as_ints(self.configuration.bck_roi)),
            str(_as_ints(self.configuration.low_res_roi)),
        )

        _dirpix = configuration.direct_pixel_overwrite if configuration.set_direct_pixel else None
        _dangle0 = configuration.direct_angle_offset_overwrite if configuration.set_direct_angle_offset else None

        direct_beam_low_res_roi = get_direct_beam_low_res_roi(conf, direct_beam.configuration)

        ws = api.MagnetismReflectometryReduction(
            InputWorkspace=self._event_workspace,
            NormalizationWorkspace=ws_norm,
            SignalPeakPixelRange=_as_ints(self.configuration.peak_roi),
            SubtractSignalBackground=True,
            SignalBackgroundPixelRange=_as_ints(self.configuration.bck_roi),
            ApplyNormalization=apply_norm,
            NormPeakPixelRange=_as_ints(direct_beam.configuration.peak_roi),
            SubtractNormBackground=True,
            NormBackgroundPixelRange=_as_ints(direct_beam.configuration.bck_roi),
            CutLowResDataAxis=True,
            LowResDataAxisPixelRange=_as_ints(self.configuration.low_res_roi),
            CutLowResNormAxis=True,
            LowResNormAxisPixelRange=direct_beam_low_res_roi,
            CutTimeAxis=True,
            QMin=0.001,
            QStep=-0.01,
            AngleOffset=angle_offset,
            UseWLTimeAxis=False,
            TimeAxisStep=self.configuration.tof_bins,
            UseSANGLE=not self.configuration.use_dangle,
            TimeAxisRange=self.configuration.tof_range,
            SpecularPixel=self.configuration.peak_position,
            ConstantQBinning=self.configuration.use_constant_q,
            # EntryName=str(self.entry_name),
            ConstQTrim=0.1,
            AcceptNullReflectivity=True,  # return empty reflectivity curves (all intensities are zero)
            ErrorWeightedBackground=False,
            SampleLength=self.configuration.sample_size,
            DAngle0Overwrite=_dangle0,
            DirectPixelOverwrite=_dirpix,
            OutputWorkspace=output_ws,
        )

        # If there's an empty reflectivity curve, add a small value to it so that it can be plotted.
        if _is_empty_reflectivity_curve(ws):
            _shift_empty_reflectivity_curve(ws)

        # FOR COMPATIBILITY WITH QUICKNXS #
        run_object = ws.getRun()
        peak_min = run_object.getProperty("scatt_peak_min").value
        peak_max = run_object.getProperty("scatt_peak_max").value
        low_res_min = run_object.getProperty("scatt_low_res_min").value
        low_res_max = run_object.getProperty("scatt_low_res_max").value
        norm_x_min = run_object.getProperty("norm_peak_min").value
        norm_x_max = run_object.getProperty("norm_peak_max").value
        norm_y_min = run_object.getProperty("norm_low_res_min").value
        norm_y_max = run_object.getProperty("norm_low_res_max").value
        tth = ws.getRun().getProperty("SANGLE").getStatistics().mean * math.pi / 180.0
        quicknxs_scale = (float(norm_x_max) - float(norm_x_min)) * (float(norm_y_max) - float(norm_y_min))
        quicknxs_scale /= (float(peak_max) - float(peak_min)) * (float(low_res_max) - float(low_res_min))
        quicknxs_scale *= 0.005 / math.sin(tth)

        ws = api.Scale(
            InputWorkspace=output_ws, OutputWorkspace=output_ws, factor=quicknxs_scale, Operation="Multiply"
        )
        #

        self.q = ws.readX(0)[:].copy()
        self._r = ws.readY(0)[:].copy()  # * self.configuration.scaling_factor
        self._dr = ws.readE(0)[:].copy()  # * self.configuration.scaling_factor

        # DeleteWorkspace(ws)
        self._reflectivity_workspace = str(ws)

    def offspec(self, direct_beam=None):
        """
        Extract off-specular scattering from 4D dataset (x,y,ToF,I).
        Uses a window in y to filter the 4D data
        and than sums all I values for each ToF and x channel.
        Qz,Qx,kiz,kfz is calculated using the x and ToF positions
        together with the tth-bank and direct pixel values.

        :param CrossSectionData direct_beam: if given, this data will be used to normalize the output
        """
        self.prepare_plot_data()
        if direct_beam:
            direct_beam.prepare_plot_data()
        self.off_spec = OffSpecular(self)
        return self.off_spec(direct_beam)

    def gisans(self, direct_beam=None):
        """
        Compute GISANS

        :param CrossSectionData direct_beam: if given, this data will be used to normalize the output
        """
        self.prepare_plot_data()
        if direct_beam:
            direct_beam.prepare_plot_data()
        self.gisans_data = GISANS(self)
        self.gisans_data(direct_beam)

        self.SGrid = self.gisans_data.SGrid
        self.QyGrid = self.gisans_data.QyGrid
        self.QzGrid = self.gisans_data.QzGrid

        return self.gisans_data


class NexusMetaData(object):
    """
    Class used to hold meta-data read before loading the neutron events
    """

    mid_q = 0
    is_direct_beam = False
