# local imports
from reflectivity_ui.interfaces.data_manager import DataManager
from reflectivity_ui.interfaces.configuration import Configuration
import reflectivity_ui.interfaces.data_handling.data_manipulation as dm
from reflectivity_ui.interfaces.data_handling.instrument import Instrument

# 3rd-party imports
import pytest


@pytest.fixture()
def setup_method():
    Instrument.USE_SLOW_FLIPPER_LOG = True
    yield
    Instrument.USE_SLOW_FLIPPER_LOG = False


class TestDataManagerTest(object):
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
        assert manager.add_active_to_normalization()
        assert manager.remove_active_from_normalization() == 0

        manager.set_active_data_from_reduction_list(0)
        manager.set_active_data_from_direct_beam_list(0)
        manager.calculate_reflectivity()
        manager.calculate_reflectivity(specular=False)
        manager.strip_overlap()

        dm.generate_script(manager.reduction_list, manager.reduction_states[0])
        dm.stitch_reflectivity(manager.reduction_list)
        dm.merge_reflectivity(manager.reduction_list, manager.reduction_states[0])
        dm.get_scaled_workspaces(manager.reduction_list, manager.reduction_states[0])
        dm.stitch_reflectivity(manager.reduction_list)

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
        """Test helper function clear_cached_unused_data"""
        manager = DataManager(data_server.directory)
        manager.load(data_server.path_to("REF_M_42112"), Configuration())
        manager.add_active_to_reduction()
        manager.load(data_server.path_to("REF_M_42113"), Configuration())
        manager.add_active_to_reduction()
        manager.load(data_server.path_to("REF_M_42099"), Configuration())
        manager.add_active_to_normalization()
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


if __name__ == "__main__":
    pytest.main([__file__])
