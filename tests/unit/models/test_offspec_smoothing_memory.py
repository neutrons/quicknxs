"""Tests for the off-specular smoothing session memory."""

import math

import pytest

from quicknxs.enums import OffSpecXAxis
from quicknxs.models.offspec_smoothing_memory import (
    DEFAULT_MINIMUM_RADIUS,
    DEFAULT_SIGMA_FRACTION,
    OffSpecRegion,
    OffSpecSmoothingMemory,
    default_coupled,
    default_radii,
    radii_from_axis,
    radii_to_axis,
)

DELTA_KZ = OffSpecXAxis.DELTA_KZ_VS_QZ
QX = OffSpecXAxis.QX_VS_QZ
KIZ_KFZ = OffSpecXAxis.KZI_VS_KZF

# Spin box limits from ui_smooth_dialog.ui
SIGMA_MIN = 1e-6
SIGMA_MAX = 1.0

# Incident angle of run 42113
TAN_THETA = math.tan(math.radians(0.8534))

# (ki_z-kf_z) vs Qz region similar to run 42112
REGION = OffSpecRegion(-0.1515, 0.1054, -0.0872, 0.1630)


class TestDefaultCoupled:
    """Default uniformity per coordinate system."""

    @pytest.mark.parametrize("axis, expected", [(DELTA_KZ, True), (QX, False), (KIZ_KFZ, True)])
    def test_matches_agreed_table(self, axis, expected):
        assert default_coupled(axis) is expected

    def test_accepts_plain_integers(self):
        """The axis is sometimes stored as an int."""
        assert default_coupled(int(QX)) is False


class TestOffSpecRegion:
    """The region box."""

    def test_extents(self):
        region = OffSpecRegion(-0.01, 0.03, 0.1, 0.3)
        assert region.width == pytest.approx(0.04)
        assert region.height == pytest.approx(0.2)

    def test_is_frozen(self):
        with pytest.raises(AttributeError):
            OffSpecRegion(0.0, 1.0, 0.0, 1.0).x_min = 5.0


class TestDefaultRadii:
    """Radii used before the user picks one."""

    def test_uncoupled_uses_a_quarter_percent_of_each_extent(self):
        sigma_x, sigma_y = default_radii(REGION, coupled=False)
        assert sigma_x == pytest.approx(DEFAULT_SIGMA_FRACTION * REGION.width)
        assert sigma_y == pytest.approx(DEFAULT_SIGMA_FRACTION * REGION.height)

    def test_coupled_uses_x_for_both(self):
        """Otherwise the uniform view would show a different y than the one carried over."""
        sigma_x, sigma_y = default_radii(REGION, coupled=True)
        assert sigma_y == sigma_x == pytest.approx(DEFAULT_SIGMA_FRACTION * REGION.width)

    def test_never_below_the_floor(self):
        narrow = OffSpecRegion(0.0, 0.001, 0.0, 0.001)
        assert default_radii(narrow, coupled=False) == (DEFAULT_MINIMUM_RADIUS, DEFAULT_MINIMUM_RADIUS)


