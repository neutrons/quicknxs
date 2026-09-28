"""Tests for the off-specular smoothing session memory."""

import pytest

from quicknxs.enums import OffSpecXAxis
from quicknxs.models.offspec_smoothing_memory import (
    DEFAULT_MINIMUM_RADIUS,
    DEFAULT_SIGMA_FRACTION,
    OffSpecRegion,
    OffSpecSmoothingMemory,
    default_coupled,
    fraction_from_radius,
    radii_from_fractions,
)

# Spin box limits from ui_smooth_dialog.ui
SIGMA_MIN = 1e-6
SIGMA_MAX = 1.0

# Regions similar to run 42112. The x extents differ a lot between coordinate systems.
REGION_DELTA_KZ = OffSpecRegion(-0.1515, 0.1054, -0.0872, 0.1630)
REGION_QX = OffSpecRegion(-0.0041, 0.0000, -0.0872, 0.1630)
REGION_KIZ_KFZ = OffSpecRegion(0.0024, 0.0091, -0.0963, 0.1539)


class TestDefaultCoupled:
    """Default uniformity per coordinate system."""

    @pytest.mark.parametrize(
        "axis, expected",
        [
            (OffSpecXAxis.DELTA_KZ_VS_QZ, True),
            (OffSpecXAxis.QX_VS_QZ, False),
            (OffSpecXAxis.KZI_VS_KZF, True),
        ],
    )
    def test_matches_agreed_table(self, axis, expected):
        assert default_coupled(axis) is expected

    def test_accepts_plain_integers(self):
        """The axis is sometimes stored as an int."""
        assert default_coupled(int(OffSpecXAxis.QX_VS_QZ)) is False


class TestOffSpecRegion:
    """The region box."""

    def test_extents(self):
        region = OffSpecRegion(-0.01, 0.03, 0.1, 0.3)
        assert region.width == pytest.approx(0.04)
        assert region.height == pytest.approx(0.2)

    def test_is_hashable_and_comparable(self):
        """Regions are frozen so stored ones can't be changed."""
        assert OffSpecRegion(0.0, 1.0, 0.0, 1.0) == OffSpecRegion(0.0, 1.0, 0.0, 1.0)
        with pytest.raises(AttributeError):
            OffSpecRegion(0.0, 1.0, 0.0, 1.0).x_min = 5.0


class TestRadiiFromFractions:
    """Converting fractions to radii."""

    def test_scales_each_axis_by_its_own_extent(self):
        sigma_x, sigma_y = radii_from_fractions(0.01, 0.02, OffSpecRegion(0.0, 2.0, 0.0, 5.0))
        assert sigma_x == pytest.approx(0.02)
        assert sigma_y == pytest.approx(0.10)

    def test_clamps_to_minimum(self):
        radii = radii_from_fractions(1e-12, 1e-12, REGION_DELTA_KZ, SIGMA_MIN, SIGMA_MAX)
        assert radii == (SIGMA_MIN, SIGMA_MIN)

    def test_clamps_to_maximum(self):
        radii = radii_from_fractions(500.0, 500.0, REGION_DELTA_KZ, SIGMA_MIN, SIGMA_MAX)
        assert radii == (SIGMA_MAX, SIGMA_MAX)

    def test_maximum_is_optional(self):
        sigma_x, _ = radii_from_fractions(500.0, 500.0, REGION_DELTA_KZ, SIGMA_MIN)
        assert sigma_x > SIGMA_MAX


class TestDefaultRadius:
    """Radii shown before the user picks one."""

    def test_is_a_quarter_percent_of_a_wide_box(self):
        sigma_x, sigma_y = radii_from_fractions(None, None, REGION_DELTA_KZ, SIGMA_MIN, SIGMA_MAX)
        assert sigma_x == pytest.approx(DEFAULT_SIGMA_FRACTION * REGION_DELTA_KZ.width)
        assert sigma_y == pytest.approx(DEFAULT_SIGMA_FRACTION * REGION_DELTA_KZ.height)

    def test_never_drops_below_the_floor_in_a_narrow_box(self):
        """Without the floor the Qx default is too small to reach the data."""
        assert DEFAULT_SIGMA_FRACTION * REGION_QX.width < DEFAULT_MINIMUM_RADIUS
        sigma_x, _ = radii_from_fractions(None, None, REGION_QX, SIGMA_MIN, SIGMA_MAX)
        assert sigma_x == DEFAULT_MINIMUM_RADIUS

    def test_the_floor_never_overrides_a_radius_the_user_chose(self):
        chosen = 0.001
        sigma_x, _ = radii_from_fractions(chosen, None, REGION_QX, SIGMA_MIN, SIGMA_MAX)
        assert sigma_x == pytest.approx(chosen * REGION_QX.width)
        assert sigma_x < DEFAULT_MINIMUM_RADIUS

    def test_each_axis_defaults_independently(self):
        sigma_x, sigma_y = radii_from_fractions(0.01, None, REGION_QX, SIGMA_MIN, SIGMA_MAX)
        assert sigma_x == pytest.approx(0.01 * REGION_QX.width)
        assert sigma_y == pytest.approx(DEFAULT_SIGMA_FRACTION * REGION_QX.height)


