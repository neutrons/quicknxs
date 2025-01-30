"""
    Meta-data information for MR reduction
"""
# pylint: disable=too-few-public-methods, wrong-import-position, too-many-instance-attributes, wrong-import-order

import sys
import time
import logging
import math
import copy

import numpy as np
from scipy import ndimage
import scipy.optimize as opt
from .peak_finding import find_peaks, peak_prominences, peak_widths

import mantid.simpleapi as api

NX_PIXELS = 304
NY_PIXELS = 256


class DataInfo(object):
    """
    Class to hold the relevant information from a run (scattering or direct beam).
    """

    peak_range_offset = 0
    tolerance = 0.02

    def __init__(self, ws, cross_section, configuration):
        self.cross_section = cross_section
        self.run_number = ws.getRunNumber()
        self.is_direct_beam = False
        self.data_type = 1
        self.peak_position = 0
        self.peak_range = [0, 0]
        self.low_res_range = [0, 0]
        self.background = configuration.bck_roi
        self.n_events_cutoff = 100

        # ROI information
        self.roi_peak = [0, 0]
        self.roi_low_res = [0, 0]
        self.roi_background = [0, 0]

        # Options to override the ROI
        self.force_peak_roi = configuration.force_peak_roi
        self.forced_peak_roi = configuration.peak_roi
        self.force_low_res_roi = configuration.force_low_res_roi
        self.forced_low_res_roi = configuration.low_res_roi
        self.force_bck_roi = configuration.force_bck_roi
        self.forced_bck_roi = configuration.bck_roi

        # Peak found before fitting for the central position
        self.found_peak = [0, 0]
        self.found_low_res = [0, 0]

        # Processing options
        # Use the ROI rather than finding the ranges
        self.use_roi = configuration.use_roi
        self.use_roi_actual = False

        # Use the 2nd ROI as the background, if available
        self.use_roi_bck = configuration.use_roi_bck

        # Use background as a region on each side of the peak
        self.use_tight_bck = configuration.use_tight_bck
        # Width of the background on each side of the peak
        self.bck_offset = configuration.bck_offset

        # Update the specular peak range after finding the peak
        # within the ROI
        self.update_peak_range = configuration.update_peak_range

        self.wl_bandwidth = configuration.wl_bandwidth
        self.tof_range = self.get_tof_range(ws)
        self.calculated_scattering_angle = 0.0
        self.theta_d = 0.0
        t_0 = time.time()
        self.determine_data_type(ws)
        logging.info("INSPECT: %s sec" % (time.time() - t_0))

    def get_tof_range(self, ws):
        """
        Determine TOF range from the data
        :param workspace ws: workspace to work with
        """
        run_object = ws.getRun()
        sample_detector_distance = run_object["SampleDetDis"].getStatistics().mean
        source_sample_distance = run_object["ModeratorSamDis"].getStatistics().mean
        # Check units
        if not run_object["SampleDetDis"].units in ["m", "meter"]:
            sample_detector_distance /= 1000.0
        if not run_object["ModeratorSamDis"].units in ["m", "meter"]:
            source_sample_distance /= 1000.0

        source_detector_distance = source_sample_distance + sample_detector_distance

        h = 6.626e-34  # m^2 kg s^-1
        m = 1.675e-27  # kg
        wl = run_object.getProperty("LambdaRequest").value[0]
        chopper_speed = run_object.getProperty("SpeedRequest1").value[0]
        wl_offset = 0
        cst = source_detector_distance / h * m
        half_width = self.wl_bandwidth / 2.0
        tof_min = cst * (wl + wl_offset * 60.0 / chopper_speed - half_width * 60.0 / chopper_speed) * 1e-4
        tof_max = cst * (wl + wl_offset * 60.0 / chopper_speed + half_width * 60.0 / chopper_speed) * 1e-4

        self.tof_range = [tof_min, tof_max]
        return [tof_min, tof_max]

    def process_roi(self, ws):
        """
        Process the ROI information and determine the peak
        range, the low-resolution range, and the background range.

        Starting in June 2018, with the DAS upgrade, the ROIs are
        specified with a start/width rather than start/stop.

        :param workspace ws: workspace to work with
        """
        roi_peak = [0, 0]
        roi_low_res = [0, 0]

        # Read ROI 1
        roi1_valid = True
        if "ROI1StartX" in ws.getRun():
            roi1_x0 = ws.getRun()["ROI1StartX"].getStatistics().mean
            roi1_y0 = ws.getRun()["ROI1StartY"].getStatistics().mean
            if "ROI1SizeX" in ws.getRun():
                size_x = ws.getRun()["ROI1SizeX"].getStatistics().mean
                size_y = ws.getRun()["ROI1SizeY"].getStatistics().mean
                roi1_x1 = roi1_x0 + size_x
                roi1_y1 = roi1_y0 + size_y
            else:
                roi1_x1 = ws.getRun()["ROI1EndX"].getStatistics().mean
                roi1_y1 = ws.getRun()["ROI1EndY"].getStatistics().mean
            if roi1_x1 > roi1_x0:
                peak1 = [int(roi1_x0), int(roi1_x1)]
            else:
                peak1 = [int(roi1_x1), int(roi1_x0)]
            if roi1_y1 > roi1_y0:
                low_res1 = [int(roi1_y0), int(roi1_y1)]
            else:
                low_res1 = [int(roi1_y1), int(roi1_y0)]
            if peak1 == [0, 0] and low_res1 == [0, 0]:
                roi1_valid = False

            # Read ROI 2
            if "ROI2StartX" in ws.getRun():
                roi2_valid = True
                roi2_x0 = ws.getRun()["ROI2StartX"].getStatistics().mean
                roi2_y0 = ws.getRun()["ROI2StartY"].getStatistics().mean
                if "ROI2SizeX" in ws.getRun():
                    size_x = ws.getRun()["ROI2SizeX"].getStatistics().mean
                    size_y = ws.getRun()["ROI2SizeY"].getStatistics().mean
                    roi2_x1 = roi2_x0 + size_x
                    roi2_y1 = roi2_y0 + size_y
                else:
                    roi2_x1 = ws.getRun()["ROI2EndX"].getStatistics().mean
                    roi2_y1 = ws.getRun()["ROI2EndY"].getStatistics().mean
                if roi2_x1 > roi2_x0:
                    peak2 = [int(roi2_x0), int(roi2_x1)]
                else:
                    peak2 = [int(roi2_x1), int(roi2_x0)]
                if roi2_y1 > roi2_y0:
                    low_res2 = [int(roi2_y0), int(roi2_y1)]
                else:
                    low_res2 = [int(roi2_y1), int(roi2_y0)]
                if peak2 == [0, 0] and low_res2 == [0, 0]:
                    roi2_valid = False
            else:
                roi2_valid = False
        else:
            roi1_valid = False
            roi2_valid = False

        # Pick the ROI that describes the reflectivity peak
        if roi1_valid and not roi2_valid:
            roi_peak = peak1
            roi_low_res = low_res1
            roi_background = [0, 0]
        elif roi2_valid and not roi1_valid:
            roi_peak = peak2
            roi_low_res = low_res2
            roi_background = [0, 0]
        elif roi1_valid and roi2_valid:
            # If ROI 2 is within ROI 1, treat it as the peak,
            # otherwise, use ROI 1
            if peak1[0] >= peak2[0] and peak1[1] <= peak2[1]:
                roi_peak = peak1
                roi_low_res = low_res1
            elif peak2[0] >= peak1[0] and peak2[1] <= peak1[1]:
                roi_peak = peak2
                roi_low_res = low_res2

            else:
                roi_peak = peak1
                roi_low_res = low_res1

        # After all this, update the ROI according to reduction options
        self.roi_peak = roi_peak
        self.roi_low_res = roi_low_res
        self.meta_data_peak2 = peak2

        if self.force_bck_roi == True:
            self.background = peak2
            self.roi_background = peak2

    def determine_data_type(self, ws):
        """
        Inspect the data and determine peak locations
        and data type.
        :param workspace ws: Workspace to inspect
        """
        # Skip empty data entries
        if ws.getNumberEvents() < self.n_events_cutoff:
            self.data_type = -1
            logging.info("No data for %s %s" % (self.run_number, self.cross_section))
            return

        # Find reflectivity peak and low resolution ranges
        # fitter = Fitter(ws, True)
        fitter = Fitter2(ws)
        peak, low_res = fitter.fit_2d_peak()

        self.found_peak = copy.copy(peak)
        self.found_low_res = copy.copy(low_res)
        logging.info("Run %s [%s]: Peak found %s" % (self.run_number, self.cross_section, peak))
        logging.info("Run %s [%s]: Low-res found %s" % (self.run_number, self.cross_section, str(low_res)))

        # Process the ROI information
        try:
            self.process_roi(ws)
        except:
            logging.info("Could not process ROI\n%s" % sys.exc_info()[1])

        # Keep track of whether we actually used the ROI
        self.use_roi_actual = False

        # If we were asked to use the ROI but no peak is in it, use the peak we found
        # If we were asked to use the ROI and there's a peak in it, use the ROI
        if self.use_roi and not self.update_peak_range and not self.roi_peak == [0, 0]:
            logging.info("Using ROI peak range: [%s %s]" % (self.roi_peak[0], self.roi_peak[1]))
            self.use_roi_actual = True
            peak = copy.copy(self.roi_peak)
            if not self.roi_low_res == [0, 0]:
                low_res = copy.copy(self.roi_low_res)

        elif self.use_roi and self.update_peak_range and not self.roi_peak == [0, 0]:
            logging.info("Using fit peak range: [%s %s]" % (peak[0], peak[1]))

        # Background
        if self.use_tight_bck:
            bck_range = [int(max(0.0, peak[0] - self.bck_offset)), int(min(NX_PIXELS, peak[1] + self.bck_offset))]

        else:
            bck_range = self.background

        # Store the information we found
        self.peak_position = (peak[1] + peak[0]) / 2.0
        self.peak_range = [int(max(0, peak[0])), int(min(peak[1], NX_PIXELS))]
        self.low_res_range = [int(max(0, low_res[0])), int(min(low_res[1], NY_PIXELS))]
        self.background = [int(max(0, bck_range[0])), int(min(bck_range[1], NY_PIXELS))]

        # Computed scattering angle
        self.calculated_scattering_angle = api.MRGetTheta(ws, SpecularPixel=self.peak_position)
        self.calculated_scattering_angle *= 180.0 / math.pi

        # Determine whether we have a direct beam
        run_object = ws.getRun()
        try:
            self.is_direct_beam = run_object.getProperty("data_type").value[0] == 1
            self.data_type = 0 if self.is_direct_beam else 1
        except:
            self.is_direct_beam = False
            self.data_type = 1


