# local imports
# 3rd-party imports
import pytest

import quicknxs.interfaces.data_handling.data_manipulation as dm
from quicknxs.interfaces.configuration import Configuration
from quicknxs.interfaces.data_handling.instrument import CrossSectionError, Instrument
from quicknxs.interfaces.data_manager import DataManager


@pytest.fixture()
def setup_method():
    Instrument.USE_SLOW_FLIPPER_LOG = True
    yield
    Instrument.USE_SLOW_FLIPPER_LOG = False


class TestDataManagerTest(object):
    """Test DataManager class."""

    @pytest.mark.datarepo
    def test_manager(self, data_server, setup_method):
        manager = DataManager(data_server.directory)
        manager.load(data_server.path_to("REF_M_29160"), Configuration())

        assert manager.current_file == data_server.path_to("REF_M_29160")

        manager.add_active_to_reduction()
        assert manager.find_data_in_reduction_list(manager._nexus_data) == 0
        assert manager.find_data_in_direct_beam_list(manager._nexus_data) is None

        q_range = manager._nexus_data.get_q_range()
        assert q_range[0:2] == pytest.approx([0.034, 0.068], abs=0.05)

        assert manager.add_active_to_direct_beam_list() == 1
        # Now it's in the list, so remove should work
        assert manager.remove_active_from_direct_beam_list() == 0

        manager.set_active_data_from_reduction_list(0)
        manager.set_active_data_from_direct_beam_list(0)
        manager.calculate_reflectivity()
        manager.calculate_reflectivity(specular=False)
        manager.strip_overlap()

        dm.generate_script(manager.reduction_list, manager.reduction_states[0])
        dm.stitch_reflectivity(manager.reduction_list, q_cutoff=0.033)
        dm.merge_reflectivity(manager.reduction_list, manager.reduction_states[0])
        dm.get_scaled_workspaces(manager.reduction_list, manager.reduction_states[0])
        dm.stitch_reflectivity(manager.reduction_list, q_cutoff=0.033)

    @pytest.mark.skip(reason="WIP")
    def test_add_ordermanager(self, data_server):
        # load up files for testing
        manager = DataManager(data_server.directory)
        try:
            file_paths = data_server.get_file_paths("39743")
            if len(file_paths) < 1:
                raise IOError("Files missing.")
            file_paths.append(data_server.get_file_paths("39744")[0])
            file_paths.append(data_server.get_file_paths("39745")[0])
            config = Configuration()
            for file_path in file_paths:
                manager.load(file_path, config)
                manager.add_active_to_reduction()
        except IOError:
            pytest.skip("Cannot find required datafiles, probably not being run on the cluster.")

        assert len(manager.reduction_list) == 3

        for i in range(len(manager.reduction_list) - 1):
            ws = manager.reduction_list[i].get_reflectivity_workspace_group()[0]
            theta = ws.getRun().getProperty("two_theta").value

            _ws = manager.reduction_list[i + 1].get_reflectivity_workspace_group()[0]
            _theta = _ws.getRun().getProperty("two_theta").value
            assert theta <= _theta

    def test_load_reduced(self, data_server):
        manager = DataManager(data_server.directory)
        manager.load_data_from_reduced_file(data_server.path_to("REF_M_29160_Specular_++.dat"))

    def test_clear_cached_unused_data(self, data_server):
        """Test helper function clear_cached_unused_data."""
        manager = DataManager(data_server.directory)
        manager.load(data_server.path_to("REF_M_42112"), Configuration())
        manager.add_active_to_reduction()
        manager.load(data_server.path_to("REF_M_42113"), Configuration())
        manager.add_active_to_reduction()
        manager.load(data_server.path_to("REF_M_42099"), Configuration())
        manager.add_active_to_direct_beam_list()
        assert manager.get_cachesize() == 3
        # Load files without adding them to reduction or normalization
        manager.load(data_server.path_to("REF_M_42100"), Configuration())
        manager.load(data_server.path_to("REF_M_42116"), Configuration())
        assert manager.get_cachesize() == 5
        # Delete unused files from cache
        manager.clear_cached_unused_data()
        assert manager.get_cachesize() == 3

    @pytest.mark.datarepo
    def test_add_additional_reduction_list(self, data_server):
        manager = DataManager(data_server.directory)
        manager.load(data_server.path_to("REF_M_40782"), Configuration())
        manager.add_active_to_reduction()
        manager.load(data_server.path_to("REF_M_40785"), Configuration())
        manager.add_active_to_reduction()

        assert len(manager.peak_reduction_lists) == 1
        assert len(manager.peak_reduction_lists[1]) == 2
        assert manager.active_reduction_list_index == 1

        manager.add_additional_reduction_list(2)

        assert len(manager.peak_reduction_lists) == 2
        assert len(manager.peak_reduction_lists[1]) == 2
        assert len(manager.peak_reduction_lists[2]) == 2
        assert manager.active_reduction_list_index == 1

        manager.remove_additional_reduction_list(2)

        assert len(manager.peak_reduction_lists) == 1
        assert len(manager.peak_reduction_lists[1]) == 2
        assert manager.active_reduction_list_index == 1

    @pytest.mark.datarepo
    def test_reduce_spec(self, mocker, data_manager_with_data_factory):
        """Test function reduce_spec."""
        manager = data_manager_with_data_factory()
        spy_calc_refl_run1 = mocker.spy(manager.reduction_list[0], "calculate_reflectivity")
        spy_calc_refl_run2 = mocker.spy(manager.reduction_list[1], "calculate_reflectivity")

        manager.reduce_spec()
        # assert that the reflectivity was recalculated for the two reflected runs
        assert spy_calc_refl_run1.call_count == 1
        assert spy_calc_refl_run2.call_count == 1

        manager.reduce_spec(direct_beam="42099")
        # assert that the reflectivity was recalculated for only one run, which matches the direct beam
        assert spy_calc_refl_run1.call_count == 2
        assert spy_calc_refl_run2.call_count == 1

    @pytest.mark.datarepo
    def test_add_active_to_reduction_no_duplicates(self, data_server, setup_method):
        """Test that add_active_to_reduction prevents duplicate entries."""
        manager = DataManager(data_server.directory)

        # Add run once
        manager.load(data_server.path_to("REF_M_42112"), Configuration())
        assert manager.add_active_to_reduction()
        assert len(manager.reduction_list) == 1

        # Try to add the same run again - should return False
        assert not manager.add_active_to_reduction()
        assert len(manager.reduction_list) == 1

    @pytest.mark.datarepo
    def test_copy_nexus_data_prevents_duplicates(self, data_server, setup_method):
        """Test that copy_nexus_data_to_reduction prevents duplicate run numbers."""
        manager = DataManager(data_server.directory)

        # Setup main reduction list
        manager.load(data_server.path_to("REF_M_42112"), Configuration())
        manager.add_active_to_reduction(peak_index=1)

        # Create second reduction list
        manager.peak_reduction_lists[2] = []

        # Copy run to second list
        nexus_data = manager.reduction_list[0]
        assert manager.copy_nexus_data_to_reduction(nexus_data, peak_index=2)
        assert len(manager.peak_reduction_lists[2]) == 1

        # Try to copy same run again - should return False
        assert not manager.copy_nexus_data_to_reduction(nexus_data, peak_index=2)
        assert len(manager.peak_reduction_lists[2]) == 1

    ########################
    ### Q ordering tests ###
    ########################

    @pytest.mark.datarepo
    def test_q_ordering_add_active_to_reduction(self, data_server, setup_method):
        """Test that runs are inserted in ascending Q order when added to reduction list.

        Load runs with different Q ranges in non-sequential order
        REF_M_42112: Q ~ 0.008-0.02 (lowest Q)
        REF_M_42113: Q ~ 0.02-0.05 (highest Q)
        REF_M_40782: Q ~ 0.01-0.03 (middle Q)
        """
        manager = DataManager(data_server.directory)

        # Add highest Q run first
        manager.load(data_server.path_to("REF_M_42113"), Configuration())
        assert manager.add_active_to_reduction()
        assert len(manager.reduction_list) == 1
        assert manager.reduction_list[0].number == "42113"

        # Add lowest Q run - should be inserted at the beginning
        manager.load(data_server.path_to("REF_M_42112"), Configuration())
        assert manager.add_active_to_reduction()
        assert len(manager.reduction_list) == 2
        assert manager.reduction_list[0].number == "42112"
        assert manager.reduction_list[1].number == "42113"

        # Add middle Q run - should be inserted in the middle
        manager.load(data_server.path_to("REF_M_40782"), Configuration())
        assert manager.add_active_to_reduction()
        assert len(manager.reduction_list) == 3
        assert manager.reduction_list[0].number == "42112"
        assert manager.reduction_list[1].number == "40782"
        assert manager.reduction_list[2].number == "42113"

        # Verify Q values are in ascending order
        for i in range(len(manager.reduction_list) - 1):
            q_min_current, _ = manager.reduction_list[i].get_q_range()
            q_min_next, _ = manager.reduction_list[i + 1].get_q_range()
            assert q_min_current <= q_min_next, (
                f"Q ordering violated: run {manager.reduction_list[i].number} "
                f"(Q={q_min_current}) should be <= run {manager.reduction_list[i + 1].number} (Q={q_min_next})"
            )

    @pytest.mark.datarepo
    def test_q_ordering_copy_nexus_data_to_reduction(self, data_server, setup_method):
        """Test that copy_nexus_data_to_reduction maintains Q ordering."""
        manager = DataManager(data_server.directory)

        # Setup main reduction list (tab 1)
        manager.load(data_server.path_to("REF_M_42113"), Configuration())
        manager.add_active_to_reduction(peak_index=1)
        manager.load(data_server.path_to("REF_M_42112"), Configuration())
        manager.add_active_to_reduction(peak_index=1)

        # Create a second reduction list (tab 2)
        manager.peak_reduction_lists[2] = []

        # Copy runs to tab 2 in different order
        nexus_data_high_q = manager.reduction_list[1]  # 42113 (high Q)
        nexus_data_low_q = manager.reduction_list[0]  # 42112 (low Q)

        # Add high Q run first
        assert manager.copy_nexus_data_to_reduction(nexus_data_high_q, peak_index=2)
        assert len(manager.peak_reduction_lists[2]) == 1

        # Add low Q run - should be inserted before high Q
        assert manager.copy_nexus_data_to_reduction(nexus_data_low_q, peak_index=2)
        assert len(manager.peak_reduction_lists[2]) == 2
        assert manager.peak_reduction_lists[2][0].number == "42112"
        assert manager.peak_reduction_lists[2][1].number == "42113"

        # Verify Q values are in ascending order
        for i in range(len(manager.peak_reduction_lists[2]) - 1):
            q_min_current, _ = manager.peak_reduction_lists[2][i].get_q_range()
            q_min_next, _ = manager.peak_reduction_lists[2][i + 1].get_q_range()
            assert q_min_current <= q_min_next

    @pytest.mark.datarepo
    def test_q_ordering_empty_list(self, data_server, setup_method):
        """Test that the first run added to an empty list initializes properly."""
        manager = DataManager(data_server.directory)

        # Add to empty list
        manager.load(data_server.path_to("REF_M_42112"), Configuration())
        assert manager.add_active_to_reduction()
        assert len(manager.reduction_list) == 1
        assert manager.reduction_states is not None
        assert len(manager.reduction_states) > 0

    @pytest.mark.datarepo
    def test_bad_files_list(self, data_server, mocker):
        """Test that files that fail to load are tracked in the bad_files list."""
        manager = DataManager(data_server.directory)

        # Mock loading the file, but use data_server to get the path for the error message
        mock_exception = CrossSectionError(data_server.path_to("REF_M_43670"))
        mocker.patch("quicknxs.interfaces.data_manager.NexusData.load", side_effect=mock_exception)
        with pytest.raises(CrossSectionError):
            manager.load(data_server.path_to("REF_M_43670"), Configuration())
        assert len(manager.bad_files) == 1
        assert "REF_M_43670.nxs.h5" in manager.bad_files

        # Test loading the same bad file again - the bad files list should not grow
        with pytest.raises(CrossSectionError):
            manager.load(data_server.path_to("REF_M_43670"), Configuration())
        assert len(manager.bad_files) == 1
        assert "REF_M_43670.nxs.h5" in manager.bad_files

        # Test loading a different bad file - should be added to the list
        mock_exception = CrossSectionError(data_server.path_to("REF_M_42537"))
        mocker.patch("quicknxs.interfaces.data_manager.NexusData.load", side_effect=mock_exception)
        with pytest.raises(CrossSectionError):
            manager.load(data_server.path_to("REF_M_42537"), Configuration())
        assert len(manager.bad_files) == 2
        assert "REF_M_42537.nxs.h5" in manager.bad_files


if __name__ == "__main__":
    pytest.main([__file__])
