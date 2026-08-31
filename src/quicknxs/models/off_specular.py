"""Class to execute and hold the off-specular reflectivity calculation."""

import logging
from typing import TYPE_CHECKING

import numpy as np
import scipy.spatial
import scipy.stats

from quicknxs.enums import OffSpecXAxis
from quicknxs.models.configuration import get_direct_beam_low_res_roi

if TYPE_CHECKING:
    from quicknxs.models.data_set import CrossSectionData, NexusData

H_OVER_M_NEUTRON = 3.956034e-7  # h/m_n [m^2/s]


class OffSpecular:
    """Compute off-specular reflectivity."""

    d_wavelength = 0
    Qx = None
    Qz = None
    ki_z = None
    kf_z = None
    S = None
    dS = None

    def __init__(self, cross_section_data: "CrossSectionData"):
        """Initialize the OffSpecular class with processed cross-section data."""
        self.data_set = cross_section_data

    def __call__(self, direct_beam: "CrossSectionData | None" = None):
        """Extract off-specular scattering from 4D dataset (x,y,ToF,I).

        Uses a window in y to filter the 4D data,
        then sums all I values for each ToF and x channel.
        Qz, Qx, kiz, kfz are calculated using the x and ToF positions
        together with the tth-bank and direct pixel values.

        Parameters
        ----------
        direct_beam:
            If given, this data will be used to normalize the output
        """
        # TODO: correct for detector sensitivity
        x_pos = self.data_set.configuration.peak_position
        if self.data_set.proton_charge > 0:
            scale = 1.0 / self.data_set.proton_charge
        else:
            logging.warning(
                f"Proton charge is zero - not calculating off-specular reflectivity for {self.data_set.run_number} {self.data_set.entry_name}."
            )
            return

        # Range in low-res direction
        y_min, y_max = self.data_set.configuration.low_res_roi

        rad_per_pixel = self.data_set.det_size_x / self.data_set.dist_sam_det / self.data_set.xydata.shape[1]

        xtth = (
            self.data_set.direct_pixel
            - np.arange(self.data_set.data.shape[0])[self.data_set.active_area_x[0] : self.data_set.active_area_x[1]]
        )
        pix_offset_spec = self.data_set.direct_pixel - x_pos
        delta_dangle = self.data_set.dangle - self.data_set.angle_offset
        tth_spec = delta_dangle * np.pi / 180.0 + pix_offset_spec * rad_per_pixel
        af = delta_dangle * np.pi / 180.0 + xtth * rad_per_pixel - tth_spec / 2.0
        ai = np.ones_like(af) * tth_spec / 2.0

        # Background
        bck = self.data_set.get_background_vs_TOF() * scale

        v_edges = self.data_set.dist_mod_det / self.data_set.tof_edges * 1e6  # m/s
        lambda_edges = H_OVER_M_NEUTRON / v_edges * 1e10  # A

        wl = (lambda_edges[:-1] + lambda_edges[1:]) / 2.0
        # The resolution for lambda is digital range with equal probability
        # therefore it is the bin size divided by sqrt(12)
        self.d_wavelength = np.abs(lambda_edges[:-1] - lambda_edges[1:]) / np.sqrt(12)
        k = 2.0 * np.pi / wl

        # calculate reciprocal space, incident and outgoing perpendicular wave vectors
        self.Qz = k[np.newaxis, :] * (np.sin(af) + np.sin(ai))[:, np.newaxis]
        self.Qx = k[np.newaxis, :] * (np.cos(af) - np.cos(ai))[:, np.newaxis]
        self.ki_z = k[np.newaxis, :] * np.sin(ai)[:, np.newaxis]
        self.kf_z = k[np.newaxis, :] * np.sin(af)[:, np.newaxis]

        # calculate ROI intensities and normalize by number of points
        raw_multi_dim = self.data_set.data[
            self.data_set.active_area_x[0] : self.data_set.active_area_x[1], y_min:y_max, :
        ]
        raw = raw_multi_dim.sum(axis=1)
        d_raw = np.sqrt(raw)

        # normalize data by width in y and multiply scaling factor
        intensity = raw / float(y_max - y_min) * scale
        d_intensity = d_raw / (y_max - y_min) * scale

        # to subtract or not to subtract, that is the question
        if self.data_set.configuration.subtract_background:
            self.S = intensity - bck[np.newaxis, :]
        else:
            self.S = intensity

        self.dS = np.sqrt(d_intensity**2 + (bck**2)[np.newaxis, :])
        self.S *= self.data_set.configuration.scaling_factor
        self.dS *= self.data_set.configuration.scaling_factor

        if direct_beam is not None:
            if not direct_beam.configuration.tof_bins == self.data_set.configuration.tof_bins:
                logging.error("Trying to normalize with a direct beam data set with different binning")

            norm_y_min, norm_y_max = get_direct_beam_low_res_roi(self.data_set.configuration, direct_beam.configuration)
            norm_x_min, norm_x_max = direct_beam.configuration.peak_roi
            norm_raw_multi_dim = direct_beam.data[norm_x_min:norm_x_max, norm_y_min:norm_y_max, :]

            norm_raw = norm_raw_multi_dim.sum(axis=0).sum(axis=0)
            norm_d_raw = np.sqrt(norm_raw)
            norm_scale = (float(norm_x_max) - float(norm_x_min)) * (float(norm_y_max) - float(norm_y_min))
            norm_raw /= norm_scale * direct_beam.proton_charge
            norm_d_raw /= norm_scale * direct_beam.proton_charge

            idxs = norm_raw > 0.0
            self.dS[:, idxs] = np.sqrt(
                (self.dS[:, idxs] / norm_raw[idxs][np.newaxis, :]) ** 2
                + (self.S[:, idxs] / norm_raw[idxs][np.newaxis, :] ** 2 * norm_d_raw[idxs][np.newaxis, :]) ** 2
            )
            self.S[:, idxs] /= norm_raw[idxs][np.newaxis, :]
            self.S[:, np.logical_not(idxs)] = 0.0
            self.dS[:, np.logical_not(idxs)] = 0.0


