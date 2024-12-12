"""
    This instrument description contains information
    that is instrument-specific and abstracts out how we obtain
    information from the data file
"""
# pylint: disable=invalid-name, too-many-instance-attributes, line-too-long, bare-except


# local
from reflectivity_ui.interfaces.data_handling import DeadTimeCorrection
from reflectivity_ui.interfaces.data_handling.filepath import FilePath

# 3rd party
from mantid.api import WorkspaceGroup, PythonAlgorithm
from mantid.dataobjects import EventWorkspace
import numpy as np
import mantid.simpleapi as api

# standard
import logging
import math
import os
import random
import sys
import string


# Constants
h = 6.626e-34  # m^2 kg s^-1
m = 1.675e-27  # kg


def get_cross_section_label(ws, entry_name):
    """
    Return the proper cross-section label.
    """
    entry_name = str(entry_name)
    pol_is_on = entry_name.lower().startswith("on")
    ana_is_on = entry_name.lower().endswith("on")

    pol_label = ""
    ana_label = ""

    # Look for log that define whether OFF or ON is +
    if "PolarizerLabel" in ws.getRun():
        pol_id = ws.getRun().getProperty("PolarizerLabel").value
        if isinstance(pol_id, np.ndarray):
            pol_id = int(pol_id[0])
        if pol_id == 1:
            pol_label = "+" if pol_is_on else "-"
        elif pol_id == 0:
            pol_label = "-" if pol_is_on else "+"

    if "AnalyzerLabel" in ws.getRun():
        ana_id = ws.getRun().getProperty("AnalyzerLabel").value
        if isinstance(ana_id, np.ndarray):
            ana_id = int(ana_id[0])
        if ana_id == 1:
            ana_label = "+" if ana_is_on else "-"
        elif ana_id == 0:
            ana_label = "-" if ana_is_on else "-"

    entry_name = entry_name.replace("_", "-")
    if ana_label == "" and pol_label == "":
        return entry_name
    else:
        return "%s%s" % (pol_label, ana_label)


def mantid_algorithm_exec(algorithm_class, **kwargs):
    """
    Helper function for executing a Mantid-style algorithm

    :param PythonAlgorithm algorithm_class: the algorithm class to execute
    :param kwargs: keyword arguments
    :returns Workspace: if ``OutputWorkspace`` is passed as a keyword argument, the value of the
                       algorithm property ``OutputWorkspace`` will be returned
    """
    algorithm_instance = algorithm_class()
    assert hasattr(algorithm_instance, "PyInit"), f"{algorithm_class} is not a Mantid Python algorithm"
    algorithm_instance.PyInit()
    for name, value in kwargs.items():
        algorithm_instance.setProperty(name, value)
    algorithm_instance.PyExec()
    if "OutputWorkspace" in kwargs:
        return algorithm_instance.getProperty("OutputWorkspace").value


def get_dead_time_correction(ws, configuration, error_ws=None):
    """
    Compute dead time correction to be applied to the reflectivity curve.
    The method will also try to load the error events from each of the
    data files to ensure that we properly estimate the dead time correction.
    :param ws: workspace with raw data to compute correction for
    :param configuration: reduction parameters
    :param error_ws: workspace with error events
    """
    tof_min = ws.getTofMin()
    tof_max = ws.getTofMax()

    corr_ws = mantid_algorithm_exec(
        DeadTimeCorrection.SingleReadoutDeadTimeCorrection,
        InputWorkspace=ws,
        InputErrorEventsWorkspace=error_ws,
        Paralyzable=configuration.paralyzable_deadtime,
        DeadTime=configuration.deadtime_value,
        TOFStep=configuration.deadtime_tof_step,
        TOFRange=[tof_min, tof_max],
        OutputWorkspace="corr",
    )
    corr_ws = api.Rebin(corr_ws, [tof_min, 10, tof_max])
    return corr_ws


def apply_dead_time_correction(ws, configuration, error_ws=None):
    """
    Apply dead time correction, and ensure that it is done only once
    per workspace.
    :param ws: workspace with raw data to compute correction for
    :param template_data: reduction parameters
    """
    if "dead_time_applied" not in ws.getRun():
        corr_ws = get_dead_time_correction(ws, configuration, error_ws=error_ws)
        ws = api.Multiply(ws, corr_ws, OutputWorkspace=str(ws))
        api.AddSampleLog(Workspace=ws, LogName="dead_time_applied", LogText="1", LogType="Number")
    return ws


