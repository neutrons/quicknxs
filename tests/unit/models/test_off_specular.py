import numpy as np
import pytest
from numpy.testing import assert_allclose

from quicknxs.enums import OffSpecXAxis
from quicknxs.models.configuration import Configuration
from quicknxs.models.off_specular import finest_intervals, smooth_data
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


def _brute_force_grid_smooth(
    x, y, intensity, sigmas, gridx, gridy, sigmax, sigmay, x1, x2, y1, y2, axis_sigma_scaling=None, xysigma0=0.06
):
    """Reference implementation: the original per-grid-point smoothing loop."""
    xout = np.linspace(x1, x2, gridx)
    yout = np.linspace(y1, y2, gridy)
    x_grid, y_grid = np.meshgrid(xout, yout)
    result = np.zeros_like(x_grid)
    ssigmax, ssigmay = sigmax**2, sigmay**2
    for i in range(gridy):
        for j in range(gridx):
            xij, yij = x_grid[i, j], y_grid[i, j]
            if axis_sigma_scaling:
                if axis_sigma_scaling == 1:
                    xyij = xij
                elif axis_sigma_scaling == 2:
                    xyij = yij
                else:
                    xyij = xij + yij
                if xyij <= 0:
                    continue
                rij = (x - xij) ** 2 / (ssigmax / xysigma0 * xyij) + (y - yij) ** 2 / (ssigmay / xysigma0 * xyij)
            else:
                rij = (x - xij) ** 2 / ssigmax + (y - yij) ** 2 / ssigmay
            take = rij < sigmas**2
            if not take.any():
                continue
            weights = np.exp(-0.5 * rij[take])
            result[i, j] = (weights * intensity[take]).sum() / weights.sum()
    return x_grid, y_grid, result


class TestSmoothData:
    """Tests for the KD-tree regular-grid smoothing."""

    def test_matches_brute_force(self):
        rng = np.random.default_rng(42)
        n = 300
        x = rng.uniform(-0.03, 0.03, n)
        y = rng.uniform(0.0, 0.1, n)
        intensity = rng.uniform(0.0, 1.0, n)
        kwargs = dict(sigmas=3.0, gridx=25, gridy=20, sigmax=0.004, sigmay=0.008, x1=-0.03, x2=0.03, y1=0.0, y2=0.1)
        x_grid, y_grid, smoothed = smooth_data(x, y, intensity, **kwargs)
        ref_x, ref_y, expected = _brute_force_grid_smooth(x, y, intensity, **kwargs)
        assert_allclose(x_grid, ref_x)
        assert_allclose(y_grid, ref_y)
        assert_allclose(smoothed, expected, rtol=1e-10)

    def test_matches_brute_force_with_sigma_scaling(self):
        rng = np.random.default_rng(7)
        n = 300
        x = rng.uniform(-0.03, 0.03, n)
        y = rng.uniform(0.0, 0.1, n)
        intensity = rng.uniform(0.0, 1.0, n)
        for scaling in (2, 3):
            kwargs = dict(
                sigmas=3.0,
                gridx=25,
                gridy=20,
                sigmax=0.004,
                sigmay=0.008,
                x1=-0.03,
                x2=0.03,
                y1=0.0,
                y2=0.1,
                axis_sigma_scaling=scaling,
                xysigma0=0.05,
            )
            _, _, smoothed = smooth_data(x, y, intensity, **kwargs)
            _, _, expected = _brute_force_grid_smooth(x, y, intensity, **kwargs)
            assert_allclose(smoothed, expected, rtol=1e-10)

    def test_grid_shape_and_empty_regions(self):
        """Output shape is (gridy, gridx); grid points far from any data stay 0."""
        x = np.array([0.0, 0.001])
        y = np.array([0.05, 0.051])
        intensity = np.array([1.0, 2.0])
        x_grid, y_grid, smoothed = smooth_data(
            x,
            y,
            intensity,
            sigmas=3.0,
            gridx=30,
            gridy=40,
            sigmax=0.0005,
            sigmay=0.0005,
            x1=-0.03,
            x2=0.03,
            y1=0.0,
            y2=0.1,
        )
        assert smoothed.shape == (40, 30)
        assert smoothed[0, 0] == 0.0  # far corner, no data in range
        assert smoothed.max() > 0.0


class _FakeConfig:
    def __init__(self, cut_first=0, cut_last=0):
        self.cut_first_n_points = cut_first
        self.cut_last_n_points = cut_last