def merge(reduction_list: list["NexusData"], pol_state: str) -> tuple[np.ndarray, ...]:
    """Merge the off-specular data from a reduction list.

    The scaling factors should have been determined at this point. Just use them
    to merge the different runs in a set.

    TODO: This doesn't deal with the overlap properly.
    It assumes that the user cut the overlapping points by hand.
    """
    _qx = np.empty(0)
    _qz = np.empty(0)
    _ki_z = np.empty(0)
    _kf_z = np.empty(0)
    _s = np.empty(0)
    _ds = np.empty(0)

    for item in reduction_list:
        offspec = item.cross_sections[pol_state].off_spec
        Qx, Qz, ki_z, kf_z, S, dS = (offspec.Qx, offspec.Qz, offspec.ki_z, offspec.kf_z, offspec.S, offspec.dS)

        try:
            n_total = len(S[0])
            p_0 = item.cross_sections[pol_state].configuration.cut_first_n_points
            p_n = n_total - item.cross_sections[pol_state].configuration.cut_last_n_points

            # NOTE: need to unravel the arrays from [TOF][pixel] to [q_points]
            Qx = np.ravel(Qx[:, p_0:p_n])
            Qz = np.ravel(Qz[:, p_0:p_n])
            ki_z = np.ravel(ki_z[:, p_0:p_n])
            kf_z = np.ravel(kf_z[:, p_0:p_n])
            S = np.ravel(S[:, p_0:p_n])
            dS = np.ravel(dS[:, p_0:p_n])

            _qx = np.concatenate((_qx, Qx))
            _qz = np.concatenate((_qz, Qz))
            _ki_z = np.concatenate((_ki_z, ki_z))
            _kf_z = np.concatenate((_kf_z, kf_z))
            _s = np.concatenate((_s, S))
            _ds = np.concatenate((_ds, dS))
        except TypeError:
            logging.warning(
                f"Off-specular data for {pol_state} in run {item.run_number} is not available, skipping this run."
            )

    return _qx, _qz, _ki_z, _kf_z, _ki_z - _kf_z, _s, _ds


def closest_bin(q: float, bin_edges: list) -> int | None:
    """Find index of closest bin to a q-value."""
    for i in range(len(bin_edges)):
        if q > bin_edges[i] and q <= bin_edges[i + 1]:
            return i
    return None