def remove_low_event_workspaces(ws_list, nbr_events_cutoff):
    """
    Removes workspaces with number of events below the cutoff from a list of workspaces

    Parameters
    ----------
    ws_list: list[EventWorkspace]
    nbr_events_cutoff: int
        Minimum number of events

    Returns
    -------
    list[EventWorkspace]
        Input list with low event workspaces removes
    """
    pruned_list = []
    for ws in ws_list:
        xs_name = ws.getRun()["cross_section_id"].value
        if ws.getNumberEvents() < nbr_events_cutoff:
            logging.warning("Too few events for %s: %s", xs_name, ws.getNumberEvents())
        else:
            pruned_list.append(ws)
    return pruned_list


class Instrument(object):
    """
    Instrument class. Holds the data handling that is unique to a specific instrument.
    """

    n_x_pixel = 304
    n_y_pixel = 256
    huber_x_cut = 6.5
    peak_range_offset = 50
    tolerance = 0.05
    pixel_width = 0.0007
    instrument_name = "REF_M"
    instrument_dir = "/SNS/REF_M"
    file_search_template = "/SNS/REF_M/*/nexus/REF_M_%s"
    legacy_search_template = "/SNS/REF_M/*/data/REF_M_%s"
    # Option to use the slow flipper logs rather than the Analyzer/Polarizer logs
    USE_SLOW_FLIPPER_LOG = False

    def __init__(self):
        # Filtering
        self.pol_state = "PolarizerState"
        self.pol_veto = "PolarizerVeto"
        self.ana_state = "AnalyzerState"
        self.ana_veto = "AnalyzerVeto"

    @staticmethod
    def dummy_filter_cross_sections(ws: EventWorkspace, name_prefix: str = None) -> WorkspaceGroup:
        r"""Filter events according to an aggregated state log.

        Examples:
        BL4A:SF:ICP:getDI
        015 (0000 1111): SF1=OFF, SF2=OFF, SF1Veto=OFF, SF2Veto=OFF
        047 (0010 1111): SF1=ON, SF2=OFF, SF1Veto=OFF, SF2Veto=OFF
        031 (0001 1111): SF1=OFF, SF2=ON, SF1Veto=OFF, SF2Veto=OFF
        063 (0011 1111): SF1=ON, SF2=ON, SF1Veto=OFF, SF2Veto=OFF

        @param ws: workspace containing the unfiltered events
        @param name_prefix: root name of the output WorkspaceGroup. If None, the run number of the workspace is chosen
        as the root name.

        @return a group workspace for each of the four different filter/analyzer conbinations
        """
        state_log = "BL4A:SF:ICP:getDI"
        states = {"Off_Off": 15, "On_Off": 47, "Off_On": 31, "On_On": 63}
        cross_sections = []
        if name_prefix is None:
            name_prefix = str(ws.getRunNumber())
        for pol_state in ["Off_Off", "On_On", "Off_On", "On_Off"]:
            try:
                _ws = api.FilterByLogValue(
                    InputWorkspace=ws,
                    LogName=state_log,
                    TimeTolerance=0.1,
                    MinimumValue=states[pol_state],
                    MaximumValue=states[pol_state],
                    LogBoundary="Left",
                    # FIXME 64 - the merged workspace only shows the first run's number
                    #  Thus this method won't give a merged workspace a unique name
                    #  And potentially it could confuse the program with single-run workspace
                    OutputWorkspace="%s_entry-%s" % (name_prefix, pol_state),
                )
                _ws.getRun()["cross_section_id"] = pol_state
                api.AddSampleLog(
                    Workspace=str(_ws),
                    LogName="loaded_with_getDI",
                    LogText="True",
                    LogType="String",
                )
                cross_sections.append(_ws)
            except RuntimeError as run_err:
                logging.error("Could not filter {}: {}\nError: {}".format(pol_state, sys.exc_info()[1], run_err))

        return cross_sections

    def load_data(self, file_path, configuration=None):
        r"""
        # type: (unicode) -> WorkspaceGroup
        @brief Load one or more data sets according to the needs ot the instrument.
        @details This function assumes that when loading more than one data file, the files are congruent and their
        events will be added together.
        @param file_path: absolute path to one or more data files. If more than one, paths should be concatenated
        with the plus symbol '+'.
        @returns WorkspaceGroup with any number of cross-sections
        """
        fp_instance = FilePath(file_path)
        xs_list = list()
        temp_workspace_root_name = "".join(random.sample(string.ascii_letters, 12))  # random string of 12 characters
        workspace_root_name = fp_instance.run_numbers(string_representation="short")
        for path in fp_instance.single_paths:
            is_legacy = path.endswith(".nxs")
            if is_legacy or not self.USE_SLOW_FLIPPER_LOG:
                _path_xs_list = api.MRFilterCrossSections(
                    Filename=path,
                    PolState=self.pol_state,
                    AnaState=self.ana_state,
                    PolVeto=self.pol_veto,
                    AnaVeto=self.ana_veto,
                    CrossSectionWorkspaces="%s_entry" % temp_workspace_root_name,
                )
                # Only keep good workspaces, and get rid of the rejected events
                if len(_path_xs_list) == 1 and not "cross_section_id" in _path_xs_list[0].getRun():
                    logging.warning("Could not filter data, using getDI")
                    ws = api.LoadEventNexus(Filename=path, OutputWorkspace="raw_events")
                    _path_xs_list = self.dummy_filter_cross_sections(ws, name_prefix=temp_workspace_root_name)
                # Remove workspaces with too few events
                _path_xs_list = remove_low_event_workspaces(_path_xs_list, configuration.nbr_events_min)
                if configuration is not None and configuration.apply_deadtime:
                    # Load error events from the bank_error_events entry
                    err_ws = api.LoadErrorEventsNexus(path)
                    # Split error events by cross-section for compatibility with normal events
                    _err_list = api.MRFilterCrossSections(
                        InputWorkspace=err_ws,
                        PolState=self.pol_state,
                        AnaState=self.ana_state,
                        PolVeto=self.pol_veto,
                        AnaVeto=self.ana_veto,
                        CrossSectionWorkspaces="%s_err_entry" % temp_workspace_root_name,
                    )
                    path_xs_list = []
                    # Apply dead-time correction for each cross-section workspace
                    for ws in _path_xs_list:
                        xs_name = ws.getRun()["cross_section_id"].value
                        if not xs_name == "unfiltered":
                            # Find the related workspace in with error events
                            is_found = False
                            for err_ws in _err_list:
                                if err_ws.getRun()["cross_section_id"].value == xs_name:
                                    is_found = True
                                    _ws = apply_dead_time_correction(ws, configuration, error_ws=err_ws)
                                    path_xs_list.append(_ws)
                            if not is_found:
                                print("Could not find error events for [%s]" % xs_name)
                                _ws = apply_dead_time_correction(ws, configuration, error_ws=None)
                                path_xs_list.append(_ws)
                else:
                    path_xs_list = [
                        ws for ws in _path_xs_list if not ws.getRun()["cross_section_id"].value == "unfiltered"
                    ]
            else:
                ws = api.LoadEventNexus(Filename=path, OutputWorkspace="raw_events")
                path_xs_list = self.dummy_filter_cross_sections(ws, name_prefix=temp_workspace_root_name)

            if len(xs_list) == 0:  # initialize xs_list with the cross sections of the first data file
                xs_list = path_xs_list
                for ws in xs_list:  # replace the temporary names with the run number(s)
                    name_new = str(ws).replace(temp_workspace_root_name, workspace_root_name)
                    api.RenameWorkspace(str(ws), name_new)
            else:
                for i, ws in enumerate(xs_list):
                    api.Plus(
                        LHSWorkspace=str(ws),
                        RHSWorkspace=str(path_xs_list[i]),
                        OutputWorkspace=str(ws),
                    )

        # Insert a log indicating which run numbers contributed to this cross-section
        for ws in xs_list:
            api.AddSampleLog(
                Workspace=str(ws),
                LogName="run_numbers",
                LogText=fp_instance.run_numbers(string_representation="short"),
                LogType="String",
            )
        return xs_list

    @classmethod
    def mid_q_value(cls, ws):
        """
        Get the mid q value, at the requested wl mid-point.
        This is used when sorting out data sets and doesn't need any overwrites.
        :param workspace ws: Mantid workspace
        """
        wl = ws.getRun().getProperty("LambdaRequest").value[0]
        theta_d = api.MRGetTheta(ws)
        return 4.0 * math.pi * math.sin(theta_d) / wl

    @classmethod
    def scattering_angle_from_data(cls, data_object):
        """
        Compute the scattering angle from a CrossSectionData object, in degrees.
        @param data_object: CrossSectionData object
        """
        _dirpix = (
            data_object.configuration.direct_pixel_overwrite if data_object.configuration.set_direct_pixel else None
        )
        _dangle0 = (
            data_object.configuration.direct_angle_offset_overwrite
            if data_object.configuration.set_direct_angle_offset
            else None
        )

        return (
            api.MRGetTheta(
                data_object.event_workspace,
                SpecularPixel=data_object.configuration.peak_position,
                DAngle0Overwrite=_dangle0,
                DirectPixelOverwrite=_dirpix,
            )
            * 180.0
            / math.pi
        )

    @classmethod
    def check_direct_beam(cls, ws):
        """
        Determine whether this data is a direct beam
        """
        try:
            return ws.getRun().getProperty("data_type").value[0] == 1
        except:
            return False

    def direct_beam_match(self, scattering, direct_beam, skip_slits=False):
        """
        Verify whether two data sets are compatible.
        """
        if math.fabs(scattering.lambda_center - direct_beam.lambda_center) < self.tolerance and (
            skip_slits
            or (
                math.fabs(scattering.slit1_width - direct_beam.slit1_width) < self.tolerance
                and math.fabs(scattering.slit2_width - direct_beam.slit2_width) < self.tolerance
                and math.fabs(scattering.slit3_width - direct_beam.slit3_width) < self.tolerance
            )
        ):
            return True
        return False

    @classmethod
    def get_info(cls, workspace, data_object):
        """
        Retrieve information that is specific to this particular instrument

        @param workspace: Mantid workspace
        @param data_object: CrossSectionData object
        """
        data = workspace.getRun()
        data_object.lambda_center = data["LambdaRequest"].value[0]
        data_object.dangle = data["DANGLE"].getStatistics().mean
        if "BL4A:Mot:S1:X:Gap" in data:
            data_object.slit1_width = data["BL4A:Mot:S1:X:Gap"].value[0]
            data_object.slit2_width = data["BL4A:Mot:S2:X:Gap"].value[0]
            data_object.slit3_width = data["BL4A:Mot:S3:X:Gap"].value[0]
        else:
            data_object.slit1_width = data["S1HWidth"].value[0]
            data_object.slit2_width = data["S2HWidth"].value[0]
            data_object.slit3_width = data["S3HWidth"].value[0]
        data_object.huber_x = data["HuberX"].getStatistics().mean

        if "SampleAngle" in data:
            data_object.sangle = data["SampleAngle"].getStatistics().mean
        else:
            data_object.sangle = data["SANGLE"].getStatistics().mean

        data_object.dist_sam_det = data["SampleDetDis"].value[0] * 1e-3
        data_object.dist_mod_det = data["ModeratorSamDis"].value[0] * 1e-3 + data_object.dist_sam_det
        data_object.dist_mod_mon = data["ModeratorSamDis"].value[0] * 1e-3 - 2.75

        # Get these from instrument
        data_object.pixel_width = float(workspace.getInstrument().getNumberParameter("pixel-width")[0]) / 1000.0
        data_object.n_det_size_x = int(workspace.getInstrument().getNumberParameter("number-of-x-pixels")[0])  # 304
        data_object.n_det_size_y = int(workspace.getInstrument().getNumberParameter("number-of-y-pixels")[0])  # 256
        data_object.det_size_x = data_object.n_det_size_x * data_object.pixel_width  # horizontal size of detector [m]
        data_object.det_size_y = data_object.n_det_size_y * data_object.pixel_width  # vertical size of detector [m]

        # The following active area used to be taken from instrument.DETECTOR_REGION
        data_object.active_area_x = (8, 295)
        data_object.active_area_y = (8, 246)

        # Convert to standard names
        data_object.direct_pixel = data["DIRPIX"].getStatistics().mean
        data_object.angle_offset = data["DANGLE0"].getStatistics().mean

        # Get proper cross-section label
        data_object.cross_section_label = get_cross_section_label(workspace, data_object.entry_name)
        try:
            data_object.is_direct_beam = data["data_type"].value[0] == 1
        except:
            data_object.is_direct_beam = False

    def integrate_detector(self, ws, specular=True):
        """
        Integrate a workspace along either the main direction (specular=False) or
        the low-resolution direction (specular=True.

        :param ws: Mantid workspace
        :param specular bool: if True, the low-resolution direction is integrated over
        """
        ws_summed = api.RefRoi(
            InputWorkspace=ws,
            IntegrateY=specular,
            NXPixel=self.n_x_pixel,
            NYPixel=self.n_y_pixel,
            ConvertToQ=False,
            OutputWorkspace="ws_summed",
        )

        integrated = api.Integration(ws_summed)
        integrated = api.Transpose(integrated)
        return integrated
