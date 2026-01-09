"""
Container class for instrument-specific data handling.

Abstracts out how we obtaininformation from the data file
"""
# pylint: disable=invalid-name, too-many-instance-attributes, line-too-long, bare-except

import math
from typing import TYPE_CHECKING, List, Optional

import mantid.simpleapi as api
import numpy as np
from mantid.dataobjects import EventWorkspace
from mr_reduction.dead_time_correction import apply_dead_time_correction
from mr_reduction.filter_events import split_error_events, split_events
from mr_reduction.settings import PolarizationLogs

from quicknxs.interfaces.data_handling.filepath import FilePath

if TYPE_CHECKING:
    from quicknxs.interfaces.configuration import Configuration
    from quicknxs.interfaces.data_handling.data_set import CrossSectionData

# Constants
h = 6.626e-34  # m^2 kg s^-1
m = 1.675e-27  # kg

UNPOLARIZED_XS_LABEL = "Off_Off"


def get_cross_section_label(ws, entry_name):
    """Return the proper cross-section label."""
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


class InsufficientEventCountError(Exception):
    """Exception raised when the number of events in the workspace is too low"""

    pass


class Instrument(object):
    """Instrument class. Holds the data handling that is unique to a specific instrument."""

    n_x_pixel: int = 304
    n_y_pixel: int = 256
    huber_x_cut: float = 6.5
    peak_range_offset: int = 50
    tolerance: float = 0.05
    pixel_width: float = 0.0007
    instrument_name: str = "REF_M"
    instrument_dir: str = "/SNS/REF_M"
    file_search_template: str = "/SNS/REF_M/*/nexus/REF_M_%s"
    legacy_search_template: str = "/SNS/REF_M/*/data/REF_M_%s"
    # Option to use the slow flipper logs rather than the Analyzer/Polarizer logs
    USE_SLOW_FLIPPER_LOG: bool = False

    def __init__(self):
        # Filtering
        self.pol_state = "PolarizerState"
        self.pol_veto = "PolarizerVeto"
        self.ana_state = "AnalyzerState"
        self.ana_veto = "AnalyzerVeto"

    def _get_xs_list(self, file_path: str, ws_root_name: str, configuration: "Configuration") -> List[EventWorkspace]:
        """Load the cross-sections from a data file. Handles both pre- and post-epics data.

        Parameters
        ----------
        file_path:
            Path to the data file
        ws_root_name:
            Root name of the workspace (used to rename the cross-sections after loading)
        configuration:
            Reduction parameters

        Returns
        -------
        List[EventWorkspace]
            List of cross-section workspaces

        Raises
        ------
        InsufficientEventCountError
            If the data file does not contain enough events
        """
        use_slow_flipper_log = self.USE_SLOW_FLIPPER_LOG
        xs_list = []

        # Determine if we need to use slow flipper log for post-epics data
        is_pre_epics = file_path.endswith(".nxs")
        if not is_pre_epics and file_path.endswith(".nxs.h5"):
            # Check metadata for post-epics data to determine if slow flipper log is needed
            event_ws = api.LoadEventNexus(Filename=file_path, OutputWorkspace="raw_events")
            metadata = event_ws.getRun()
            polarizer = metadata.getProperty("Polarizer").value[0]
            analyzer = metadata.getProperty("Analyzer").value[0]
            if (polarizer > 0 and self.pol_state not in event_ws.getRun()) or (
                analyzer > 0 and self.ana_state not in event_ws.getRun()
            ):
                use_slow_flipper_log = True
                print("\n\nMISSING POLARIZER/ANALYZER META-DATA: USING SLOW LOGS\n\n")
            # Delete the temporary workspace as split_events will reload it
            api.DeleteWorkspace("raw_events")
        elif not is_pre_epics and not file_path.endswith(".nxs.h5"):
            raise RuntimeError(f"Unknown file type: {file_path}")

        # Use mr_reduction's split_events to load and filter cross-sections
        try:
            # Create PolarizationLogs with custom log names matching REF_M
            pol_logs = PolarizationLogs()
            pol_logs.POL_STATE = self.pol_state
            pol_logs.ANA_STATE = self.ana_state
            pol_logs.POL_VETO = self.pol_veto
            pol_logs.ANA_VETO = self.ana_veto

            _path_xs_list = split_events(
                file_path=file_path,
                output_workspace=ws_root_name,
                min_event_count=0,  # We'll filter manually to match original behavior
                use_slow_flipper_log=use_slow_flipper_log,
                polarization_logs=pol_logs,
            )

            # Filter out workspaces with too few events (matching original behavior)
            _path_xs_list = [ws for ws in _path_xs_list if ws.getNumberEvents() >= configuration.nbr_events_min]

            if len(_path_xs_list) == 0:
                raise InsufficientEventCountError(
                    f"All cross-sections contain fewer than {configuration.nbr_events_min} events in: {file_path}"
                )
        except ValueError as e:
            # split_events raises ValueError when there are insufficient events at the workspace level
            raise InsufficientEventCountError(
                f"All cross-sections contain fewer than {configuration.nbr_events_min} events in: {file_path}"
            ) from e

        # Dead-time correction only applies to post-epics data
        if configuration is not None and configuration.apply_deadtime and not is_pre_epics:
            # Create PolarizationLogs with custom log names matching REF_M
            pol_logs = PolarizationLogs()
            pol_logs.POL_STATE = self.pol_state
            pol_logs.ANA_STATE = self.ana_state
            pol_logs.POL_VETO = self.pol_veto
            pol_logs.ANA_VETO = self.ana_veto

            # Use mr_reduction's split_error_events to load and filter error events
            _err_list = split_error_events(
                file_path=file_path,
                output_workspace=f"{ws_root_name}_err",
                use_slow_flipper_log=use_slow_flipper_log,
                polarization_logs=pol_logs,
            )

            # Apply dead-time correction for each cross-section workspace
            path_xs_list = []
            for ws in _path_xs_list:
                xs_name = ws.getRun()["cross_section_id"].value
                if not xs_name == "unfiltered":
                    # Find the related workspace in with error events
                    is_found = False
                    for err_ws in _err_list:
                        if err_ws.getRun()["cross_section_id"].value == xs_name:
                            is_found = True
                            _ws = apply_dead_time_correction(
                                ws,
                                configuration.paralyzable_deadtime,
                                configuration.deadtime_value,
                                configuration.deadtime_tof_step,
                                error_ws=err_ws,
                            )
                            path_xs_list.append(_ws)
                    if not is_found:
                        print("Could not find error events for [%s]" % xs_name)
                        _ws = apply_dead_time_correction(
                            ws,
                            configuration.paralyzable_deadtime,
                            configuration.deadtime_value,
                            configuration.deadtime_tof_step,
                        )
                        path_xs_list.append(_ws)
        else:
            path_xs_list = [ws for ws in _path_xs_list if not ws.getRun()["cross_section_id"].value == "unfiltered"]

        # initialize xs_list with the cross sections of the first data file
        if len(xs_list) == 0:
            xs_list = path_xs_list
        else:
            # Merge the cross sections from the new data file with the existing ones
            for i, ws in enumerate(xs_list):
                api.Plus(
                    LHSWorkspace=str(ws),
                    RHSWorkspace=str(path_xs_list[i]),
                    OutputWorkspace=str(ws),
                )
        return xs_list

    def load_data(self, file_path: str, configuration: Optional["Configuration"] = None) -> List[EventWorkspace]:
        r"""Load one or more data sets according to the needs of the instrument.

        This function assumes that when loading more than one data file, the files are congruent and their
        events will be added together.

        Args:
            file_path (str): absolute path to one or more data files. If more than one, paths should be concatenated with the plus symbol '+'.
            configuration (Configuration): reduction configuration parameters

        Returns
        -------
        List[EventWorkspace]:
            A list of EventWorkspaces, one for each cross-section

        Raises
        ------
        InsufficientEventCountError
            If the data file does not contain enough events
        """
        fp_instance = FilePath(file_path)
        ws_root_name = fp_instance.run_numbers(string_representation="short")
        xs_list = list()

        for path in fp_instance.single_paths:
            xs_list += self._get_xs_list(path, ws_root_name, configuration)

        # Insert a log indicating which run numbers contributed to this cross-section
        for ws in xs_list:
            api.AddSampleLog(
                Workspace=str(ws),
                LogName="run_numbers",
                LogText=ws_root_name,
                LogType="String",
            )

        return xs_list

    @classmethod
    def mid_q_value(cls, ws: EventWorkspace) -> float:
        """Get the mid q value, at the requested wl mid-point.

        This is used when sorting out data sets and doesn't need any overwrites.
        """
        wl = ws.getRun().getProperty("LambdaRequest").value[0]
        theta_d = api.MRGetTheta(ws)
        return 4.0 * math.pi * math.sin(theta_d) / wl

    @classmethod
    def scattering_angle_from_data(cls, data_object: "CrossSectionData") -> float:
        """Compute the scattering angle from a CrossSectionData object, in degrees."""
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
        """Determine whether this data is a direct beam."""
        try:
            return ws.getRun().getProperty("data_type").value[0] == 1
        except:
            return False

    def direct_beam_match(self, scattering, direct_beam, skip_slits=False):
        """Verify whether two data sets are compatible."""
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

    def direct_beam_distance(self, scattering, direct_beam) -> float:
        """Return a Euclidean squared-distance between slit widths in scattered, direct beams"""
        scatter_slit_array = (scattering.slit1_width, scattering.slit2_width, scattering.slit3_width)
        direct_slit_array = (direct_beam.slit1_width, direct_beam.slit2_width, direct_beam.slit3_width)
        return sum([(scatter - direct) ** 2 for scatter, direct in zip(scatter_slit_array, direct_slit_array)])

    @classmethod
    def get_info(cls, workspace, data_object):
        """
        Retrieve information that is specific to this particular instrument.

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

    def integrate_detector(self, ws: EventWorkspace, specular: bool = True):
        """Integrate a workspace along either the main direction or the low-resolution direction.

        ws:
            Mantid workspace to integrate
        specular:
            If True, the workspace is integrated over the low-resolution direction.
            If False, the workspace is integrated over the main direction.
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
