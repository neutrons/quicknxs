import mantid.simpleapi as api
import numpy as np

from quicknxs.interfaces.data_handling import instrument


def load_data(run="REF_M_30769"):
    if run.startswith("/SNS"):
        filepath = run
    else:
        filepath = "/SNS/REF_M/IPTS-21391/nexus/" + run + ".nxs.h5"
    _instrument = instrument.Instrument()

    ws_list = _instrument.load_data(filepath)

    _n_counts = 0
    _high_count_ws = None
    for _ws in ws_list:
        _i_counts = _ws.getNumberEvents()
        if _n_counts < _i_counts:
            _n_counts = _i_counts
            _high_count_ws = _ws
    return _high_count_ws


def get_peak(center, width, max_pixel=None):
    peak_min = int(round(float(center) - float(width) / 2.0))
    peak_max = int(round(float(center) + float(width) / 2.0 + 1.0))
    if max_pixel is not None:
        if peak_min < 0:
            peak_min = 0
        if peak_max >= max_pixel:
            peak_max = max_pixel - 1
    return peak_min, peak_max


def get_wl_range(ws):
    """
    Determine TOF range from the data
    :param workspace ws: workspace to work with
    """
    run_object = ws.getRun()

    wl = run_object.getProperty("LambdaRequest").value[0]
    chopper_speed = run_object.getProperty("SpeedRequest1").value[0]

    # Cut the edges by using a width of 2.6 A
    wl_min = wl - 1.3 * 60.0 / chopper_speed
    wl_max = wl + 1.3 * 60.0 / chopper_speed

    return [wl_min, wl_max]


def get_q_binning(q_min=0.001, q_max=0.15, q_step=-0.02):
    if q_step > 0:
        n_steps = np.int((q_max - q_min) / q_step)
        return q_min + np.asarray([q_step * i for i in range(n_steps)])
    else:
        _step = 1.0 + np.abs(q_step)
        n_steps = np.int(np.log(q_max / q_min) / np.log(_step))
        return q_min * np.asarray([_step**i for i in range(n_steps)])


def quicknxs_scale(theta, peak, low_res, norm_peak, norm_low_res):
    """
    Scaling factor to multiply by to be compatible with QuickNXS 1.0.
    """
    quicknxs_scale = (float(norm_peak[1]) - float(norm_peak[0])) * (float(norm_low_res[1]) - float(norm_low_res[0]))
    quicknxs_scale /= (float(peak[1]) - float(peak[0])) * (float(low_res[1]) - float(low_res[0]))
    _scale = 0.005 / np.sin(theta) if theta > 0.0002 else 1.0
    quicknxs_scale *= _scale
    return quicknxs_scale