def chi2(data, model):
    """Returns the chi^2 for a data set and model pair"""
    err = np.fabs(data)
    err[err <= 0] = 1
    return np.sum((data - model) ** 2 / err) / len(data)


class Fitter2(object):
    DEAD_PIXELS = 10

    def __init__(self, workspace):
        self.workspace = workspace
        self._prepare_data()

    def _prepare_data(self):
        """
        Read in the data and create arrays for fitting
        """
        # Prepare data to fit
        self.n_x = int(self.workspace.getInstrument().getNumberParameter("number-of-x-pixels")[0])
        self.n_y = int(self.workspace.getInstrument().getNumberParameter("number-of-y-pixels")[0])

        _integrated = api.Integration(InputWorkspace=self.workspace)
        signal = _integrated.extractY()
        self.z = np.reshape(signal, (self.n_x, self.n_y))
        self.y = np.arange(0, self.n_y)[self.DEAD_PIXELS : -self.DEAD_PIXELS]
        # 1D data x/y vs counts
        self.x_vs_counts = np.sum(self.z, 1)
        self.y_vs_counts = np.sum(self.z, 0)

        self.guess_x = np.argmax(self.x_vs_counts)
        self.guess_wx = 6.0

    def _scan_peaks(self):
        f1 = ndimage.gaussian_filter(self.x_vs_counts, 3)
        peaks, _ = find_peaks(f1)
        prom, _, _ = peak_prominences(f1, peaks)
        peaks_w, _, _, _ = peak_widths(f1, peaks)

        # The quality factor is the size of the peak (height*width) multiply by
        # a factor that peaks in the middle of the detector, where the peak usually is.
        nx = 304.0
        delta = 100.0
        mid_point = 150.0
        quality_pos = np.exp(-((mid_point - peaks) ** 2.0) / 2000.0)
        low_peaks = peaks < delta
        high_peaks = peaks > nx - delta
        quality_pos[low_peaks] = quality_pos[low_peaks] * (1 - np.abs(delta - peaks[low_peaks]) / delta) ** 3
        quality_pos[high_peaks] = quality_pos[high_peaks] * (1 - np.abs(nx - delta - peaks[high_peaks]) / delta) ** 3
        quality = -peaks_w * prom * quality_pos

        zipped = zip(peaks, peaks_w, quality, prom)
        ordered = sorted(zipped, key=lambda a: a[2])
        found_peaks = [p[0] for p in ordered]

        if found_peaks:
            #    self.guess_x = ordered[0][0]
            #    self.guess_ws = ordered[0][1]
            i_final = 0
            if (
                len(ordered) > 1
                and (ordered[0][2] - ordered[1][2]) / ordered[0][2] < 0.75
                and ordered[1][0] < ordered[0][0]
            ):
                i_final = 1
            self.guess_x = ordered[i_final][0]
            self.guess_ws = ordered[i_final][1]

        return found_peaks

    def fit_2d_peak(self):
        """Backward compatibility"""
        spec_peak = self.fit_peak()
        beam_peak = self.fit_beam_width()
        return spec_peak, beam_peak

    def fit_peak(self):
        self.peaks = self._scan_peaks()

        # Package the best results
        x_min = max(0, int(self.guess_x - np.fabs(self.guess_wx)))
        x_max = min(self.n_x - 1, int(self.guess_x + np.fabs(self.guess_wx)))

        return [x_min, x_max]

    def gaussian_1d(self, value, *p):
        """
        1D Gaussian
        """
        A, center_x, width_x, background = p
        A = np.abs(A)
        values = A * np.exp(-((value - center_x) ** 2) / (2.0 * width_x**2))
        values += background
        return values

    def peak_derivative(self, value, *p):
        """
        Double Gaussian to fit the first derivative of a plateau/peak.
        """
        A, center_x, width_x, edge_width, background = p
        mu_right = center_x + width_x / 2.0
        mu_left = center_x - width_x / 2.0
        A = np.abs(A)
        values = A * np.exp(-((value - mu_left) ** 2) / (2.0 * edge_width**2)) - A * np.exp(
            -((value - mu_right) ** 2) / (2.0 * edge_width**2)
        )
        values += background
        return values

    def _perform_beam_fit(self, y_d, derivative, derivative_err, y_r=None, signal_r=None, gaussian_first=False):
        if gaussian_first:
            _running_err = np.sqrt(signal_r)
            _gauss, _ = opt.curve_fit(
                self.gaussian_1d, y_r, signal_r, p0=[np.max(signal_r), 140, 50, 0], sigma=_running_err
            )
            p0 = [np.max(derivative), _gauss[1], 2.0 * _gauss[2], 5, 0]
        else:
            p0 = [np.max(derivative), 140, 60, 5, 0]

        # p = A, center_x, width_x, edge_width, background
        _coef, _ = opt.curve_fit(self.peak_derivative, y_d, derivative, p0=p0, sigma=derivative_err)
        return _coef

    def fit_beam_width(self):
        """
        Fit the data distribution in y and get its range.
        """
        peak_min = 0
        peak_max = self.n_x
        try:
            _integral = [np.sum(self.y_vs_counts[:i]) for i in range(len(self.y_vs_counts))]
            _running = 0.1 * np.convolve(self.y_vs_counts, np.ones(10), mode="valid")
            _deriv = np.asarray([_running[i + 1] - _running[i] for i in range(len(_running) - 1)])
            _deriv_err = np.sqrt(_running)[:-1]
            _deriv_err[_deriv_err < 1] = 1
            _y = np.arange(len(self.y_vs_counts))[5:-5]

            _coef = self._perform_beam_fit(_y, _deriv, _deriv_err, gaussian_first=False)
            peak_min = _coef[1] - np.abs(_coef[2]) / 2.0 - 2.0 * np.abs(_coef[3])
            peak_max = _coef[1] + np.abs(_coef[2]) / 2.0 + 2.0 * np.abs(_coef[3])
            if peak_max - peak_min < 10:
                logging.error("Low statisting: trying again")
                _y_running = self.y[5:-4]
                _coef = self._perform_beam_fit(_y, _deriv, _deriv_err, _y_running, _running, gaussian_first=True)

            self.guess_y = _coef[1]
            self.guess_wy = (peak_max - peak_min) / 2.0
            peak_min = max(peak_min, self.DEAD_PIXELS)
            peak_max = min(peak_max, self.n_x - self.DEAD_PIXELS)
        except:
            logging.error("Could not fit the beam width")
        return [peak_min, peak_max]
