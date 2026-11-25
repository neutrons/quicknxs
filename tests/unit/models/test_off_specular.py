from types import SimpleNamespace

import numpy as np
import pytest

from quicknxs.models.configuration import Configuration
from quicknxs.models.off_specular import merge
from quicknxs.models.processing_workflow import ProcessingWorkflow
from quicknxs.presenters.data_manager import DataManager


@pytest.mark.datarepo
def test_off_specular(data_server):
    """Test of the OffSpecular calculation."""
    manager = DataManager(data_server.directory)
    manager.load(data_server.path_to("REF_M_42112"), Configuration())
    manager.add_active_to_reduction()
    manager.load(data_server.path_to("REF_M_42100"), Configuration())
    manager.add_active_to_direct_beam_list()
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


def _fake_run(n_pix: int, n_tof: int, cut_first: int, cut_last: int):
    """Minimal stand-in for a NexusData with one cross-section holding off-specular arrays.

    As in ``OffSpecular.__call__``, arrays are indexed [pixel][TOF] with TOF ascending, so the
    wavevector (and Q) *descends* along the second axis. ``S`` holds the TOF index itself.
    """
    tof_index = np.tile(np.arange(n_tof, dtype=float), (n_pix, 1))
    k = 1.0 / (1.0 + tof_index)  # short TOF = large k
    off_spec = SimpleNamespace(Qx=0.0 * k, Qz=2.0 * k, ki_z=k, kf_z=k, S=tof_index.copy(), dS=np.ones_like(k))
    configuration = SimpleNamespace(cut_first_n_points=cut_first, cut_last_n_points=cut_last)
    xs = SimpleNamespace(off_spec=off_spec, configuration=configuration, cross_section_label="Off_Off")
    return SimpleNamespace(cross_sections={"Off_Off": xs}, run_number="1")


def test_merge_cuts_first_points_at_low_q():
    """The "first" points of a run are its lowest-Q points, as in the reflectivity curve."""
    n_tof, cut_first, cut_last = 20, 2, 5
    run = _fake_run(n_pix=3, n_tof=n_tof, cut_first=cut_first, cut_last=cut_last)
    _, qz, ki_z, _, _, s, _ = merge([run], "Off_Off")
    # the `cut_last` shortest-TOF (highest-Q) and `cut_first` longest-TOF (lowest-Q) bins are gone
    assert sorted(set(s)) == list(range(cut_last, n_tof - cut_first))
    assert ki_z.max() == pytest.approx(1.0 / (1.0 + cut_last))
    assert qz.min() == pytest.approx(2.0 / (n_tof - cut_first))


def test_raw_export_trim_matches_merge(mocker):
    """The raw export and the binned/smoothed export (via `merge`) keep the same TOF bins."""
    n_tof, cut_first, cut_last = 20, 2, 5
    run = _fake_run(n_pix=3, n_tof=n_tof, cut_first=cut_first, cut_last=cut_last)
    data_manager = mocker.Mock(reduction_states=["Off_Off"], reduction_list=[run])
    data_dict = ProcessingWorkflow(data_manager).get_offspec_data()
    (rdata,) = data_dict["Off_Off"]  # [pixel][TOF][column]
    assert rdata.shape == (3, n_tof - cut_first - cut_last, 7)
    np.testing.assert_array_equal(rdata[0, :, 5], np.arange(cut_last, n_tof - cut_first))
    np.testing.assert_array_equal(np.sort(rdata[:, :, 5].ravel()), np.sort(merge([run], "Off_Off")[5]))


@pytest.mark.datarepo
def test_off_specular_tof_axis_runs_from_high_to_low_q(data_server):
    """Guard the premise of the trim: ki_z decreases along the TOF axis of the off-specular arrays."""
    manager = DataManager(data_server.directory)
    manager.load(data_server.path_to("REF_M_42112"), Configuration())
    xs = manager.active_cross_section
    xs.offspec()
    assert np.all(np.diff(xs.off_spec.ki_z, axis=1) < 0)
