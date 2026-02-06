"""
Container class for instrument-specific data handling.

Abstracts out how we obtaininformation from the data file
"""
# pylint: disable=invalid-name, too-many-instance-attributes, line-too-long, bare-except

import logging
import math
from typing import TYPE_CHECKING, List, Optional, Union

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


def remove_low_event_workspaces(ws_list, nbr_events_cutoff):
    """
    Removes workspaces with number of events below the cutoff from a list of workspaces.

    Parameters
    ----------
    ws_list: list[EventWorkspace]
    nbr_events_cutoff: int
        Minimum number of events

    Returns
    -------
    List[EventWorkspace]
        Input list with low event workspaces removed
    """
    pruned_list = []
    for ws in ws_list:
        xs_name = ws.getRun()["cross_section_id"].value
        if ws.getNumberEvents() < nbr_events_cutoff:
            logging.warning("Too few events for %s: %s", xs_name, ws.getNumberEvents())
        else:
            pruned_list.append(ws)
    return pruned_list


class NoCrossSectionsFoundError(Exception):
    """Exception raised when no valid cross section data can be loaded"""

    def __init__(self, file_path: Union[str, List[str]], message: str = None, min_num_evts: int = 100):
        self.file_path = FilePath(file_path)
        run_numbers = self.file_path.run_numbers()

        _xs_list = []
        self.path_dict = dict()
        for idx, path in enumerate(self.file_path.single_paths):
            _, fpath = FilePath(path).split()
            self.path_dict[run_numbers[idx]] = fpath
            ws_name = api.mtd.unique_hidden_name()
            ws = api.LoadEventNexus(Filename=path, OutputWorkspace=ws_name)
            ws.mutableRun().addProperty("run_number", run_numbers[idx], True)
            _xs_list.append(ws)

        self.xs_list = _xs_list
        self.min_num_events = min_num_evts
        self.bad_files = set()
        self.bad_files.add(self.file_path.split()[1])
        self.diagnostic_data = self._extract_diagnostic_data()
        self.sample_logs = self._get_sample_logs()

        if message is None:
            message = f"No valid cross-sections found in file: {file_path}"
        self.message = message
        super().__init__(message)

    def _extract_diagnostic_data(self):
        """Extract diagnostic information from workspaces.

        Returns
        -------
        list of dict
            List of dictionaries containing diagnostic information for each workspace.
        """
        diagnostic_data = []

        for idx, ws in enumerate(self.xs_list):
            run = ws.getRun()

            def get_prop_value(prop_name, default="N/A"):
                if run.hasProperty(prop_name):
                    try:
                        prop = run.getProperty(prop_name)
                        if hasattr(prop, "getStatistics"):
                            return prop.getStatistics().mean
                        else:
                            return prop.value
                    except Exception:
                        return default
                return default

            data = {}

            run_number = get_prop_value("run_number")
            xs_id = get_prop_value("cross_section_id")
            if xs_id != "N/A":
                data["cross_section_id"] = f"Run {run_number} ({xs_id})"
            else:
                data["cross_section_id"] = f"Run {run_number}"

            event_count = ws.getNumberEvents()
            if event_count < self.min_num_events:
                self.bad_files.add(self.path_dict[run_number])
            data["event_count"] = event_count
            data["lambda_center"] = get_prop_value("LambdaRequest")
            data["direct_pixel"] = get_prop_value("DIRPIX")
            data["proton_charge"] = get_prop_value("gd_prtn_chrg")
            sample_angle = get_prop_value("SampleAngle")
            if sample_angle == "N/A":
                sample_angle = get_prop_value("SANGLE")
            data["sample_angle"] = sample_angle
            data["dangle"] = get_prop_value("DANGLE")
            data["dangle0"] = get_prop_value("DANGLE0")
            counting_time = get_prop_value("duration")
            data["counting_time"] = counting_time

            if counting_time != "N/A" and counting_time > 0:
                data["count_rate"] = event_count / counting_time
            else:
                data["count_rate"] = "N/A"

            diagnostic_data.append(data)

        return diagnostic_data

    def _get_sample_logs(self):
        """Extract all sample logs from workspaces.

        Returns
        -------
        list of dict
            List of dictionaries, each containing:
            - 'run_id': identifier for the run
            - 'logs': list of tuples (property_name, property_value)
        """
        sample_logs = []

        for ws in self.xs_list:
            run = ws.getRun()
            run_id = run.getProperty("run_number").value

            logs = []
            for prop in run.getProperties():
                logs.append((prop.name, str(prop.value)))
            logs = sorted(logs, key=lambda x: x[0])

            sample_logs.append({"run_id": run_id, "logs": logs})

        return sample_logs


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
        NoCrossSectionsFoundError
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
            # Note: PolarizationLogs doesn't support initialization with parameters,
            # so we set attributes individually. This could be improved in mr_reduction.
            pol_logs = PolarizationLogs()
            pol_logs.POL_STATE = self.pol_state
            pol_logs.ANA_STATE = self.ana_state
            pol_logs.POL_VETO = self.pol_veto
            pol_logs.ANA_VETO = self.ana_veto

            _path_xs_list = split_events(
                file_path=file_path,
                output_workspace=ws_root_name,
                min_event_count=0,  # We'll filter manually to preserve warning logs
                use_slow_flipper_log=use_slow_flipper_log,
                polarization_logs=pol_logs,
            )

            # Filter out workspaces with too few events and log warnings
            _path_xs_list = remove_low_event_workspaces(_path_xs_list, configuration.nbr_events_min)

            if len(_path_xs_list) == 0:
                raise NoCrossSectionsFoundError(
                    file_path,
                    f"All cross-sections contain fewer than {configuration.nbr_events_min} events in: {file_path}",
                    configuration.nbr_events_min,
                )
        except ValueError as e:
            # split_events raises ValueError when there are insufficient events at the workspace level
            raise NoCrossSectionsFoundError(
                file_path,
                f"All cross-sections contain fewer than {configuration.nbr_events_min} events in: {file_path}",
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

        return path_xs_list

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
        NoCrossSectionsFoundError
            If the data file does not contain enough events
        """
        fp_instance = FilePath(file_path)
        ws_root_name = fp_instance.run_numbers(string_representation="short")
        ws_run_numbers = fp_instance.run_numbers(string_representation="long")

        # Collect cross-sections from all files
        all_xs_lists = []
        try:
            for idx, path in enumerate(fp_instance.single_paths):
                # Use unique workspace names for each file to avoid overwrites
                path_fp = FilePath(path)
                path_ws_name = path_fp.run_numbers(string_representation="short")
                all_xs_lists.append(self._get_xs_list(path, path_ws_name, configuration))
        except NoCrossSectionsFoundError as err:
            raise NoCrossSectionsFoundError(file_path, err.message)
        
        # If only one file, return its cross-sections directly
        if len(all_xs_lists) == 1:
            xs_list = all_xs_lists[0]
        else:
            # Merge cross-sections from multiple files by matching cross_section_id
            xs_list = all_xs_lists[0]
            for i, ws in enumerate(xs_list):
                # Merge workspaces with matching cross_section_id from subsequent files
                for xs_group in all_xs_lists[1:]:
                    merged = api.Plus(
                        LHSWorkspace=str(ws),
                        RHSWorkspace=str(xs_group[i]),
                        OutputWorkspace=str(ws),
                    )
                    xs_list[i] = merged  # Update the reference to the merged workspace

        # Insert a log indicating which run numbers contributed to this cross-section
        for ws in xs_list:
            api.AddSampleLog(
                Workspace=str(ws),
                LogName="run_numbers",
                LogText=ws_run_numbers,
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
