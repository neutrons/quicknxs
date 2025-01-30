"""
Bare bones version of the scipy 1.1.0 code to find peaks, which we use on a system that cannot
run version 1.1.0 but only runs an old version.

Functions for identifying peaks in signals.

https://github.com/scipy/scipy/blob/master/LICENSE.txt

Copyright (c) 2001, 2002 Enthought, Inc.
All rights reserved.

Copyright (c) 2003-2017 SciPy Developers.
All rights reserved.
"""


import math
import numpy as np

__all__ = ["peak_prominences", "peak_widths", "find_peaks"]


def peak_prominences(x, peaks, wlen=None):
    """Calculate the prominence of each peak in a signal.

    .. versionadded:: 1.1.0

    References
    ----------

    Wikipedia Article for Topographic Prominence:
    https://en.wikipedia.org/wiki/Topographic_prominence
    """
    # Inner function expects `x` to be C-contiguous
    x = np.asarray(x, order="C", dtype=np.float64)
    if x.ndim != 1:
        raise ValueError("`x` must have exactly one dimension")

    peaks = np.asarray(peaks)
    if peaks.ndim == 2:
        peaks = peaks[0]
    if peaks.size == 0:
        # Empty arrays default to np.float64 but are valid input
        peaks = np.array([], dtype=np.intp)
    if peaks.ndim != 1:
        raise ValueError("`peaks` must have exactly one dimension")

    if wlen is None:
        wlen = -1  # Inner function expects int -> None == -1
    elif 1 < wlen:
        # Round up to next positive integer; rounding up to next odd integer
        # happens implicitly inside the inner function
        wlen = int(math.ceil(wlen))
    else:
        # Give feedback if wlen has unexpected value
        raise ValueError("`wlen` must be at larger than 1, was " + str(wlen))

    return _peak_prominences(x, peaks, wlen)


def peak_widths(x, peaks, rel_height=0.5, prominence_data=None, wlen=None):
    """
    Calculate the width of each peak in a signal.
    .. versionadded:: 1.1.0
    """
    # Inner function expects `x` to be C-contiguous
    x = np.asarray(x, order="C", dtype=np.float64)
    if x.ndim != 1:
        raise ValueError("`x` must have exactly one dimension")

    peaks = np.asarray(peaks)
    if peaks.size == 0:
        # Empty arrays default to np.float64 but are valid input
        peaks = np.array([], dtype=np.intp)
    if peaks.ndim != 1:
        print(peaks.ndim)
        raise ValueError("`peaks` must have exactly one dimension")

    if rel_height < 0.0:
        raise ValueError("`rel_height` must be greater or equal to 0.0")

    if prominence_data is None:
        # Calculate prominence if not supplied and use wlen if supplied.
        prominence_data = peak_prominences(x, peaks, wlen)

    return _peak_widths(x, peaks, rel_height, *prominence_data)


def _unpack_condition_args(interval, x, peaks):
    """
    Parse condition arguments for `find_peaks`.
    .. versionadded:: 1.1.0
    """
    try:
        imin, imax = interval
    except (TypeError, ValueError):
        imin, imax = (interval, None)

    # Reduce arrays if arrays
    if isinstance(imin, np.ndarray):
        if imin.size != x.size:
            raise ValueError("array size of lower interval border must match x")
        imin = imin[peaks]
    if isinstance(imax, np.ndarray):
        if imax.size != x.size:
            raise ValueError("array size of upper interval border must match x")
        imax = imax[peaks]

    return imin, imax


def _select_by_property(peak_properties, pmin, pmax):
    """
    Evaluate where the generic property of peaks confirms to an interval.
    .. versionadded:: 1.1.0
    """
    keep = np.ones(peak_properties.size, dtype=bool)
    if pmin is not None:
        keep &= pmin <= peak_properties
    if pmax is not None:
        keep &= peak_properties <= pmax
    return keep


