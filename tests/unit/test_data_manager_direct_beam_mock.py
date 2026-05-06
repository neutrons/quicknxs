"""Unit tests for the ability to add non-direct-beam runs to the direct beam list (using mocks)."""

from unittest import mock

import pytest

from quicknxs.enums import AddToDirectBeamResult
from quicknxs.models.data_set import NexusData
from quicknxs.presenters.data_presenter import DataPresenter


class TestDirectBeamFeatureMocked:
    """Test the feature that allows adding any run as a direct beam using mocks."""

    def test_add_non_direct_beam_run(self):
        """Test that adding a non-direct-beam run returns the correct result."""
        data_presenter = DataPresenter("/tmp")

        # Create a mock NexusData that is NOT a direct beam
        mock_nexus = mock.Mock(spec=NexusData)
        mock_nexus.is_direct_beam.return_value = False
        mock_nexus.number = "12345"
        data_presenter._nexus_data = mock_nexus

        # Should return 1 (added but not a true direct beam)
        result = data_presenter.add_active_to_direct_beam_list()
        assert result == AddToDirectBeamResult.SUCCESS_REFLECTED

        # Should be in the direct beam list (as a deepcopy with same run number)
        assert len(data_presenter.direct_beam_list) == 1
        assert data_presenter.direct_beam_list[0].number == mock_nexus.number
        # It should be a different object (deepcopied)
        assert data_presenter.direct_beam_list[0] is not mock_nexus

    def test_add_true_direct_beam_run(self):
        """Test that adding a true direct beam run returns the correct result."""
        data_presenter = DataPresenter("/tmp")

        # Create a mock NexusData that IS a direct beam
        mock_nexus = mock.Mock(spec=NexusData)
        mock_nexus.is_direct_beam.return_value = True
        mock_nexus.number = "12346"
        data_presenter._nexus_data = mock_nexus

        # Should return 2 (added and is a true direct beam)
        result = data_presenter.add_active_to_direct_beam_list()
        assert result == AddToDirectBeamResult.SUCCESS

        # Should be in the direct beam list
        assert len(data_presenter.direct_beam_list) == 1
        assert data_presenter.direct_beam_list[0].number == mock_nexus.number

    def test_add_duplicate_run(self):
        """Test that adding the same run twice returns the correct result."""
        data_presenter = DataPresenter("/tmp")

        # Create a mock NexusData
        mock_nexus = mock.Mock(spec=NexusData)
        mock_nexus.is_direct_beam.return_value = False
        mock_nexus.number = "12347"
        data_presenter._nexus_data = mock_nexus

        # Add it the first time
        result1 = data_presenter.add_active_to_direct_beam_list()
        assert result1 == AddToDirectBeamResult.SUCCESS_REFLECTED
        assert len(data_presenter.direct_beam_list) == 1

        # Try to add it again
        result2 = data_presenter.add_active_to_direct_beam_list()
        assert result2 == AddToDirectBeamResult.ALREADY_IN_LIST
        assert len(data_presenter.direct_beam_list) == 1  # Still only one entry

    def test_mixed_direct_beam_list(self):
        """Test that direct beam list can contain both true and non-true direct beams."""
        data_presenter = DataPresenter("/tmp")

        # Add a true direct beam
        mock_true_db = mock.Mock(spec=NexusData)
        mock_true_db.is_direct_beam.return_value = True
        mock_true_db.number = "12348"
        mock_true_db.file_path = "/tmp/test_12348.nxs"
        data_presenter._nexus_data = mock_true_db
        result1 = data_presenter.add_active_to_direct_beam_list()
        assert result1 == AddToDirectBeamResult.SUCCESS

        # Add a non-direct-beam run
        mock_not_db = mock.Mock(spec=NexusData)
        mock_not_db.is_direct_beam.return_value = False
        mock_not_db.number = "12349"
        mock_not_db.file_path = "/tmp/test_12349.nxs"
        data_presenter._nexus_data = mock_not_db
        result2 = data_presenter.add_active_to_direct_beam_list()
        assert result2 == AddToDirectBeamResult.SUCCESS_REFLECTED

        # Both should be in the list
        assert len(data_presenter.direct_beam_list) == 2
        assert data_presenter.direct_beam_list[0].is_direct_beam() is True
        assert data_presenter.direct_beam_list[1].is_direct_beam() is False

    def test_remove_non_direct_beam_from_list(self):
        """Test that a non-direct-beam run can be removed from the direct beam list."""
        data_presenter = DataPresenter("/tmp")

        # Mock a non-direct-beam run
        mock_nexus = mock.Mock(spec=NexusData)
        mock_nexus.is_direct_beam.return_value = False
        mock_nexus.number = "12351"
        data_presenter._nexus_data = mock_nexus
        data_presenter.add_active_to_direct_beam_list()
        assert len(data_presenter.direct_beam_list) == 1

        # Remove it
        index = data_presenter.remove_active_from_direct_beam_list()
        assert index == 0
        assert len(data_presenter.direct_beam_list) == 0

    def test_backward_compatibility_with_existing_code(self):
        """Test that existing code calling add_active_to_direct_beam_list still works."""
        data_presenter = DataPresenter("/tmp")

        # Create a mock NexusData
        mock_nexus = mock.Mock(spec=NexusData)
        mock_nexus.is_direct_beam.return_value = True
        mock_nexus.number = "12351"
        data_presenter._nexus_data = mock_nexus

        # Call without checking return value (like existing code does)
        data_presenter.add_active_to_direct_beam_list()

        # Should work fine
        assert len(data_presenter.direct_beam_list) == 1

        result = data_presenter.add_active_to_direct_beam_list()
        assert result == AddToDirectBeamResult.ALREADY_IN_LIST

    def test_update_active_direct_beam_switches_to_direct_beam_copy(self):
        """Switching to the direct beam tab should swap in the direct beam copy of a shared run."""
        data_presenter = DataPresenter("/tmp")

        reflected_copy = mock.Mock(spec=NexusData)
        reflected_copy.number = "12352"

        direct_beam_copy = mock.Mock(spec=NexusData)
        direct_beam_copy.number = "12352"

        data_presenter._nexus_data = reflected_copy
        data_presenter.direct_beam_list = [direct_beam_copy]
        data_presenter.set_active_cross_section = mock.Mock(return_value=True)

        data_presenter.update_active_direct_beam()

        assert data_presenter._nexus_data is direct_beam_copy
        assert data_presenter.last_selected_direct_beam_row == 0
        data_presenter.set_active_cross_section.assert_called_once_with(0)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
