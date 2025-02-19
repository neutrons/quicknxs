# package imports
import pytest

# 3rd party imports
from mantid.api import MatrixWorkspaceProperty, PythonAlgorithm
from mantid.kernel import Direction
from mantid.simpleapi import CreateSingleValuedWorkspace

from quicknxs.interfaces.configuration import Configuration
from quicknxs.interfaces.data_handling.instrument import mantid_algorithm_exec


@pytest.mark.datarepo
def test_load_data_deadtime(data_server):
    """Test load data with and without dead-time correction"""
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


def test_mantid_algorithm_exec():
    """Test helper function mantid_algorithm_exec"""

    # test wrong type of class
    class TestNotMantidAlgo:
        pass

    with pytest.raises(AssertionError, match="is not a Mantid Python algorithm"):
        mantid_algorithm_exec(TestNotMantidAlgo)
    # test Mantid Python algorithm

    class TestMantidAlgo(PythonAlgorithm):
        def PyInit(self):
            self.declareProperty("Value", 8, "Value in workspace")
            self.declareProperty(
                MatrixWorkspaceProperty("OutputWorkspace", "", Direction.Output),
                "Output workspace",
            )

        def PyExec(self):
            value = self.getProperty("Value").value
            ws = CreateSingleValuedWorkspace(value)
            self.setProperty("OutputWorkspace", ws)

    custom_value = 4
    ws_out = mantid_algorithm_exec(TestMantidAlgo, Value=custom_value, OutputWorkspace="output")
    assert ws_out.readY(0)[0] == custom_value


@pytest.mark.datarepo
def test_load_data_nbr_events_min(data_server):
    """Test load data with one cross-section with too few events"""
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