def _select_by_peak_threshold(x, peaks, tmin, tmax):
    """
    Evaluate which peaks fulfill the threshold condition.
    .. versionadded:: 1.1.0
    """
    # Stack thresholds on both sides to make min / max operations easier:
    # tmin is compared with the smaller, and tmax with the greater thresold to
    # each peak's side
    stacked_thresholds = np.vstack([x[peaks] - x[peaks - 1], x[peaks] - x[peaks + 1]])
    keep = np.ones(peaks.size, dtype=bool)
    if tmin is not None:
        min_thresholds = np.min(stacked_thresholds, axis=0)
        keep &= tmin <= min_thresholds
    if tmax is not None:
        max_thresholds = np.max(stacked_thresholds, axis=0)
        keep &= max_thresholds <= tmax

    return keep, stacked_thresholds[0], stacked_thresholds[1]


def find_peaks(x, height=None, threshold=None, distance=None, prominence=None, width=None, wlen=None, rel_height=0.5):
    """
    Find peaks inside a signal based on peak properties.
    .. versionadded:: 1.1.0
    """
    # _argmaxima1d expects array of dtype 'float64'
    x = np.asarray(x, dtype=np.float64)
    if x.ndim != 1:
        raise ValueError("`x` must have exactly one dimension")
    if distance is not None and distance < 1:
        raise ValueError("`distance` must be greater or equal to 1")

    peaks = _argmaxima1d(x)
    properties = {}

    if height is not None:
        # Evaluate height condition
        peak_heights = x[peaks]
        hmin, hmax = _unpack_condition_args(height, x, peaks)
        keep = _select_by_property(peak_heights, hmin, hmax)
        peaks = peaks[keep]
        properties["peak_heights"] = peak_heights[keep]

    if threshold is not None:
        # Evaluate threshold condition
        tmin, tmax = _unpack_condition_args(threshold, x, peaks)
        keep, left_thresholds, right_thresholds = _select_by_peak_threshold(x, peaks, tmin, tmax)
        peaks = peaks[keep]
        properties["left_thresholds"] = left_thresholds
        properties["right_thresholds"] = right_thresholds
        properties = {key: array[keep] for key, array in properties.items()}

    if distance is not None:
        raise ValueError("find_peaks: distance option not available")

    if prominence is not None or width is not None:
        # Calculate prominence (required for both conditions)
        properties.update(zip(["prominences", "left_bases", "right_bases"], peak_prominences(x, peaks, wlen=wlen)))

    if prominence is not None:
        # Evaluate prominence condition
        pmin, pmax = _unpack_condition_args(prominence, x, peaks)
        keep = _select_by_property(properties["prominences"], pmin, pmax)
        peaks = peaks[keep]
        properties = {key: array[keep] for key, array in properties.items()}

    if width is not None:
        # Calculate widths
        properties.update(
            zip(
                ["widths", "width_heights", "left_ips", "right_ips"],
                peak_widths(
                    x,
                    peaks,
                    rel_height,
                    (properties["prominences"], properties["left_bases"], properties["right_bases"]),
                ),
            )
        )
        # Evaluate width condition
        wmin, wmax = _unpack_condition_args(width, x, peaks)
        keep = _select_by_property(properties["widths"], wmin, wmax)
        peaks = peaks[keep]
        properties = {key: array[keep] for key, array in properties.items()}

    return np.asarray(peaks), properties


# The following code belongs in _peak_finding_utils #####################################


