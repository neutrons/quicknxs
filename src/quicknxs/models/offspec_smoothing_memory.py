"""Session scoped memory for the off specular smoothing dialog.

The smoothing dialog lets the user pick a region of reciprocal space (the "blue box")
and a pair of smoothing radii, in one of the coordinate systems of :class:`OffSpecXAxis`.
This module holds what the dialog remembers between visits within one application run.
Nothing here is written to disk: closing the application discards it.

The radii are remembered as *fractions* of the region extent rather than as absolute
values. Switching coordinate system therefore re-derives the radii from the new region,
so the smoothing spot keeps the same apparent size on the plot. The region and the
uniformity flag are physical choices tied to the system they were made in, so those are
remembered per coordinate system instead.

Until the user chooses a radius, each view shows its own default: a fixed fraction of
its box, but never less than a floor. The floor matters in the two diagnostic views,
where the horizontal axis is narrow enough that the fraction alone gives a radius too
small to reach the data points, and the smoothed map comes out full of empty nodes.

All lengths are in inverse Angstrom. Fractions are dimensionless.
"""

from dataclasses import dataclass, field, replace

from quicknxs.enums import OffSpecXAxis

DEFAULT_SIGMA_FRACTION = 0.0025
"""Smoothing radius as a fraction of the region extent, before the user changes anything."""

DEFAULT_MINIMUM_RADIUS = 1e-4
"""Smallest default smoothing radius, in inverse Angstrom.

Applies to defaults only; a radius the user types is used as is. Kept from the previous
default rule, which clamped at the same value. Without it, run 42112 smoothed on the
default grid leaves about 36% (Qx vs Qz) and 30% (ki_z vs kf_z) of the nodes that the
previous defaults filled empty. With it, under 1%.
"""

_DEFAULT_COUPLED: dict[OffSpecXAxis, bool] = {
    OffSpecXAxis.DELTA_KZ_VS_QZ: True,
    OffSpecXAxis.QX_VS_QZ: False,
    OffSpecXAxis.KZI_VS_KZF: True,
}


def default_coupled(axis: OffSpecXAxis | int) -> bool:
    """Return whether the radii are uniform by default in the given coordinate system.

    Parameters
    ----------
    axis:
        Coordinate system, as an :class:`OffSpecXAxis` member or its integer value.

    Returns
    -------
    bool
        True when the Y radius mirrors the X radius by default.
    """
    return _DEFAULT_COUPLED.get(OffSpecXAxis(axis), True)


@dataclass(frozen=True)
class OffSpecRegion:
    """The rectangular region of reciprocal space shown as the blue box on the plot.

    The bounds belong to whichever coordinate system was active when they were chosen,
    so a region is only meaningful alongside its :class:`OffSpecXAxis`.
    """

    x_min: float
    x_max: float
    y_min: float
    y_max: float

    @property
    def width(self) -> float:
        """Extent along the horizontal axis, in inverse Angstrom."""
        return self.x_max - self.x_min

    @property
    def height(self) -> float:
        """Extent along the vertical axis, in inverse Angstrom."""
        return self.y_max - self.y_min


