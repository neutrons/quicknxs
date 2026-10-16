"""Session memory for the off-specular smoothing dialog.

Nothing here is saved to disk. Regions and uniformity are stored per coordinate system.
The radii are stored once, as fractions of the plot's axis ranges, so the smoothing spot
takes up the same part of the plot in every view:

- x radius = fraction_x * width of the plotted x range
- y radius = fraction_y * height of the plotted y range

A uniform view has one radius for both axes, which comes from fraction_x.

All lengths are in 1/Angstrom.
"""

from dataclasses import dataclass, field, replace

from quicknxs.enums import OffSpecXAxis

# Default radius as a fraction of the region box
DEFAULT_SIGMA_FRACTION = 0.0025

# Smallest default radius, kept from the old defaults. Typed radii are not clamped.
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
    """Rectangle in one coordinate system: the blue box, or the plotted axis ranges."""

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


def default_radii(region: OffSpecRegion, coupled: bool) -> tuple[float, float]:
    """Return the default (x, y) radii for a (ki_z-kf_z) vs Qz region.

    When coupled, y equals x so the default matches what the uniform view shows.
    """
    sigma_x = max(DEFAULT_SIGMA_FRACTION * region.width, DEFAULT_MINIMUM_RADIUS)
    if coupled:
        return sigma_x, sigma_x
    return sigma_x, max(DEFAULT_SIGMA_FRACTION * region.height, DEFAULT_MINIMUM_RADIUS)


def _to_fraction(radius: float, length: float) -> float:
    # Without a usable axis range the radius is kept as is
    return radius / length if length > 0.0 else radius


def _to_radius(fraction: float, length: float) -> float:
    return fraction * length if length > 0.0 else fraction


def radii_to_fractions(sigma_x: float, sigma_y: float, extent: OffSpecRegion) -> tuple[float, float]:
    """Convert (x, y) radii to fractions of the plotted axis ranges `extent`."""
    return _to_fraction(sigma_x, extent.width), _to_fraction(sigma_y, extent.height)


def fractions_to_radii(
    fraction_x: float, fraction_y: float, extent: OffSpecRegion, coupled: bool
) -> tuple[float, float]:
    """Convert fractions of the plotted axis ranges `extent` to (x, y) radii.

    When coupled, both radii come from `fraction_x`.
    """
    sigma_x = _to_radius(fraction_x, extent.width)
    if coupled:
        return sigma_x, sigma_x
    return sigma_x, _to_radius(fraction_y, extent.height)


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
        Radii as fractions of the plotted x and y ranges. None until the user picks one.
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

    def r_sigmas_for(self, fallback: float) -> float:
        return fallback if self.r_sigmas is None else self.r_sigmas

    def _fractions_or(self, default: tuple[float, float]) -> tuple[float, float]:
        if self.fraction_x is None or self.fraction_y is None:
            return default
        return self.fraction_x, self.fraction_y

    def radii_for(
        self,
        extent: OffSpecRegion,
        default: tuple[float, float],
        coupled: bool,
        minimum: float = 0.0,
        maximum: float | None = None,
    ) -> tuple[float, float]:
        """Return the (x, y) radii to show for a plot with axis ranges `extent`.

        `default` is the pair of fractions used until the user picks radii. The radii are
        clamped to the spin box limits.
        """

        def _clamp(value: float) -> float:
            value = max(value, minimum)
            return value if maximum is None else min(value, maximum)

        sigma_x, sigma_y = fractions_to_radii(*self._fractions_or(default), extent, coupled)
        return _clamp(sigma_x), _clamp(sigma_y)

    def store_region(self, axis: OffSpecXAxis | int, region: OffSpecRegion) -> None:
        self.regions[OffSpecXAxis(axis)] = region

    def store_coupled(self, axis: OffSpecXAxis | int, coupled: bool) -> None:
        self.coupled[OffSpecXAxis(axis)] = bool(coupled)

    def store_r_sigmas(self, r_sigmas: float) -> None:
        self.r_sigmas = float(r_sigmas)

    def store_radii(
        self,
        extent: OffSpecRegion,
        shown_x: float,
        shown_y: float,
        default: tuple[float, float],
        *,
        edited_x: bool,
        edited_y: bool,
        coupled: bool,
    ) -> None:
        """Store radii the user edited on a plot with axis ranges `extent`, as fractions.

        Only call this after the user edits a radius. An unedited radius keeps its stored
        fraction rather than being read back from the spin box, so its rounding isn't
        stored. While coupled, y is a copy of x.
        """
        if coupled:
            shown_y = shown_x
            edited_y = edited_y or edited_x
        fraction_x, fraction_y = self._fractions_or(default)
        shown_fraction_x, shown_fraction_y = radii_to_fractions(shown_x, shown_y, extent)
        self.fraction_x = shown_fraction_x if edited_x else fraction_x
        self.fraction_y = shown_fraction_y if edited_y else fraction_y

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
