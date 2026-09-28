"""Session memory for the off-specular smoothing dialog.

Nothing here is saved to disk. The radii are stored as fractions of the region box so
they keep the same apparent size when switching coordinate system. Regions and
uniformity are stored per coordinate system. All lengths are in 1/Angstrom.
"""

from dataclasses import dataclass, field, replace

from quicknxs.enums import OffSpecXAxis

# Default radius as a fraction of the region box
DEFAULT_SIGMA_FRACTION = 0.0025

# Smallest default radius, kept from the old defaults. Without it the narrow Qx and ki_z
# axes get radii too small to reach the data and the smoothed map has empty nodes.
# Typed radii are not clamped.
DEFAULT_MINIMUM_RADIUS = 1e-4

_DEFAULT_COUPLED: dict[OffSpecXAxis, bool] = {
    OffSpecXAxis.DELTA_KZ_VS_QZ: True,
    OffSpecXAxis.QX_VS_QZ: False,
    OffSpecXAxis.KZI_VS_KZF: True,
}


def default_coupled(axis: OffSpecXAxis | int) -> bool:
    """Return whether the radii are uniform by default for this coordinate system."""
    return _DEFAULT_COUPLED.get(OffSpecXAxis(axis), True)


@dataclass(frozen=True)
class OffSpecRegion:
    """Region box (the blue box) in the coordinate system it was picked in."""

    x_min: float
    x_max: float
    y_min: float
    y_max: float

    @property
    def width(self) -> float:
        return self.x_max - self.x_min

    @property
    def height(self) -> float:
        return self.y_max - self.y_min


def radii_from_fractions(
    fraction_x: float | None,
    fraction_y: float | None,
    region: OffSpecRegion,
    minimum: float = 0.0,
    maximum: float | None = None,
) -> tuple[float, float]:
    """Return the (x, y) radii for a region.

    A fraction of None means the user hasn't picked one, so the default is used.
    `minimum` and `maximum` are the spin box limits.
    """

    def _radius(fraction: float | None, extent: float) -> float:
        if fraction is None:
            value = max(DEFAULT_SIGMA_FRACTION * extent, DEFAULT_MINIMUM_RADIUS)
        else:
            value = fraction * extent
        value = max(value, minimum)
        return value if maximum is None else min(value, maximum)

    return _radius(fraction_x, region.width), _radius(fraction_y, region.height)


def fraction_from_radius(radius: float, extent: float, fallback: float | None) -> float | None:
    """Return the radius as a fraction of the extent, or `fallback` if the extent is not positive."""
    if extent <= 0.0:
        return fallback
    return radius / extent


@dataclass
class OffSpecSmoothingMemory:
    """Settings the smoothing dialog remembers for the rest of the session.

    Parameters
    ----------
    regions:
        Last region used in each coordinate system.
    coupled:
        Last uniformity setting used in each coordinate system.
    fraction_x, fraction_y:
        Radii as fractions of the region width and height, shared by all coordinate
        systems. None until the user picks a radius.
    r_sigmas:
        Search range in units of sigma, or None until the user sets it.
    """

    regions: dict[OffSpecXAxis, OffSpecRegion] = field(default_factory=dict)
    coupled: dict[OffSpecXAxis, bool] = field(default_factory=dict)
    fraction_x: float | None = None
    fraction_y: float | None = None
    r_sigmas: float | None = None

    def region_for(self, axis: OffSpecXAxis | int, fallback: OffSpecRegion) -> OffSpecRegion:
        return self.regions.get(OffSpecXAxis(axis), fallback)

    def coupled_for(self, axis: OffSpecXAxis | int) -> bool:
        return self.coupled.get(OffSpecXAxis(axis), default_coupled(axis))

    def radii_for(
        self,
        region: OffSpecRegion,
        minimum: float = 0.0,
        maximum: float | None = None,
    ) -> tuple[float, float]:
        """Return the (x, y) radii for a region. Coupling is left to the caller."""
        return radii_from_fractions(self.fraction_x, self.fraction_y, region, minimum, maximum)

    def r_sigmas_for(self, fallback: float) -> float:
        return fallback if self.r_sigmas is None else self.r_sigmas

    def store_region(self, axis: OffSpecXAxis | int, region: OffSpecRegion) -> None:
        self.regions[OffSpecXAxis(axis)] = region

    def store_coupled(self, axis: OffSpecXAxis | int, coupled: bool) -> None:
        self.coupled[OffSpecXAxis(axis)] = bool(coupled)

    def store_r_sigmas(self, r_sigmas: float) -> None:
        self.r_sigmas = float(r_sigmas)

    def store_fractions(
        self,
        radius_x: float,
        radius_y: float,
        region: OffSpecRegion,
        coupled: bool,
        *,
        update_x: bool = True,
        update_y: bool = True,
    ) -> None:
        """Update the fractions from the radii shown against `region`.

        Only call this after the user edits a radius or the region. Calling it when just
        showing a coordinate system would feed spin box rounding back into the fractions.
        Use `update_x` / `update_y` to update only the radius that was edited.

        The y fraction is not updated while coupled, since y is then just a copy of x.
        """
        if update_x:
            self.fraction_x = fraction_from_radius(radius_x, region.width, self.fraction_x)
        if update_y and not coupled:
            self.fraction_y = fraction_from_radius(radius_y, region.height, self.fraction_y)

    def snapshot(self) -> "OffSpecSmoothingMemory":
        """Return an independent copy."""
        return replace(self, regions=dict(self.regions), coupled=dict(self.coupled))

    def copy_from(self, other: "OffSpecSmoothingMemory") -> None:
        """Copy `other` into this object in place, so the main window keeps the same instance."""
        self.regions = dict(other.regions)
        self.coupled = dict(other.coupled)
        self.fraction_x = other.fraction_x
        self.fraction_y = other.fraction_y
        self.r_sigmas = other.r_sigmas