class TestConversions:
    """Converting (dk, Qz) radii to and from each coordinate system."""

    def test_the_default_system_is_unchanged(self):
        assert radii_to_axis(0.001, 0.002, DELTA_KZ, TAN_THETA) == (0.001, 0.002)
        assert radii_from_axis(0.001, 0.002, DELTA_KZ, TAN_THETA) == (0.001, 0.002)

    def test_qz_is_shared_with_qx_vs_qz(self):
        """Qx vs Qz has the same y axis, so the y radius must not change."""
        _, sigma_y = radii_to_axis(0.001, 0.002, QX, TAN_THETA)
        assert sigma_y == 0.002

    def test_qx_is_dk_times_tan_theta(self):
        sigma_x, _ = radii_to_axis(0.001, 0.002, QX, TAN_THETA)
        assert sigma_x == pytest.approx(0.001 * TAN_THETA)

    def test_uniform_radii_shrink_by_root_two_in_kiz_vs_kfz(self):
        sigma = 0.001
        converted = radii_to_axis(sigma, sigma, KIZ_KFZ, TAN_THETA)
        assert converted == pytest.approx((sigma / math.sqrt(2), sigma / math.sqrt(2)))

    @pytest.mark.parametrize("axis", [DELTA_KZ, QX, KIZ_KFZ])
    def test_round_trip(self, axis):
        sigma = 0.000123
        shown = radii_to_axis(sigma, sigma, axis, TAN_THETA)
        assert radii_from_axis(*shown, axis, TAN_THETA) == pytest.approx((sigma, sigma), rel=1e-12)

    def test_non_uniform_radii_come_back_uniform_from_kiz_vs_kfz(self):
        """The kernel can't represent the dk-Qz correlation, so that information is lost."""
        shown = radii_to_axis(0.001, 0.003, KIZ_KFZ, TAN_THETA)
        sigma_dk, sigma_qz = radii_from_axis(*shown, KIZ_KFZ, TAN_THETA)
        assert sigma_dk == pytest.approx(sigma_qz)

    @pytest.mark.parametrize("tan_theta", [None, 0.0, -0.1])
    def test_qx_is_left_unconverted_without_an_incident_angle(self, tan_theta):
        assert radii_to_axis(0.001, 0.002, QX, tan_theta) == (0.001, 0.002)
        assert radii_from_axis(0.001, 0.002, QX, tan_theta) == (0.001, 0.002)


class TestLookups:
    """Reading from the memory."""

    def test_no_radii_until_the_user_picks_one(self):
        memory = OffSpecSmoothingMemory()
        assert memory.sigma_x is None
        assert memory.sigma_y is None

    def test_radii_for_uses_the_default_until_radii_are_stored(self):
        memory = OffSpecSmoothingMemory()
        assert memory.radii_for(QX, (0.001, 0.002), TAN_THETA) == pytest.approx((0.001 * TAN_THETA, 0.002))

    def test_radii_for_clamps_to_the_spin_box_limits(self):
        memory = OffSpecSmoothingMemory(sigma_x=1e-9, sigma_y=50.0)
        assert memory.radii_for(DELTA_KZ, (0.0, 0.0), TAN_THETA, SIGMA_MIN, SIGMA_MAX) == (SIGMA_MIN, SIGMA_MAX)

    def test_region_for_falls_back_when_not_stored(self):
        assert OffSpecSmoothingMemory().region_for(QX, REGION) == REGION

    def test_region_for_returns_the_stored_region(self):
        memory = OffSpecSmoothingMemory()
        stored = OffSpecRegion(0.0, 1.0, 0.0, 1.0)
        memory.store_region(QX, stored)
        assert memory.region_for(QX, REGION) == stored

    def test_coupled_for_falls_back_to_the_default(self):
        assert OffSpecSmoothingMemory().coupled_for(QX) is False

    def test_coupled_for_returns_the_stored_flag(self):
        memory = OffSpecSmoothingMemory()
        memory.store_coupled(QX, True)
        assert memory.coupled_for(QX) is True

    def test_r_sigmas_falls_back_until_stored(self):
        memory = OffSpecSmoothingMemory()
        assert memory.r_sigmas_for(3.0) == 3.0
        memory.store_r_sigmas(5.0)
        assert memory.r_sigmas_for(3.0) == 5.0

    def test_axis_keys_are_normalised_from_integers(self):
        memory = OffSpecSmoothingMemory()
        memory.store_region(int(KIZ_KFZ), REGION)
        memory.store_coupled(int(KIZ_KFZ), False)
        assert memory.region_for(KIZ_KFZ, OffSpecRegion(0, 1, 0, 1)) == REGION
        assert memory.coupled_for(KIZ_KFZ) is False