def rebin_extract(
    reduction_list,
    pol_state,
    axes=None,
    use_weights: bool = True,
    n_bins_x: int = 350,
    n_bins_y: int = 350,
    x_min: float = -0.015,
    x_max: float = 0.015,
    y_min: float = 0,
    y_max: float = 0.1,
):
    """Rebin off-specular data and extract cut at given Qz values.

    TODO: the analysis computers with RHEL7 have Scipy 0.12 installed,
    which makes this code uglier. Refactor once we get a more recent version.
    """
    Qx, Qz, ki_z, kf_z, delta_k, S, dS = merge(reduction_list, pol_state)

    # Specify how many bins we want in each direction.
    _bins = [n_bins_x, n_bins_y]

    # Specify the axes
    if axes is None:
        axes = reduction_list[0].cross_sections[pol_state].configuration.off_spec_x_axis
    x_label = "ki_z-kf_z"
    y_label = "Qz"
    x_values = delta_k
    y_values = Qz
    if axes == OffSpecXAxis.QX_VS_QZ:
        x_label = "Qx"
        x_values = Qx
    elif axes == OffSpecXAxis.KZI_VS_KZF:
        x_label = "ki_z"
        y_label = "kf_z"
        x_values = ki_z
        y_values = kf_z

    # Find the indices of S[TOF][main_axis_pixel] where we have non-zero data.
    if use_weights:
        # Compute the weighted average
        # - Weighted sum
        _r = S / dS**2
        statistic, x_edge, y_edge, _ = scipy.stats.binned_statistic_2d(
            x_values, y_values, _r, statistic="sum", range=[[x_min, x_max], [y_min, y_max]], bins=_bins
        )
        # - Sum of weights
        _w = 1 / dS**2
        w_statistic, _, _, _ = scipy.stats.binned_statistic_2d(
            x_values, y_values, _w, statistic="sum", range=[[x_min, x_max], [y_min, y_max]], bins=[x_edge, y_edge]
        )

        result = statistic / w_statistic
        result = result.T
        error = np.sqrt(1.0 / w_statistic).T
        result = np.nan_to_num(result)
        error = np.nan_to_num(error)
    else:
        # Compute the simple average, with errors
        statistic, x_edge, y_edge, _ = scipy.stats.binned_statistic_2d(
            x_values, y_values, S, statistic="mean", range=[[x_min, x_max], [y_min, y_max]], bins=_bins
        )
        # Compute the errors
        _w = dS**2
        w_statistic, _, _, _ = scipy.stats.binned_statistic_2d(
            x_values, y_values, _w, statistic="sum", range=[[x_min, x_max], [y_min, y_max]], bins=[x_edge, y_edge]
        )

        _c = np.ones(len(x_values))
        counts, _, _, _ = scipy.stats.binned_statistic_2d(
            x_values, y_values, _c, statistic="sum", range=[[x_min, x_max], [y_min, y_max]], bins=[x_edge, y_edge]
        )

        result = statistic.T
        error = (np.sqrt(w_statistic) / counts).T
        result = np.nan_to_num(result)
        error = np.nan_to_num(error)

    x_middle = x_edge[:-1] + (x_edge[1] - x_edge[0]) / 2.0
    y_middle = y_edge[:-1] + (y_edge[1] - y_edge[0]) / 2.0

    return result, error, x_middle, y_middle, [x_label, y_label]


def get_slice(qz, data, error, q_min, q_max):
    """Get a slice for a Qz band.

    Parameters
    ----------
    qz:
        Qz array
    data:
        2d data array
    error:
        Uncertainty on the data array
    q_min:
        Lower Qz bound
    q_max:
        Upper Qz bound
    """
    i_min = len(qz[qz < q_min])
    i_max = len(qz[qz < q_max])
    _data = np.sum(data[i_min : i_max + 1], axis=0) / (i_max - i_min + 1)
    if error is not None:
        _err = np.sum(error[i_min : i_max + 1] ** 2, axis=0)
        _err = np.sqrt(_err) / (i_max - i_min + 1)
    else:
        _err = np.zeros_like(_data)
    return _data, _err


