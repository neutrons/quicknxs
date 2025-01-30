# pylint: disable=too-many-locals, too-many-arguments
"""
    Class to execute and hold the off-specular reflectivity calculation.
"""
import logging
import numpy as np
import scipy.stats
from multiprocessing import Pool

from quicknxs.interfaces.configuration import Configuration, get_direct_beam_low_res_roi
from functools import reduce

H_OVER_M_NEUTRON = 3.956034e-7  # h/m_n [m^2/s]


class OffSpecular(object):
    """
    Compute off-specular reflectivity
    """

    d_wavelength = 0
    Qx = None
    Qz = None
    ki_z = None
    kf_z = None
    S = None
    dS = None

    def __init__(self, cross_section_data):
        """
        :param CrossSectionData cross_section_data: processed data object
        """
        self.data_set = cross_section_data

    def __call__(self, direct_beam=None):
        """
        Extract off-specular scattering from 4D dataset (x,y,ToF,I).
        Uses a window in y to filter the 4D data
        and than sums all I values for each ToF and x channel.
        Qz,Qx,kiz,kfz is calculated using the x and ToF positions
        together with the tth-bank and direct pixel values.

        :param CrossSectionData direct_beam: if given, this data will be used to normalize the output
        """
        # TODO: correct for detector sensitivity
        x_pos = self.data_set.configuration.peak_position
        scale = 1.0 / self.data_set.proton_charge

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

            norm_y_min, norm_y_max = get_direct_beam_low_res_roi(
                self.data_set.configuration, direct_beam.configuration
            )
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


