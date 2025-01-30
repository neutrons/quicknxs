# package imports
# 3rd-party imports
import mantid.simpleapi as api
import pytest
from mantid.kernel import amend_config

from quicknxs.interfaces.data_handling.DeadTimeCorrection import SingleReadoutDeadTimeCorrection
from quicknxs.interfaces.data_handling.instrument import mantid_algorithm_exec

# standard imports


@pytest.mark.datarepo
@pytest.mark.parametrize("is_paralyzable", [False, True])
def test_deadtime(is_paralyzable, data_server):
    """Test of the dead-time correction algorithm SingleReadoutDeadTimeCorrection"""
    with amend_config(data_dir=data_server.h5_full_path):
        ws = api.Load("REF_M_42112")
    corr_ws = mantid_algorithm_exec(
        SingleReadoutDeadTimeCorrection,
        InputWorkspace=ws,
        Paralyzable=is_paralyzable,
        OutputWorkspace="dead_time_corr",
    )
    corr = corr_ws.readY(0)
    for c in corr:
        assert 1.0 <= c < 1.001, "value not between 1.0 and 1.001"