class TestStoreRadii:
    """Storing radii the user edited, converted to (dk, Qz)."""

    def _store(self, memory, axis, shown, edited_x=True, edited_y=True, coupled=False, default=(0.0004, 0.0004)):
        memory.store_radii(axis, *shown, default, TAN_THETA, edited_x=edited_x, edited_y=edited_y, coupled=coupled)

    def test_an_edit_in_the_default_system_is_stored_as_is(self):
        memory = OffSpecSmoothingMemory()
        self._store(memory, DELTA_KZ, (0.001, 0.002))
        assert (memory.sigma_x, memory.sigma_y) == (0.001, 0.002)

    def test_an_edit_in_qx_vs_qz_is_converted_back(self):
        memory = OffSpecSmoothingMemory()
        self._store(memory, QX, (0.00002, 0.002))
        assert memory.sigma_x == pytest.approx(0.00002 / TAN_THETA)
        assert memory.sigma_y == 0.002

    def test_the_unedited_radius_is_not_read_back_from_the_spin_box(self):
        """The Qx radius is tiny, so its rounded display would shift the stored value."""
        memory = OffSpecSmoothingMemory(sigma_x=0.0004, sigma_y=0.0004)
        rounded_on_screen = round(0.0004 * TAN_THETA, 6)

        self._store(memory, QX, (rounded_on_screen, 0.002), edited_x=False)

        assert memory.sigma_x == pytest.approx(0.0004, rel=1e-12)
        assert memory.sigma_y == 0.002

    def test_while_coupled_y_follows_x(self):
        memory = OffSpecSmoothingMemory()
        self._store(memory, KIZ_KFZ, (0.001, 0.005), edited_y=False, coupled=True)
        assert (memory.sigma_x, memory.sigma_y) == pytest.approx((0.001 * math.sqrt(2), 0.001 * math.sqrt(2)))

    def test_the_default_is_used_for_an_unedited_radius(self):
        memory = OffSpecSmoothingMemory()
        self._store(memory, DELTA_KZ, (0.001, 0.999), edited_y=False, default=(0.0004, 0.0007))
        assert (memory.sigma_x, memory.sigma_y) == (0.001, 0.0007)

    def test_showing_other_systems_does_not_change_the_stored_radii(self):
        memory = OffSpecSmoothingMemory(sigma_x=0.000123, sigma_y=0.000456)
        for axis in (QX, KIZ_KFZ, DELTA_KZ):
            memory.radii_for(axis, (0.0, 0.0), TAN_THETA, SIGMA_MIN, SIGMA_MAX)
        assert (memory.sigma_x, memory.sigma_y) == (0.000123, 0.000456)


class TestWorkingCopies:
    """Working copy that is only committed on OK."""

    def test_snapshot_is_independent(self):
        memory = OffSpecSmoothingMemory()
        memory.store_region(QX, REGION)
        snapshot = memory.snapshot()

        memory.store_region(KIZ_KFZ, REGION)
        memory.sigma_x = 9.9

        assert KIZ_KFZ not in snapshot.regions
        assert snapshot.sigma_x is None

    def test_copy_from_mutates_in_place(self):
        """The main window holds this instance, so it has to be updated in place."""
        memory = OffSpecSmoothingMemory()
        snapshot = memory.snapshot()
        memory.store_region(QX, REGION)
        memory.store_coupled(QX, True)
        memory.store_r_sigmas(5.0)
        memory.sigma_x = 9.9
        identity = id(memory)

        memory.copy_from(snapshot)

        assert id(memory) == identity
        assert memory == OffSpecSmoothingMemory()

    def test_copy_from_does_not_alias_the_source(self):
        memory = OffSpecSmoothingMemory()
        snapshot = memory.snapshot()
        memory.copy_from(snapshot)

        memory.store_region(QX, REGION)

        assert snapshot.regions == {}


if __name__ == "__main__":
    pytest.main([__file__])
