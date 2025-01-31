"""
Computations for GISANS
"""

import logging
from multiprocessing import Pool

import numpy as np

from quicknxs.interfaces.configuration import get_direct_beam_low_res_roi

H_OVER_M_NEUTRON = 3.956034e-7  # h/m_n [m^2/s]


class GISANS(object):
    """
    Compute grazing-incident SANS
    """

    def __init__(self, cross_section_data):
        """
        :param CrossSectionData cross_section_data: processed data object

        The calculations here are meant to match QuickNXS v1. The following are
        items to improve on:
            - Background subtraction
            - Trim the TOF distribution to the chopper bandwidth

        """
        self.data_set = cross_section_data

    def __call__(self, direct_beam=None):
        x_pos = self.data_set.configuration.peak_position
        y_pos = self.data_set.configuration.low_res_position
        scale = 1.0 / self.data_set.proton_charge * self.data_set.configuration.scaling_factor

        rad_per_pixel = self.data_set.det_size_x / self.data_set.dist_sam_det / self.data_set.xydata.shape[1]

        # QuickNXS v1 uses the whole detector for GISANS calculations and doesn't trim the edges
        # active_area_x = self.data_set.active_area_x
        # active_area_y = self.data_set.active_area_y
        active_area_x = [0, 304]
        active_area_y = [0, 256]
        xtth = self.data_set.direct_pixel - np.arange(self.data_set.data.shape[0])[active_area_x[0] : active_area_x[1]]
        pix_offset_spec = self.data_set.direct_pixel - x_pos
        delta_dangle = self.data_set.dangle - self.data_set.angle_offset
        tth_spec = delta_dangle * np.pi / 180.0 + pix_offset_spec * rad_per_pixel
        af = delta_dangle * np.pi / 180.0 + xtth * rad_per_pixel - tth_spec / 2.0
        ai = np.ones_like(af) * tth_spec / 2.0

        phi = (np.arange(self.data_set.data.shape[1])[active_area_y[0] : active_area_y[1]] - y_pos) * rad_per_pixel

        # To be compatible with QuickNXS v1, take the whole TOF range rather than trimming the edges
        # ws = self.data_set.event_workspace
        # tof_edges = np.arange(ws.getTofMin(), ws.getTofMax(), self.data_set.configuration.tof_bins)
        tof_edges = self.data_set.tof_edges

        v_edges = self.data_set.dist_mod_det / tof_edges * 1e6  # m/s
        lambda_edges = H_OVER_M_NEUTRON / v_edges * 1e10  # A

        wavelengths = np.asarray((lambda_edges[:-1] + lambda_edges[1:]) / 2.0)
        k = 2.0 * np.pi / wavelengths
        # calculate ROI intensities and normalize by number of points
        # Note: the number of points here may need to be adjusted from the specular reflectivity
        # calculation if we used a final rebining.
        P0 = self.data_set.configuration.cut_first_n_points
        PN = len(self.data_set.tof) - self.data_set.configuration.cut_last_n_points
        self.wavelengths = wavelengths[P0:PN]

        # calculate reciprocal space, incident and outgoing perpendicular wave vectors
        self.Qy = k[np.newaxis, np.newaxis, P0:PN] * (np.sin(phi) * np.cos(af)[:, np.newaxis])[:, :, np.newaxis]
        p_i = k[np.newaxis, np.newaxis, P0:PN] * ((0.0 * phi) + np.sin(ai)[:, np.newaxis])[:, :, np.newaxis]
        self.p_f = k[np.newaxis, np.newaxis, P0:PN] * ((0.0 * phi) + np.sin(af)[:, np.newaxis])[:, :, np.newaxis]
        self.Qz = p_i + self.p_f

        raw = self.data_set.data[active_area_x[0] : active_area_x[1], active_area_y[0] : active_area_y[1], P0:PN]

        intensity = scale * np.array(raw)
        d_intensity = scale * np.sqrt(raw)

        if direct_beam is not None:
            if not direct_beam.configuration.tof_bins == self.data_set.configuration.tof_bins:
                logging.error("Trying to normalize with a direct beam data set with different binning")

            norm_y_min, norm_y_max = get_direct_beam_low_res_roi(self.data_set.configuration, direct_beam.configuration)
            norm_x_min, norm_x_max = direct_beam.configuration.peak_roi
            norm_raw_multi_dim = direct_beam.data[norm_x_min:norm_x_max, norm_y_min:norm_y_max, P0:PN]

            norm_raw = norm_raw_multi_dim.sum(axis=0).sum(axis=0)
            norm_d_raw = np.sqrt(norm_raw)
            norm_scale = (float(norm_x_max) - float(norm_x_min)) * (float(norm_y_max) - float(norm_y_min))
            norm_raw /= norm_scale * direct_beam.proton_charge
            norm_d_raw /= norm_scale * direct_beam.proton_charge

            idxs = norm_raw > 0.0
            d_intensity[:, :, idxs] = np.sqrt(
                (d_intensity[:, :, idxs] / norm_raw[idxs][np.newaxis, np.newaxis, :]) ** 2
                + (
                    intensity[:, :, idxs]
                    / norm_raw[idxs][np.newaxis, np.newaxis, :] ** 2
                    * norm_d_raw[idxs][np.newaxis, np.newaxis, :]
                )
                ** 2
            )
            intensity[:, :, idxs] /= norm_raw[idxs][np.newaxis, np.newaxis, :]
            intensity[:, :, np.logical_not(idxs)] = 0.0
            d_intensity[:, :, np.logical_not(idxs)] = 0.0

        self.S = intensity
        self.dS = d_intensity

        # Create plotting data
        # TODO: use options to plot the right data (for instance: qz or pf)
        self.SGrid, qy, qz = np.histogram2d(
            self.Qy.flatten(), self.Qz.flatten(), bins=(50, 50), weights=intensity.flatten()
        )
        npoints, _, _ = np.histogram2d(self.Qy.flatten(), self.Qz.flatten(), bins=(50, 50))
        self.SGrid[npoints > 0] /= npoints[npoints > 0]
        self.SGrid = self.SGrid.transpose()
        qy = (qy[:-1] + qy[1:]) / 2.0
        qz = (qz[:-1] + qz[1:]) / 2.0
        self.QyGrid, self.QzGrid = np.meshgrid(qy, qz)


