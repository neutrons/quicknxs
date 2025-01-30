"""
    Methods used to process data, usually calling Mantid
"""
# pylint: disable=invalid-name, too-many-instance-attributes, line-too-long, multiple-statements, bare-except, protected-access, wrong-import-position

import sys
import logging
import h5py
import math
import time

import mantid.simpleapi as api
import mantid
import numpy as np

from .instrument import Instrument
from .data_set import NexusMetaData


class NormalizeToUnityQCutoffError(Exception):
    """When normalizing to unity fails due to no data below Q cutoff"""

    pass


def generate_short_script(reduction_list):
    """
    Generate a simple reduction script for Mantid
    """
    if len(reduction_list) == 0:
        return "# No data in reduction list\n"

    xs = list(reduction_list[0].cross_sections.keys())[0]
    script = "# Mantid version %s\n" % mantid.__version__
    script += "# Date: %s\n\n" % time.strftime("%Y-%m-%d %H:%M:%S")
    script += "from mantid.simpleapi import *\n"

    logging.info("Cross section for script %s", xs)
    for i in range(len(reduction_list)):
        # If we couldn't calculate the reflectivity, we won't have a workspace available
        if reduction_list[i].cross_sections[xs].reflectivity_workspace is None:
            logging.info("  No workspace: %s", i)
            continue

        ws_name = "r%s" % reduction_list[i].cross_sections[xs].number

        # NOTE: It is possible that only one cross section is present in the run, therefore
        #       api.mtd[ws_name] could be a Workspace2D instead of a workspace group.
        #       Given that a modernization process is scheduled, we are going to do a ducktape
        #       fixing here.
        contain_single_crosssection = False
        try:
            if len(api.mtd[ws_name]) == 0:
                logging.info("  No entry in %s workspace group", ws_name)
        except TypeError:
            # NOTE: based on the information we have, the only possible data type here should be
            #       a workspace2D
            contain_single_crosssection = True
            logging.info("  single cross sectoin in %s (Workspace2D)", ws_name)
        # short-hand it
        ws_iterable = [api.mtd[ws_name]] if contain_single_crosssection else api.mtd[ws_name]

        script += "# Run:%s\n" % reduction_list[i].cross_sections[xs].number
        script_text = api.GeneratePythonScript(ws_iterable[0])
        script += script_text.replace(", ", ",\n                                ")
        script += "\n\n"
        script += "# Crop points on each end\n"
        q = ws_iterable[0].readX(0)
        p_0 = reduction_list[i].cross_sections[xs].configuration.cut_first_n_points
        p_f = len(q) - reduction_list[i].cross_sections[xs].configuration.cut_last_n_points - 1
        q0 = q[p_0]
        qf = q[p_f]
        logging.info("%s %s %s %s", q0, qf, p_0, p_f)

        for item in ws_iterable:
            script += "CropWorkspace(InputWorkspace='%s', XMin=%s, XMax=%s, " % (str(item), q0, qf)
            script += "OutputWorkspace='%s')\n" % str(item)
            script += "Scale(InputWorkspace='%s', Operation='Multiply', " % str(item)
            script += "Factor=%s, " % reduction_list[i].cross_sections[xs].configuration.scaling_factor
            script += "OutputWorkspace='%s')\n\n" % str(item)

    return script


def generate_script(reduction_list, pol_state):
    """
    Generate a Mantid script for the reflectivity reduction

    :param list reduction_list: list of NexusData objects
    :param str pol_state: cross-section name
    """
    ws_list = get_scaled_workspaces(reduction_list, pol_state)

    # If the reflectivity calculation failed, we may not have data to work with
    # for this cross-section.
    if not ws_list:
        return ""

    script = "# Cross-section: %s\n" % pol_state
    for ws in ws_list:
        script += "# Run:%s\n" % ws.getRunNumber()
        script_text = api.GeneratePythonScript(ws)
        script += script_text.replace(", ", ",\n                                ")
        script += "\n"
    return script


