# pylint: disable=bare-except
"""Data manager. Holds information about the current data location and manages the data cache."""

import copy
import glob
import logging
import os
import sys
import time
from typing import Callable, Dict, List, Optional, Union

import numpy as np

from quicknxs.interfaces.configuration import Configuration
from quicknxs.interfaces.data_handling import data_manipulation, gisans, quicknxs_io
from quicknxs.interfaces.data_handling.data_set import CrossSectionData, NexusData
from quicknxs.interfaces.data_handling.filepath import FilePath, RunNumbers
from quicknxs.interfaces.event_handlers.progress_reporter import ProgressReporter


class DataManager(object):
    """Holds information about the current data location and manages the data cache.

    Attributes
    ----------
    current_directory
        Current directory
    current_file_name
        Current file name, used for file list table to set the current item
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
        self.current_file_name: Optional[str] = None
        self._nexus_data: Optional[NexusData] = None

        self.active_cross_section: Optional[CrossSectionData] = None
        self.active_reduction_list_index: int = 1

        # Main data structure holding the reduction list for each ROI/peak
        #    key: reduction list index, corresponds to the reduction table tab in the UI
        #    value: list of NexusData
        self.peak_reduction_lists: Dict[int, List[NexusData]] = {self.active_reduction_list_index: []}

        self.direct_beam_list: List[NexusData] = []

        # List of cross-sections common to all reduced data sets
        self.reduction_states: List[str] = []

        self.final_merged_reflectivity = {}

        self._cache: List[NexusData] = list()
        self.cached_offspec: Optional[dict] = None
        self.cached_gisans: Optional[dict] = None

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
            return (self.find_data_in_reduction_list(f) is not None) or (
                self.find_data_in_direct_beam_list(f) is not None
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

    def set_active_data_from_direct_beam_list(self, index: int):
        """Set a data set in the direct beam list as the active data set according to its index.

        Args:
            index : index in the direct beam list
        """
        if index < len(self.direct_beam_list):
            self._nexus_data = self.direct_beam_list[index]
            self.set_active_cross_section(0)

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

    def is_nexus_data_compatible(self, nexus_data: NexusData, reduction_list: List[NexusData]) -> bool:
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

    def find_run_number_in_reduction_list(self, run_number: int, reduction_list: list[NexusData]):
        """Look for the given run number in the reduction list.

        Returns
        -------
        int | None
            The index in the reduction list or None
        """
        for i, nexus_data in enumerate(reduction_list):
            if nexus_data.number == run_number:
                return i
        return None

    def find_data_in_reduction_list(self, nexus_data):
        """Look for the given data in the reduction list.

        Returns
        -------
        int | None:
            The index within the reduction list, or none.
        """
        for i in range(len(self.reduction_list)):
            if nexus_data == self.reduction_list[i]:
                return i
        return None

    def find_data_in_direct_beam_list(self, nexus_data: NexusData) -> Optional[int]:
        """Look for the given data in the direct beam list.

        Returns
        -------
        int | None:
            The index within the direct beam list, or none.
        """
        for i in range(len(self.direct_beam_list)):
            if nexus_data == self.direct_beam_list[i]:
                return i
        return None

    def find_active_data_id(self) -> Optional[int]:
        """Look for the active data in the reduction list.

        Returns
        -------
        int | None:
            The index within the reduction list or none.
        """
        return self.find_data_in_reduction_list(self._nexus_data)

    def find_active_direct_beam_id(self) -> Optional[int]:
        """Look for the active data in the direct beam list.

        Returns
        -------
        int | None:
            The index within the direct beam list or none.
        """
        return self.find_data_in_direct_beam_list(self._nexus_data)

    def add_active_to_reduction(self, peak_index=MAIN_REDUCTION_LIST_INDEX) -> bool:
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
        bool
            True if the active data set was added to the reduction list, False if it was not added
        """
        reduct_list = self.peak_reduction_lists[peak_index]

        if self._nexus_data not in reduct_list:
            if self.is_nexus_data_compatible(self._nexus_data, reduct_list):
                if len(reduct_list) == 0:
                    self.reduction_states = list(self.data_sets.keys())
                is_inserted = False
                q_min, _ = self._nexus_data.get_q_range()
                if q_min is None:
                    logging.error("Could not get q range information")
                    return False
                for i in range(len(reduct_list)):
                    _q_min, _ = reduct_list[i].get_q_range()
                    if q_min <= _q_min:
                        reduct_list.insert(i, self._nexus_data)
                        is_inserted = True
                        break
                if not is_inserted:
                    reduct_list.append(self._nexus_data)
                return True
            else:
                logging.error("The data you are trying to add has different cross-sections")
        return False

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
        if any(run_data.number == nexus_data_to_copy.number for run_data in reduction_list):
            return False

        nexus_data = copy.deepcopy(nexus_data_to_copy)
        if self.is_nexus_data_compatible(nexus_data, reduction_list):
            is_inserted = False
            q_min, _ = nexus_data.get_q_range()
            for i in range(len(reduction_list)):
                _q_min, _ = reduction_list[i].get_q_range()
                if q_min <= _q_min:
                    reduction_list.insert(i, nexus_data)
                    is_inserted = True
                    break
            if not is_inserted:
                reduction_list.append(nexus_data)
            return True
        else:
            logging.error("The data you are trying to add has different cross-sections")
        return False

    def add_active_to_direct_beam_list(self):
        """Add active data set to the direct beam list."""
        if self._nexus_data not in self.direct_beam_list and self._nexus_data.is_direct_beam():
            self.direct_beam_list.append(self._nexus_data)
            return True
        return False

    def remove_active_from_direct_beam_list(self):
        """Remove the active data set from the direct beam list."""
        for i in range(len(self.direct_beam_list)):
            if self.direct_beam_list[i] == self._nexus_data:
                self.direct_beam_list.pop(i)
                return i
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
        progress: Optional[Callable] = None,
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
        # 3. Update attributes _nexus_data, current_directory, and current_file_name
        # 4. If we're overwriting cached data that was allocated in the reduction_list and direct_beam_list,
        #    then assign the new data to the proper indexes in lists reduction_list and direct_beam_list
        # 5. Compute reflectivity if data is loaded from file

        nexus_data = None  # type: Optional[NexusData]
        is_from_cache = False  # if True, the file has been loaded before
        reduction_list_id = None
        direct_beam_list_id = None
        file_path = FilePath(file_path, sort=True).path  # force sorting by increasing run number

        if progress is not None:
            progress(10, "Loading data...")

        # Check whether the file has already been loaded (in cache)
        for i in range(len(self._cache)):
            if self._cache[i].file_path == file_path:
                if force:
                    # Check whether the data is in the reduction list before removing it
                    reduction_list_id = self.find_data_in_reduction_list(self._cache[i])
                    direct_beam_list_id = self.find_data_in_direct_beam_list(self._cache[i])
                    self._cache.pop(i)
                else:
                    nexus_data = self._cache[i]
                    is_from_cache = True
                break

        # If we don't have the data, load it
        if nexus_data is None:
            nexus_data = NexusData(file_path, configuration)
            sub_task = progress.create_sub_task(max_value=70) if progress else None
            nexus_data.load(progress=sub_task, update_parameters=update_parameters)

        if progress is not None:
            progress(80, "Calculating...")

        if nexus_data is not None:
            self._nexus_data = nexus_data
            # Example: '/SNS/REF_M/IPTS-25531/nexus/REF_M_38198.nxs.h5+/SNS/REF_M/IPTS-25531/nexus/REF_M_38199.nxs.h5'
            # will be split into directory='/SNS/REF_M/IPTS-25531/nexus' and
            # file_name='REF_M_38198.nxs.h5+REF_M_38199.nxs.h5'
            directory, file_name = FilePath(file_path).split()
            self.current_directory = directory
            self.current_file_name = file_name
            self.set_active_cross_section(0)

            # If we didn't get this data set from our cache, add it and compute its reflectivity.
            if not is_from_cache:
                # Find suitable direct beam
                if configuration.match_direct_beam:
                    self.find_best_direct_beam()

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

    def update_configuration(self, configuration, active_only: bool = False, nexus_data: Optional[NexusData] = None):
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

    def _find_direct_beam(self, nexus_data: Union[NexusData, CrossSectionData]) -> Optional[CrossSectionData]:
        """Attempt to find a direct beam data set for a given reflectivity data set.

        Returns
        -------
        CrossSectionData or None:
            The direct beam data set if found, otherwise None.
        """
        direct_beam = None
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

        if data_xs.configuration is not None and data_xs.configuration.direct_beam is not None:
            for item in self.direct_beam_list:
                # convert _run_number to int if it can be
                try:
                    _run_number = int(data_xs.configuration.direct_beam)
                except (ValueError, TypeError):
                    _run_number = data_xs.configuration.direct_beam
                # convert item.number to int if it can be
                try:
                    item_number = int(item.number)
                except (ValueError, TypeError):
                    item_number = item.number
                if item_number == _run_number:
                    keys = list(item.cross_sections.keys())
                    if len(keys) >= 1:
                        if len(keys) > 1:
                            logging.error("More than one cross-section for the direct beam, using the first one")
                        direct_beam = item.cross_sections[keys[0]]
            if direct_beam is None:
                logging.error("The specified direct beam is not available: skipping")

        return direct_beam

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
            except:
                logging.error("Could not compute GISANS for %s\n  %s", nexus_data.number, sys.exc_info()[1])
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
        logging.info("Calculate GISANS: %s %s sec", nexus_data.number, (time.time() - t_0))
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

    def reduce_spec(self):
        """Calculate reflectivity for all runs in all reduction lists."""
        for reduct_list in self.peak_reduction_lists.values():
            for nexus_data in reduct_list:
                try:
                    self.calculate_reflectivity(nexus_data=nexus_data)
                except:
                    logging.error("Could not compute reflectivity for %s\n  %s", nexus_data.number, sys.exc_info()[1])

    def reduce_offspec(self, progress=None):
        """Calculate off-specular reflectivity for all datasets in all reduction list.

        Since the specular reflectivity is prominently displayed, it is updated as
        soon as parameters change. This is not the case for the off-specular, which is
        computed on-demand.
        """
        for nexus_data in self.reduction_list:
            try:
                self.calculate_reflectivity(nexus_data=nexus_data, specular=False)
            except:
                logging.error("Could not compute reflectivity for %s\n  %s", nexus_data.number, sys.exc_info()[1])

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

    # TODO 67 FInd out whether it can work with merged data
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
        # TODO 65+ Can it work with merged data?
        # Select the first run number if the active cross section is derived from more than one run
        active_cross_section_number = RunNumbers(self.active_cross_section.number).numbers[0]
        closest = None
        for item in self.direct_beam_list:
            item_number = int(item.number)
            xs_keys = list(item.cross_sections.keys())
            if len(xs_keys) > 0:
                xs = item.cross_sections[list(item.cross_sections.keys())[0]]
                if self.active_cross_section.configuration.instrument.direct_beam_match(self.active_cross_section, xs):
                    if closest is None:
                        closest = item_number
                    elif abs(item_number - active_cross_section_number) < abs(closest - active_cross_section_number):
                        closest = item_number

        if closest is None:
            # If we didn't find a direct beam, try with just the wavelength
            for item in self.direct_beam_list:
                item_number = int(item.number)
                xs_keys = list(item.cross_sections.keys())
                if len(xs_keys) > 0:
                    xs = item.cross_sections[list(item.cross_sections.keys())[0]]
                    if self.active_cross_section.configuration.instrument.direct_beam_match(
                        self.active_cross_section, xs, skip_slits=True
                    ):
                        if closest is None:
                            closest = item_number
                        elif abs(item_number - active_cross_section_number) < abs(
                            closest - active_cross_section_number
                        ):
                            closest = item_number
        if closest is not None:
            # return self._nexus_data.set_parameter("normalization", closest)
            return self._nexus_data.set_parameter("direct_beam", closest)
        return False

    def get_trim_values(self) -> Optional[List[int]]:
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
        poly_degree: Optional[int] = None,
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
        data_manipulation.smart_stitch_reflectivity(
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
        self, file_path: str, configuration: Optional[Configuration] = None, progress: ProgressReporter = None
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
            progress.set_value(1, message="Loaded %s" % os.path.basename(file_path), out_of=n_total)
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
        db_files: List[tuple],
        data_files: List[tuple],
        additional_peaks: Optional[list] = None,
        configuration: Optional[Configuration] = None,
        progress: Optional[ProgressReporter] = None,
        force: bool = False,
        t_0: Optional[float] = None,
    ):
        """Load direct beam and data files and add them to the direct beam list and reduction list, respectively.

        Parameters
        ----------
        db_files: list
            List of (run_number, run_file, conf) for direct beam files
        data_files: list
            List of (run_number, run_file, conf) for data files
        additional_peaks: list | None
            List of (peak_index, run_number, run_file, conf) for data files for additional peaks
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
        for r_id, run_file, conf in db_files:
            t_i = time.time()
            if os.path.isfile(run_file):
                is_from_cache = self.load(run_file, conf, force=force, update_parameters=False)
                if is_from_cache:
                    configuration.direct_beam = None
                    self._nexus_data.update_configuration(conf)
                self.add_active_to_direct_beam_list()
                logging.info("%s loaded: %s sec [%s]", r_id, time.time() - t_i, time.time() - t_0)
                if progress:
                    progress.set_value(n_loaded, message="%s loaded" % os.path.basename(run_file), out_of=n_total)
            else:
                logging.error("File does not exist: %s", run_file)
                if progress:
                    progress.set_value(n_loaded, message="ERROR: %s does not exist" % run_file, out_of=n_total)
            n_loaded += 1
        for r_id, run_file, conf in data_files:
            t_i = time.time()
            do_files_exist = []
            for name in run_file.split("+"):
                do_files_exist.append((os.path.isfile(name)))

            if all(do_files_exist):
                is_from_cache = self.load(run_file, conf, force=force, update_parameters=False)
                if is_from_cache:
                    configuration.direct_beam = None
                    self._nexus_data.update_configuration(conf)
                    self.calculate_reflectivity()
                if self.add_active_to_reduction():
                    logging.info("%s loaded: %s sec [%s]", r_id, time.time() - t_i, time.time() - t_0)
                else:
                    logging.error("Could not load %s", r_id)
                if progress:
                    progress.set_value(n_loaded, message="%s loaded" % os.path.basename(run_file), out_of=n_total)
            else:
                logging.error("File does not exist: %s", run_file)
                if progress:
                    progress.set_value(n_loaded, message="ERROR: %s does not exist" % run_file, out_of=n_total)
            n_loaded += 1
        if progress:
            progress.set_value(n_total, message="Done", out_of=n_total)

        # Initialize any additional peak reduction lists by copying the data from the main reduction list
        if additional_peaks:
            for peak_index, r_id, run_file, conf in additional_peaks:
                if peak_index not in self.peak_reduction_lists:
                    self.peak_reduction_lists[peak_index] = []
                self.set_active_reduction_list_index(peak_index)
                # find run in main reduction list and make a copy TODO: what if it is missing?
                run_index = [i for i, data in enumerate(self.main_reduction_list) if data.number == str(r_id)][0]
                self._nexus_data = copy.deepcopy(self.main_reduction_list[run_index])
                configuration.direct_beam = None
                self.update_configuration(conf)
                self.calculate_reflectivity()
                self.add_active_to_reduction(peak_index)

    @property
    def current_event_files(self) -> List[str]:
        """Sorted list of event files in the current directory.

        Return only file names with pattern '*event.nxs' or '*.nxs.h5'
        """
        event_file_list = glob.glob(os.path.join(self.current_directory, "*event.nxs"))
        h5_file_list = glob.glob(os.path.join(self.current_directory, "*.nxs.h5"))
        event_file_list.extend(h5_file_list)
        return sorted([os.path.basename(name) for name in event_file_list])

    def reload_files(self, configuration: Optional[Configuration] = None, progress=None):
        """Force reload of files in the reduction lists and direct beam list."""

        def _get_nexus_conf(nexus_data: NexusData) -> Configuration:
            """Returns the configuration for the main cross-section of the run."""
            return nexus_data.cross_sections[nexus_data.main_cross_section].configuration

        # Get files to reload
        db_files = [(nexus.number, nexus.file_path, _get_nexus_conf(nexus)) for nexus in self.direct_beam_list]
        data_files = []
        additional_peaks = []
        for ipeak, reduction_list in self.peak_reduction_lists.items():
            if ipeak == self.MAIN_REDUCTION_LIST_INDEX:
                data_files = [(nexus.number, nexus.file_path, _get_nexus_conf(nexus)) for nexus in reduction_list]
            else:
                additional_peaks = [
                    (ipeak, nexus.number, nexus.file_path, _get_nexus_conf(nexus)) for nexus in reduction_list
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
        active_data_idx = self.find_active_data_id()
        self.set_active_reduction_list_index(tab_index)
        # keep same selected run if available in the other reduction table
        if active_data_idx and active_data_idx < len(self.reduction_list):
            self.set_active_data_from_reduction_list(active_data_idx)
        else:
            self.set_active_data_from_reduction_list(0)

    def clear_reduction_lists(self):
        """Resets to one empty reduction list."""
        self.active_reduction_list_index = 1
        self.peak_reduction_lists = {self.active_reduction_list_index: []}
