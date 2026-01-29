from unittest import mock

import pytest

from quicknxs.interfaces.configuration import Configuration
from quicknxs.interfaces.data_handling.instrument import NoCrossSectionsFoundError


@pytest.mark.datarepo
def test_load_data_pre_epics(data_server):
    """Test load data with pre-epics cross-sections."""
    conf = Configuration()
    file_path = data_server.path_to("REF_M_24945_event.nxs")
    ws_list = conf.instrument.load_data(file_path, conf)
    assert len(ws_list) == 1
    for ws in ws_list:
        assert ws.getNumberEvents() == 7880217


@pytest.mark.datarepo
def test_load_data_deadtime(data_server):
    """Test load data with and without dead-time correction."""
    conf = Configuration()
    file_path = data_server.path_to("REF_M_42112")
    corrected_events = [52226.65, 42024.57, 66802.82, 43401.94]

    # load with dead-time correction
    conf.apply_deadtime = True
    ws_list = conf.instrument.load_data(file_path, conf)
    assert len(ws_list) == 4
    for iws, ws in enumerate(ws_list):
        assert "dead_time_applied" in ws.getRun()
        assert ws.extractY().sum() == pytest.approx(corrected_events[iws])

    # load without dead-time correction
    conf.apply_deadtime = False
    ws_list = conf.instrument.load_data(file_path, conf)
    assert len(ws_list) == 4
    for ws in ws_list:
        assert "dead_time_applied" not in ws.getRun()
        assert ws.extractY().sum() == ws.getNumberEvents()


@pytest.mark.datarepo
def test_load_data_nbr_events_min(data_server):
    """Test load data with one cross-section with too few events."""
    conf = Configuration()
    file_path = data_server.path_to("REF_M_40776")

    # load with no cut-off on number of events
    conf.nbr_events_min = 0
    ws_list = conf.instrument.load_data(file_path, conf)
    assert len(ws_list) == 3

    # load with cut-off on number of events
    conf.nbr_events_min = 100
    ws_list = conf.instrument.load_data(file_path, conf)
    assert len(ws_list) == 2

    # test loading with dead-time correction
    conf.nbr_events_min = 100
    conf.apply_deadtime = True
    ws_list = conf.instrument.load_data(file_path, conf)
    assert len(ws_list) == 2


@pytest.mark.datarepo
def test_load_data_insufficient_event_count(data_server):
    """Test load data with too few events"""
    Configuration.setup_default_values()

    conf = Configuration()
    file_path = data_server.path_to("REF_M_43670")

    with pytest.raises(NoCrossSectionsFoundError):
        conf.instrument.load_data(file_path, conf)


@pytest.mark.parametrize(
    "apply_deadtime",
    [
        False,
        True,
    ],
)
@pytest.mark.datarepo
def test_load_unpolarized_data(data_server, apply_deadtime):
    """Test load unpolarized data with Polarizer = 0 and Analyzer = 0."""
    conf = Configuration()
    conf.apply_deadtime = apply_deadtime
    file_path = data_server.path_to("REF_M_41889")
    ws_list = conf.instrument.load_data(file_path, conf)
    assert len(ws_list) == 1
    run = ws_list[0].getRun()
    assert "cross_section_id" in run


@pytest.mark.datarepo
def test_load_data_sum_two_files(data_server):
    """Test loading and summing two files together."""
    conf = Configuration()
    # Use files 42112 and 42113 which are known to work individually
    file_path = data_server.path_to("REF_M_42112") + "+" + data_server.path_to("REF_M_42113")

    ws_list = conf.instrument.load_data(file_path, conf)

    # Should have 4 cross-sections (not 8 - that would indicate concatenation not merging)
    assert len(ws_list) == 4, f"Expected 4 cross-sections, got {len(ws_list)}"

    # Verify run_numbers property exists and is correct
    for ws in ws_list:
        run = ws.getRun()
        assert run.hasProperty("run_numbers"), "run_numbers property not found"
        run_numbers = run.getProperty("run_numbers").value
        assert run_numbers == "42112+42113", f"Expected '42112+42113', got '{run_numbers}'"

    # Load individual files to compare event counts
    conf_single = Configuration()
    ws_list_42112 = conf_single.instrument.load_data(data_server.path_to("REF_M_42112"), conf_single)
    ws_list_42113 = conf_single.instrument.load_data(data_server.path_to("REF_M_42113"), conf_single)

    # Verify events are summed correctly for each cross-section
    for i in range(4):
        expected_events = ws_list_42112[i].getNumberEvents() + ws_list_42113[i].getNumberEvents()
        actual_events = ws_list[i].getNumberEvents()
        assert actual_events == expected_events, (
            f"Cross-section {i}: expected {expected_events} events, got {actual_events}"
        )


@pytest.mark.datarepo
def test_load_data_sum_with_deadtime(data_server):
    """Test summing files with dead-time correction applied."""
    conf = Configuration()
    conf.apply_deadtime = True
    file_path = data_server.path_to("REF_M_42112") + "+" + data_server.path_to("REF_M_42113")

    ws_list = conf.instrument.load_data(file_path, conf)

    # Should have 4 cross-sections
    assert len(ws_list) == 4

    # Verify dead-time was applied
    for ws in ws_list:
        run = ws.getRun()
        assert "dead_time_applied" in run
        # Verify run_numbers is set
        assert run.hasProperty("run_numbers")


@pytest.mark.datarepo
def test_load_data_sum_cross_section_matching(data_server):
    """Test that cross-sections are correctly matched by ID when summing."""
    conf = Configuration()
    file_path = data_server.path_to("REF_M_42112") + "+" + data_server.path_to("REF_M_42113")

    ws_list = conf.instrument.load_data(file_path, conf)

    # Load individual files
    ws_list_42112 = conf.instrument.load_data(data_server.path_to("REF_M_42112"), conf)
    ws_list_42113 = conf.instrument.load_data(data_server.path_to("REF_M_42113"), conf)

    # Verify cross_section_id properties match
    for i in range(4):
        xs_id_merged = ws_list[i].getRun().getProperty("cross_section_id").value
        xs_id_42112 = ws_list_42112[i].getRun().getProperty("cross_section_id").value
        xs_id_42113 = ws_list_42113[i].getRun().getProperty("cross_section_id").value

        assert xs_id_merged == xs_id_42112 == xs_id_42113, f"Cross-section ID mismatch at position {i}"


def test_direct_beam_distance():
    # get an instrument
    conf = Configuration()
    instrument = conf.instrument

    # use scattering as reference
    scattering = mock.Mock(
        slit1_width=1.0,
        slit2_width=1.0,
        slit3_width=1.0,
    )

    # in same location, should be zero distance
    direct_beam = mock.Mock(
        slit1_width=1.0,
        slit2_width=1.0,
        slit3_width=1.0,
    )
    assert instrument.direct_beam_distance(scattering, direct_beam) == 0.0

    # beam (2-1)^2 + (2-1)^2 + (2-1)^2 = 3
    direct_beam = mock.Mock(
        slit1_width=2.0,
        slit2_width=2.0,
        slit3_width=2.0,
    )
    assert instrument.direct_beam_distance(scattering, direct_beam) == 3.0

    # beam (3-1)^2 + (3-1)^2 + (3-1)^2 = 4 + 4 + 4 = 12
    direct_beam = mock.Mock(
        slit1_width=3.0,
        slit2_width=3.0,
        slit3_width=3.0,
    )
    assert instrument.direct_beam_distance(scattering, direct_beam) == 12.0