class EventReflectivity(object):
    """
    Event based reflectivit calculation.
    List of items to be taken care of outside this class:
      - Edge points cropping
      - Calculate theta using SANGLE or not
      - Angle offset
      - Direct pixel overwrite
      - DANGLE0 overwrite

    Options that are left out:
      - rounding up pixel to assign the proper Qx
    """

    QX_VS_QZ = 0
    KZI_VS_KZF = 1
    DELTA_KZ_VS_QZ = 3
    INSTRUMENT_4A = 0
    INSTRUMENT_4B = 1

    def __init__(
        self,
        scattering_workspace,
        direct_workspace,
        signal_peak,
        signal_bck,
        norm_peak,
        norm_bck,
        specular_pixel,
        signal_low_res,
        norm_low_res,
        q_min=None,
        q_step=-0.02,
        q_max=None,
        tof_range=None,
        theta=1.0,
        sample_length=10,
        instrument=None,
    ):
        """
        Pixel ranges include the min and max pixels.

        :param scattering_workspace: Mantid workspace containing the reflected data
        :param direct_workspace: Mantid workspace containing the direct beam data [if None, normalization won't be applied]
        :param signal_peak: pixel min and max for the specular peak
        :param signal_bck: pixel range of the background [if None, the background won't be subtracted]
        :param norm_peak: pixel range of the direct beam peak
        :param norm_bck: pixel range of the direct beam background [if None, the background won't be subtracted]
        :param specular_pixel: pixel of the specular peak
        :param signal_low_res: pixel range of the specular peak out of the scattering plane
        :param norm_low_res: pixel range of the direct beam out of the scattering plane
        :param q_min: value of lowest q point
        :param q_step: step size in Q. Enter a negative value to get a log scale
        :param q_min: value of largest q point
        :param tof_range: TOF range,or None
        :param theta: theta scattering angle in radians
        :param sample_length: sample size, for resolution calculation

        """
        if instrument in [self.INSTRUMENT_4A, self.INSTRUMENT_4B]:
            self.instrument = instrument
        else:
            self.instrument = self.INSTRUMENT_4A
        self.signal_peak = signal_peak
        self.signal_bck = signal_bck
        self.norm_peak = norm_peak
        self.norm_bck = norm_bck
        self.signal_low_res = signal_low_res
        self.norm_low_res = norm_low_res
        self.specular_pixel = specular_pixel
        self.q_min = q_min
        self.q_max = q_max
        self.q_step = q_step
        self.tof_range = tof_range
        self.theta = theta
        self.sample_length = sample_length
        self._offspec_x_bins = None
        self._offspec_z_bins = None

        # Process workspaces
        if self.tof_range is not None:
            self._ws_sc = api.CropWorkspace(
                InputWorkspace=scattering_workspace,
                XMin=tof_range[0],
                XMax=tof_range[1],
                OutputWorkspace="_" + str(scattering_workspace),
            )
            self._ws_db = api.CropWorkspace(
                InputWorkspace=direct_workspace,
                XMin=tof_range[0],
                XMax=tof_range[1],
                OutputWorkspace="_" + str(direct_workspace),
            )
        else:
            self._ws_sc = scattering_workspace
            self._ws_db = direct_workspace

        # Extract meta data
        self.extract_meta_data()

    def extract_meta_data(self):
        # Set up basic data
        self.n_x = int(self._ws_sc.getInstrument().getNumberParameter("number-of-x-pixels")[0])
        self.n_y = int(self._ws_sc.getInstrument().getNumberParameter("number-of-y-pixels")[0])

        self.pixel_width = float(self._ws_sc.getInstrument().getNumberParameter("pixel-width")[0]) / 1000.0

        if self.instrument == self.INSTRUMENT_4B:
            self.extract_meta_data_4B()
        else:
            self.extract_meta_data_4A()

        h = 6.626e-34  # m^2 kg s^-1
        m = 1.675e-27  # kg
        self.constant = 1e-4 * m * self.source_detector_distance / h

        if self.tof_range is None:
            self.wl_range = get_wl_range(self._ws_sc)
        else:
            self.wl_range = [self.tof_range[0] / self.constant, self.tof_range[1] / self.constant]

        if self.q_min is None:
            self.q_min = 4.0 * np.pi / self.wl_range[1] * np.sin(self.theta)
        if self.q_max is None:
            self.q_max = 4.0 * np.pi / self.wl_range[0] * np.sin(self.theta)

        # Q binning to use
        self.q_bins = get_q_binning(self.q_min, self.q_max, self.q_step)

    def extract_meta_data_4A(self):
        run_object = self._ws_sc.getRun()
        self.det_distance = run_object["SampleDetDis"].getStatistics().mean
        source_sample_distance = run_object["ModeratorSamDis"].getStatistics().mean
        if run_object["SampleDetDis"].units not in ["m", "meter"]:
            self.det_distance /= 1000.0
        if run_object["ModeratorSamDis"].units not in ["m", "meter"]:
            source_sample_distance /= 1000.0
        self.source_detector_distance = source_sample_distance + self.det_distance

    def extract_meta_data_4B(self):
        self.det_distance = 1.83
        source_sample_distance = 13.63
        self.source_detector_distance = source_sample_distance + self.det_distance

    def __repr__(self):
        output = "sample-det: %s\n" % self.det_distance
        output += "pixel: %s\n" % self.pixel_width
        output += "WL: %s %s\n" % (self.wl_range[0], self.wl_range[1])
        output += "Q: %s %s\n" % (self.q_min, self.q_max)
        output += "Theta = %s" % self.theta
        return output

    def specular(self, q_summing=True):
        # Scattering data
        refl, d_refl = self._reflectivity(
            self._ws_sc,
            peak_position=self.specular_pixel,
            peak=self.signal_peak,
            low_res=self.signal_low_res,
            theta=self.theta,
            q_summing=q_summing,
        )
        norm, d_norm = self._reflectivity(
            self._ws_db,
            peak_position=0,
            peak=self.norm_peak,
            low_res=self.norm_low_res,
            theta=self.theta,
            q_summing=False,
        )

        if False and self.norm_bck is not None:
            norm_bck, d_norm_bck = self._norm_bck_in_pixel()
            norm -= norm_bck
            d_norm = np.sqrt(d_norm**2 + d_norm_bck**2)

        db_bins = norm > 0

        if False and self.signal_bck is not None:
            refl_bck, d_refl_bck = self._signal_bck_in_pixel()
            refl -= refl_bck
            d_refl = np.sqrt(d_refl**2 + d_refl_bck**2)

            self.refl_bck = refl_bck[db_bins] / norm[db_bins]
            self.d_refl_bck = np.sqrt(
                d_refl_bck[db_bins] ** 2 / norm[db_bins] ** 2
                + refl_bck[db_bins] ** 2 * d_norm[db_bins] ** 2 / norm[db_bins] ** 4
            )

        refl[db_bins] = refl[db_bins] / norm[db_bins]
        d_refl[db_bins] = np.sqrt(
            d_refl[db_bins] ** 2 / norm[db_bins] ** 2 + refl[db_bins] ** 2 * d_norm[db_bins] ** 2 / norm[db_bins] ** 4
        )

        self.refl = refl
        self.d_refl = d_refl
        return self.q_bins, refl, d_refl

    def _signal_bck_in_pixel(self, normalize_to_single_pixel=False, q_bins=None):
        q_bins = self.q_bins if q_bins is None else q_bins
        refl_bck, d_refl_bck = self._reflectivity(
            self._ws_sc,
            peak_position=0,
            q_bins=q_bins,
            peak=self.signal_bck,
            low_res=self.signal_low_res,
            theta=self.theta,
            q_summing=False,
        )

        _pixel_area = self.signal_bck[1] - self.signal_bck[0] + 1.0
        if not normalize_to_single_pixel:
            _pixel_area /= self.signal_peak[1] - self.signal_peak[0] + 1.0
        refl_bck /= _pixel_area
        d_refl_bck /= _pixel_area
        return refl_bck, d_refl_bck

    def _norm_bck_in_pixel(self, q_bins=None):
        if q_bins is None:
            q_bins = self.q_bins
        norm_bck, d_norm_bck = self._reflectivity(
            self._ws_db,
            peak_position=0,
            q_bins=q_bins,
            peak=self.norm_bck,
            low_res=self.norm_low_res,
            theta=self.theta,
            q_summing=False,
        )

        _pixel_area = (self.norm_bck[1] - self.norm_bck[0] + 1.0) / (self.norm_peak[1] - self.norm_peak[0] + 1.0)
        norm_bck /= _pixel_area
        d_norm_bck /= _pixel_area
        return norm_bck, d_norm_bck

    def slice(self, x_min=0.002, x_max=0.004, x_bins=None, z_bins=None, refl=None, d_refl=None, normalize=False):
        x_bins = self._offspec_x_bins if x_bins is None else x_bins
        z_bins = self._offspec_z_bins if z_bins is None else z_bins
        refl = self._offspec_refl if refl is None else refl
        d_refl = self._offspec_d_refl if d_refl is None else d_refl

        i_min = len(x_bins[x_bins < x_min])
        i_max = len(x_bins[x_bins < x_max])

        _spec = np.sum(refl[i_min:i_max], axis=0)
        _d_spec = np.sum((d_refl[i_min:i_max]) ** 2, axis=0)
        _d_spec = np.sqrt(_d_spec)
        if normalize:
            _spec /= i_max - i_min
            _d_spec /= i_max - i_min

        return z_bins, _spec, _d_spec

    def _reflectivity(self, ws, peak_position, peak, low_res, theta, q_bins=None, q_summing=False):
        """
        Assumes that the input workspace is normalized by proton charge.
        """
        charge = ws.getRun()["gd_prtn_chrg"].value
        _q_bins = self.q_bins if q_bins is None else q_bins

        refl = np.zeros(len(_q_bins) - 1)
        _pixel_width = self.pixel_width if q_summing else 0.0

        for i in range(low_res[0], int(low_res[1] + 1)):
            for j in range(peak[0], int(peak[1] + 1)):
                if self.instrument == self.INSTRUMENT_4A:
                    pixel = j * self.n_y + i
                else:
                    pixel = i * self.n_y + j
                evt_list = ws.getSpectrum(pixel)
                if evt_list.getNumberEvents() == 0:
                    continue

                wl_list = evt_list.getTofs() / self.constant
                x_distance = _pixel_width * (peak_position - j)
                delta_theta_f = np.arctan(x_distance / self.det_distance) / 2.0
                qz = 4.0 * np.pi / wl_list * np.sin(theta + delta_theta_f) * np.cos(delta_theta_f)

                _counts, _ = np.histogram(qz, bins=_q_bins)
                refl += _counts

        d_refl_sq = np.sqrt(refl) / charge
        refl /= charge

        return refl, d_refl_sq

    def _get_events(self, ws, peak, low_res):
        """
        Return an array of wavelengths for a given workspace.
        """
        wl_events = np.asarray([])

        for i in range(low_res[0], int(low_res[1] + 1)):
            for j in range(peak[0], int(peak[1] + 1)):
                if self.instrument == self.INSTRUMENT_4A:
                    pixel = j * self.n_y + i
                else:
                    pixel = i * self.n_y + j
                evt_list = ws.getSpectrum(pixel)
                wl_list = evt_list.getTofs() / self.constant
                wl_events = np.concatenate((wl_events, wl_list))

        return wl_events

    def off_specular(
        self, x_axis=None, x_min=-0.015, x_max=0.015, x_npts=50, z_min=None, z_max=None, z_npts=-120, bck_in_q=None
    ):
        """
        Compute off-specular
        :param x_axis: Axis selection
        :param x_min: Min value on x-axis
        :param x_max: Max value on x-axis
        :param x_npts: Number of points in x (negative will produce a log scale)
        :param z_min: Min value on z-axis (if none, default Qz will be used)
        :param z_max: Max value on z-axis (if none, default Qz will be used)
        :param z_npts: Number of points in z (negative will produce a log scale)
        """
        # Z axis binning
        qz_bins = self.q_bins
        if z_min is not None and z_max is not None:
            if z_npts < 0:
                qz_bins = np.logspace(np.log10(z_min), np.log10(z_max), num=np.abs(z_npts))
            else:
                qz_bins = np.linspace(z_min, z_max, num=z_npts)

        # X axis binning
        if x_npts > 0:
            qx_bins = np.linspace(x_min, x_max, num=x_npts)
        else:
            qx_bins = np.logspace(np.log10(x_min), np.log10(x_max), num=np.abs(x_npts))

        wl_events = self._get_events(self._ws_db, self.norm_peak, self.norm_low_res)
        wl_dist, wl_bins = np.histogram(wl_events, bins=60)
        wl_middle = [(wl_bins[i + 1] + wl_bins[i]) / 2.0 for i in range(len(wl_bins) - 1)]

        _refl, _d_refl = self._off_specular(
            self._ws_sc, wl_dist, wl_middle, qx_bins, qz_bins, self.specular_pixel, self.theta, x_axis=x_axis
        )
        db_charge = self._ws_db.getRun()["gd_prtn_chrg"].value
        _refl *= db_charge * (wl_bins[1] - wl_bins[0])
        _d_refl *= db_charge * (wl_bins[1] - wl_bins[0])

        # Background
        if self.signal_bck:
            if bck_in_q is None:
                print("Not implemented")
                # refl_bck, d_refl_bck = self._signal_bck_in_pixel(normalize_to_single_pixel=True, q_bins=qz_bins)
            else:
                _, refl_bck, d_refl_bck = self.slice(
                    bck_in_q[0],
                    bck_in_q[1],
                    x_bins=qx_bins,
                    z_bins=qz_bins,
                    refl=_refl,
                    d_refl=_d_refl,
                    normalize=True,
                )

                _refl -= refl_bck
                _d_refl = np.sqrt(_d_refl**2 + d_refl_bck**2)

        self._offspec_x_bins = qx_bins
        self._offspec_z_bins = qz_bins
        self._offspec_refl = _refl
        self._offspec_d_refl = _d_refl

        return qx_bins, qz_bins, _refl, _d_refl

    def _off_specular(self, ws, wl_dist, wl_bins, x_bins, z_bins, peak_position, theta, x_axis=None):
        charge = ws.getRun()["gd_prtn_chrg"].value
        refl = np.zeros([len(x_bins) - 1, len(z_bins) - 1])
        counts = np.zeros([len(x_bins) - 1, len(z_bins) - 1])

        for j in range(0, self.n_x):
            wl_list = np.asarray([])
            for i in range(self.signal_low_res[0], int(self.signal_low_res[1] + 1)):
                if self.instrument == self.INSTRUMENT_4A:
                    pixel = j * self.n_y + i
                else:
                    pixel = i * self.n_y + j
                evt_list = ws.getSpectrum(pixel)
                wl_events = evt_list.getTofs() / self.constant
                wl_list = np.concatenate((wl_events, wl_list))

            k = 2.0 * np.pi / wl_list
            wl_weights = 1.0 / np.interp(wl_list, wl_bins, wl_dist, np.inf, np.inf)

            x_distance = float(peak_position - j) * self.pixel_width
            delta_theta_f = np.arctan(x_distance / self.det_distance)
            theta_f = theta + delta_theta_f

            qz = k * (np.sin(theta_f) + np.sin(theta))
            qx = k * (np.cos(theta_f) - np.cos(theta))
            ki_z = k * np.sin(theta)
            kf_z = k * np.sin(theta_f)

            _x = qx
            _z = qz
            if x_axis == EventReflectivity.DELTA_KZ_VS_QZ:
                _x = ki_z - kf_z
            elif x_axis == EventReflectivity.KZI_VS_KZF:
                _x = ki_z
                _z = kf_z

            histo_weigths = wl_weights * _z / wl_list
            _counts, _, _ = np.histogram2d(_x, _z, bins=[x_bins, z_bins], weights=histo_weigths)
            refl += _counts
            _counts, _, _ = np.histogram2d(_x, _z, bins=[x_bins, z_bins])
            counts += _counts

        bin_size = z_bins[1] - z_bins[0]
        d_refl_sq = refl / np.sqrt(counts) / charge / bin_size
        refl /= charge * bin_size

        return refl, d_refl_sq
