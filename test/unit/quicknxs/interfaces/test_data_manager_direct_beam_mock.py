"""Unit tests for the ability to add non-direct-beam runs to the direct beam list (using mocks)."""

# standard library imports
from unittest import mock

# 3rd-party imports
import pytest

# local imports
from quicknxs.interfaces.data_handling.data_set import NexusData
from quicknxs.interfaces.data_manager import DataManager


class TestDirectBeamFeatureMocked:
    """Test the feature that allows adding any run as a direct beam using mocks."""

    def test_add_non_direct_beam_run_returns_1(self):
        """Test that adding a non-direct-beam run returns 1."""
        manager = DataManager("/tmp")

        # Create a mock NexusData that is NOT a direct beam
        mock_nexus = mock.Mock(spec=NexusData)
        mock_nexus.is_direct_beam.return_value = False
        mock_nexus.number = "12345"
        manager._nexus_data = mock_nexus

        # Should return 1 (added but not a true direct beam)
        result = manager.add_active_to_direct_beam_list()
        assert result == 1

        # Should be in the direct beam list (as a deepcopy with same run number)
        assert len(manager.direct_beam_list) == 1
        assert manager.direct_beam_list[0].number == mock_nexus.number
        # It should be a different object (deepcopied)
        assert manager.direct_beam_list[0] is not mock_nexus

    def test_add_true_direct_beam_run_returns_2(self):
        """Test that adding a true direct beam run returns 2."""
        manager = DataManager("/tmp")

        # Create a mock NexusData that IS a direct beam
        mock_nexus = mock.Mock(spec=NexusData)
        mock_nexus.is_direct_beam.return_value = True
        mock_nexus.number = "12346"
        manager._nexus_data = mock_nexus

        # Should return 2 (added and is a true direct beam)
        result = manager.add_active_to_direct_beam_list()
        assert result == 2

        # Should be in the direct beam list
        assert len(manager.direct_beam_list) == 1
        assert manager.direct_beam_list[0] == mock_nexus

    def test_add_duplicate_run_returns_0(self):
        """Test that adding the same run twice returns 0."""
        manager = DataManager("/tmp")

        # Create a mock NexusData
        mock_nexus = mock.Mock(spec=NexusData)
        mock_nexus.is_direct_beam.return_value = False
        mock_nexus.number = "12347"
        manager._nexus_data = mock_nexus

        # Add it the first time
        result1 = manager.add_active_to_direct_beam_list()
        assert result1 == 1
        assert len(manager.direct_beam_list) == 1

        # Try to add it again
        result2 = manager.add_active_to_direct_beam_list()
        assert result2 == 0  # Already in list
        assert len(manager.direct_beam_list) == 1  # Still only one entry

    def test_mixed_direct_beam_list(self):
        """Test that direct beam list can contain both true and non-true direct beams."""
        manager = DataManager("/tmp")

        # Add a true direct beam
        mock_true_db = mock.Mock(spec=NexusData)
        mock_true_db.is_direct_beam.return_value = True
        mock_true_db.number = "12348"
        manager._nexus_data = mock_true_db
        result1 = manager.add_active_to_direct_beam_list()
        assert result1 == 2

        # Add a non-direct-beam run
        mock_not_db = mock.Mock(spec=NexusData)
        mock_not_db.is_direct_beam.return_value = False
        mock_not_db.number = "12349"
        manager._nexus_data = mock_not_db
        result2 = manager.add_active_to_direct_beam_list()
        assert result2 == 1

        # Both should be in the list
        assert len(manager.direct_beam_list) == 2
        assert manager.direct_beam_list[0].is_direct_beam() is True
        assert manager.direct_beam_list[1].is_direct_beam() is False

    def test_remove_non_direct_beam_from_list(self):
        """Test that a non-direct-beam run can be removed from the direct beam list."""
        manager = DataManager("/tmp")

        # Add a non-direct-beam run
        mock_nexus = mock.Mock(spec=NexusData)
        mock_nexus.is_direct_beam.return_value = False
        mock_nexus.number = "12350"
        manager._nexus_data = mock_nexus
        manager.add_active_to_direct_beam_list()
        assert len(manager.direct_beam_list) == 1

        # Remove it
        index = manager.remove_active_from_direct_beam_list()
        assert index == 0
        assert len(manager.direct_beam_list) == 0

    def test_backward_compatibility_with_existing_code(self):
        """Test that existing code calling add_active_to_direct_beam_list still works."""
        manager = DataManager("/tmp")

        # Create a mock NexusData
        mock_nexus = mock.Mock(spec=NexusData)
        mock_nexus.is_direct_beam.return_value = True
        mock_nexus.number = "12351"
        manager._nexus_data = mock_nexus

        # Call without checking return value (like existing code does)
        manager.add_active_to_direct_beam_list()

        # Should work fine
        assert len(manager.direct_beam_list) == 1

        # Truthiness check should still work (non-zero is truthy)
        result = manager.add_active_to_direct_beam_list()
        assert result == 0  # Already in list
        # Even 0 can be checked as "if result == 0" in new code


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
