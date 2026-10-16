"""Tests for the off-specular smoothing session memory."""

import pytest

from quicknxs.enums import OffSpecXAxis
from quicknxs.models.offspec_smoothing_memory import (
    DEFAULT_MINIMUM_RADIUS,
    DEFAULT_SIGMA_FRACTION,
    OffSpecRegion,
    OffSpecSmoothingMemory,
    default_coupled,
    default_radii,
    fractions_to_radii,
    radii_to_fractions,
)

DELTA_KZ = OffSpecXAxis.DELTA_KZ_VS_QZ
QX = OffSpecXAxis.QX_VS_QZ
KIZ_KFZ = OffSpecXAxis.KZI_VS_KZF

# Spin box limits from ui_smooth_dialog.ui
SIGMA_MIN = 1e-8
SIGMA_MAX = 1.0

# (ki_z-kf_z) vs Qz region similar to run 42112
REGION = OffSpecRegion(-0.1515, 0.1054, -0.0872, 0.1630)

# Plotted axis ranges similar to runs 47286-47288
EXTENT = {
    DELTA_KZ: OffSpecRegion(-0.115, 0.068, -0.05, 0.19),
    QX: OffSpecRegion(-0.0044, 0.001, -0.05, 0.19),
    KIZ_KFZ: OffSpecRegion(0.0035, 0.051, -0.06, 0.14),
}


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
    """Converting radii to and from fractions of the plotted axis ranges."""

    def test_radii_are_divided_by_the_axis_ranges(self):
        extent = OffSpecRegion(0.0, 0.04, 0.1, 0.3)
        assert radii_to_fractions(0.001, 0.002, extent) == pytest.approx((0.025, 0.01))

    def test_fractions_are_multiplied_by_the_axis_ranges(self):
        extent = OffSpecRegion(0.0, 0.04, 0.1, 0.3)
        assert fractions_to_radii(0.025, 0.01, extent, coupled=False) == pytest.approx((0.001, 0.002))

    def test_a_uniform_view_takes_both_radii_from_x(self):
        extent = OffSpecRegion(0.0, 0.04, 0.1, 0.3)
        assert fractions_to_radii(0.025, 0.5, extent, coupled=True) == pytest.approx((0.001, 0.001))

    @pytest.mark.parametrize("axis", [DELTA_KZ, QX, KIZ_KFZ])
    def test_round_trip(self, axis):
        fractions = radii_to_fractions(0.000123, 0.000456, EXTENT[axis])
        assert fractions_to_radii(*fractions, EXTENT[axis], coupled=False) == pytest.approx(
            (0.000123, 0.000456), rel=1e-12
        )

    @pytest.mark.parametrize("axis", [DELTA_KZ, QX, KIZ_KFZ])
    def test_the_spot_is_the_same_fraction_of_every_plot(self, axis):
        """The agreed rule: switching views must not make the spot jump in size."""
        fractions = radii_to_fractions(0.000411, 0.000411, EXTENT[DELTA_KZ])
        sigma_x, sigma_y = fractions_to_radii(*fractions, EXTENT[axis], coupled=False)
        assert sigma_x / EXTENT[axis].width == pytest.approx(0.000411 / EXTENT[DELTA_KZ].width)
        assert sigma_y / EXTENT[axis].height == pytest.approx(0.000411 / EXTENT[DELTA_KZ].height)

    def test_qz_radius_is_unchanged_in_qx_vs_qz(self):
        """Both views plot the same Qz range, so the same fraction gives the same radius."""
        fractions = radii_to_fractions(0.001, 0.002, EXTENT[DELTA_KZ])
        _, sigma_y = fractions_to_radii(*fractions, EXTENT[QX], coupled=False)
        assert sigma_y == pytest.approx(0.002)

    def test_an_empty_axis_range_leaves_the_radius_unscaled(self):
        empty = OffSpecRegion(0.1, -0.1, 0.5, -0.1)
        assert radii_to_fractions(0.001, 0.002, empty) == (0.001, 0.002)
        assert fractions_to_radii(0.001, 0.002, empty, coupled=False) == (0.001, 0.002)