def _argmaxima1d(x):
    """
    Find local maxima in a 1D array.
    .. versionadded:: 1.1.0
    """
    # Preallocate, there can't be more maxima than half the size of `x`
    midpoints = np.empty(x.shape[0] // 2, dtype=np.intp)
    left_edges = np.empty(x.shape[0] // 2, dtype=np.intp)
    right_edges = np.empty(x.shape[0] // 2, dtype=np.intp)
    m = 0  # Pointer to the end of valid area in allocated arrays

    i = 1  # Pointer to current sample, first one can't be maxima
    i_max = x.shape[0] - 1  # Last sample can't be maxima
    while i < i_max:
        # Test if previous sample is smaller
        if x[i - 1] < x[i]:
            i_ahead = i + 1  # Index to look ahead of current sample

            # Find next sample that is unequal to x[i]
            while i_ahead < i_max and x[i_ahead] == x[i]:
                i_ahead += 1

            # Maxima is found if next unequal sample is smaller than x[i]
            if x[i_ahead] < x[i]:
                left_edges[m] = i
                right_edges[m] = i_ahead - 1
                midpoints[m] = (left_edges[m] + right_edges[m]) // 2
                m += 1
                # Skip samples that can't be maximum
                i = i_ahead
        i += 1

    # Keep only valid part of array memory.
    midpoints.resize(m, refcheck=False)
    left_edges.resize(m, refcheck=False)
    right_edges.resize(m, refcheck=False)

    return midpoints  # , left_edges, right_edges


def _peak_prominences(x, peaks, wlen):
    """
    Calculate the prominence of each peak in a signal.
    """
    show_warning = False
    prominences = np.empty(peaks.shape[0], dtype=np.float64)
    left_bases = np.empty(peaks.shape[0], dtype=np.intp)
    right_bases = np.empty(peaks.shape[0], dtype=np.intp)

    for peak_nr in range(peaks.shape[0]):
        peak = peaks[peak_nr]
        i_min = 0
        i_max = x.shape[0] - 1
        if not i_min <= peak <= i_max:
            raise ValueError("peak {} is not a valid index for `x`".format(peak))

        if 2 <= wlen:
            # Adjust window around the evaluated peak (within bounds);
            # if wlen is even the resulting window length is is implicitly
            # rounded to next odd integer
            i_min = max(peak - wlen // 2, i_min)
            i_max = min(peak + wlen // 2, i_max)

        # Find the left base in interval [i_min, peak]
        i = left_bases[peak_nr] = peak
        left_min = x[peak]
        while i_min <= i and x[i] <= x[peak]:
            if x[i] < left_min:
                left_min = x[i]
                left_bases[peak_nr] = i
            i -= 1

        # Find the right base in interval [peak, i_max]
        i = right_bases[peak_nr] = peak
        right_min = x[peak]
        while i <= i_max and x[i] <= x[peak]:
            if x[i] < right_min:
                right_min = x[i]
                right_bases[peak_nr] = i
            i += 1

        prominences[peak_nr] = x[peak] - max(left_min, right_min)
        if prominences[peak_nr] == 0:
            show_warning = True

    if show_warning:
        print("some peaks have a prominence of 0")
    # Return memoryviews as ndarrays
    return np.asarray(prominences), left_bases, right_bases


def _peak_widths(x, peaks, rel_height, prominences, left_bases, right_bases):
    """
    Calculate the width of each each peak in a signal.
    """

    if rel_height < 0:
        raise ValueError("`rel_height` must be greater or equal to 0.0")
    if not (peaks.shape[0] == prominences.shape[0] == left_bases.shape[0] == right_bases.shape[0]):
        raise ValueError("arrays in `prominence_data` must have the same shape " "as `peaks`")

    show_warning = False
    widths = np.empty(peaks.shape[0], dtype=np.float64)
    width_heights = np.empty(peaks.shape[0], dtype=np.float64)
    left_ips = np.empty(peaks.shape[0], dtype=np.float64)
    right_ips = np.empty(peaks.shape[0], dtype=np.float64)

    for p in range(peaks.shape[0]):
        i_min = left_bases[p]
        i_max = right_bases[p]
        peak = peaks[p]
        # Validate bounds and order
        if not 0 <= i_min <= peak <= i_max < x.shape[0]:
            raise ValueError("prominence data is invalid for peak {}".format(peak))
        height = width_heights[p] = x[peak] - prominences[p] * rel_height

        # Find intersection point on left side
        i = peak
        while i_min < i and height < x[i]:
            i -= 1
        left_ip = i
        if x[i] < height:
            # Interpolate if true intersection height is between samples
            left_ip += (height - x[i]) / (x[i + 1] - x[i])

        # Find intersection point on right side
        i = peak
        while i < i_max and height < x[i]:
            i += 1
        right_ip = i
        if x[i] < height:
            # Interpolate if true intersection height is between samples
            right_ip -= (height - x[i]) / (x[i - 1] - x[i])

        widths[p] = right_ip - left_ip
        if widths[p] == 0:
            show_warning = True
        left_ips[p] = left_ip
        right_ips[p] = right_ip

    if show_warning:
        print("some peaks have a width of 0")
    return np.asarray(widths), width_heights, left_ips, right_ips
