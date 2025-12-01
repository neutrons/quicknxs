"""Test that "Match Direct Beam" adds non-direct beam runs to the direct beam list when appropriate."""

# 3rd-party imports
import pytest

# local imports
from quicknxs.interfaces.configuration import Configuration
from quicknxs.interfaces.enums import DirectBeamTableColumn as DBTableCols
from quicknxs.interfaces.enums import ReductionTableColumn as RTCols
from quicknxs.interfaces.main_window import MainWindow


@pytest.mark.datarepo
def test_match_direct_beam_adds_run_to_direct_beam_list(qtbot, data_server):
    """Test Marie's scenario: Match Direct Beam should add the active run to the direct beam list if it's the best match.

    Scenario:
    1. Load 42099 as direct beam (true direct beam)
    2. Load 42112 as data run only (NOT as direct beam)
    3. Click "Match Direct Beam" on 42112
    4. Expected: 42112 should be added to the direct beam list and matched to itself
    """
    window_main = MainWindow()
    qtbot.addWidget(window_main)
    Configuration.setup_default_values()

    # Load 42099 as direct beam
    window_main.file_handler.open_file(data_server.path_to("REF_M_42099"))
    window_main.actionAddDirectBeam.triggered.emit()

    # Verify 42099 is in the direct beam table
    db_table = window_main.ui.directBeamTable
    assert db_table.rowCount() == 1
    assert db_table.item(0, DBTableCols.RUN_NUMBER).text() == "42099"

    # Load 42112 as data run ONLY (not as direct beam)
    window_main.file_handler.open_file(data_server.path_to("REF_M_42112"))
    window_main.actionAddRefl.triggered.emit()

    # Verify 42112 is in the reduction table
    reduction_table = window_main.ui.reductionTable
    assert reduction_table.rowCount() == 1
    assert reduction_table.item(0, RTCols.RUN_NUMBER).text() == "42112"

    # Verify 42112 is NOT yet in the direct beam table
    assert db_table.rowCount() == 1  # Still only 42099

    # Make 42112 active in the data table
    window_main.set_active_reduction_data(True, 0)

    # Click "Match Direct Beam" button
    window_main.match_direct_beam_clicked()

    # Now 42112 should be added to the direct beam list
    assert db_table.rowCount() == 2, "42112 should have been added to the direct beam list"

    # Check that both direct beams are in the table
    db_runs = [db_table.item(i, DBTableCols.RUN_NUMBER).text() for i in range(db_table.rowCount())]
    assert "42099" in db_runs
    assert "42112" in db_runs

    # Verify that 42112 is matched to itself
    db_id = reduction_table.item(0, RTCols.DIRECT_BEAM).text()
    assert db_id == "42112", f"42112 should be matched to itself, but DIRECT_BEAM is {db_id}"


@pytest.mark.datarepo
def test_match_direct_beam_does_not_add_when_better_match_exists(qtbot, data_server):
    """Test that Match Direct Beam doesn't add the active run if a better direct beam already exists.

    Scenario:
    1. Load 42099 as direct beam (true direct beam, matches 42112 well)
    2. Load 42112 as data run only
    3. Click "Match Direct Beam" on 42112
    4. Expected: 42112 should NOT be added to direct beam list, should use 42099
    """
    window_main = MainWindow()
    qtbot.addWidget(window_main)
    Configuration.setup_default_values()

    # Enable automatic matching
    Configuration().match_direct_beam = True

    # Load 42099 as direct beam
    window_main.file_handler.open_file(data_server.path_to("REF_M_42099"))
    window_main.actionAddDirectBeam.triggered.emit()

    db_table = window_main.ui.directBeamTable
    assert db_table.rowCount() == 1

    # Load 42112 as data run
    window_main.file_handler.open_file(data_server.path_to("REF_M_42112"))
    window_main.actionAddRefl.triggered.emit()

    reduction_table = window_main.ui.reductionTable
    assert reduction_table.rowCount() == 1

    # 42112 should already be matched to 42099 automatically
    db_id = reduction_table.item(0, RTCols.DIRECT_BEAM).text()
    assert db_id == "42099", "42112 should be automatically matched to 42099"

    # Direct beam table should still only have 42099
    assert db_table.rowCount() == 1
    assert db_table.item(0, DBTableCols.RUN_NUMBER).text() == "42099"


@pytest.mark.datarepo
def test_match_direct_beam_with_no_direct_beams_adds_active_run(qtbot, data_server):
    """Test that Match Direct Beam adds the active run when there are no direct beams yet.

    Scenario:
    1. Load 42112 as data run only (no direct beams)
    2. Click "Match Direct Beam" on 42112
    3. Expected: 42112 should be added to the direct beam list and matched to itself
    """
    window_main = MainWindow()
    qtbot.addWidget(window_main)
    Configuration.setup_default_values()

    # Load 42112 as data run only
    window_main.file_handler.open_file(data_server.path_to("REF_M_42112"))
    window_main.actionAddRefl.triggered.emit()

    db_table = window_main.ui.directBeamTable
    reduction_table = window_main.ui.reductionTable

    # Verify no direct beams yet
    assert db_table.rowCount() == 0
    assert reduction_table.rowCount() == 1

    # Make 42112 active
    window_main.set_active_reduction_data(True, 0)

    # Click "Match Direct Beam"
    window_main.match_direct_beam_clicked()

    # 42112 should now be in the direct beam list
    assert db_table.rowCount() == 1, "42112 should have been added to the direct beam list"
    assert db_table.item(0, DBTableCols.RUN_NUMBER).text() == "42112"

    # And matched to itself
    db_id = reduction_table.item(0, RTCols.DIRECT_BEAM).text()
    assert db_id == "42112", f"42112 should be matched to itself, but DIRECT_BEAM is {db_id}"