def radii_from_fractions(
    fraction_x: float | None,
    fraction_y: float | None,
    region: OffSpecRegion,
    minimum: float = 0.0,
    maximum: float | None = None,
) -> tuple[float, float]:
    """Scale the remembered fractions into radii for a region.

    Parameters
    ----------
    fraction_x:
        Horizontal radius as a fraction of the region width, or None while the user has
        not chosen one, in which case the default applies: `DEFAULT_SIGMA_FRACTION` of
        the width, but at least `DEFAULT_MINIMUM_RADIUS`.
    fraction_y:
        Vertical radius as a fraction of the region height; see `fraction_x`.
    region:
        Region to scale against, in the coordinate system being shown.
    minimum:
        Lower clamp, normally the smallest value the radius spin box accepts.
    maximum:
        Upper clamp, normally the largest value the radius spin box accepts.
        Clamping here keeps the remembered value and the displayed value in step,
        rather than letting the widget silently truncate it.

    Returns
    -------
    tuple[float, float]
        The horizontal and vertical radii, in inverse Angstrom.
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
    """Express a radius as a fraction of an extent.

    A region can be collapsed to zero width or height while the user is editing its
    bounds, which carries no information about the fraction they want. In that case the
    previous fraction is kept rather than raising or storing an infinity.

    Parameters
    ----------
    radius:
        Smoothing radius along one axis, in inverse Angstrom.
    extent:
        Region extent along the same axis, in inverse Angstrom.
    fallback:
        Fraction to keep when `extent` is not positive. May be None, meaning the default.

    Returns
    -------
    float | None
        The radius as a fraction of the extent, or `fallback`.
    """
    if extent <= 0.0:
        return fallback
    return radius / extent


@dataclass
class OffSpecSmoothingMemory:
    """What the smoothing dialog carries between visits within one application run.

    Parameters
    ----------
    regions:
        Region last used in each coordinate system. A system absent from the mapping has
        not been visited yet and falls back to the region derived from the data extents.
    coupled:
        Uniformity flag last used in each coordinate system. A system absent from the
        mapping falls back to :func:`default_coupled`.
    fraction_x:
        Horizontal radius as a fraction of the region width. Shared across coordinate
        systems: this is what makes the spot keep its apparent size when switching.
        None until the user chooses a radius, which gives every view its own default.
    fraction_y:
        Vertical radius as a fraction of the region height, or None as for `fraction_x`.
        Only meaningful while the radii are not coupled, since coupling drives the Y
        radius from the X radius.
    r_sigmas:
        Search range in units of sigma, or None while the user has not set one.
    """

    regions: dict[OffSpecXAxis, OffSpecRegion] = field(default_factory=dict)
    coupled: dict[OffSpecXAxis, bool] = field(default_factory=dict)
    fraction_x: float | None = None
    fraction_y: float | None = None
    r_sigmas: float | None = None

    ### Lookups

    def region_for(self, axis: OffSpecXAxis | int, fallback: OffSpecRegion) -> OffSpecRegion:
        """Return the remembered region for `axis`, or `fallback` if there is none."""
        return self.regions.get(OffSpecXAxis(axis), fallback)

    def coupled_for(self, axis: OffSpecXAxis | int) -> bool:
        """Return the remembered uniformity flag for `axis`, or its default."""
        return self.coupled.get(OffSpecXAxis(axis), default_coupled(axis))

    def radii_for(
        self,
        region: OffSpecRegion,
        minimum: float = 0.0,
        maximum: float | None = None,
    ) -> tuple[float, float]:
        """Return the radii to show for a region, derived from the remembered fractions.

        The caller is expected to apply coupling afterwards, which overwrites the Y
        radius with the X radius when the active system is uniform.
        """
        return radii_from_fractions(self.fraction_x, self.fraction_y, region, minimum, maximum)

    def r_sigmas_for(self, fallback: float) -> float:
        """Return the remembered sigma search range, or `fallback` if there is none."""
        return fallback if self.r_sigmas is None else self.r_sigmas

    ### Updates

    def store_region(self, axis: OffSpecXAxis | int, region: OffSpecRegion) -> None:
        """Remember `region` as the region for `axis`."""
        self.regions[OffSpecXAxis(axis)] = region

    def store_coupled(self, axis: OffSpecXAxis | int, coupled: bool) -> None:
        """Remember `coupled` as the uniformity flag for `axis`."""
        self.coupled[OffSpecXAxis(axis)] = bool(coupled)

    def store_r_sigmas(self, r_sigmas: float) -> None:
        """Remember the sigma search range."""
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
        """Re-derive the remembered fractions from radii shown against `region`.

        Called when the user edits a radius or moves the region, which are the only two
        actions that change what fraction of the box the smoothing spot covers. Showing a
        coordinate system must not call this, otherwise the rounding of the spin box
        would be fed back into the fractions and the values would drift on every switch.

        When the radii are coupled the Y radius is a mirror of the X radius rather than a
        choice the user made, so the vertical fraction is left as it was. That keeps a
        vertical fraction chosen in a non uniform system from being overwritten by a
        detour through a uniform one.

        Parameters
        ----------
        radius_x:
            Horizontal radius currently shown, in inverse Angstrom.
        radius_y:
            Vertical radius currently shown, in inverse Angstrom.
        region:
            Region the radii are shown against, in the active coordinate system.
        coupled:
            Whether the radii are currently uniform.
        update_x:
            Whether to re-derive the horizontal fraction. Pass False when the user only
            edited the vertical radius, so the horizontal one is not re-read from the
            spin box and nudged by its rounding.
        update_y:
            Whether to re-derive the vertical fraction; see `update_x`.
        """
        if update_x:
            self.fraction_x = fraction_from_radius(radius_x, region.width, self.fraction_x)
        if update_y and not coupled:
            self.fraction_y = fraction_from_radius(radius_y, region.height, self.fraction_y)

    ### Working copies, so the dialog only commits what the user confirmed with OK

    def snapshot(self) -> "OffSpecSmoothingMemory":
        """Return an independent copy of this memory."""
        return replace(self, regions=dict(self.regions), coupled=dict(self.coupled))

    def copy_from(self, other: "OffSpecSmoothingMemory") -> None:
        """Overwrite this memory in place with the contents of `other`.

        Mutates rather than replaces so that holders of this object, such as the main
        window, keep seeing the same instance.
        """
        self.regions = dict(other.regions)
        self.coupled = dict(other.coupled)
        self.fraction_x = other.fraction_x
        self.fraction_y = other.fraction_y
        self.r_sigmas = other.r_sigmas