def stitch_reflectivity(reduction_list, xs=None, normalize_to_unity=True, q_cutoff=0.01):
    """
    Stitch and normalize data sets

    :param string xs: name of the cross-section to use
    :param bool normalize_to_unity: if True, the specular ridge will be normalized to 1
    """
    if not reduction_list:
        return []

    # Select the cross-section we will use to determine the scaling factors
    if xs is None:
        xs = list(reduction_list[0].cross_sections.keys())[0]

    # First, determine the overall scaling factor as needed
    scaling_factor = 1.0
    if normalize_to_unity:
        idx_list = reduction_list[0].cross_sections[xs].q < q_cutoff
        total = 0
        weights = 0
        for i in range(len(reduction_list[0].cross_sections[xs]._r)):
            if idx_list[i]:
                w = 1.0 / float(reduction_list[0].cross_sections[xs]._dr[i]) ** 2
                total += w * float(reduction_list[0].cross_sections[xs]._r[i])
                weights += w
        if weights > 0 and total > 0:
            scaling_factor = weights / total
        reduction_list[0].set_parameter("scaling_factor", scaling_factor)
    else:
        scaling_factor = reduction_list[0].cross_sections[xs].configuration.scaling_factor

    # Stitch the data sets together
    _previous_ws = None
    running_scale = scaling_factor
    scaling_factors = [running_scale]

    for i in range(len(reduction_list)):
        n_total = len(reduction_list[i].cross_sections[xs].q)
        p_0 = reduction_list[i].cross_sections[xs].configuration.cut_first_n_points
        p_n = n_total - reduction_list[i].cross_sections[xs].configuration.cut_last_n_points
        ws = api.CreateWorkspace(
            DataX=reduction_list[i].cross_sections[xs].q[p_0:p_n],
            DataY=reduction_list[i].cross_sections[xs]._r[p_0:p_n],
            DataE=reduction_list[i].cross_sections[xs]._dr[p_0:p_n],
        )
        ws.setDistribution(True)
        ws = api.ConvertToHistogram(ws)
        if _previous_ws is not None:
            _, scale = api.Stitch1D(_previous_ws, ws)
            running_scale *= scale
            scaling_factors.append(running_scale)
            reduction_list[i].set_parameter("scaling_factor", running_scale)
        _previous_ws = api.CloneWorkspace(ws)

    return scaling_factors


def _prepare_workspace_for_stitching(cross_sections, xs_input, global_fit, ws_name):
    """
    Create a workspace from a CrossSectionData object that we
    can call Stitch1D on.
    :param dict cross_sections: dictionary with cross-section name and CrossSectionData objects
    :param str xs: cross-section to use
    :param bool global_fit: if True, merge data from all cross-sections
    :param str ws_name: output workspace name
    """
    if global_fit:
        xs_names = cross_sections.keys()
    else:
        xs_names = [xs_input]

    ws_list = []
    for xs in xs_names:
        cross_section = cross_sections[xs]
        n_total = len(cross_section.q)
        p_0 = cross_section.configuration.cut_first_n_points
        p_n = n_total - cross_section.configuration.cut_last_n_points
        ws_xs = api.CreateWorkspace(
            DataX=cross_section.q[p_0:p_n],
            DataY=cross_section._r[p_0:p_n],
            DataE=cross_section._dr[p_0:p_n],
            OutputWorkspace="tmp_prepare_stitching_" + xs,
        )
        ws_list.append(str(ws_xs))

    ws_merge = api.MergeRuns(ws_list)
    ws_merge.setDistribution(True)
    ws = api.ConvertToHistogram(ws_merge, OutputWorkspace=ws_name)
    # Delete temporary workspaces
    api.DeleteWorkspaces(ws_list)
    api.DeleteWorkspace(ws_merge)
    return ws


