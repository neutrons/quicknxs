"""Data presenter. Holds information about the current data location and manages the data cache."""

import copy
import glob
import logging
import os
import time
from bisect import insort_left
from collections.abc import Callable

import numpy as np

from quicknxs.enums import AddToDirectBeamResult, AddToReductionResult, NexusDataType
from quicknxs.exceptions import CrossSectionError
from quicknxs.models import Configuration, data_manipulation, gisans, quicknxs_io
from quicknxs.models.data_set import CrossSectionData, NexusData
from quicknxs.presenters.progress_reporter import ProgressReporter
from quicknxs.utils.filepath import FilePath


class DataManager:
    """Holds information about the current data location and manages the data cache.

    Attributes
    ----------
    current_directory
        Current directory
    _nexus_data
        Current data set
    active_cross_section
        Currently active CrossSectionData
    _cache
        Cache of loaded data
    active_reduction_list_index
        Index of current data (ROI) tab
    peak_reduction_lists
        Dictionary of reduction lists
        key: reduction list index, corresponds to the reduction table tab in the UI
    direct_beam_list
        List of direct beam data sets
    reduction_states
        List of cross-sections common to all reduced data sets
    final_merged_reflectivity
        Merged reflectivity data
    cached_offspec
        Cached off-specular data
    cached_gisans
        Cached GISANS data
    """

    MAX_CACHE = 50  # maximum number of loaded datasets (either single-file or merged-files types)
    MAIN_REDUCTION_LIST_INDEX = 1

    def __init__(self, current_directory: str):
        self.current_directory: str = current_directory
        self._nexus_data: NexusData | None = None

        self.active_cross_section: CrossSectionData | None = None
        self.active_reduction_list_index: int = 1

        # Main data structure holding the reduction list for each ROI/peak
        #    key: reduction list index, corresponds to the reduction table tab in the UI
        #    value: list of NexusData
        self.peak_reduction_lists: dict[int, list[NexusData]] = {self.active_reduction_list_index: []}

        self.direct_beam_list: list[NexusData] = []

        # Track the last selected row index for each reduction table tab and the direct beam tab
        # This allows us to maintain the selection when switching between tabs
        self.last_selected_reduction_row: dict[int, int] = {}  # key: tab index, value: row index
        self.last_selected_direct_beam_row: int = 0

        # List of cross-sections common to all reduced data sets
        self.reduction_states: list[str] = []

        self.final_merged_reflectivity = {}

        # TODO: cache could be improved to be a dict or named tuple with file_path as key (Glass)
        self._cache: list[NexusData] = list()
        self.cached_offspec: dict | None = None
        self.cached_gisans: dict | None = None

        # List of bad files that can't be loaded due to insufficient event count or other failure
        self.bad_files: set[str] = set()

    @property
    def data_sets(self):
        """dict: Dict of reduced cross sections."""
        if self._nexus_data is None:
            return None
        return self._nexus_data.cross_sections

    @property
    def current_file(self):
        if self._nexus_data is None:
            return None
        return self._nexus_data.file_path

    @property
    def current_file_name(self):
        if self._nexus_data is None:
            return None
        return self._nexus_data.file_name

    @property
    def reduction_list(self) -> list[NexusData]:
        """list[NexusData]: Reduction list for the active data tab."""
        return self.peak_reduction_lists[self.active_reduction_list_index]

    @reduction_list.setter
    def reduction_list(self, value):
        self.peak_reduction_lists[self.active_reduction_list_index] = value

    @property
    def main_reduction_list(self) -> list[NexusData]:
        """Reduction list for the first (mandatory) data tab."""
        return self.peak_reduction_lists[self.MAIN_REDUCTION_LIST_INDEX]

    def get_cachesize(self):
        return len(self._cache)

    def clear_cache(self):
        self._cache = []

    def clear_cached_unused_data(self):
        """Delete cached files that are not in the reduction list or direct beam list."""

        def is_used_in_reduction(f: NexusData):
            return (self.find_run_number_in_reduction_list(f) is not None) or (
                self.find_run_number_in_direct_beam_list(f) is not None
            )

        self._cache[:] = [file for file in self._cache if is_used_in_reduction(file)]

    def set_active_data_from_reduction_list(self, index):
        """Set a data set in the reduction list as the active data set according to its index.

        Args:
            index (int): index in the reduction list
        """
        if index < len(self.reduction_list):
            self._nexus_data = self.reduction_list[index]
            self.set_active_cross_section(0)
            # Track the last selected row for this reduction table
            self.last_selected_reduction_row[self.active_reduction_list_index] = index

    def set_active_data_from_direct_beam_list(self, index: int):
        """Set a data set in the direct beam list as the active data set according to its index.

        Args:
            index : index in the direct beam list
        """
        if index < len(self.direct_beam_list):
            self._nexus_data = self.direct_beam_list[index]
            self.set_active_cross_section(0)
            # Track the last selected row for the direct beam table
            self.last_selected_direct_beam_row = index

    def set_active_cross_section(self, index: int) -> bool:
        """Set the current cross section to the specified index, or zero if it doesn't exist."""
        if self.data_sets is None:
            return False
        cross_sections = list(self.data_sets.keys())
        if index < len(cross_sections):
            # cross section index is allowed
            self.active_cross_section = self.data_sets[cross_sections[index]]
            return True
        elif len(cross_sections) == 0:
            # no cross sections
            logging.error("Could not set active cross section: no data available")
        else:
            # default
            self.active_cross_section = self.data_sets[cross_sections[0]]
        return False

    def is_active(self, data_set: NexusData):
        """Check if the given data set is the active data set."""
        return data_set == self._nexus_data

    def is_nexus_data_compatible(self, nexus_data: NexusData, reduction_list: list[NexusData]) -> bool:
        """Determine if the data set is compatible with the data sets in the reduction list.

        A data set is compatible if the polarization cross-section states matches those of the
        first run in the reduction list, both the same number of states and the same states.

        Parameters
        ----------
        nexus_data : NexusData
            The data set to check if compatible with reduction list
        reduction_list : list[NexusData]
            The reduction list

        Returns
        -------
        bool
            True if the data set is compatible with the reduction list, False otherwise.
        """
        # If we are starting a new reduction list, just proceed
        if not reduction_list:
            return True

        nexus_data_states = list(nexus_data.cross_sections.keys())
        reduction_list_states = list(reduction_list[0].cross_sections.keys())

        # First, check that we have the same number of states
        if not len(reduction_list_states) == len(nexus_data_states):
            logging.error(
                f"Nexus data cross-sections ({reduction_list_states}) different than those of the"
                f" reduction list ({nexus_data_states})"
            )
            return False

        # Second, make sure the states match
        for cross_section_state in nexus_data_states:
            if cross_section_state not in reduction_list_states:
                logging.error(
                    f"Nexus data cross-section {cross_section_state} not found in those of the reduction list"
                )
                return False
        return True

    def find_run_number_in_reduction_list(
        self,
        nexus_data: NexusData | None,
        reduction_list: list[NexusData] | None = None,
    ) -> int | None:
        """Look for the given run number in a reduction list, or the active reduction list if None.

        Returns
        -------
        int | None
            The index in the reduction list or None
        """
        if nexus_data is None:
            return None

        if reduction_list is None:
            reduction_list = self.reduction_list

        for i, _nexus_data in enumerate(reduction_list):
            if _nexus_data.run_number == nexus_data.run_number:
                return i
        return None

    def find_data_in_reduction_list(self, nexus_data: NexusData | None) -> int | None:
        """Return the index of the given data in the active reduction list, or None if not found.

        Returns
        -------
        int | None:
            The index within the reduction list, or none.
        """
        if nexus_data is None:
            return None
        for i in range(len(self.reduction_list)):
            if nexus_data == self.reduction_list[i]:
                return i
        return None

    def find_data_in_direct_beam_list(self, nexus_data: NexusData | None) -> int | None:
        """Return the index of the given data in the direct beam list, or None if not found.

        Returns
        -------
        int | None:
            The index within the direct beam list, or none.
        """
        if nexus_data is None:
            return None
        for i in range(len(self.direct_beam_list)):
            if nexus_data == self.direct_beam_list[i]:
                return i
        return None

    def find_run_number_in_direct_beam_list(self, nexus_data: NexusData | None) -> int | None:
        """Look for data with the same run number in the direct beam list.

        This method compares by run number rather than object identity, which is useful
        for detecting duplicates when deepcopied objects are involved.

        Parameters
        ----------
        nexus_data : NexusData | None
            The data to search for by run number.

        Returns
        -------
        int | None:
            The index within the direct beam list, or None if not found.
        """
        if nexus_data is None:
            return None
        for i in range(len(self.direct_beam_list)):
            if nexus_data.run_number == self.direct_beam_list[i].run_number:
                return i
        return None

    def find_active_data_id(self) -> int | None:
        """Look for the active data in the reduction list.

        Returns
        -------
        int | None:
            The index within the reduction list or none.
        """
        return self.find_data_in_reduction_list(self._nexus_data)

    def find_active_direct_beam_id(self) -> int | None:
        """Look for the active data in the direct beam list.

        Returns
        -------
        int | None:
            The index within the direct beam list or none.
        """
        return self.find_data_in_direct_beam_list(self._nexus_data)

    def _insert_into_reduction_list_by_q(self, nexus_data: NexusData, reduction_list: list[NexusData]) -> bool:
        """Insert NexusData into reduction list in ascending Q order.

        Parameters
        ----------
        nexus_data:
            Data to insert
        reduction_list:
            Target reduction list

        Returns
        -------
        bool
            True if successfully inserted, False if Q range is unavailable
        """
        q_min, _ = nexus_data.get_q_range()

        if q_min is None:
            # Try calculating reflectivity to get Q range if not already available
            try:
                self.calculate_reflectivity(nexus_data=nexus_data)
                q_min, _ = nexus_data.get_q_range()
            except Exception:  # TODO (Glass): determine specific exceptions to catch here
                logging.exception(f"Error calculating reflectivity for data set {nexus_data.run_number}")

        # If we still don't have q range information, we can't insert in order
        if q_min is None:
            logging.error(f"Could not get q range for data set {nexus_data.run_number}, cannot insert in order.")
            return False

        # Use binary search to find the correct insertion point to keep the list sorted by q_min
        insort_left(reduction_list, nexus_data, key=lambda x: x.get_q_range()[0])
        return True

    def add_active_to_reduction(self, peak_index=MAIN_REDUCTION_LIST_INDEX) -> AddToReductionResult:
        """Add active data set to reduction list.

        New data sets are always added to the main reduction list. Data sets are added to secondary
        reduction lists by initializing from the main reduction list (button to add new data tab)
        or by propagating individual data sets to other tabs (right-click menu).

        Parameters
        ----------
        peak_index: int
            The index of the peak in peak_reduction_lists

        Returns
        -------
        AddToReductionResult
            Result of the add operation, including success or reason for failure.
        """
        reduction_list = self.peak_reduction_lists[peak_index]

        # Check if already in list by run number (since we may have deepcopied objects)
        if self.find_run_number_in_reduction_list(self._nexus_data, reduction_list) is not None:
            logging.warning(f"Data set {self._nexus_data.run_number} is already in the reduction list.")
            return AddToReductionResult.ALREADY_IN_LIST

        if not self.is_nexus_data_compatible(self._nexus_data, reduction_list):
            logging.error("The data you are trying to add has different cross-sections")
            return AddToReductionResult.INCOMPATIBLE

        if len(reduction_list) == 0:
            self.reduction_states = list(self.data_sets.keys())

        # Create a deepcopy to allow adding the same run to the reduction list(s) and direct beam list without sharing state
        # Ensure data added to reduction list is marked as reflected, even if original data is a direct beam
        nexus_data = copy.deepcopy(self._nexus_data)
        nexus_data.set_is_direct_beam(False)
        nexus_data.clone_and_rename_event_workspaces(data_type=NexusDataType.REFLECTED)

        result = self._insert_into_reduction_list_by_q(nexus_data, reduction_list)
        if not result:
            return AddToReductionResult.OTHER_ERROR

        if self._nexus_data.is_direct_beam():
            logging.warning(
                f"Run {nexus_data.run_number} was added to the reduction list but is labeled as a direct beam."
            )
            result = AddToReductionResult.SUCCESS_DIRECT_BEAM
        else:
            result = AddToReductionResult.SUCCESS

        self._nexus_data = nexus_data
        return result

    def copy_nexus_data_to_reduction(self, nexus_data_to_copy: NexusData, peak_index: int):
        """Add data set to the reduction list specified by `peak_index`.

        Parameters
        ----------
        nexus_data_to_copy:
            Data set to copy
        peak_index:
            reduction list to copy data set to

        Returns
        -------
        bool
            True if the data set was added successfully, otherwise False
        """
        reduction_list = self.peak_reduction_lists[peak_index]

        # check if run already exists in this reduction list
        if any(run_data.run_number == nexus_data_to_copy.run_number for run_data in reduction_list):
            return False

        nexus_data = copy.deepcopy(nexus_data_to_copy)
        if self.is_nexus_data_compatible(nexus_data, reduction_list):
            return self._insert_into_reduction_list_by_q(nexus_data, reduction_list)
        else:
            logging.error("The data you are trying to add has different cross-sections")
        return False

    def add_active_to_direct_beam_list(self):
        """Add active data set to the direct beam list.

        This method allows adding any run to the direct beam list, even if it wasn't originally
        acquired as a direct beam (i.e., when the PV data_type != 1). This is useful for
        calibration and other runs started with "Start RUN" command in EPICS, which don't add
        the "Direct Beam" PV-tag.

        Returns
        -------
        AddToDirectBeamResult
            Result of the add operation, including success or reason for failure.
        """
        # Check if already in list by run number (since we may have deepcopied objects)
        if self.find_run_number_in_direct_beam_list(self._nexus_data) is not None:
            return AddToDirectBeamResult.ALREADY_IN_LIST

        # Create a deepcopy to allow adding the same run to the direct beam and data lists without sharing state
        # ensure data added to direct beam list is marked as direct beam, even if original data is reflected
        nexus_data = copy.deepcopy(self._nexus_data)
        nexus_data.set_is_direct_beam(True)
        nexus_data.clone_and_rename_event_workspaces(data_type=NexusDataType.DIRECT_BEAM)
        self.direct_beam_list.append(nexus_data)

        if self._nexus_data.is_direct_beam():
            result = AddToDirectBeamResult.SUCCESS
        else:
            logging.warning(
                f"Run {self._nexus_data.run_number} was added to the direct beam list but is not labeled as a direct beam "
                "(data_type PV ≠ 1). This run may have been started with 'Start RUN' command."
            )
            result = AddToDirectBeamResult.SUCCESS_REFLECTED

        self._nexus_data = nexus_data
        return result

    def remove_active_from_direct_beam_list(self):
        """Remove the active data set from the direct beam list.

        Uses run number comparison to find the entry.
        """
        index = self.find_run_number_in_direct_beam_list(self._nexus_data)
        if index is not None:
            self.direct_beam_list.pop(index)
            return index
        return -1

    def remove_from_active_reduction_list(self, index: int):
        """
        Remove item from the active reduction list.

        Parameters
        ----------
        index: int
            Index of the item to remove
        """
        self.reduction_list.pop(index)

    def clear_direct_beam_list(self):
        """Remove all items from the direct beam list."""
        # TODO: remove links from scattering data sets.
        self.direct_beam_list = []

    def _loading_progress(self, call_back, start_value, stop_value, value, message=None):
        _value = start_value + (stop_value - start_value) * value
        call_back(_value, message)

    def load(
        self,
        file_path: str,
        configuration: Configuration,
        force: bool = False,
        update_parameters: bool = True,
        progress: Callable | None = None,
    ) -> bool:
        """Load one or more Nexus data files.

        Parameters
        ----------
        file_path:
            absolute path to one or more files.
            If more than one, files are concatenated with the merge symbol '+'.
        configuration:
            Configuration to use to load the data
        force:
            if True, existing data in the cache will be replaced by reading from file.
        update_parameters:
            if True, we will find peak ranges
        progress:
            aggregator to estimate percent of time allotted to this function

        Returns
        -------
        bool:
            True if the data is retrieved from the cache of past loading events
        """
        # Actions taken in this function:
        # 1. Find if the file has been loaded in the past. Retrieve the cache when force==False
        # 2. If file not in cache, or if force==True: invoke NexusData.load()
        # 3. Update attributes _nexus_data and current_directory
        # 4. If we're overwriting cached data that was allocated in the reduction_list and direct_beam_list,
        #    then assign the new data to the proper indexes in lists reduction_list and direct_beam_list
        # 5. Compute reflectivity if data is loaded from file

        nexus_data = None  # type: NexusData | None
        is_from_cache = False  # if True, the file has been loaded before
        reduction_list_id = None
        direct_beam_list_id = None
        file_path = FilePath(file_path, sort=True).path  # force sorting by increasing run number

        if progress is not None:
            progress(10, "Loading data...")

        # Search through current reduction list, direct beam list, and cache for the file path.
        # If found and force is False, the matching data will become the active data in the UI.
        # Cache entries are iterated last so they don't take priority over reduction/direct beam list copies
        # that share the same file_path (e.g. deep copies created when adding a run to multiple lists).
        # This prevents force-reloading from accidentally replacing a direct beam list entry with a
        # freshly-loaded object that lacks the _DIRECT_BEAM workspace suffix.
        nexus_data_search = self.reduction_list + self.direct_beam_list + self._cache
        file_paths_in_search_list = {data.file_path: data for data in nexus_data_search}
        if file_path in file_paths_in_search_list:
            logging.info(f"DataManager.load: found {file_path} in cache of previously loaded data")
            _nxs_data = file_paths_in_search_list[file_path]
            if force:
                logging.info(f"DataManager.load: force=True - reloading {file_path} from file and replacing cache")
                # Check whether the data is in the reduction list before removing it
                reduction_list_id = self.find_data_in_reduction_list(_nxs_data)
                direct_beam_list_id = self.find_data_in_direct_beam_list(_nxs_data)
                # If the data is in the cache, remove it
                if _nxs_data in self._cache:
                    self._cache.remove(_nxs_data)
            else:
                logging.info(f"DataManager.load: force=False - using cached data for {file_path}")
                nexus_data = _nxs_data
                is_from_cache = True

        # If we don't have the data, load it
        if nexus_data is None:
            nexus_data = NexusData(file_path, configuration)
            sub_task = progress.create_sub_task(max_value=70) if progress else None
            try:
                nexus_data.load(progress=sub_task, update_parameters=update_parameters)
            except CrossSectionError as ex:
                self.bad_files.add(ex.file_name)
                raise

        if progress is not None:
            progress(80, "Calculating...")

        # Set the current data to the loaded data, whether from cache or from file
        self._nexus_data = nexus_data

        # Example: '/SNS/REF_M/IPTS-25531/nexus/REF_M_38198.nxs.h5+/SNS/REF_M/IPTS-25531/nexus/REF_M_38199.nxs.h5'
        # will be split into directory='/SNS/REF_M/IPTS-25531/nexus' and
        # file_name='REF_M_38198.nxs.h5+REF_M_38199.nxs.h5'
        directory, file_name = FilePath(file_path).split()
        self.current_directory = directory
        self.set_active_cross_section(0)

        # If we didn't get this data set from our cache, add it and compute its reflectivity.
        if not is_from_cache:
            # Find suitable direct beam
            if configuration.match_direct_beam:
                match_found = self.find_best_direct_beam()
                direct_beam = self.get_active_direct_beam()
                if match_found and direct_beam is not None:
                    dpix = direct_beam.configuration.peak_position
                    self._nexus_data.set_parameter("direct_pixel_overwrite", dpix)
                else:
                    logging.info(f"DataManager.load: No matching direct beam found - {match_found=}, {direct_beam=}")

            # Replace reduction and direct beam entries as needed
            if reduction_list_id is not None:
                self.reduction_list[reduction_list_id] = nexus_data
            if direct_beam_list_id is not None:
                self.direct_beam_list[direct_beam_list_id] = nexus_data

            # Compute reflectivity
            if not nexus_data.is_direct_beam():
                try:
                    self.calculate_reflectivity()
                except Exception as e:
                    logging.error(f"Reflectivity calculation failed for {file_name}: {e}")

            # if cached reduced data exceeds maximum cache size, remove the oldest reduced data
            while len(self._cache) >= self.MAX_CACHE:
                self._cache.pop(0)
            self._cache.append(nexus_data)

        if progress is not None:
            progress(100)
        return is_from_cache

    def update_configuration(self, configuration, active_only: bool = False, nexus_data: NexusData | None = None):
        """Update configuration."""
        if active_only:
            if self.active_cross_section is None:
                logging.error("No active cross section to update configuration")
                return
            self.active_cross_section.update_configuration(configuration)
        elif nexus_data is not None:
            nexus_data.update_configuration(configuration)
        else:
            self._nexus_data.update_configuration(configuration)

    def get_active_direct_beam(self):
        """Return the direct beam data object for the active data."""
        return self._find_direct_beam(self._nexus_data)

    def update_direct_pixel_from_direct_beam(self) -> float | None:
        """Set `direct_pixel_overwrite` based on the matched direct beam peak position."""
        if self._nexus_data is None:
            return None

        direct_beam = self.get_active_direct_beam()
        if direct_beam is None:
            return None

        dpix = direct_beam.configuration.peak_position
        self._nexus_data.set_parameter("direct_pixel_overwrite", dpix)
        return dpix

    def is_same_run(self, run_number_a: str | int, run_number_b: str | int) -> bool:
        """
        Returns True if two run numbers are considered the same.

        Tries to compare the run numbers as integers if possible;
        falls back to comparing them as-is (e.g., strings).

        Parameters
        ----------
        run_number_a : str or int
            The first run number.
        run_number_b : str or int
            The second run number.

        Returns
        -------
        bool
            True if the run numbers are equal (after normalization), False otherwise.
        """

        def normalize(run):
            try:
                return int(run)
            except (ValueError, TypeError):
                return run

        return normalize(run_number_a) == normalize(run_number_b)

    def is_direct_beam_for_run(self, nexus_data: NexusData, direct_beam_run: str | int) -> bool:
        """Check if the direct beam is the configured direct beam for the given run.

        Parameters
        ----------
        nexus_data : NexusData
            NexusData run object
        direct_beam : str | int
            Direct beam run number
        """
        run_direct_beam = self._find_direct_beam(nexus_data)
        return run_direct_beam is not None and self.is_same_run(run_direct_beam.run_number, direct_beam_run)

    def _find_direct_beam(self, nexus_data: NexusData | CrossSectionData) -> CrossSectionData | None:
        """Attempt to find a direct beam data set for a given reflectivity data set.

        Returns
        -------
        CrossSectionData or None:
            The direct beam data set if found, otherwise None.
        """
        # Find the CrossSectionData object to work with
        if isinstance(nexus_data, NexusData):
            # Get the direct beam info from the configuration
            # All the cross sections should have the same direct beam file.
            data_keys = list(nexus_data.cross_sections.keys())
            if len(data_keys) == 0:
                logging.error("DataManager._find_direct_beam: no data available in NexusData object")
                return
            data_xs = nexus_data.cross_sections[data_keys[0]]
        elif isinstance(nexus_data, CrossSectionData):
            data_xs = nexus_data
        else:
            raise TypeError("nexus_data must be a NexusData or CrossSectionData object")

        direct_beam = None
        if data_xs.configuration is None or data_xs.configuration.direct_beam is None:
            return direct_beam
        data_xs_direct_beam = data_xs.configuration.direct_beam
        for direct_beam_item in self.direct_beam_list:
            if not self.is_same_run(direct_beam_item.run_number, data_xs_direct_beam):
                continue
            keys = list(direct_beam_item.cross_sections.keys())
            if not keys:
                logging.error(f"Direct beam {direct_beam_item.run_number} has no cross-sections")
                continue
            if len(keys) > 1:
                logging.error("More than one cross-section for the direct beam, using the first one")
            direct_beam = direct_beam_item.cross_sections[keys[0]]
            break
        if direct_beam is None:
            logging.error("The specified direct beam is not available: skipping")

        return direct_beam

    def find_direct_beam_by_name(self, direct_beam_name: str) -> NexusData | None:
        """Find a direct beam data set by its name.

        Parameters
        ----------
        direct_beam_name : str
            Name of the direct beam run to find.

        Returns
        -------
        NexusData or None
            The direct beam data set if found, otherwise None.
        """
        for db in self.direct_beam_list:
            if db.run_number == str(direct_beam_name):
                return db
        return None

    def reduce_gisans(self, progress=None):
        """Calculate GISANS for all datasets in the reduction list.

        Since the specular reflectivity is prominently displayed, it is updated as
        soon as parameters change. This is not the case for GISANS, which is
        computed on-demand.
        """
        if progress is not None:
            progress(1, "Reducing GISANS...")
        for i, nexus_data in enumerate(self.reduction_list):
            try:
                self.calculate_gisans(nexus_data=nexus_data, progress=None)
                if progress is not None:
                    progress(100.0 / len(self.reduction_list) * (i + 1))
            except Exception as e:
                logging.error("Could not compute GISANS for %s\n  %s", nexus_data.run_number, e)
        if progress is not None:
            progress(100)

    def calculate_gisans(self, nexus_data=None, progress=None):
        """Compute GISANS for a single data set."""
        t_0 = time.time()
        # Select the data to work on
        if nexus_data is None:
            nexus_data = self._nexus_data

        # We must have a direct beam data set to normalize with
        direct_beam = self._find_direct_beam(nexus_data)
        if direct_beam is None:
            return False

        nexus_data.calculate_gisans(direct_beam=direct_beam, progress=progress)
        logging.info("Calculate GISANS: %s %s sec", nexus_data.run_number, (time.time() - t_0))
        return True

    def is_offspec_available(self):
        """Verify that all data sets and all cross-sections have calculated off-specular data available."""
        for nexus_data in self.reduction_list:
            if not nexus_data.is_offspec_available():
                return False
        return True

    def is_gisans_available(self, active_only=True):
        """Verify that all data sets and all cross-sections have calculated GISANS data available."""
        if active_only:
            return self._nexus_data.is_gisans_available()

        for nexus_data in self.reduction_list:
            if not nexus_data.is_gisans_available():
                return False
        return True

    def reduce_spec(self, direct_beam: str | int | None = None):
        """
        Calculate reflectivity for all runs in all reduction lists.

        If a direct beam is given, only calculate reflectivity for the runs using the given direct beam.

        Parameters
        ----------
        direct_beam : str | int | None
            Direct beam run number
        """
        for reduct_list in self.peak_reduction_lists.values():
            for nexus_data in reduct_list:
                if direct_beam is not None and not self.is_direct_beam_for_run(nexus_data, direct_beam):
                    continue
                try:
                    self.calculate_reflectivity(nexus_data=nexus_data)
                except Exception as e:
                    logging.error("Could not compute reflectivity for %s\n  %s", nexus_data.run_number, e)

    def reduce_offspec(self, progress=None):
        """Calculate off-specular reflectivity for all datasets in all reduction list.

        Since the specular reflectivity is prominently displayed, it is updated as
        soon as parameters change. This is not the case for the off-specular, which is
        computed on-demand.
        """
        for nexus_data in self.reduction_list:
            try:
                self.calculate_reflectivity(nexus_data=nexus_data, specular=False)
            except Exception as e:
                logging.error("Could not compute reflectivity for %s\n  %s", nexus_data.run_number, e)

    def rebin_gisans(self, pol_state, wl_min=0, wl_max=100, qy_npts=50, qz_npts=50, use_pf=False):
        """Merge all the off-specular reflectivity data and rebin."""
        return gisans.rebin_extract(
            self.reduction_list,
            pol_state=pol_state,
            wl_min=wl_min,
            wl_max=wl_max,
            qy_npts=qy_npts,
            qz_npts=qz_npts,
            use_pf=use_pf,
        )

    # TODO 67 Find out whether it can work with merged data
    def calculate_reflectivity(self, configuration=None, active_only=False, nexus_data=None, specular=True):
        """Calculate reflectivity using the current configuration."""
        # Select the data to work on
        if nexus_data is None:
            nexus_data = self._nexus_data

        # Try to find the direct beam in the list of direct beam data sets
        direct_beam = self._find_direct_beam(nexus_data)

        if not specular:
            nexus_data.calculate_offspec(direct_beam=direct_beam)
        elif active_only:
            self.active_cross_section.reflectivity(direct_beam=direct_beam, configuration=configuration)
        else:
            nexus_data.calculate_reflectivity(
                direct_beam=direct_beam, configuration=configuration, ws_suffix=str(self.active_reduction_list_index)
            )

    def find_best_direct_beam(self):
        """Find the best direct beam in the direct beam list for the active data.

        Returns
        -------
        bool:
            True if we have updated the data with a new normalization run.
        """
        closest = None
        # for each run in the beamline, compute a closeness score
        # if the wavelengths do not match within tolerance, this is some overlarge value
        # if the wavelengths do match, compute a euclidean difference of their slit widths
        # pick the run with a matching wavelength and lowest euclidean slit difference
        active_xs = self.active_cross_section
        active_instrument = active_xs.configuration.instrument
        closeness: dict[int, float] = {}
        for item in self.direct_beam_list:
            item_number = int(item.run_number)
            xs_keys = list(item.cross_sections.keys())
            if len(xs_keys) > 0:
                xs = item.cross_sections[xs_keys[0]]
                if active_instrument.direct_beam_match(active_xs, xs, skip_slits=True):
                    closeness[item_number] = active_instrument.direct_beam_distance(active_xs, xs)
                else:
                    closeness[item_number] = 1.0e16

        if len(self.direct_beam_list) > 0:
            closest = min(closeness.items(), key=lambda item: item[1])[0]

        logging.info(f"Best direct beam for run {self._nexus_data.run_number} is {closest}")
        if closest is not None:
            try:
                self._nexus_data.set_parameter("direct_beam", closest)
                return True
            except Exception as e:
                logging.error(f"Could not set direct beam to {closest}: {e}")
                return False
        return False

    def get_trim_values(self) -> list[int] | None:
        """Cut the start and end of the active data set to 5% of its maximum intensity."""
        if (
            self.active_cross_section is not None
            and self.active_cross_section.q is not None
            and self.active_cross_section.configuration.direct_beam is not None
        ):
            direct_beam = self._find_direct_beam(self.active_cross_section)

            if direct_beam is None:
                logging.error("The specified direct beam is not available: skipping")
                return None

            region = np.where(direct_beam.r >= (direct_beam.r.max() * 0.05))[0]
            p_0 = region[0]
            p_n = len(direct_beam.r) - region[-1] - 1
            self._nexus_data.set_parameter("cut_first_n_points", p_0)
            self._nexus_data.set_parameter("cut_last_n_points", p_n)
            return [p_0, p_n]
        return None

    def strip_overlap(self):
        """Remove overlapping points in the reflectivity, cutting always from the lower Qz measurements."""
        if len(self.reduction_list) < 2:
            logging.error("You need to have at least two datasets in the reduction table")
            return
        xs = self.active_cross_section.name
        for idx, item in enumerate(self.reduction_list[:-1]):
            next_item = self.reduction_list[idx + 1]
            end_idx = next_item.cross_sections[xs].configuration.cut_first_n_points

            overlap_idx = np.where(item.cross_sections[xs].q >= next_item.cross_sections[xs].q[end_idx])
            logging.error(overlap_idx[0])
            if len(overlap_idx[0]) > 0:
                n_points = len(item.cross_sections[xs].q) - overlap_idx[0][0]
                item.set_parameter("cut_last_n_points", n_points)

    def stitch_data_sets(
        self,
        normalize_to_unity: bool = True,
        q_cutoff: float = 0.01,
        global_stitching: bool = False,
        poly_degree: int | None = None,
        poly_points: int = 3,
    ):
        """Determine scaling factors for each data set.

        Parameters
        ----------
        normalize_to_unity:
            If True, the reflectivity plateau will be normalized to 1.
        q_cutoff:
            critical q-value below which we expect R=1
        global_stitching:
            If True, use data from all cross-sections to calculate scaling factors
        poly_degree:
            if not None, find the scaling factor by simultaneously fitting a polynomial and scaling factor to the curves
        poly_points:
            number of additional points on each end of the overlap region to include in the fit
        """
        data_manipulation.stitch_reflectivity(
            self.reduction_list,
            self.active_cross_section.name,
            normalize_to_unity,
            q_cutoff,
            global_stitching,
            poly_degree,
            poly_points,
        )

    def merge_data_sets(self, asymmetry=True):
        self.final_merged_reflectivity = {}
        for pol_state in self.reduction_states:
            # The scaling factors should have been determined at this point. Just use them
            # to merge the different runs in a set.
            merged_ws = data_manipulation.merge_reflectivity(
                self.reduction_list, xs=pol_state, q_min=0.001, q_step=-0.01
            )
            self.final_merged_reflectivity[pol_state] = merged_ws

        # Compute asymmetry
        if asymmetry:
            self.asymmetry()

    def determine_asymmetry_states(self):
        """Determine which cross-section to use to compute asymmetry."""
        # Inspect cross-section
        # - For two states, just calculate the asymmetry using those two
        p_state = None
        m_state = None
        if len(self.reduction_states) == 2:
            if self.reduction_states[0].lower() in ["off_off", "off-off"]:
                p_state = self.reduction_states[0]
                m_state = self.reduction_states[1]
            else:
                p_state = self.reduction_states[1]
                m_state = self.reduction_states[0]
        else:
            _p_state_data = None
            _m_state_data = None
            for item in self.reduction_states:
                if item.lower() in ["off_off", "off-off"]:
                    _p_state_data = item
                if item.lower() in ["on_on", "on-on"]:
                    _m_state_data = item

            if _p_state_data is None or _m_state_data is None:
                _p_state_data = None
                _m_state_data = None
                for item in self.reduction_states:
                    if self.data_sets[item].cross_section_label == "++":
                        _p_state_data = item
                    if self.data_sets[item].cross_section_label == "--":
                        _m_state_data = item

            if _p_state_data is None or _m_state_data is None:
                p_state = None
                m_state = None

        # - If we haven't made sense of it yet, take the first and last cross-sections
        if p_state is None and m_state is None and len(self.reduction_states) >= 2:
            p_state = self.reduction_states[0]
            m_state = self.reduction_states[-1]

        return p_state, m_state

    def asymmetry(self):
        """Determine which cross-section to use to compute asymmetry, and compute it."""
        p_state, m_state = self.determine_asymmetry_states()

        # Get the list of workspaces
        if p_state in self.final_merged_reflectivity and m_state in self.final_merged_reflectivity:
            p_ws = self.final_merged_reflectivity[p_state]
            m_ws = self.final_merged_reflectivity[m_state]
            ratio_ws = (p_ws - m_ws) / (p_ws + m_ws)

            self.final_merged_reflectivity["SA"] = ratio_ws

    def extract_metadata(self, file_path=None):
        """Return the current q-value at the center of the wavelength range of the current data set.

        If a file path is provided, the mid q-value will be extracted from that data file.
        """
        if file_path is not None:
            return data_manipulation.extract_metadata(
                file_path=file_path, configuration=self.active_cross_section.configuration
            )
        return data_manipulation.extract_metadata(cross_section_data=self.active_cross_section)

    def load_data_from_reduced_file(
        self,
        file_path: str,
        configuration: Configuration | None = None,
        progress: ProgressReporter | None = None,
    ):
        """Load the information from a reduced file, the load the data.

        Ask the main event handler to update the UI once we are done.
        """
        t_0 = time.time()
        db_files, data_files, additional_peaks, has_scaling_error = quicknxs_io.read_reduced_file(
            file_path, configuration
        )
        logging.info("Reduced file loaded: %s sec", time.time() - t_0)
        n_total = len(db_files) + len(data_files)
        if progress and n_total > 0:
            progress.set_value(1, message=f"Loaded {os.path.basename(file_path)}", out_of=n_total)
        self.load_direct_beam_and_data_files(db_files, data_files, additional_peaks, configuration, progress, True, t_0)
        if progress and not has_scaling_error:
            progress.set_value(
                1,
                "NOTE: Initial error bars may be inaccurate - please run stitching to update scaling factor errors.",
                1,
            )
        logging.info("DONE: %s sec", time.time() - t_0)

    def load_direct_beam_and_data_files(
        self,
        db_files: list[tuple],
        data_files: list[tuple],
        additional_peaks: list | None = None,
        configuration: Configuration | None = None,
        progress: ProgressReporter | None = None,
        force: bool = False,
        t_0: float | None = None,
    ):
        """Load direct beam and data files and add them to the direct beam list and reduction list, respectively.

        Parameters
        ----------
        db_files: list
            List of (run_number, run_file, conf, slice_value) for direct beam files
        data_files: list
            List of (run_number, run_file, conf, slice_value) for data files
        additional_peaks: list | None
            List of (peak_index, run_number, run_file, conf, slice_value) for data files for additional peaks
        configuration: Configuration
            Configuration to base the loaded data on
        progress: ProgressReporter
            Progress reporter
        force: bool
            If True, ignore cache and force reloading from file
        t_0: float
            Start time for logging data loading time
        """
        if not t_0:
            t_0 = time.time()
        n_loaded = 0
        n_total = len(db_files) + len(data_files)
        # Add direct beam runs
        for r_id, run_file, conf, slice_value in db_files:
            logging.info(f"LOADING DIR BEAM FILE: {run_file}")
            t_i = time.time()
            if os.path.isfile(run_file):
                is_from_cache = self.load(run_file, conf, force=force, update_parameters=False)
                if is_from_cache:
                    configuration.direct_beam = None
                    self._nexus_data.update_configuration(conf)
                # Set the slice value on the NexusData object
                self._nexus_data.slice = slice_value
                self.add_active_to_direct_beam_list()
                logging.info("%s loaded: %s sec [%s]", r_id, time.time() - t_i, time.time() - t_0)
                if progress:
                    progress.set_value(n_loaded, message=f"{os.path.basename(run_file)} loaded", out_of=n_total)
            else:
                logging.error("File does not exist: %s", run_file)
                if progress:
                    progress.set_value(n_loaded, message=f"ERROR: {run_file} does not exist", out_of=n_total)
            n_loaded += 1

        # Add reflectivity runs
        for r_id, run_file, conf, slice_value in data_files:
            logging.info(f"LOADING REF FILE: {run_file}")
            t_i = time.time()
            do_files_exist = []
            for name in run_file.split("+"):
                do_files_exist.append(os.path.isfile(name))

            if all(do_files_exist):
                is_from_cache = self.load(run_file, conf, force=force, update_parameters=False)
                if is_from_cache:
                    configuration.direct_beam = None
                    self._nexus_data.update_configuration(conf)
                    self.calculate_reflectivity()
                # Set the slice value on the NexusData object
                self._nexus_data.slice = slice_value
                result = self.add_active_to_reduction()
                if result in [AddToReductionResult.SUCCESS, AddToReductionResult.SUCCESS_DIRECT_BEAM]:
                    logging.info(f"{r_id} loaded: {time.time() - t_i} sec [{time.time() - t_0}]")
                else:
                    logging.error(f"Could not add run {r_id} to reduction table: {result.value}")
                if progress:
                    progress.set_value(n_loaded, message=f"{os.path.basename(run_file)} loaded", out_of=n_total)
            else:
                logging.error(f"File does not exist: {run_file}")
                if progress:
                    progress.set_value(n_loaded, message=f"ERROR: {run_file} does not exist", out_of=n_total)
            n_loaded += 1
        if progress:
            progress.set_value(n_total, message="Done", out_of=n_total)

        # Initialize any additional peak reduction lists by copying the data from the main reduction list
        if additional_peaks:
            for peak_index, r_id, run_file, conf, slice_value in additional_peaks:
                if peak_index not in self.peak_reduction_lists:
                    self.peak_reduction_lists[peak_index] = []
                self.set_active_reduction_list_index(peak_index)
                # find run in main reduction list and make a copy
                # Match by file path which handles both single and summed runs correctly
                run_index = [i for i, data in enumerate(self.main_reduction_list) if data.file_path == run_file][0]
                self._nexus_data = copy.deepcopy(self.main_reduction_list[run_index])
                configuration.direct_beam = None
                self.update_configuration(conf)
                self.calculate_reflectivity()
                # Set the slice value on the NexusData object
                self._nexus_data.slice = slice_value
                self.add_active_to_reduction(peak_index)

    @property
    def current_event_files(self) -> list[str]:
        """Sorted list of event files in the current directory.

        Return only file names with pattern '*event.nxs' or '*.nxs.h5'
        """
        event_file_list = glob.glob(os.path.join(self.current_directory, "*event.nxs"))
        h5_file_list = glob.glob(os.path.join(self.current_directory, "*.nxs.h5"))
        event_file_list.extend(h5_file_list)
        return sorted([os.path.basename(name) for name in event_file_list])

    def reload_files(self, configuration: Configuration | None = None, progress=None):
        """Force reload of files in the reduction lists and direct beam list."""

        def _get_nexus_conf(nexus_data: NexusData) -> Configuration:
            """Returns the configuration for the main cross-section of the run."""
            return nexus_data.cross_sections[nexus_data.main_cross_section].configuration

        # Get files to reload
        db_files = [
            (nexus.run_number, nexus.file_path, _get_nexus_conf(nexus), nexus.slice) for nexus in self.direct_beam_list
        ]
        data_files = []
        additional_peaks = []
        for ipeak, reduction_list in self.peak_reduction_lists.items():
            if ipeak == self.MAIN_REDUCTION_LIST_INDEX:
                data_files = [
                    (nexus.run_number, nexus.file_path, _get_nexus_conf(nexus), nexus.slice) for nexus in reduction_list
                ]
            else:
                additional_peaks = [
                    (ipeak, nexus.run_number, nexus.file_path, _get_nexus_conf(nexus), nexus.slice)
                    for nexus in reduction_list
                ]
        # Clear the lists
        self.direct_beam_list.clear()
        [reduct_list.clear() for reduct_list in self.peak_reduction_lists.values()]
        # Reload files and add to reduction and direct beam lists
        self.load_direct_beam_and_data_files(db_files, data_files, additional_peaks, configuration, progress, True)

    def add_additional_reduction_list(self, tab_index: int):
        """Add reduction list for an additional ROI/peak.

        Parameters
        ----------
        tab_index: int
            Index of the peak in `self.peak_reduction_lists`
        """
        if self.main_reduction_list is not None and tab_index not in self.peak_reduction_lists:
            self.peak_reduction_lists[tab_index] = copy.deepcopy(self.main_reduction_list)

    def remove_additional_reduction_list(self, tab_index: int):
        """Remove reduction list for additional ROI/peak.

        Parameters
        ----------
        tab_index: int
            Index of the peak in `self.peak_reduction_lists`
        """
        if tab_index in self.peak_reduction_lists:
            self.peak_reduction_lists.pop(tab_index)

    def set_active_reduction_list_index(self, tab_index: int):
        """Set the active reduction list index.

        Parameters
        ----------
        tab_index: int
            Index of the peak in `self.peak_reduction_lists`
        """
        self.active_reduction_list_index = tab_index

    def update_active_reduction_list(self, tab_index: int):
        """Updates the active reduction list and run.

        Parameters
        ----------
        tab_index: int
            Index of the peak in `self.peak_reduction_lists`
        """
        self.set_active_reduction_list_index(tab_index)

        # Try to restore the last selected row for this tab
        if tab_index in self.last_selected_reduction_row:
            last_row = self.last_selected_reduction_row[tab_index]
            if last_row < len(self.reduction_list):
                self.set_active_data_from_reduction_list(last_row)
                return

        # Otherwise, try to keep same row index as current active data
        active_data_idx = self.find_active_data_id()
        if active_data_idx and active_data_idx < len(self.reduction_list):
            self.set_active_data_from_reduction_list(active_data_idx)
        else:
            # Default to first row
            self.set_active_data_from_reduction_list(0)

    def update_active_direct_beam(self):
        """Updates the active direct beam when switching to the direct beam tab.

        Tries to maintain the previously selected direct beam row index if available,
        otherwise defaults to the first direct beam.
        """
        # Keep the current object only if it is already the direct beam copy.
        # The same run number can exist in both the reduction and direct beam lists
        # as separate deep-copied objects with different workspace types.
        active_direct_beam_idx = self.find_data_in_direct_beam_list(self._nexus_data)
        if active_direct_beam_idx is not None:
            # Update the tracked index to match current selection
            self.last_selected_direct_beam_row = active_direct_beam_idx
            return

        # Try to restore the last selected direct beam row
        if self.last_selected_direct_beam_row < len(self.direct_beam_list):
            self.set_active_data_from_direct_beam_list(self.last_selected_direct_beam_row)
        elif self.direct_beam_list:
            # Default to first direct beam if last selection is out of range
            self.set_active_data_from_direct_beam_list(0)

    def clear_reduction_lists(self):
        """Resets to one empty reduction list."""
        self.active_reduction_list_index = 1
        self.peak_reduction_lists = {self.active_reduction_list_index: []}