def _kernel_average(
    x: np.ndarray,
    y: np.ndarray,
    I: np.ndarray,
    eval_x: np.ndarray,
    eval_y: np.ndarray,
    sigmas: float,
    sigmax: float,
    sigmay: float,
    axis_sigma_scaling: int | None,
    xysigma0: float,
) -> np.ndarray:
    """Truncated-Gaussian weighted average of scattered intensities at arbitrary points.

    Each evaluated intensity is the average of all input intensities within
    `sigmas` normalized distance of the evaluation point, weighted by the
    Gaussian of the distance. Evaluation points with no input point in range
    (or with a non-positive sigma-scaling coordinate) get intensity 0.

    A KD-tree on sigma-scaled coordinates, where the anisotropic Gaussian is
    isotropic with unit width, makes the neighbor search fast; the position-
    dependent sigma scaling becomes a per-point search radius.

    Parameters
    ----------
    x:
        x-values of the input data (any shape); same units as `sigmax`
    y:
        y-values of the input data (same shape as x); same units as `sigmay`
    I:
        Intensity values of the input data (same shape as x)
    eval_x:
        x-values of the evaluation points (any shape)
    eval_y:
        y-values of the evaluation points (same shape as eval_x)
    sigmas:
        Range in units of sigma to search around each evaluation point
    sigmax:
        Sigma in x direction
    sigmay:
        Sigma in y direction
    axis_sigma_scaling:
        Defines how the variances change with the x/y value:
        1 scales them with x, 2 with y, 3 with x + y
    xysigma0:
        x/y value where the given sigmas apply exactly

    Returns
    -------
    np.ndarray
        Averaged intensities, 1D, one per evaluation point
    """
    data_points = np.column_stack(
        (np.ravel(np.asarray(x, dtype=float)) / sigmax, np.ravel(np.asarray(y, dtype=float)) / sigmay)
    )
    intensity = np.ravel(np.asarray(I, dtype=float))
    tree = scipy.spatial.cKDTree(data_points)

    eval_x = np.ravel(np.asarray(eval_x, dtype=float))
    eval_y = np.ravel(np.asarray(eval_y, dtype=float))
    eval_points = np.column_stack((eval_x / sigmax, eval_y / sigmay))

    # Per-point variance scale factor: sigma_eff^2 = sigma^2 * (xy / xysigma0)
    if axis_sigma_scaling:
        if axis_sigma_scaling == 1:
            xy = eval_x
        elif axis_sigma_scaling == 2:
            xy = eval_y
        elif axis_sigma_scaling == 3:
            xy = eval_x + eval_y
        else:
            raise ValueError(f"Unknown axis_sigma_scaling: {axis_sigma_scaling}")
        variance_scale = xy / xysigma0
    else:
        variance_scale = np.ones_like(eval_x)

    result = np.zeros_like(eval_x)
    # Points with a non-positive variance scale keep a zero intensity
    valid = np.flatnonzero(variance_scale > 0)

    # Evaluate in chunks to bound the size of the neighbor arrays
    chunk_size = 5000
    for start in range(0, len(valid), chunk_size):
        idx = valid[start : start + chunk_size]
        radii = sigmas * np.sqrt(variance_scale[idx])
        neighbors = tree.query_ball_point(eval_points[idx], r=radii, workers=-1)
        counts = np.fromiter((len(nb) for nb in neighbors), dtype=np.intp, count=len(neighbors))
        if counts.sum() == 0:
            continue
        flat = np.concatenate([np.asarray(nb, dtype=np.intp) for nb in neighbors if nb])
        rows = np.repeat(np.arange(len(idx)), counts)
        distance_sq = np.sum((data_points[flat] - eval_points[idx][rows]) ** 2, axis=1)
        weights = np.exp(-0.5 * distance_sq / variance_scale[idx][rows])
        weight_sum = np.bincount(rows, weights=weights, minlength=len(idx))
        weighted_intensity = np.bincount(rows, weights=weights * intensity[flat], minlength=len(idx))
        nonzero = weight_sum > 0
        result[idx[nonzero]] = weighted_intensity[nonzero] / weight_sum[nonzero]

    return result


