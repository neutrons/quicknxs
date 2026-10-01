"""Session memory for the off-specular smoothing dialog.

Nothing here is saved to disk. Regions and uniformity are stored per coordinate system.
The radii are stored once, in the (ki_z-kf_z) vs Qz system, and converted to the other
systems with the relations between the axes, so the smoothing spot covers the same part
of reciprocal space in every view:

- ki_z = (Qz + dk) / 2 and kf_z = (Qz - dk) / 2, where dk = ki_z - kf_z
- Qx = dk * tan(theta_i) near the specular ridge, and Qz is shared

All lengths are in 1/Angstrom.
"""

import math
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


def default_radii(region: OffSpecRegion, coupled: bool) -> tuple[float, float]:
    """Return the default (dk, Qz) radii for a (ki_z-kf_z) vs Qz region.

    When coupled, y equals x so the default matches what the uniform view shows.
    """
    sigma_x = max(DEFAULT_SIGMA_FRACTION * region.width, DEFAULT_MINIMUM_RADIUS)
    if coupled:
        return sigma_x, sigma_x
    return sigma_x, max(DEFAULT_SIGMA_FRACTION * region.height, DEFAULT_MINIMUM_RADIUS)


def _usable(tan_theta: float | None) -> bool:
    return tan_theta is not None and tan_theta > 0.0


def radii_to_axis(sigma_dk: float, sigma_qz: float, axis: OffSpecXAxis, tan_theta: float | None) -> tuple[float, float]:
    """Convert (dk, Qz) radii to the (x, y) radii of `axis`.

    Without a usable incident angle, Qx vs Qz falls back to the (dk, Qz) radii.
    """
    axis = OffSpecXAxis(axis)
    if axis == OffSpecXAxis.KZI_VS_KZF:
        sigma = math.hypot(sigma_dk, sigma_qz) / 2.0
        return sigma, sigma
    if axis == OffSpecXAxis.QX_VS_QZ and _usable(tan_theta):
        return sigma_dk * tan_theta, sigma_qz
    return sigma_dk, sigma_qz


def radii_from_axis(sigma_x: float, sigma_y: float, axis: OffSpecXAxis, tan_theta: float | None) -> tuple[float, float]:
    """Convert the (x, y) radii of `axis` to (dk, Qz) radii. Inverse of `radii_to_axis`.

    Going from ki_z vs kf_z, non-uniform radii come back uniform, since the kernel can't
    represent the correlation between dk and Qz.
    """
    axis = OffSpecXAxis(axis)
    if axis == OffSpecXAxis.KZI_VS_KZF:
        sigma = math.hypot(sigma_x, sigma_y)
        return sigma, sigma
    if axis == OffSpecXAxis.QX_VS_QZ and _usable(tan_theta):
        return sigma_x / tan_theta, sigma_y
    return sigma_x, sigma_y


@dataclass
class OffSpecSmoothingMemory:
    """Settings the smoothing dialog remembers for the rest of the session.

    Parameters
    ----------
    regions:
        Last region used in each coordinate system.
    coupled:
        Last uniformity setting used in each coordinate system.
    sigma_x, sigma_y:
        Radii in the (ki_z-kf_z) vs Qz system (dk and Qz). None until the user picks one.
    r_sigmas:
        Search range in units of sigma, or None until the user sets it.
    """

    regions: dict[OffSpecXAxis, OffSpecRegion] = field(default_factory=dict)
    coupled: dict[OffSpecXAxis, bool] = field(default_factory=dict)
    sigma_x: float | None = None
    sigma_y: float | None = None
    r_sigmas: float | None = None

    def region_for(self, axis: OffSpecXAxis | int, fallback: OffSpecRegion) -> OffSpecRegion:
        return self.regions.get(OffSpecXAxis(axis), fallback)

    def coupled_for(self, axis: OffSpecXAxis | int) -> bool:
        return self.coupled.get(OffSpecXAxis(axis), default_coupled(axis))

    def r_sigmas_for(self, fallback: float) -> float:
        return fallback if self.r_sigmas is None else self.r_sigmas

    def _radii_or(self, default: tuple[float, float]) -> tuple[float, float]:
        if self.sigma_x is None or self.sigma_y is None:
            return default
        return self.sigma_x, self.sigma_y

    def radii_for(
        self,
        axis: OffSpecXAxis | int,
        default: tuple[float, float],
        tan_theta: float | None,
        minimum: float = 0.0,
        maximum: float | None = None,
    ) -> tuple[float, float]:
        """Return the (x, y) radii to show for `axis`, clamped to the spin box limits.

        `default` is the (dk, Qz) pair used until the user picks radii. Coupling is left
        to the caller.
        """

        def _clamp(value: float) -> float:
            value = max(value, minimum)
            return value if maximum is None else min(value, maximum)

        sigma_x, sigma_y = radii_to_axis(*self._radii_or(default), axis, tan_theta)
        return _clamp(sigma_x), _clamp(sigma_y)

    def store_region(self, axis: OffSpecXAxis | int, region: OffSpecRegion) -> None:
        self.regions[OffSpecXAxis(axis)] = region

    def store_coupled(self, axis: OffSpecXAxis | int, coupled: bool) -> None:
        self.coupled[OffSpecXAxis(axis)] = bool(coupled)

    def store_r_sigmas(self, r_sigmas: float) -> None:
        self.r_sigmas = float(r_sigmas)

    def store_radii(
        self,
        axis: OffSpecXAxis | int,
        shown_x: float,
        shown_y: float,
        default: tuple[float, float],
        tan_theta: float | None,
        *,
        edited_x: bool,
        edited_y: bool,
        coupled: bool,
    ) -> None:
        """Store radii the user edited in `axis`, converted to (dk, Qz).

        Only call this after the user edits a radius. An unedited radius is taken from the
        stored value rather than the spin box, so its rounding isn't read back in. While
        coupled, y is a copy of x.
        """
        if coupled:
            shown_y = shown_x
            edited_y = edited_y or edited_x
        exact_x, exact_y = radii_to_axis(*self._radii_or(default), axis, tan_theta)
        sigma_x = shown_x if edited_x else exact_x
        sigma_y = shown_y if edited_y else exact_y
        self.sigma_x, self.sigma_y = radii_from_axis(sigma_x, sigma_y, axis, tan_theta)

    def snapshot(self) -> "OffSpecSmoothingMemory":
        """Return an independent copy."""
        return replace(self, regions=dict(self.regions), coupled=dict(self.coupled))

    def copy_from(self, other: "OffSpecSmoothingMemory") -> None:
        """Copy `other` into this object in place, so the main window keeps the same instance."""
        self.regions = dict(other.regions)
        self.coupled = dict(other.coupled)
        self.sigma_x = other.sigma_x
        self.sigma_y = other.sigma_y
        self.r_sigmas = other.r_sigmas
