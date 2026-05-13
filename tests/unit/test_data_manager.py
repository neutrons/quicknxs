import pytest

import quicknxs.models.data_manipulation as dm
from quicknxs.enums import AddToDirectBeamResult, AddToReductionResult
from quicknxs.exceptions import CrossSectionError
from quicknxs.models.configuration import Configuration
from quicknxs.models.instrument import Instrument
from quicknxs.presenters.data_presenter import DataPresenter


@pytest.fixture()
def setup_method():
    Instrument.USE_SLOW_FLIPPER_LOG = True
    yield
    Instrument.USE_SLOW_FLIPPER_LOG = False


class TestDataPresenterTest:
    """Test DataPresenter class."""

    @pytest.mark.datarepo
    def test_data_presenter(self, data_server, setup_method):
        data_presenter = DataPresenter(data_server.directory)
        data_presenter.load(data_server.path_to("REF_M_29160"), Configuration())

        assert data_presenter.current_file == data_server.path_to("REF_M_29160")

        data_presenter.add_active_to_reduction()
        assert data_presenter.find_run_number_in_reduction_list(data_presenter._nexus_data) == 0
        assert data_presenter.find_data_in_direct_beam_list(data_presenter._nexus_data) is None

        q_range = data_presenter._nexus_data.get_q_range()
        assert q_range[0:2] == pytest.approx([0.034, 0.068], abs=0.05)

        assert data_presenter.add_active_to_direct_beam_list() == AddToDirectBeamResult.SUCCESS_REFLECTED
        # Now it's in the list, so remove should work
        assert data_presenter.remove_active_from_direct_beam_list() == 0

        data_presenter.set_active_data_from_reduction_list(0)
        data_presenter.set_active_data_from_direct_beam_list(0)
        data_presenter.calculate_reflectivity()
        data_presenter.calculate_reflectivity(specular=False)
        data_presenter.strip_overlap()

        dm.generate_script(data_presenter.reduction_list, data_presenter.reduction_states[0])
        dm.stitch_reflectivity(data_presenter.reduction_list, q_cutoff=0.033)
        dm.merge_reflectivity(data_presenter.reduction_list, data_presenter.reduction_states[0])
        dm.get_scaled_workspaces(data_presenter.reduction_list, data_presenter.reduction_states[0])
        dm.stitch_reflectivity(data_presenter.reduction_list, q_cutoff=0.033)

    @pytest.mark.skip(reason="WIP")
    def test_add_orderdata_presenter(self, data_server):
        # load up files for testing
        data_presenter = DataPresenter(data_server.directory)
        try:
            file_paths = data_server.get_file_paths("39743")
            if len(file_paths) < 1:
                raise OSError("Files missing.")
            file_paths.append(data_server.get_file_paths("39744")[0])
            file_paths.append(data_server.get_file_paths("39745")[0])
            config = Configuration()
            for file_path in file_paths:
                data_presenter.load(file_path, config)
                data_presenter.add_active_to_reduction()
        except OSError:
            pytest.skip("Cannot find required datafiles, probably not being run on the cluster.")

        assert len(data_presenter.reduction_list) == 3

        for i in range(len(data_presenter.reduction_list) - 1):
            ws = data_presenter.reduction_list[i].get_reflectivity_workspace_group()[0]
            theta = ws.getRun().getProperty("two_theta").value

            _ws = data_presenter.reduction_list[i + 1].get_reflectivity_workspace_group()[0]
            _theta = _ws.getRun().getProperty("two_theta").value
            assert theta <= _theta

    def test_load_reduced(self, data_server):
        data_presenter = DataPresenter(data_server.directory)
        data_presenter.load_data_from_reduced_file(data_server.path_to("REF_M_29160_Specular_++.dat"))

    def test_clear_cached_unused_data(self, data_server):
        """Test helper function clear_cached_unused_data."""
        data_presenter = DataPresenter(data_server.directory)
        data_presenter.load(data_server.path_to("REF_M_42112"), Configuration())
        data_presenter.add_active_to_reduction()
        data_presenter.load(data_server.path_to("REF_M_42113"), Configuration())
        data_presenter.add_active_to_reduction()
        data_presenter.load(data_server.path_to("REF_M_42099"), Configuration())
        data_presenter.add_active_to_direct_beam_list()
        assert data_presenter.get_cachesize() == 3
        # Load files without adding them to reduction or normalization
        data_presenter.load(data_server.path_to("REF_M_42100"), Configuration())
        data_presenter.load(data_server.path_to("REF_M_42116"), Configuration())
        assert data_presenter.get_cachesize() == 5
        # Delete unused files from cache
        data_presenter.clear_cached_unused_data()
        assert data_presenter.get_cachesize() == 3

    @pytest.mark.datarepo
    def test_add_additional_reduction_list(self, data_server):
        data_presenter = DataPresenter(data_server.directory)
        data_presenter.load(data_server.path_to("REF_M_40782"), Configuration())
        data_presenter.add_active_to_reduction()
        data_presenter.load(data_server.path_to("REF_M_40785"), Configuration())
        data_presenter.add_active_to_reduction()

        assert len(data_presenter.peak_reduction_lists) == 1
        assert len(data_presenter.peak_reduction_lists[1]) == 2
        assert data_presenter.active_reduction_list_index == 1

        data_presenter.add_additional_reduction_list(2)

        assert len(data_presenter.peak_reduction_lists) == 2
        assert len(data_presenter.peak_reduction_lists[1]) == 2
        assert len(data_presenter.peak_reduction_lists[2]) == 2
        assert data_presenter.active_reduction_list_index == 1

        data_presenter.remove_additional_reduction_list(2)

        assert len(data_presenter.peak_reduction_lists) == 1
        assert len(data_presenter.peak_reduction_lists[1]) == 2
        assert data_presenter.active_reduction_list_index == 1

    @pytest.mark.datarepo
    def test_reduce_spec(self, mocker, data_presenter_with_data_factory):
        """Test function reduce_spec."""
        data_presenter = data_presenter_with_data_factory()
        spy_calc_refl_run1 = mocker.spy(data_presenter.reduction_list[0], "calculate_reflectivity")
        spy_calc_refl_run2 = mocker.spy(data_presenter.reduction_list[1], "calculate_reflectivity")

        data_presenter.reduce_spec()
        # assert that the reflectivity was recalculated for the two reflected runs
        assert spy_calc_refl_run1.call_count == 1
        assert spy_calc_refl_run2.call_count == 1

        data_presenter.reduce_spec(direct_beam="42099")
        # assert that the reflectivity was recalculated for only one run, which matches the direct beam
        assert spy_calc_refl_run1.call_count == 2
        assert spy_calc_refl_run2.call_count == 1

    @pytest.mark.datarepo
    def test_add_active_to_reduction_no_duplicates(self, data_server, setup_method):
        """Test that add_active_to_reduction prevents duplicate entries."""
        data_presenter = DataPresenter(data_server.directory)

        # Add run once
        data_presenter.load(data_server.path_to("REF_M_42112"), Configuration())
        assert data_presenter.add_active_to_reduction() == AddToReductionResult.SUCCESS
        assert len(data_presenter.reduction_list) == 1

        # Try to add the same run again - should return AddToReductionResult.ALREADY_IN_LIST
        assert data_presenter.add_active_to_reduction() == AddToReductionResult.ALREADY_IN_LIST
        assert len(data_presenter.reduction_list) == 1

    @pytest.mark.datarepo
    def test_copy_nexus_data_prevents_duplicates(self, data_server, setup_method):
        """Test that copy_nexus_data_to_reduction prevents duplicate run numbers."""
        data_presenter = DataPresenter(data_server.directory)

        # Setup main reduction list
        data_presenter.load(data_server.path_to("REF_M_42112"), Configuration())
        data_presenter.add_active_to_reduction(peak_index=1)

        # Create second reduction list
        data_presenter.peak_reduction_lists[2] = []

        # Copy run to second list
        nexus_data = data_presenter.reduction_list[0]
        assert data_presenter.copy_nexus_data_to_reduction(nexus_data, peak_index=2)
        assert len(data_presenter.peak_reduction_lists[2]) == 1

        # Try to copy same run again - should return False
        assert not data_presenter.copy_nexus_data_to_reduction(nexus_data, peak_index=2)
        assert len(data_presenter.peak_reduction_lists[2]) == 1

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
        data_presenter = DataPresenter(data_server.directory)

        # Add highest Q run first
        data_presenter.load(data_server.path_to("REF_M_42113"), Configuration())
        assert data_presenter.add_active_to_reduction() == AddToReductionResult.SUCCESS
        assert len(data_presenter.reduction_list) == 1
        assert data_presenter.reduction_list[0].run_number == "42113"

        # Add lowest Q run - should be inserted at the beginning
        data_presenter.load(data_server.path_to("REF_M_42112"), Configuration())
        assert data_presenter.add_active_to_reduction() == AddToReductionResult.SUCCESS
        assert len(data_presenter.reduction_list) == 2
        assert data_presenter.reduction_list[0].run_number == "42112"
        assert data_presenter.reduction_list[1].run_number == "42113"

        # Add middle Q run - should be inserted in the middle
        data_presenter.load(data_server.path_to("REF_M_40782"), Configuration())
        assert data_presenter.add_active_to_reduction() == AddToReductionResult.SUCCESS
        assert len(data_presenter.reduction_list) == 3
        assert data_presenter.reduction_list[0].run_number == "42112"
        assert data_presenter.reduction_list[1].run_number == "40782"
        assert data_presenter.reduction_list[2].run_number == "42113"

        # Verify Q values are in ascending order
        for i in range(len(data_presenter.reduction_list) - 1):
            q_min_current, _ = data_presenter.reduction_list[i].get_q_range()
            q_min_next, _ = data_presenter.reduction_list[i + 1].get_q_range()
            assert q_min_current <= q_min_next, (
                f"Q ordering violated: run {data_presenter.reduction_list[i].run_number} "
                f"(Q={q_min_current}) should be <= run {data_presenter.reduction_list[i + 1].run_number} (Q={q_min_next})"
            )

    @pytest.mark.datarepo
    def test_q_ordering_copy_nexus_data_to_reduction(self, data_server, setup_method):
        """Test that copy_nexus_data_to_reduction maintains Q ordering."""
        data_presenter = DataPresenter(data_server.directory)

        # Setup main reduction list (tab 1)
        data_presenter.load(data_server.path_to("REF_M_42113"), Configuration())
        data_presenter.add_active_to_reduction(peak_index=1)
        data_presenter.load(data_server.path_to("REF_M_42112"), Configuration())
        data_presenter.add_active_to_reduction(peak_index=1)

        # Create a second reduction list (tab 2)
        data_presenter.peak_reduction_lists[2] = []

        # Copy runs to tab 2 in different order
        nexus_data_high_q = data_presenter.reduction_list[1]  # 42113 (high Q)
        nexus_data_low_q = data_presenter.reduction_list[0]  # 42112 (low Q)

        # Add high Q run first
        assert data_presenter.copy_nexus_data_to_reduction(nexus_data_high_q, peak_index=2)
        assert len(data_presenter.peak_reduction_lists[2]) == 1

        # Add low Q run - should be inserted before high Q
        assert data_presenter.copy_nexus_data_to_reduction(nexus_data_low_q, peak_index=2)
        assert len(data_presenter.peak_reduction_lists[2]) == 2
        assert data_presenter.peak_reduction_lists[2][0].run_number == "42112"
        assert data_presenter.peak_reduction_lists[2][1].run_number == "42113"

        # Verify Q values are in ascending order
        for i in range(len(data_presenter.peak_reduction_lists[2]) - 1):
            q_min_current, _ = data_presenter.peak_reduction_lists[2][i].get_q_range()
            q_min_next, _ = data_presenter.peak_reduction_lists[2][i + 1].get_q_range()
            assert q_min_current <= q_min_next

    @pytest.mark.datarepo
    def test_q_ordering_empty_list(self, data_server, setup_method):
        """Test that the first run added to an empty list initializes properly."""
        data_presenter = DataPresenter(data_server.directory)

        # Add to empty list
        data_presenter.load(data_server.path_to("REF_M_42112"), Configuration())
        assert data_presenter.add_active_to_reduction() == AddToReductionResult.SUCCESS
        assert len(data_presenter.reduction_list) == 1
        assert data_presenter.reduction_states is not None
        assert len(data_presenter.reduction_states) > 0

    @pytest.mark.datarepo
    def test_bad_files_list(self, data_server, mocker):
        """Test that files that fail to load are tracked in the bad_files list."""
        data_presenter = DataPresenter(data_server.directory)

        # Mock loading the file, but use data_server to get the path for the error message
        mock_exception = CrossSectionError(data_server.path_to("REF_M_43670"))
        mocker.patch("quicknxs.presenters.data_presenter.NexusData.load", side_effect=mock_exception)
        with pytest.raises(CrossSectionError):
            data_presenter.load(data_server.path_to("REF_M_43670"), Configuration())
        assert len(data_presenter.bad_files) == 1
        assert "REF_M_43670.nxs.h5" in data_presenter.bad_files

        # Test loading the same bad file again - the bad files list should not grow
        with pytest.raises(CrossSectionError):
            data_presenter.load(data_server.path_to("REF_M_43670"), Configuration())
        assert len(data_presenter.bad_files) == 1
        assert "REF_M_43670.nxs.h5" in data_presenter.bad_files

        # Test loading a different bad file - should be added to the list
        mock_exception = CrossSectionError(data_server.path_to("REF_M_42537"))
        mocker.patch("quicknxs.presenters.data_presenter.NexusData.load", side_effect=mock_exception)
        with pytest.raises(CrossSectionError):
            data_presenter.load(data_server.path_to("REF_M_42537"), Configuration())
        assert len(data_presenter.bad_files) == 2
        assert "REF_M_42537.nxs.h5" in data_presenter.bad_files


if __name__ == "__main__":
    pytest.main([__file__])