def smooth_data(
    x: np.ndarray,
    y: np.ndarray,
    I: np.ndarray,
    sigmas: float = 3.0,
    gridx: int = 150,
    gridy: int = 50,
    sigmax: float = 0.0005,
    sigmay: float = 0.0005,
    x1: float = -0.03,
    x2: float = 0.03,
    y1: float = 0.0,
    y2: float = 0.1,
    axis_sigma_scaling: int | None = None,
    xysigma0: float = 0.06,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Smooth an irregularly spaced dataset onto a regular grid.

    Takes each intensity within a distance of `sigmas` normalized sigma units
    of a given grid point and averages the intensities weighted by the
    Gaussian of the distance.

    Parameters
    ----------
    x:
        x-values of the original data; same units as `sigmax`
    y:
        y-values of the original data; same units as `sigmay`
    I:
        Intensity values of the original data
    sigmas:
        Range in units of sigma to search around a grid point
    gridx:
        Number of grid points in x direction
    gridy:
        Number of grid points in y direction
    sigmax:
        Sigma in x direction
    sigmay:
        Sigma in y direction
    x1:
        Lower x bound of the grid
    x2:
        Upper x bound of the grid
    y1:
        Lower y bound of the grid
    y2:
        Upper y bound of the grid
    axis_sigma_scaling:
        Defines how the sigmas change with the x/y value:
        1 scales the variances with x, 2 with y, 3 with x + y
    xysigma0:
        x/y value where the given sigmas apply exactly

    Returns
    -------
    tuple[np.ndarray, np.ndarray, np.ndarray]
        X grid, Y grid, and smoothed intensities, each of shape (gridy, gridx)
    """
    xout = np.linspace(x1, x2, gridx)
    yout = np.linspace(y1, y2, gridy)
    Xout, Yout = np.meshgrid(xout, yout)
    Iout = _kernel_average(x, y, I, Xout, Yout, sigmas, sigmax, sigmay, axis_sigma_scaling, xysigma0)
    return Xout, Yout, Iout.reshape(Xout.shape)


def finest_intervals(
    reduction_list: list["NexusData"],
    pol_state: str,
    axes=None,
    x_range: tuple[float, float] | None = None,
    y_range: tuple[float, float] | None = None,
    percentile: float = 50.0,
) -> tuple[float, float] | None:
    """Estimate the typical x and y spacings present in the off-specular data.

    Looks at the absolute differences between adjacent points of the 2D
    (detector pixel by TOF) coordinate arrays, along both array axes, over all
    runs. The median of the positive differences is used instead of the
    strict minimum (or a low percentile) because near-zero spacings are
    structural, not rare outliers: every detector row near the specular ridge
    has ki_z-kf_z (and Qx) close to 0 across its whole TOF range, and Qz steps
    shrink toward the low-Q end, so a low percentile still lands on values
    that would ask for an absurdly fine grid.

    Parameters
    ----------
    reduction_list:
        Loaded runs to inspect
    pol_state:
        Cross-section to read the off-specular data from
    axes:
        `OffSpecXAxis` coordinate-system choice; defaults to ki_z-kf_z vs Qz
    x_range:
        If given, only differences between points inside [min, max] in x count
    y_range:
        If given, only differences between points inside [min, max] in y count
    percentile:
        Percentile of the positive differences to report, in percent

    Returns
    -------
    tuple[float, float] or None
        Typical (x, y) intervals in 1/A, or None when no off-specular data is
        available
    """
    x_diffs: list[np.ndarray] = []
    y_diffs: list[np.ndarray] = []

    for item in reduction_list:
        if pol_state not in item.cross_sections:
            continue
        cross_section = item.cross_sections[pol_state]
        offspec = cross_section.off_spec
        if offspec is None or offspec.S is None:
            continue

        n_total = len(offspec.S[0])
        p_0 = cross_section.configuration.cut_first_n_points
        p_n = n_total - cross_section.configuration.cut_last_n_points

        if axes == OffSpecXAxis.QX_VS_QZ:
            x = offspec.Qx[:, p_0:p_n]
            y = offspec.Qz[:, p_0:p_n]
        elif axes == OffSpecXAxis.KZI_VS_KZF:
            x = offspec.ki_z[:, p_0:p_n]
            y = offspec.kf_z[:, p_0:p_n]
        else:
            x = (offspec.ki_z - offspec.kf_z)[:, p_0:p_n]
            y = offspec.Qz[:, p_0:p_n]

        in_region = np.ones(x.shape, dtype=bool)
        if x_range is not None:
            in_region &= (x >= x_range[0]) & (x <= x_range[1])
        if y_range is not None:
            in_region &= (y >= y_range[0]) & (y <= y_range[1])

        for axis in (0, 1):
            # Count a difference only when both of its points are in the region
            if axis == 0:
                pair_in_region = in_region[:-1, :] & in_region[1:, :]
            else:
                pair_in_region = in_region[:, :-1] & in_region[:, 1:]
            for values, collected in ((x, x_diffs), (y, y_diffs)):
                diffs = np.abs(np.diff(values, axis=axis))[pair_in_region]
                collected.append(diffs[diffs > 0])

    if not x_diffs:
        return None
    x_all = np.concatenate(x_diffs)
    y_all = np.concatenate(y_diffs)
    if len(x_all) == 0 or len(y_all) == 0:
        return None
    return float(np.percentile(x_all, percentile)), float(np.percentile(y_all, percentile))