class TestFractionFromRadius:
    """Converting a radius to a fraction."""

    def test_divides_by_the_extent(self):
        assert fraction_from_radius(0.02, 2.0, fallback=0.5) == pytest.approx(0.01)

    @pytest.mark.parametrize("extent", [0.0, -0.3])
    def test_keeps_the_fallback_for_a_degenerate_extent(self, extent):
        """A collapsed box says nothing about the fraction, so the old one is kept."""
        assert fraction_from_radius(0.02, extent, fallback=0.5) == 0.5


class TestLookups:
    """Reading from the memory."""

    def test_no_fraction_is_chosen_until_the_user_picks_a_radius(self):
        memory = OffSpecSmoothingMemory()
        assert memory.fraction_x is None
        assert memory.fraction_y is None

    def test_radii_for_applies_the_fractions_to_the_given_region(self):
        memory = OffSpecSmoothingMemory()
        sigma_x, sigma_y = memory.radii_for(REGION_DELTA_KZ, SIGMA_MIN, SIGMA_MAX)
        assert sigma_x == pytest.approx(DEFAULT_SIGMA_FRACTION * REGION_DELTA_KZ.width)
        assert sigma_y == pytest.approx(DEFAULT_SIGMA_FRACTION * REGION_DELTA_KZ.height)

    def test_region_for_falls_back_when_the_axis_was_never_visited(self):
        memory = OffSpecSmoothingMemory()
        assert memory.region_for(OffSpecXAxis.QX_VS_QZ, REGION_QX) == REGION_QX

    def test_region_for_returns_the_stored_region(self):
        memory = OffSpecSmoothingMemory()
        memory.store_region(OffSpecXAxis.QX_VS_QZ, REGION_QX)
        assert memory.region_for(OffSpecXAxis.QX_VS_QZ, REGION_DELTA_KZ) == REGION_QX

    def test_coupled_for_falls_back_to_the_default(self):
        assert OffSpecSmoothingMemory().coupled_for(OffSpecXAxis.QX_VS_QZ) is False

    def test_coupled_for_returns_the_stored_flag(self):
        memory = OffSpecSmoothingMemory()
        memory.store_coupled(OffSpecXAxis.QX_VS_QZ, True)
        assert memory.coupled_for(OffSpecXAxis.QX_VS_QZ) is True

    def test_r_sigmas_falls_back_until_stored(self):
        memory = OffSpecSmoothingMemory()
        assert memory.r_sigmas_for(3.0) == 3.0
        memory.store_r_sigmas(5.0)
        assert memory.r_sigmas_for(3.0) == 5.0

    def test_axis_keys_are_normalised_from_integers(self):
        memory = OffSpecSmoothingMemory()
        memory.store_region(int(OffSpecXAxis.KZI_VS_KZF), REGION_KIZ_KFZ)
        memory.store_coupled(int(OffSpecXAxis.KZI_VS_KZF), False)
        assert memory.region_for(OffSpecXAxis.KZI_VS_KZF, REGION_QX) == REGION_KIZ_KFZ
        assert memory.coupled_for(OffSpecXAxis.KZI_VS_KZF) is False


class TestSwitchingCoordinateSystem:
    """Radii follow the box when switching, without drifting."""

    def test_same_fraction_gives_a_different_radius_per_system(self):
        """Same fraction, different radius, so the spot keeps its apparent size."""
        memory = OffSpecSmoothingMemory(fraction_x=0.01)
        in_delta_kz, _ = memory.radii_for(REGION_DELTA_KZ, SIGMA_MIN, SIGMA_MAX)
        in_qx, _ = memory.radii_for(REGION_QX, SIGMA_MIN, SIGMA_MAX)
        assert in_delta_kz / REGION_DELTA_KZ.width == pytest.approx(in_qx / REGION_QX.width)
        assert in_delta_kz > in_qx

    def test_round_trip_without_an_edit_is_exact(self):
        """Just showing a coordinate system must not change the stored fractions."""
        memory = OffSpecSmoothingMemory()
        start = memory.radii_for(REGION_DELTA_KZ, SIGMA_MIN, SIGMA_MAX)

        memory.radii_for(REGION_QX, SIGMA_MIN, SIGMA_MAX)
        memory.radii_for(REGION_KIZ_KFZ, SIGMA_MIN, SIGMA_MAX)

        assert memory.radii_for(REGION_DELTA_KZ, SIGMA_MIN, SIGMA_MAX) == start