def _get_stitching_overlap_region(ws_lo, ws_hi, n_points_outside_overlap=3):
    """Get the x boundary values of the overlap region between two workspaces

    :param ~mantid.api.MatrixWorkspace ws_lo: the low-Q reflectivity curve
    :param ~mantid.api.MatrixWorkspace ws_hi: the high-Q reflectivity curve
    :param int n_points_outside_overlap: number of additional points on each end of the overlap region to include in the fit
    :returns: tuple (min, max) defining the overlap region
    :raises ValueError: if the x-range of workspace ws_lo is higher than the x-range of ws_hi
    """
    if ws_lo.readX(0)[0] > ws_hi.readX(0)[0] or ws_lo.readX(0)[-1] > ws_hi.readX(0)[-1]:
        raise ValueError("x-range for ws_lo must not be higher than x-range for ws_hi")

    # get initial boundaries from lowest Q of the high-Q curve and highest Q of the low-Q curve
    x_lo_max = ws_lo.readX(0)[-1]
    x_hi_min = ws_hi.readX(0)[0]

    if x_hi_min > x_lo_max:
        # no overlap, use only extra points
        min_idx_lo = -n_points_outside_overlap
        max_idx_hi = n_points_outside_overlap - 1
    else:
        # use overlap plus extra points
        min_idx_lo = np.where(ws_lo.readX(0) >= x_hi_min)[0][0]
        min_idx_lo = max(min_idx_lo - n_points_outside_overlap, 0)
        max_idx_hi = np.where(ws_hi.readX(0) <= x_lo_max)[0][-1]
        max_idx_hi = min(max_idx_hi + n_points_outside_overlap, ws_hi.readX(0).size - 1)

    # get x values corresponding to the found indices
    xmin = ws_lo.readX(0)[min_idx_lo]
    xmax = ws_hi.readX(0)[max_idx_hi]

    return xmin, xmax


def _get_polynomial_fit_stitching_scaling_factor(ws_lo, ws_hi, n_polynom, n_points_outside_overlap=3):
    """Get the scaling factor for stitching two curves by fitting a polynomial and a scaling factor

    For example, if the polynomial degree is 3, the scaling factor is obtained by minimizing the function

    f(ws_lo, ws_hi) = sum_{ws_lo}{A0 + A1*x_i + A2*x_i^2 + A3*x_i^3} +
        scaling_factor * sum_{ws_hi}{A0 + A1*x_i + A2*x_i^2 + A3*x_i^3}

    where the independent variables are A0, A1, A2, A3 and scaling_factor.

    :param ~mantid.api.MatrixWorkspace ws_lo: Low-Q reflectivity curve
    :param ~mantid.api.MatrixWorkspace ws_hi: High-Q reflectivity curve
    :param int n_polynom: Degree of the polynomial to fit the curves to
    :param int n_points_outside_overlap: Number of additional points on each end of the overlap region to include in the fit
    :returns: dictionary with keys `scale_factor_value`, `scale_factor_error`, `polynomial_coeffients`
    :raises RunTimeError: If there are too few data points compared to the number of independent variables
    :raises ValueError: If the x-range of workspace ws_lo is higher than the x-range of ws_hi
    """
    # crop to the overlap region of the curves plus extra points
    xmin, xmax = _get_stitching_overlap_region(ws_lo, ws_hi, n_points_outside_overlap)
    ws_lo_crop = api.CropWorkspace(InputWorkspace=ws_lo, XMin=xmin, XMax=xmax)
    ws_hi_crop = api.CropWorkspace(InputWorkspace=ws_hi, XMin=xmin, XMax=xmax)

    # build the strings to represent the polynomial, initial values and ties in the Mantid function definition
    formula_str = "A0"
    initial_val_str = "A0=1"
    ties_str = "f1.A0=f0.A0"
    for i in range(1, n_polynom + 1):
        formula_str += "+A{}*x^{}".format(i, i)  # "A0 + A1*x + A2*x^2 + ..."
        initial_val_str += ", A{}=1".format(i)  # "A0=1, A1=1, ..."
        ties_str += ",f1.A{}=f0.A{}".format(i, i)  # "f1.A0=f0.A0, f1.A1=f0.A1, ..."

    poly_func = ";name=UserFunction, Formula={}, {}, $domains=0".format(formula_str, initial_val_str)
    scaled_poly_func = ";name=UserFunction, Formula=poly_scale*({}), poly_scale=1, {}, $domains=1".format(
        formula_str, initial_val_str
    )
    ties = ";ties=({})".format(ties_str)
    multi_func = "composite=MultiDomainFunction, NumDeriv=1" + poly_func + scaled_poly_func + ties

    # fit MultiDomain function to the low-Q and high-Q workspaces
    fit = api.Fit(
        Function=multi_func,
        InputWorkspace=ws_lo_crop,
        WorkspaceIndex=0,
        InputWorkspace_1=ws_hi_crop,
        WorkspaceIndex_1=0,
        Output="fit",
    )

    # the scaling factor poly_scale scaled the polynomial to match the high-Q reflectivity curve, therefore, take the
    # inverse to get the scaling factor for matching the high-Q reflectivity curve with the low-Q curve
    output = {}
    i_scale = n_polynom + 1
    poly_scale = fit.Function.function.getParameterValue(i_scale)
    poly_scale_error = fit.Function.function.getError(i_scale)
    output["scale_factor_value"] = 1 / poly_scale
    output["scale_factor_error"] = poly_scale_error / poly_scale**2
    output["polynomial_coeff"] = fit.OutputParameters.column(1)[: n_polynom + 1]

    # delete temporary workspaces
    api.DeleteWorkspace(ws_lo_crop)
    api.DeleteWorkspace(ws_hi_crop)

    return output


