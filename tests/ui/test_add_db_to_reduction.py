"""UI tests for adding a direct beam run to the reduction list, using nexus files with intentionally mislabeled PV."""

import pytest
from pytestqt.qtbot import QtBot

from quicknxs.interfaces.configuration import Configuration
from quicknxs.interfaces.enums import ReductionTableColumn
from quicknxs.interfaces.main_window import MainWindow


@pytest.mark.datarepo
def test_add_db_to_reduction(qtbot: QtBot, data_server):
    """Test adding a reflected run that was mislabeled as a direct beam run to the reduction list."""
    # Set up the main window and load the test .nxs file
    main_window = MainWindow()
    qtbot.addWidget(main_window)
    Configuration.setup_default_values()
    # main_window.show()

    # Add the mislabeled direct beam run to the reduction list
    ref_mislabeled_as_db = data_server.path_to("REF_M_1111.nxs.h5")
    main_window.file_handler.open_file(ref_mislabeled_as_db)

    # It should look like a direct beam run in the UI
    assert main_window.data_manager._nexus_data.is_direct_beam()

    # Add to reduction table
    main_window.actionAddRefl.trigger()

    # Check that it was added to reduction table
    table = main_window.ui.reductionTable
    assert table.rowCount() == 1
    assert table.item(0, ReductionTableColumn.RUN_NUMBER).text() == "1111"


@pytest.mark.datarepo
def test_add_mislabeled_db_to_reduction(qtbot: QtBot, data_server):
    """Test adding a direct beam run that was mislabeled as a reflected run to the reduction list."""
    # Set up the main window and load the test .nxs file
    main_window = MainWindow()
    qtbot.addWidget(main_window)
    Configuration.setup_default_values()
    # main_window.show()

    # Add the mislabeled reflected run to the reduction list
    db_mislabeled_as_ref = data_server.path_to("REF_M_0000.nxs.h5")
    main_window.file_handler.open_file(db_mislabeled_as_ref)

    # It should look like a reflected run in the UI
    assert not main_window.data_manager._nexus_data.is_direct_beam()

    # Add to reduction table
    main_window.actionAddRefl.trigger()

    # Check that it was added to reduction table
    table = main_window.ui.reductionTable
    assert table.rowCount() == 1
    assert int(table.item(0, ReductionTableColumn.RUN_NUMBER).text()) == 0
    # Normalize the run number; formatting (e.g., leading zeros) may vary in the UI.
