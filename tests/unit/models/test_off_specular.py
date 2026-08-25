import numpy as np
import pytest
from numpy.testing import assert_allclose

from quicknxs.models.configuration import Configuration
from quicknxs.models.off_specular import smooth_data_irregular
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


def _brute_force_smooth(x, y, intensity, sigmas, sigmax, sigmay, axis_sigma_scaling=None, xysigma0=0.06):
    """Reference implementation: the smoothing loop from `_smooth_data` evaluated at the input points."""
    result = np.zeros_like(intensity, dtype=float)
    for i in range(len(x)):
        if axis_sigma_scaling:
            if axis_sigma_scaling == 1:
                xy = x[i]
            elif axis_sigma_scaling == 2:
                xy = y[i]
            else:
                xy = x[i] + y[i]
            if xy <= 0:
                continue
            ssigmax = sigmax**2 / xysigma0 * xy
            ssigmay = sigmay**2 / xysigma0 * xy
        else:
            ssigmax = sigmax**2
            ssigmay = sigmay**2
        rij = (x - x[i]) ** 2 / ssigmax + (y - y[i]) ** 2 / ssigmay
        take = rij < sigmas**2
        weights = np.exp(-0.5 * rij[take])
        result[i] = (weights * intensity[take]).sum() / weights.sum()
    return result


class TestSmoothDataIrregular:
    """Tests for smoothing evaluated on the input's own irregular grid."""

    def test_matches_brute_force(self):
        """The KD-tree implementation must match the direct Gaussian average."""
        rng = np.random.default_rng(42)
        n = 400
        x = rng.uniform(-0.03, 0.03, n)
        y = rng.uniform(0.0, 0.1, n)
        intensity = rng.uniform(0.0, 1.0, n)
        smoothed = smooth_data_irregular(x, y, intensity, sigmas=3.0, sigmax=0.005, sigmay=0.01)
        expected = _brute_force_smooth(x, y, intensity, sigmas=3.0, sigmax=0.005, sigmay=0.01)
        assert_allclose(smoothed, expected, rtol=1e-10)

    def test_matches_brute_force_with_sigma_scaling(self):
        """The position-dependent sigma scaling must match the direct computation."""
        rng = np.random.default_rng(1234)
        n = 400
        x = rng.uniform(-0.03, 0.03, n)
        y = rng.uniform(0.0, 0.1, n)
        intensity = rng.uniform(0.0, 1.0, n)
        for scaling in (2, 3):
            smoothed = smooth_data_irregular(
                x, y, intensity, sigmas=3.0, sigmax=0.005, sigmay=0.01, axis_sigma_scaling=scaling, xysigma0=0.05
            )
            expected = _brute_force_smooth(
                x, y, intensity, sigmas=3.0, sigmax=0.005, sigmay=0.01, axis_sigma_scaling=scaling, xysigma0=0.05
            )
            assert_allclose(smoothed, expected, rtol=1e-10)

    def test_preserves_shape(self):
        """2D pixel-by-TOF input arrays come back with the same shape."""
        rng = np.random.default_rng(7)
        x = rng.uniform(-0.03, 0.03, (15, 20))
        y = rng.uniform(0.0, 0.1, (15, 20))
        intensity = rng.uniform(0.0, 1.0, (15, 20))
        smoothed = smooth_data_irregular(x, y, intensity, sigmax=0.005, sigmay=0.01)
        assert smoothed.shape == (15, 20)

    def test_constant_intensity_is_unchanged(self):
        """A weighted average of a constant field returns the constant."""
        rng = np.random.default_rng(3)
        x = rng.uniform(-0.03, 0.03, 200)
        y = rng.uniform(0.0, 0.1, 200)
        intensity = np.full(200, 2.5)
        smoothed = smooth_data_irregular(x, y, intensity, sigmax=0.005, sigmay=0.01)
        assert_allclose(smoothed, 2.5)

    def test_nonpositive_scaling_coordinate_gives_zero(self):
        """Points where the sigma-scaling coordinate is <= 0 keep a zero intensity."""
        x = np.array([0.01, 0.02, 0.03])
        y = np.array([-0.05, 0.0, 0.05])
        intensity = np.ones(3)
        smoothed = smooth_data_irregular(
            x, y, intensity, sigmax=0.005, sigmay=0.01, axis_sigma_scaling=2, xysigma0=0.05
        )
        assert smoothed[0] == 0.0
        assert smoothed[1] == 0.0
        assert smoothed[2] > 0.0

    def test_unknown_scaling_raises(self):
        x = y = intensity = np.ones(3)
        with pytest.raises(ValueError, match="axis_sigma_scaling"):
            smooth_data_irregular(x, y, intensity, axis_sigma_scaling=4)
