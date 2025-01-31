# local imports
# third-party imports
import pytest

from quicknxs.interfaces.configuration import Configuration
from quicknxs.interfaces.data_manager import DataManager


@pytest.mark.datarepo
def test_off_specular(data_server):
    """Test of the OffSpecular calculation"""
    manager = DataManager(data_server.directory)
    manager.load(data_server.path_to("REF_M_42112"), Configuration())
    manager.add_active_to_reduction()
    manager.load(data_server.path_to("REF_M_42100"), Configuration())
    manager.add_active_to_normalization()
    direct_beam = manager.direct_beam_list[0].cross_sections["Off_On"]
    xs = manager.reduction_list[0].cross_sections["Off_On"]
    xs.offspec(direct_beam=direct_beam)
    # check output values
    rel_tol = 1e-4
    assert xs.off_spec.S.shape == xs.off_spec.Qx.shape == xs.off_spec.Qz.shape == (287, 84)
    assert xs.off_spec.Qx.min() == pytest.approx(-0.0041124, rel=rel_tol)
    assert xs.off_spec.Qx.max() == pytest.approx(1.4527e-5, rel=rel_tol)
    assert xs.off_spec.Qz.min() == pytest.approx(-0.087175, rel=rel_tol)
    assert xs.off_spec.Qz.max() == pytest.approx(0.16304, rel=rel_tol)
    assert xs.off_spec.kf_z.min() == pytest.approx(-0.096310, rel=rel_tol)
    assert xs.off_spec.kf_z.max() == pytest.approx(0.15391, rel=rel_tol)
    assert xs.off_spec.ki_z.min() == pytest.approx(0.0023673, rel=rel_tol)
    assert xs.off_spec.ki_z.max() == pytest.approx(0.0091347, rel=rel_tol)