class _FakeOffSpec:
    def __init__(self, ki_z, kf_z, Qx, Qz):
        self.ki_z, self.kf_z, self.Qx, self.Qz = ki_z, kf_z, Qx, Qz
        self.S = np.zeros_like(ki_z)


class _FakeCrossSection:
    def __init__(self, off_spec, configuration):
        self.off_spec = off_spec
        self.configuration = configuration


class _FakeItem:
    def __init__(self, cross_sections):
        self.cross_sections = cross_sections


def _fake_run(ki_step=0.01, kf_step=0.002, n_pix=10, n_tof=20, cut_first=0, cut_last=0):
    """A run whose ki_z varies by row and kf_z by column, with uniform steps."""
    ii, jj = np.meshgrid(np.arange(n_pix, dtype=float), np.arange(n_tof, dtype=float), indexing="ij")
    ki_z = 0.01 + ki_step * ii
    kf_z = 0.01 + kf_step * jj
    off_spec = _FakeOffSpec(ki_z=ki_z, kf_z=kf_z, Qx=0.1 * ki_z, Qz=ki_z + kf_z)
    return _FakeItem({"Off_Off": _FakeCrossSection(off_spec, _FakeConfig(cut_first, cut_last))})


class TestFinestIntervals:
    """Tests for the finest-interval estimate used by the auto grid."""

    def test_uniform_grid(self):
        result = finest_intervals([_fake_run()], "Off_Off", axes=OffSpecXAxis.KZI_VS_KZF)
        assert result is not None
        assert result[0] == pytest.approx(0.01)
        assert result[1] == pytest.approx(0.002)

    def test_minimum_over_runs(self):
        runs = [_fake_run(ki_step=0.01, kf_step=0.002), _fake_run(ki_step=0.004, kf_step=0.005)]
        dx, dy = finest_intervals(runs, "Off_Off", axes=OffSpecXAxis.KZI_VS_KZF)
        # 1st percentile of the pooled differences sits at the finer run's spacing
        assert dx == pytest.approx(0.004)
        assert dy == pytest.approx(0.002)

    def test_region_restriction(self):
        # Without a region the y estimate is dominated by the fine kf steps of
        # the full range; restricting y to the first few columns must not
        # change the uniform spacing, restricting to a single column removes
        # all y differences
        run = _fake_run(kf_step=0.002, n_tof=20)
        full = finest_intervals([run], "Off_Off", axes=OffSpecXAxis.KZI_VS_KZF)
        restricted = finest_intervals([run], "Off_Off", axes=OffSpecXAxis.KZI_VS_KZF, y_range=(0.0095, 0.0165))
        assert restricted is not None
        assert restricted[1] == pytest.approx(full[1])
        single_column = finest_intervals([run], "Off_Off", axes=OffSpecXAxis.KZI_VS_KZF, y_range=(0.0095, 0.0105))
        assert single_column is None  # no in-region y differences left

    def test_cut_points_are_excluded(self):
        # Make the first TOF column pathologically close to the second one;
        # cutting it must remove its tiny interval from the estimate
        run = _fake_run(kf_step=0.002, n_tof=20)
        off_spec = run.cross_sections["Off_Off"].off_spec
        off_spec.kf_z[:, 0] = off_spec.kf_z[:, 1] - 1e-8
        uncut = finest_intervals([run], "Off_Off", axes=OffSpecXAxis.KZI_VS_KZF)
        assert uncut[1] < 0.002
        run.cross_sections["Off_Off"].configuration.cut_first_n_points = 1
        cut = finest_intervals([run], "Off_Off", axes=OffSpecXAxis.KZI_VS_KZF)
        assert cut[1] == pytest.approx(0.002)

    def test_no_data_returns_none(self):
        assert finest_intervals([], "Off_Off", axes=OffSpecXAxis.KZI_VS_KZF) is None
        item = _FakeItem({"Off_Off": _FakeCrossSection(None, _FakeConfig())})
        assert finest_intervals([item], "Off_Off", axes=OffSpecXAxis.KZI_VS_KZF) is None

    def test_default_axes_is_delta_kz_vs_qz(self):
        run = _fake_run(ki_step=0.01, kf_step=0.002)
        dx, dy = finest_intervals([run], "Off_Off")
        # x = ki_z - kf_z: steps 0.01 along rows and 0.002 along columns
        assert dx == pytest.approx(0.002, rel=0.05)
        # y = Qz = ki_z + kf_z: same steps
        assert dy == pytest.approx(0.002, rel=0.05)