class TestLookups:
    """Reading from the memory."""

    def test_no_radii_until_the_user_picks_one(self):
        memory = OffSpecSmoothingMemory()
        assert memory.fraction_x is None
        assert memory.fraction_y is None

    def test_radii_for_uses_the_default_until_radii_are_stored(self):
        memory = OffSpecSmoothingMemory()
        extent = OffSpecRegion(0.0, 0.04, 0.1, 0.3)
        assert memory.radii_for(extent, (0.025, 0.01), coupled=False) == pytest.approx((0.001, 0.002))

    def test_radii_for_couples_the_radii(self):
        memory = OffSpecSmoothingMemory(fraction_x=0.025, fraction_y=0.01)
        extent = OffSpecRegion(0.0, 0.04, 0.1, 0.3)
        assert memory.radii_for(extent, (0.0, 0.0), coupled=True) == pytest.approx((0.001, 0.001))

    def test_radii_for_clamps_to_the_spin_box_limits(self):
        memory = OffSpecSmoothingMemory(fraction_x=1e-12, fraction_y=500.0)
        assert memory.radii_for(EXTENT[DELTA_KZ], (0.0, 0.0), False, SIGMA_MIN, SIGMA_MAX) == (SIGMA_MIN, SIGMA_MAX)

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
    """Storing radii the user edited, as fractions of the plotted axis ranges."""

    def _store(self, memory, axis, shown, edited_x=True, edited_y=True, coupled=False, default=(0.002, 0.002)):
        memory.store_radii(EXTENT[axis], *shown, default, edited_x=edited_x, edited_y=edited_y, coupled=coupled)

    def _shown(self, memory, axis, coupled=False):
        return memory.radii_for(EXTENT[axis], (0.0, 0.0), coupled)

    def test_an_edit_is_stored_as_fractions(self):
        memory = OffSpecSmoothingMemory()
        self._store(memory, DELTA_KZ, (0.001, 0.002))
        assert (memory.fraction_x, memory.fraction_y) == pytest.approx(
            (0.001 / EXTENT[DELTA_KZ].width, 0.002 / EXTENT[DELTA_KZ].height)
        )

    def test_an_edit_is_shown_unchanged_when_coming_back(self):
        memory = OffSpecSmoothingMemory()
        self._store(memory, QX, (0.00001234, 0.000411))
        assert self._shown(memory, QX) == pytest.approx((0.00001234, 0.000411), rel=1e-12)

    def test_the_unedited_radius_is_not_read_back_from_the_spin_box(self):
        """The Qx radius is small, so its rounded display would shift the stored value."""
        memory = OffSpecSmoothingMemory(fraction_x=0.00224567, fraction_y=0.002)
        rounded_on_screen = round(0.00224567 * EXTENT[QX].width, 8)

        self._store(memory, QX, (rounded_on_screen, 0.0005), edited_x=False)

        assert memory.fraction_x == 0.00224567
        assert memory.fraction_y == pytest.approx(0.0005 / EXTENT[QX].height)

    def test_while_coupled_y_follows_x(self):
        memory = OffSpecSmoothingMemory()
        self._store(memory, KIZ_KFZ, (0.001, 0.005), edited_y=False, coupled=True)
        assert (memory.fraction_x, memory.fraction_y) == pytest.approx(
            (0.001 / EXTENT[KIZ_KFZ].width, 0.001 / EXTENT[KIZ_KFZ].height)
        )

    def test_the_default_is_used_for_an_unedited_radius(self):
        memory = OffSpecSmoothingMemory()
        self._store(memory, DELTA_KZ, (0.001, 0.999), edited_y=False, default=(0.004, 0.007))
        assert memory.fraction_y == 0.007

    def test_uneven_radii_from_kiz_vs_kfz_are_kept(self):
        """Bogdan's screenshots 5-7: these used to come back uniform."""
        memory = OffSpecSmoothingMemory()
        self._store(memory, KIZ_KFZ, (0.0001, 0.000291))
        assert self._shown(memory, KIZ_KFZ) == pytest.approx((0.0001, 0.000291), rel=1e-12)

    def test_a_qx_vertical_radius_does_not_change_the_uniform_views(self):
        """Bogdan's screenshot 10: a y typed in Qx vs Qz used to change the ki_z vs kf_z spot."""
        memory = OffSpecSmoothingMemory()
        self._store(memory, DELTA_KZ, (0.000794, 0.000794), coupled=True)
        before = self._shown(memory, KIZ_KFZ, coupled=True)

        self._store(memory, QX, (0.0, 0.000411), edited_x=False)

        assert self._shown(memory, KIZ_KFZ, coupled=True) == pytest.approx(before, rel=1e-12)
        assert self._shown(memory, DELTA_KZ, coupled=True) == pytest.approx((0.000794, 0.000794), rel=1e-12)

    def test_showing_other_systems_does_not_change_the_stored_fractions(self):
        memory = OffSpecSmoothingMemory(fraction_x=0.00123, fraction_y=0.00456)
        for axis in (QX, KIZ_KFZ, DELTA_KZ):
            for coupled in (True, False):
                self._shown(memory, axis, coupled)
        assert (memory.fraction_x, memory.fraction_y) == (0.00123, 0.00456)


class TestWorkingCopies:
    """Working copy that is only committed on OK."""

    def test_snapshot_is_independent(self):
        memory = OffSpecSmoothingMemory()
        memory.store_region(QX, REGION)
        snapshot = memory.snapshot()

        memory.store_region(KIZ_KFZ, REGION)
        memory.fraction_x = 9.9

        assert KIZ_KFZ not in snapshot.regions
        assert snapshot.fraction_x is None

    def test_copy_from_mutates_in_place(self):
        """The main window holds this instance, so it has to be updated in place."""
        memory = OffSpecSmoothingMemory()
        snapshot = memory.snapshot()
        memory.store_region(QX, REGION)
        memory.store_coupled(QX, True)
        memory.store_r_sigmas(5.0)
        memory.fraction_x = 9.9
        memory.fraction_y = 9.9
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
