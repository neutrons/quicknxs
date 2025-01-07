# local imports
from quicknxs.interfaces.configuration import Configuration
from quicknxs.interfaces.data_handling.gisans import GISANS
from quicknxs.interfaces.data_manager import DataManager

# third-party imports
import pytest


@pytest.mark.datarepo
def test_gisans(data_server):
    """Test of the GISANS calculation"""
    manager = DataManager(data_server.directory)
    manager.load(data_server.path_to("REF_M_42112"), Configuration())
    manager.add_active_to_reduction()
    manager.load(data_server.path_to("REF_M_42100"), Configuration())
    manager.add_active_to_normalization()
    direct_beam = manager.direct_beam_list[0].cross_sections["Off_On"]
    xs = manager.reduction_list[0].cross_sections["Off_On"]
    xs.gisans(direct_beam=direct_beam)
    # check output values
    rel_tol = 1e-4
    assert xs.QyGrid.shape == xs.QzGrid.shape == xs.SGrid.shape == (50, 50)
    assert xs.QyGrid.min() == pytest.approx(-0.13908, rel=rel_tol)
    assert xs.QyGrid.max() == pytest.approx(0.072288, rel=rel_tol)
    assert xs.QzGrid.min() == pytest.approx(-0.089320, rel=rel_tol)
    assert xs.QzGrid.max() == pytest.approx(0.16181, rel=rel_tol)
    assert xs.gisans_data.p_f.min() == pytest.approx(-0.10071, rel=rel_tol)
    assert xs.gisans_data.p_f.max() == pytest.approx(0.15554, rel=rel_tol)