def merge(reduction_list, pol_state):
    """
    Merge the off-specular data from a reduction list.
    :param list reduction_list: list of NexusData objects
    :param string pol_state: polarization state to consider

    The scaling factors should have been determined at this point. Just use them
    to merge the different runs in a set.

    TODO: This doesn't deal with the overlap properly. It assumes that the user
    cut the overlapping points by hand.
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

    return _qx, _qz, _ki_z, _kf_z, _ki_z - _kf_z, _s, _ds


def closest_bin(q, bin_edges):
    """
    Find closest bin to a q-value
    :param float q: q-value
    :param list bin_edges: list of bin edges
    """
    for i in range(len(bin_edges)):
        if q > bin_edges[i] and q <= bin_edges[i + 1]:
            return i
    return None


def rebin_extract(
    reduction_list,
    pol_state,
    axes=None,
    use_weights=True,
    n_bins_x=350,
    n_bins_y=350,
    x_min=-0.015,
    x_max=0.015,
    y_min=0,
    y_max=0.1,
):
    """
    Rebin off-specular data and extract cut at given Qz values.
    Note: the analysis computers with RHEL7 have Scipy 0.12 installed, which makes
    this code uglier. Refactor once we get a more recent version.
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
    if axes == Configuration.QX_VS_QZ:
        x_label = "Qx"
        x_values = Qx
    elif axes == Configuration.KZI_VS_KZF:
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
    """
    Get a slice for a Qz band
    :param qz: Qz array
    :param data: 2D data array
    :param error: uncertainty on the data array
    :param q_min: lower Qz bound
    :param q_max: upper Qz bound
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


def _smooth_data(
    x,
    y,
    I,
    sigmas=3.0,
    gridx=150,
    gridy=50,
    sigmax=0.0005,
    sigmay=0.0005,
    x1=-0.03,
    x2=0.03,
    y1=0.0,
    y2=0.1,
    axis_sigma_scaling=None,
    xysigma0=0.06,
    indices=None,
):
    """
    Smooth a irregular spaced dataset onto a regular grid.
    Takes each intensities with a distance < 3*sigma
    to a given grid point and averages their intensities
    weighted by the gaussian of the distance.

    :param dict settings: Contains options for 'grid', 'sigma' and 'region' of the algorithm
    :param numpy.ndarray x: x-values of the original data
    :param numpy.ndarray y: y-values of the original data
    :param numpy.ndarray I: Intensity values of the original data
    :param float sigmas: Range in units of sigma to search around a grid point
    :param int axis_sigma_scaling: Defines how the sigmas change with the x/y value
    :param float xysigma0: x/y value where the given sigmas are used
    :param list indices: list of indices to run over
    """
    xout = np.linspace(x1, x2, gridx)
    yout = np.linspace(y1, y2, gridy)
    Xout, Yout = np.meshgrid(xout, yout)
    Iout = np.zeros_like(Xout)
    ssigmax, ssigmay = sigmax**2, sigmay**2

    imax = len(Xout)
    for i in range(imax):
        # for j in range(len(Xout[0])):
        for j in range(indices[0], indices[1]):
            xij = Xout[i, j]
            yij = Yout[i, j]
            if axis_sigma_scaling:
                if axis_sigma_scaling == 1:
                    xyij = xij
                elif axis_sigma_scaling == 2:
                    xyij = yij
                elif axis_sigma_scaling == 3:
                    xyij = xij + yij
                if xyij == 0:
                    continue
                ssigmaxi = ssigmax / xysigma0 * xyij
                ssigmayi = ssigmay / xysigma0 * xyij
                rij = (x - xij) ** 2 / ssigmaxi + (y - yij) ** 2 / ssigmayi  # normalized distance^2
            else:
                rij = (x - xij) ** 2 / ssigmax + (y - yij) ** 2 / ssigmay  # normalized distance^2
            take = np.where(rij < sigmas**2)  # take points up to 3 sigma distance
            if len(take[0]) == 0:
                continue
            Pij = np.exp(-0.5 * rij[take])
            Pij /= Pij.sum()
            Iout[i, j] = (Pij * I[take]).sum()
    return Xout, Yout, Iout


def proc(data):
    """
    Serializable function to be called by each thread
    """
    return _smooth_data(
        x=data["x"],
        y=data["y"],
        I=data["I"],
        sigmas=data["sigmas"],
        gridx=data["gridx"],
        gridy=data["gridy"],
        sigmax=data["sigmax"],
        sigmay=data["sigmay"],
        x1=data["x1"],
        x2=data["x2"],
        y1=data["y1"],
        y2=data["y2"],
        axis_sigma_scaling=data["axis_sigma_scaling"],
        xysigma0=data["xysigma0"],
        indices=data["indices"],
    )


def smooth_data(
    x,
    y,
    I,
    sigmas=3.0,
    gridx=150,
    gridy=50,
    sigmax=0.0005,
    sigmay=0.0005,
    x1=-0.03,
    x2=0.03,
    y1=0.0,
    y2=0.1,
    axis_sigma_scaling=None,
    xysigma0=0.06,
    pool=5,
):
    """
    Execute legacy smoothing process by spreading it to a pool
    of processes.
    """
    pool = int(pool)
    xout = np.linspace(x1, x2, gridx)
    p = Pool(pool)
    n = len(xout)
    step = int(n / pool)
    indices = [[step * i, step * (i + 1)] for i in range(pool)]
    indices[-1][1] = n

    inputs = []
    for i in range(pool):
        _d = dict(
            x=x,
            y=y,
            I=I,
            sigmas=sigmas,
            gridx=gridx,
            gridy=gridy,
            sigmax=sigmax,
            sigmay=sigmay,
            x1=x1,
            x2=x2,
            y1=y1,
            y2=y2,
            axis_sigma_scaling=axis_sigma_scaling,
            xysigma0=xysigma0,
            indices=indices[i],
        )
        inputs.append(_d)

    results = p.map(proc, inputs)
    x_out = results[0][0]
    y_out = results[0][1]
    _data = [r[2] for r in results]
    intensity_out = reduce((lambda x, y: x + y), _data)

    return x_out, y_out, intensity_out