class TestStoreFractions:
    """Updating the fractions after a user edit."""

    def test_an_uncoupled_edit_updates_both_fractions(self):
        memory = OffSpecSmoothingMemory()
        memory.store_fractions(0.0002, 0.02, REGION_QX, coupled=False)
        assert memory.fraction_x == pytest.approx(0.0002 / REGION_QX.width)
        assert memory.fraction_y == pytest.approx(0.02 / REGION_QX.height)

    def test_a_coupled_edit_leaves_the_vertical_fraction_alone(self):
        """While coupled, y is just a copy of x, so the y fraction is kept."""
        memory = OffSpecSmoothingMemory()
        memory.store_fractions(0.0002, 0.02, REGION_QX, coupled=False)
        chosen_y = memory.fraction_y

        memory.store_fractions(0.01, 0.01, REGION_DELTA_KZ, coupled=True)

        assert memory.fraction_x == pytest.approx(0.01 / REGION_DELTA_KZ.width)
        assert memory.fraction_y == chosen_y

    def test_editing_only_the_vertical_radius_leaves_the_horizontal_fraction_alone(self):
        """The rounded x radius on screen must not be read back when only y was edited."""
        memory = OffSpecSmoothingMemory()
        rounded_on_screen = 0.000005  # true value 0.0000045 before the spin box rounded it

        memory.store_fractions(rounded_on_screen, 0.02, REGION_QX, coupled=False, update_x=False)

        assert memory.fraction_x is None
        assert memory.fraction_y == pytest.approx(0.02 / REGION_QX.height)

    def test_editing_only_the_horizontal_radius_leaves_the_vertical_fraction_alone(self):
        memory = OffSpecSmoothingMemory()

        memory.store_fractions(0.0002, 0.99, REGION_QX, coupled=False, update_y=False)

        assert memory.fraction_x == pytest.approx(0.0002 / REGION_QX.width)
        assert memory.fraction_y is None

    def test_moving_the_region_re_derives_the_fraction(self):
        """The radius stays the same and its fraction of the box changes."""
        memory = OffSpecSmoothingMemory()
        radius = 0.0002
        memory.store_fractions(radius, 0.02, OffSpecRegion(-0.004, 0.0, 0.0, 0.1), coupled=False)
        wide = memory.fraction_x

        memory.store_fractions(radius, 0.02, OffSpecRegion(-0.002, 0.0, 0.0, 0.1), coupled=False)

        assert memory.fraction_x == pytest.approx(2.0 * wide)

    def test_a_degenerate_region_keeps_the_previous_fractions(self):
        memory = OffSpecSmoothingMemory()
        memory.store_fractions(0.0002, 0.02, REGION_QX, coupled=False)
        before = (memory.fraction_x, memory.fraction_y)

        memory.store_fractions(0.0002, 0.02, OffSpecRegion(0.0, 0.0, 0.1, 0.1), coupled=False)

        assert (memory.fraction_x, memory.fraction_y) == before

    def test_an_edit_then_a_switch_rescales_the_radius(self):
        memory = OffSpecSmoothingMemory()
        memory.store_fractions(0.01, 0.01, REGION_DELTA_KZ, coupled=True)

        sigma_x, _ = memory.radii_for(REGION_QX, SIGMA_MIN, SIGMA_MAX)

        assert sigma_x == pytest.approx(0.01 * REGION_QX.width / REGION_DELTA_KZ.width)


class TestWorkingCopies:
    """Working copy that is only committed on OK."""

    def test_snapshot_is_independent(self):
        memory = OffSpecSmoothingMemory()
        memory.store_region(OffSpecXAxis.QX_VS_QZ, REGION_QX)
        snapshot = memory.snapshot()

        memory.store_region(OffSpecXAxis.KZI_VS_KZF, REGION_KIZ_KFZ)
        memory.fraction_x = 9.9

        assert OffSpecXAxis.KZI_VS_KZF not in snapshot.regions
        assert snapshot.fraction_x is None

    def test_copy_from_mutates_in_place(self):
        """The main window holds this instance, so it has to be updated in place."""
        memory = OffSpecSmoothingMemory()
        snapshot = memory.snapshot()

        memory.store_region(OffSpecXAxis.QX_VS_QZ, REGION_QX)
        memory.store_coupled(OffSpecXAxis.QX_VS_QZ, True)
        memory.store_r_sigmas(5.0)
        memory.fraction_x = 9.9
        identity = id(memory)

        memory.copy_from(snapshot)

        assert id(memory) == identity
        assert memory.regions == {}
        assert memory.coupled == {}
        assert memory.r_sigmas is None
        assert memory.fraction_x is None

    def test_copy_from_does_not_alias_the_source(self):
        memory = OffSpecSmoothingMemory()
        snapshot = memory.snapshot()
        memory.copy_from(snapshot)

        memory.store_region(OffSpecXAxis.QX_VS_QZ, REGION_QX)

        assert snapshot.regions == {}


if __name__ == "__main__":
    pytest.main([__file__])
