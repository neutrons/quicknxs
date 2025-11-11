"""Unit tests for the ability to add non-direct-beam runs to the direct beam list."""

# local imports
# 3rd-party imports
import pytest

from quicknxs.interfaces.configuration import Configuration
from quicknxs.interfaces.data_handling.instrument import Instrument
from quicknxs.interfaces.data_manager import DataManager


@pytest.fixture()
def setup_method():
    Instrument.USE_SLOW_FLIPPER_LOG = True
    yield
    Instrument.USE_SLOW_FLIPPER_LOG = False


class TestDirectBeamFeature:
    """Test the feature that allows adding any run as a direct beam."""

    @pytest.mark.datarepo
    def test_add_non_direct_beam_run(self, data_server, setup_method):
        """Test that a non-direct-beam run can be added to the direct beam list."""
        manager = DataManager(data_server.directory)

        # Load a scattering run (not a direct beam)
        manager.load(data_server.path_to("REF_M_29160"), Configuration())

        # Verify it's not a direct beam
        assert manager._nexus_data.is_direct_beam() is False

        # Should be able to add it to the direct beam list now
        # Return value: 1 = added but not a true direct beam
        result = manager.add_active_to_direct_beam_list()
        assert result == 1

        # Verify it's in the direct beam list
        assert len(manager.direct_beam_list) == 1
        assert manager.direct_beam_list[0] == manager._nexus_data

    @pytest.mark.datarepo
    def test_add_true_direct_beam_run(self, data_server, setup_method):
        """Test that a true direct beam run still works as before."""
        manager = DataManager(data_server.directory)

        # Load a true direct beam run (REF_M_42099 is a direct beam)
        manager.load(data_server.path_to("REF_M_42099"), Configuration())

        # Verify it IS a direct beam
        assert manager._nexus_data.is_direct_beam() is True

        # Should be able to add it to the direct beam list
        # Return value: 2 = added and is a true direct beam
        result = manager.add_active_to_direct_beam_list()
        assert result == 2

        # Verify it's in the direct beam list
        assert len(manager.direct_beam_list) == 1
        assert manager.direct_beam_list[0] == manager._nexus_data

    @pytest.mark.datarepo
    def test_add_duplicate_run(self, data_server, setup_method):
        """Test that adding the same run twice returns 0."""
        manager = DataManager(data_server.directory)

        # Load and add a run
        manager.load(data_server.path_to("REF_M_29160"), Configuration())
        result1 = manager.add_active_to_direct_beam_list()
        assert result1 == 1  # Added successfully as non-direct-beam

        # Try to add the same run again
        result2 = manager.add_active_to_direct_beam_list()
        assert result2 == 0  # Already in list

        # Verify there's still only one entry
        assert len(manager.direct_beam_list) == 1

    @pytest.mark.datarepo
    def test_non_direct_beam_normalization(self, data_server, setup_method):
        """Test that a non-direct-beam run can be used for normalization."""
        manager = DataManager(data_server.directory)

        # Load a direct beam run and add it to the list (using a scattering run as DB)
        manager.load(data_server.path_to("REF_M_42112"), Configuration())
        manager.add_active_to_direct_beam_list()

        # Load a scattering run and add it to reduction list
        manager.load(data_server.path_to("REF_M_42113"), Configuration())
        manager.add_active_to_reduction()

        # Set the "direct beam" for this run (even though it's not a true DB)
        manager._nexus_data.set_parameter("direct_beam", "42112")

        # Calculate reflectivity - this should work without errors
        try:
            manager.calculate_reflectivity()
            success = True
        except Exception as e:
            success = False
            pytest.fail(f"Reflectivity calculation failed: {e}")

        assert success

    @pytest.mark.datarepo
    def test_mixed_direct_beam_list(self, data_server, setup_method):
        """Test that direct beam list can contain both true and non-true direct beams."""
        manager = DataManager(data_server.directory)

        # Add a true direct beam
        manager.load(data_server.path_to("REF_M_42099"), Configuration())
        result1 = manager.add_active_to_direct_beam_list()
        assert result1 == 2  # True direct beam

        # Add a non-direct-beam run
        manager.load(data_server.path_to("REF_M_42112"), Configuration())
        result2 = manager.add_active_to_direct_beam_list()
        assert result2 == 1  # Non-direct beam

        # Verify both are in the list
        assert len(manager.direct_beam_list) == 2
        assert manager.direct_beam_list[0].is_direct_beam() is True
        assert manager.direct_beam_list[1].is_direct_beam() is False

    @pytest.mark.datarepo
    def test_remove_non_direct_beam_from_list(self, data_server, setup_method):
        """Test that a non-direct-beam run can be removed from the direct beam list."""
        manager = DataManager(data_server.directory)

        # Load and add a non-direct-beam run
        manager.load(data_server.path_to("REF_M_29160"), Configuration())
        manager.add_active_to_direct_beam_list()
        assert len(manager.direct_beam_list) == 1

        # Remove it
        index = manager.remove_active_from_direct_beam_list()
        assert index == 0
        assert len(manager.direct_beam_list) == 0


if __name__ == "__main__":
    pytest.main([__file__])