def smart_stitch_reflectivity(
    reduction_list, xs=None, normalize_to_unity=True, q_cutoff=0.01, global_fit=False, poly_degree=None, poly_points=3
):
    """
    Stitch and normalize data sets

    :param list[NexusData] reduction_list: list of data sets to stitch
    :param string xs: name of the cross-section to use for the first data set
    :param bool normalize_to_unity: if `True`, the specular ridge will be normalized to 1
    :param float q_cutoff: used if `normalize_to_unity` = `True`, data with q < `q_cutoff` are part of the specular ridge
    :param bool global_fit: if `True`, use data from all cross-sections to calculate scaling factors
    :param int poly_degree: if not `None`, find the scaling factor by simultaneously fitting a polynomial and scaling factor to the two curves
    :param int poly_points: number of additional points on each end of the overlap region to include in the fit
    :returns: tuple (list of scaling factors, list of scaling factor errors)
    :raises: NormalizeToUnityQCutoffError: if `normalize_to_unity` = `True`, but there is no data below `q_cutoff`
    """
    if not reduction_list:
        return []

    # Select the cross-section we will use to determine the scaling factors
    if xs is None:
        xs = list(reduction_list[0].cross_sections.keys())[0]

    # First, determine the overall scaling factor as needed
    scaling_factor = 1.0
    scaling_error = 0.0
    if normalize_to_unity:
        # Calculate scaling factor for normalizing the specular ridge to 1
        idx_list = reduction_list[0].cross_sections[xs].q < q_cutoff
        if not any(idx_list):
            raise NormalizeToUnityQCutoffError(
                """No data below Q cutoff.\n
                Critical Q cutoff: {}\n
                Smallest Q value: {:.5f}""".format(
                    q_cutoff, reduction_list[0].cross_sections[xs].q.min()
                )
            )
        total = 0
        weights = 0
        for i in range(len(reduction_list[0].cross_sections[xs]._r)):
            if idx_list[i]:
                w = 1.0 / float(reduction_list[0].cross_sections[xs]._dr[i]) ** 2
                total += w * float(reduction_list[0].cross_sections[xs]._r[i])
                weights += w
        if weights > 0 and total > 0:
            # Since weighted_average = \sum{ r_i / dr_i^2 } / \sum{ 1 / dr_i^2 }, the error is
            # weighted_average_error = 1 / \sqrt{ \sum{ 1 / dr_i^2 } } = 1 / \sqrt{weights}
            weighted_average = total / weights
            weighted_average_error = 1.0 / np.sqrt(weights)
            # Scaling factor S = 1 / u, error dS = du / u^2
            scaling_factor = 1 / weighted_average
            scaling_error = weighted_average_error / weighted_average**2
        reduction_list[0].set_parameter("scaling_factor", scaling_factor)
        reduction_list[0].set_parameter("scaling_error", scaling_error)
    else:
        scaling_factor = reduction_list[0].cross_sections[xs].configuration.scaling_factor

    # Stitch the data sets together
    running_scale = scaling_factor
    running_error = scaling_error
    scaling_factors = [running_scale]
    scaling_errors = [running_error]

    for i in range(len(reduction_list) - 1):

        # Low-Q data set
        _previous_ws = _prepare_workspace_for_stitching(
            reduction_list[i].cross_sections, xs, global_fit, "low_q_workspace"
        )
        # High-Q data set
        ws = _prepare_workspace_for_stitching(reduction_list[i + 1].cross_sections, xs, global_fit, "high_q_workspace")

        if isinstance(poly_degree, int) and poly_degree > 0:
            output_poly = _get_polynomial_fit_stitching_scaling_factor(_previous_ws, ws, poly_degree, poly_points)
            scale = output_poly["scale_factor_value"]
            scale_error = output_poly["scale_factor_error"]
        else:
            _, scale = api.Stitch1D(_previous_ws, ws, OutputScalingWorkspace="ws_stitching_scale")
            scale_error = api.mtd["ws_stitching_scale"].readE(0)[0]

        # Calculate the error in the product of two scaling factors, f1 * f2, as \sqrt{(df2 * f1)^2 + (df1 * f2)^2}
        running_error = np.sqrt((scale_error * running_scale) ** 2 + (running_error * scale) ** 2)
        scaling_errors.append(running_error)
        reduction_list[i + 1].set_parameter("scaling_error", running_error)
        running_scale *= scale
        scaling_factors.append(running_scale)
        reduction_list[i + 1].set_parameter("scaling_factor", running_scale)

    return scaling_factors, scaling_errors