def merge(reduction_list, pol_state, wl_min=0, wl_max=100):
    """
    Merge the off-specular data from a reduction list.
    :param list reduction_list: list of NexusData objects
    :param string pol_state: polarization state to consider

    The scaling factors should have been determined at this point. Just use them
    to merge the different runs in a set.

    TODO: This doesn't deal with the overlap properly. It assumes that the user
    cut the overlapping points by hand.
    """
    _qy = np.zeros(0)
    _qz = np.zeros(0)
    _pf = np.zeros(0)
    _s = np.zeros(0)
    _ds = np.zeros(0)
    _wl = np.zeros(0)

    for item in reduction_list:
        gisans = item.cross_sections[pol_state].gisans_data
        Qy, Qz, pf, S, dS = (gisans.Qy, gisans.Qz, gisans.p_f, gisans.S, gisans.dS)

        # Filter according to wavelength
        filtered = np.where((gisans.wavelengths >= wl_min) & (gisans.wavelengths <= wl_max))
        _qy = np.concatenate((_qy, Qy[:, :, filtered].flatten()))
        _qz = np.concatenate((_qz, Qz[:, :, filtered].flatten()))
        _pf = np.concatenate((_pf, pf[:, :, filtered].flatten()))
        _s = np.concatenate((_s, S[:, :, filtered].flatten()))
        _ds = np.concatenate((_ds, dS[:, :, filtered].flatten()))
        _wl = np.concatenate((_wl, gisans.wavelengths[filtered]))

    return _qy, _qz, _pf, _s, _ds, _wl


def rebin_extract(reduction_list, pol_state, wl_min, wl_max, qy_npts=50, qz_npts=50, use_pf=False):
    binning = (qy_npts + 1, qz_npts + 1)
    qy, qz, pf, intensity, d_intensity, _ = merge(reduction_list, pol_state, wl_min=wl_min, wl_max=wl_max)
    if use_pf:
        _z_axis = pf
    else:
        _z_axis = qz

    n_points, _qy, _qz_axis = np.histogram2d(qy, _z_axis, bins=binning)
    _intensity_summed, _, _ = np.histogram2d(qy, _z_axis, bins=(_qy, _qz_axis), weights=intensity)
    _intensity_err, _, _ = np.histogram2d(qy, _z_axis, bins=(_qy, _qz_axis), weights=d_intensity**2)

    _intensity_summed[n_points > 0] /= n_points[n_points > 0]
    _intensity_err = np.sqrt(_intensity_err)
    _intensity_err[n_points > 0] /= n_points[n_points > 0]

    _qy = (_qy[:-1] + _qy[1:]) / 2.0
    _qz_axis = (_qz_axis[:-1] + _qz_axis[1:]) / 2.0

    return _intensity_summed, _qy, _qz_axis, _intensity_err


def _rebin_proc(data):
    # Filter data
    wl = data["wl"]
    filtered = np.where((wl >= data["wl_min"]) & (wl <= data["wl_max"]))
    qy = data["qy"][filtered]
    _z_axis = data["qz"][filtered]
    intensity = data["intensity"][filtered]
    d_intensity = data["d_intensity"][filtered]

    # Perform binning
    n_points, _qy, _qz_axis = np.histogram2d(qy, _z_axis, bins=data["binning"])
    _intensity_summed, _, _ = np.histogram2d(qy, _z_axis, bins=(_qy, _qz_axis), weights=intensity)
    _intensity_err, _, _ = np.histogram2d(qy, _z_axis, bins=(_qy, _qz_axis), weights=d_intensity**2)

    _intensity_summed[n_points > 0] /= n_points[n_points > 0]
    _intensity_err = np.sqrt(_intensity_err)
    _intensity_err[n_points > 0] /= n_points[n_points > 0]

    _qy = (_qy[:-1] + _qy[1:]) / 2.0
    _qz_axis = (_qz_axis[:-1] + _qz_axis[1:]) / 2.0

    return _intensity_summed, _qy, _qz_axis, _intensity_err


def rebin_parallel(reduction_list, pol_state, wl_min, wl_max, wl_npts=2, qy_npts=50, qz_npts=50, use_pf=False):
    """
    Process the wavelength bands in parallel.
    """
    # First, merge all the data
    binning = (qy_npts + 1, qz_npts + 1)
    qy, qz, pf, intensity, d_intensity, wl_array = merge(reduction_list, pol_state, wl_min=0, wl_max=100.0)
    if use_pf:
        _z_axis = pf
    else:
        _z_axis = qz

    # Create one job per wavelength band
    inputs = []
    for i in range(wl_npts):
        wl_step = (wl_max - wl_min) / wl_npts
        _wl_min = wl_min + i * wl_step
        _wl_max = wl_min + (i + 1) * wl_step
        _d = dict(
            qy=qy,
            qz=_z_axis,
            intensity=intensity,
            d_intensity=d_intensity,
            wl=wl_array,
            wl_min=_wl_min,
            wl_max=_wl_max,
            binning=binning,
        )
        inputs.append(_d)

    pool = Pool(wl_npts)
    results = pool.map(_rebin_proc, inputs)
    return results