def merge_reflectivity(reduction_list, xs, q_min=0.001, q_step=-0.01):
    """
    Combine the workspaces for a given cross-section into a single workspace.

    TODO: trim workspaces
        trim_first = [item.cross_sections[pol_state].configuration.cut_first_n_points for item in self.data_manager.reduction_list]
        trim_last = [item.cross_sections[pol_state].configuration.cut_last_n_points for item in self.data_manager.reduction_list]

    """
    ws_list = []
    scaling_factors = []
    q_max = q_min

    for i in range(len(reduction_list)):
        # If we couldn't calculate the reflectivity, we won't have a workspace available
        if reduction_list[i].cross_sections[xs].reflectivity_workspace is None:
            continue

        _, _q_max = reduction_list[i].get_q_range()
        q_max = max(q_max, _q_max)
        ws_name = str(reduction_list[i].cross_sections[xs].reflectivity_workspace)
        # Stitch1DMany only scales workspaces relative to the first one
        if i == 0:
            api.Scale(
                InputWorkspace=ws_name,
                OutputWorkspace=ws_name + "_histo",
                factor=reduction_list[i].cross_sections[xs].configuration.scaling_factor,
                Operation="Multiply",
            )
            api.ConvertToHistogram(InputWorkspace=ws_name + "_histo", OutputWorkspace=ws_name + "_histo")
        else:
            scaling_factors.append(reduction_list[i].cross_sections[xs].configuration.scaling_factor)
            api.ConvertToHistogram(InputWorkspace=ws_name, OutputWorkspace=ws_name + "_histo")
        ws_list.append(ws_name + "_histo")
        params = "%s, %s, %s" % (q_min, q_step, q_max)

    if len(ws_list) > 1:
        merged_ws, _ = api.Stitch1DMany(
            InputWorkspaces=ws_list,
            Params=params,
            UseManualScaleFactors=True,
            ManualScaleFactors=scaling_factors,
            OutputWorkspace=ws_name + "_merged",
        )
        # sort WorkspaceGroup by theta
        merged_ws = sorted(merged_ws, key=lambda ws: ws.getRun().getProperty("two_theta").value)
    elif len(ws_list) == 1:
        merged_ws = api.CloneWorkspace(ws_list[0], OutputWorkspace=ws_name + "_merged")
    else:
        return None

    # Remove temporary workspaces
    for ws in ws_list:
        api.DeleteWorkspace(ws)

    api.SaveAscii(InputWorkspace=merged_ws, Filename="/tmp/test.txt")
    return merged_ws


def get_scaled_workspaces(reduction_list, xs):
    """
    Return a list of scaled workspaces
    :param list reduction_list: list of NexusData objects
    :param str xs: cross-section name
    """
    ws_list = []

    for i in range(len(reduction_list)):
        # If we couldn't calculate the reflectivity, we won't have a workspace available
        if reduction_list[i].cross_sections[xs].reflectivity_workspace is None:
            continue

        ws_name = str(reduction_list[i].cross_sections[xs].reflectivity_workspace)
        ws_tmp = api.Scale(
            InputWorkspace=ws_name,
            OutputWorkspace=ws_name + "_scaled",
            factor=reduction_list[i].cross_sections[xs].configuration.scaling_factor,
            Operation="Multiply",
        )
        api.AddSampleLog(
            Workspace=ws_tmp,
            LogName="scaling_factor",
            LogText=str(reduction_list[i].cross_sections[xs].configuration.scaling_factor),
            LogType="Number",
            LogUnit="",
        )
        ws_list.append(ws_tmp)

    return ws_list


def extract_meta_data(file_path=None, cross_section_data=None, configuration=None):
    """
    Get mid Q-value from meta data
    :param str file_path: name of the file to read
    """
    meta_data = NexusMetaData()

    if cross_section_data is not None:
        meta_data.mid_q = Instrument.mid_q_value(cross_section_data.event_workspace)
        meta_data.is_direct_beam = cross_section_data.is_direct_beam
        return meta_data
    elif file_path is None:
        raise RuntimeError("Either a file path or a data object must be supplied")

    nxs = h5py.File(file_path, mode="r")
    keys = list(nxs.keys())
    keys.sort()
    nxs.close()

    if len(keys) == 0:
        logging.error("No entry in data file %s", file_path)
        return meta_data

    try:
        ws = api.LoadEventNexus(str(file_path), MetaDataOnly=True, NXentryName=str(keys[0]))
        meta_data.mid_q = Instrument.mid_q_value(ws)
        meta_data.is_direct_beam = Instrument.check_direct_beam(ws)
    except:
        logging.error("Exception extracting metadata")
        raise RuntimeError("Could not load file %s [%s]" % (file_path, keys[0]))

    return meta_data


def read_log(ws, name, target_units="", assumed_units=""):
    """
    Read a log value, taking care of units.
    If the log entry has no units, the target units are assumed.
    :param ws: workspace
    :param str name: name of the property to read
    :param str target_units: units to convert to
    :param str assumed_units: units of origin, if not specified in the log itself
    """
    _units = {
        "m": {
            "mm": 1000.0,
        },
        "mm": {
            "m": 0.001,
        },
        "deg": {
            "rad": math.pi / 180.0,
        },
        "rad": {
            "deg": 180.0 / math.pi,
        },
    }
    prop = ws.getRun().getProperty(name)
    value = prop.getStatistics().mean

    # If the property has units we don't recognize, use the assumed units
    units = prop.units if prop.units in _units else assumed_units

    if units in _units and target_units in _units[units]:
        return value * _units[units][target_units]
    return value
