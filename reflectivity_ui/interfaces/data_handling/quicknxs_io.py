# pylint: disable=bare-except, too-many-locals, too-many-statements, too-many-branches, wrong-import-order, too-many-arguments
"""
    Read and write quicknxs reduced files
"""
import re
import sys
import os
import time
import copy
import math
import logging
import numpy as np

import mantid

from ... import __version__
from ..configuration import Configuration


def _find_h5_data(filename):
    """
    Because we have legacy data and new data re-processed for QuickNXS, we have to
    ensure that we get the proper data file.
    """
    if filename.endswith(".nxs"):
        _new_filename = filename.replace("_histo.nxs", ".nxs.h5")
        _new_filename = _new_filename.replace("_event.nxs", ".nxs.h5")
        _new_filename = _new_filename.replace("data", "nexus")
        if os.path.isfile(_new_filename):
            logging.warning("Using %s" % _new_filename)
            return _new_filename
    return filename


def write_reflectivity_header(peak_reduction_lists, active_list_index, direct_beam_list, output_path, pol_state):
    """
    Write out reflectivity header in a format readable by QuickNXS

    Parameters
    ----------
    peak_reduction_lists: dict[int, list[~reflectivity_ui.interfaces.data_handling.data_set.NexusData]]
        All reduction lists to include as additional peaks in the header
    active_list_index: int
        The index of the reduction list that the output reflectivity data is for
    direct_beam_list: list[~reflectivity_ui.interfaces.data_handling.data_set.NexusData]
        Direct beam list
    output_path: str
        Output file path
    pol_state: str
        Descriptor for the polarization state
    """
    # Sanity check
    if active_list_index not in peak_reduction_lists or not peak_reduction_lists[active_list_index]:
        return

    reduction_list = peak_reduction_lists[active_list_index]

    direct_beam_options = [
        "DB_ID",
        "P0",
        "PN",
        "x_pos",
        "x_width",
        "y_pos",
        "y_width",
        "bg_pos",
        "bg_width",
        "dpix",
        "tth",
        "number",
        "File",
    ]
    dataset_options = [
        "scale",
        "P0",
        "PN",
        "x_pos",
        "x_width",
        "y_pos",
        "y_width",
        "bg_pos",
        "bg_width",
        "fan",
        "dpix",
        "tth",
        "number",
        "DB_ID",
        "File",
    ]

    fd = open(output_path, "w")
    fd.write("# Datafile created by QuickNXS %s\n" % __version__)
    fd.write("# Datafile created using Mantid %s\n" % mantid.__version__)
    fd.write("# Date: %s\n" % time.strftime("%Y-%m-%d %H:%M:%S"))
    fd.write("# Type: Specular\n")
    run_list = [str(item.number) for item in reduction_list]
    fd.write("# Input file indices: %s\n" % ",".join(run_list))
    fd.write("# Extracted states: %s\n" % pol_state)
    fd.write("#\n")
    fd.write("# [Direct Beam Runs]\n")
    toks = ["%8s" % item for item in direct_beam_options]
    fd.write("# %s\n" % "  ".join(toks))

    # Get the list of cross-sections
    pol_list = list(reduction_list[0].cross_sections.keys())
    if not pol_list:
        logging.error("No data found in run %s", reduction_list[0].number)
        return

    # Direct beam section
    i_direct_beam = 0
    for data_set in reduction_list:
        run_object = data_set.cross_sections[pol_list[0]].reflectivity_workspace.getRun()
        normalization_run = run_object.getProperty("normalization_run").value
        if normalization_run == "None":
            continue
        direct_beam = None
        for db_i in direct_beam_list:
            if str(db_i.number) == str(normalization_run):
                direct_beam = db_i
        if direct_beam is None:
            continue
        db_pol = list(direct_beam.cross_sections.keys())[0]
        conf = direct_beam.cross_sections[db_pol].configuration
        i_direct_beam += 1
        dpix = run_object.getProperty("normalization_dirpix").value
        filename = run_object.getProperty("normalization_file_path").value

        item = dict(
            DB_ID=i_direct_beam,
            tth=0,
            P0=0,
            PN=0,
            x_pos=conf.peak_position,
            x_width=conf.peak_width,
            y_pos=conf.low_res_position,
            y_width=conf.low_res_width,
            bg_pos=conf.bck_position,
            bg_width=conf.bck_width,
            dpix=dpix,
            number=normalization_run,
            File=filename,
        )

        par_list = ["{%s}" % p for p in direct_beam_options]
        template = "# %s\n" % "  ".join(par_list)
        config_value_dict = {}
        for key in item:
            if isinstance(item[key], (bool, str)):
                config_value_dict[key] = "%8s" % item[key]
            else:
                config_value_dict[key] = "%8g" % item[key]
        fd.write(template.format(**config_value_dict))

    # Scattering data
    par_list = ["{%s}" % p for p in dataset_options]
    template = "# %s\n" % "  ".join(par_list)

    # Peak for reflectivity data
    fd.write("#\n")
    fd.write("# [Data Runs]\n")
    toks = ["%8s" % item for item in dataset_options]
    fd.write("# %s\n" % "  ".join(toks))
    i_direct_beam = 0
    for data_set in reduction_list:
        cross_section_data = data_set.cross_sections[pol_list[0]]
        config_value_dict = _get_cross_section_config_values(cross_section_data, i_direct_beam)
        fd.write(template.format(**config_value_dict))

    # All peaks
    for peak_index, peak_reduction_list in peak_reduction_lists.items():
        fd.write("#\n")
        fd.write(f"# [Peak {peak_index} Runs]\n")
        fd.write("# %s\n" % "  ".join(toks))
        i_direct_beam = 0
        for data_set in peak_reduction_list:
            cross_section_data = data_set.cross_sections[pol_list[0]]
            config_value_dict = _get_cross_section_config_values(cross_section_data, i_direct_beam)
            fd.write(template.format(**config_value_dict))

    fd.write("#\n")
    fd.write("# [Global Options]\n")
    fd.write("# name               value\n")
    conf = reduction_list[0].configuration
    sample_size = 10 if conf is None else conf.sample_size
    fd.write("# sample_length      %s\n" % str(sample_size))
    fd.write("# lock_direct_beam_y %s\n" % str(Configuration.lock_direct_beam_y))
    fd.write("#\n")
    fd.close()


def _get_cross_section_config_values(cross_section_data, i_direct_beam):
    """
    Get dictionary of cross-section data configuration to write to QuickNXS file

    Parameters
    ----------
    cross_section_data: ~reflectivity_ui.interfaces.data_handling.data_set.CrossSectionData
        Cross-section to get parameter values from
    i_direct_beam: int
        Current direct beam index in the reduction list

    Returns
    -------
    dict
    """
    conf = cross_section_data.configuration
    ws = cross_section_data.reflectivity_workspace
    run_object = ws.getRun()
    dpix = run_object.getProperty("DIRPIX").getStatistics().mean
    filename = run_object.getProperty("Filename").value
    constant_q_binning = run_object.getProperty("constant_q_binning").value
    scatt_pos = run_object.getProperty("specular_pixel").value
    scaling_factor = conf.scaling_factor
    # For some reason, the tth value that QuickNXS expects is offset.
    # It seems to be because that same offset is applied later in the QuickNXS calculation.
    # Correct tth here so that it can load properly in QuickNXS and produce the same result.
    tth = run_object.getProperty("two_theta").value
    det_distance = run_object["SampleDetDis"].getStatistics().mean / 1000.0
    direct_beam_pix = run_object["DIRPIX"].getStatistics().mean
    # Get pixel size from instrument properties
    if ws.getInstrument().hasParameter("pixel-width"):
        pixel_width = float(ws.getInstrument().getNumberParameter("pixel-width")[0]) / 1000.0
    else:
        pixel_width = 0.0007
    tth -= ((direct_beam_pix - scatt_pos) * pixel_width) / det_distance * 180.0 / math.pi
    normalization_run = run_object.getProperty("normalization_run").value
    if normalization_run == "None":
        db_id = 0
    else:
        i_direct_beam += 1
        db_id = i_direct_beam
    item = dict(
        scale=scaling_factor,
        DB_ID=db_id,
        P0=conf.cut_first_n_points,
        PN=conf.cut_last_n_points,
        tth=tth,
        fan=constant_q_binning,
        x_pos=conf.peak_position,
        x_width=conf.peak_width,
        y_pos=conf.low_res_position,
        y_width=conf.low_res_width,
        bg_pos=conf.bck_position,
        bg_width=conf.bck_width,
        dpix=dpix,
        number=str(ws.getRunNumber()),
        File=filename,
    )
    parameter_values = {}
    for key in item:
        if isinstance(item[key], str):
            parameter_values[key] = "%8s" % item[key]
        else:
            parameter_values[key] = "%8g" % item[key]
    return parameter_values


def write_reflectivity_data(output_path, data, col_names, as_5col=True):
    """
    Write out reflectivity header in a format readable by QuickNXS
    :param str output_path: output file path
    :param ndarray or list data: data to be written
    :param list col_names: list of column names
    :param bool as_5col: if True, a 5-column ascii will be written (theta is the last column)
    """
    with open(output_path, "a") as fd:
        # Determine how many columns to write
        if isinstance(data, list):
            four_cols = True
        else:
            four_cols = not as_5col and data.shape[1] > 4

        fd.write("# [Data]\n")
        if four_cols:
            toks = ["%12s" % item for item in col_names[:4]]
        else:
            toks = ["%12s" % item for item in col_names]
        fd.write("# %s\n" % "\t".join(toks))

        if isinstance(data, list):
            # [TOF][pixel][parameter]
            for tof_item in data:
                for pixel_item in tof_item:
                    np.savetxt(fd, pixel_item, delimiter="\t", fmt="%-18e")
                    fd.write("\n")
        else:
            if four_cols:
                np.savetxt(fd, data[:, :4], delimiter=" ", fmt="%-18e")
            else:
                np.savetxt(fd, data, delimiter="\t", fmt="%-18e")


def read_reduced_file(file_path, configuration=None):
    """
    Read in configurations from a reduced data file.
    :param str file_path: reduced data file
    """
    direct_beam_runs = []
    data_runs = []
    additional_peaks = []

    # reading is mocked. The file_path is the prefix of the path. File name is obtained from the mocked data
    with open(file_path, "r") as file_content:
        # Section identifier
        #   0: None
        #   1: direct beams
        #   2: data runs
        #   3: additional peak data runs
        #   4: global options
        _in_section = 0
        _file_start = True
        for line in file_content.readlines():
            if _file_start and not line.startswith("# Datafile created by QuickNXS"):
                raise RuntimeError("The selected file does not conform to the QuickNXS format")
            _file_start = False
            if "Input file indices" in line:
                data_file_indicies = line
            if "[Direct Beam Runs]" in line:
                _in_section = 1
            elif "[Data Runs]" in line:
                _in_section = 2
            elif "[Peak 1 Runs]" in line:
                # if existing, use this section instead of "[Data Runs]"
                _in_section = 2
                data_runs = []
            elif "[Peak" in line:
                _in_section = 3
                peak_index = int(line.split("[Peak ")[1].split(" Runs]")[0])
            elif "[Global Options]" in line:
                _in_section = 4

            # Process direct beam runs
            if _in_section == 1:
                toks = line.split()
                if len(toks) < 14 or "DB_ID" in line:
                    continue
                try:
                    if configuration is not None:
                        conf = copy.deepcopy(configuration)
                    else:
                        conf = Configuration()
                    conf.cut_first_n_points = int(toks[2])
                    conf.cut_last_n_points = int(toks[3])
                    conf.peak_position = float(toks[4])
                    conf.peak_width = float(toks[5])
                    conf.low_res_position = float(toks[6])
                    conf.low_res_width = float(toks[7])
                    conf.bck_position = float(toks[8])
                    conf.bck_width = float(toks[9])
                    conf.direct_pixel_overwrite = float(toks[10])
                    run_number = int(toks[12])
                    run_file = os.path.join(file_path, toks[-1])
                    # This application only deals with event data, to be able to load
                    # reduced files created with histo nexus files, we have to
                    # use the corresponding event file instead.
                    # Similarly, the number of points cut on each side probably
                    # doesn't make sense, so reset those options.
                    if run_file.endswith("histo.nxs"):
                        run_file = run_file.replace("histo.", "event.")
                        # conf.cut_first_n_points = 0
                        # conf.cut_last_n_points = 0
                    # Catch data files meant for QuickNXS and use the raw file instead
                    run_file = _find_h5_data(run_file)
                    direct_beam_runs.append([run_number, run_file, conf])
                except:
                    logging.error("Could not parse reduced data file:\n %s", sys.exc_info()[1])
                    logging.error(line)

            # Process data runs and additional peaks
            if _in_section == 2 or _in_section == 3:
                toks = line.split()
                if len(toks) < 16 or "DB_ID" in line:
                    continue
                try:
                    if configuration is not None:
                        conf = copy.deepcopy(configuration)
                    else:
                        conf = Configuration()
                    conf.scaling_factor = float(toks[1])
                    conf.cut_first_n_points = int(toks[2])
                    conf.cut_last_n_points = int(toks[3])
                    conf.peak_position = float(toks[4])
                    conf.peak_width = float(toks[5])
                    conf.low_res_position = float(toks[6])
                    conf.low_res_width = float(toks[7])
                    conf.bck_position = float(toks[8])
                    conf.bck_width = float(toks[9])
                    Configuration.use_constant_q = toks[10].strip().lower() == "true"
                    conf.direct_pixel_overwrite = float(toks[11])
                    if int(toks[14]) > 0 and len(direct_beam_runs) > int(toks[14]) - 1:
                        conf.normalization = direct_beam_runs[int(toks[14]) - 1][0]
                    run_number = int(toks[13])
                    run_file = os.path.join(file_path, toks[-1])
                    if run_file.endswith("histo.nxs"):
                        run_file = run_file.replace("histo.", "event.")
                        # conf.cut_first_n_points = 0
                        # conf.cut_last_n_points = 0
                    run_file = _find_h5_data(run_file)
                    run_file = determine_which_files_to_sum(run_file, data_file_indicies)
                    if _in_section == 2:
                        data_runs.append([run_number, run_file, conf])
                    else:
                        additional_peaks.append([peak_index, run_number, run_file, conf])
                except:
                    logging.error("Could not parse reduced data file:\n %s", sys.exc_info()[1])
                    logging.error(line)

            # Options
            if _in_section == 4:
                if line.startswith("# sample_length"):
                    try:
                        conf.sample_size = float((line[len("# sample_length") :]).strip())
                    except:
                        logging.error("Could not extract sample size: %s" % line)
                if line.startswith("# lock_direct_beam_y"):
                    try:
                        Configuration.lock_direct_beam_y = (
                            line[len("# lock_direct_beam_y") :]
                        ).strip().lower() == "true"
                    except:
                        logging.error("Could not extract direct beam y lock: %s" % line)

    return direct_beam_runs, data_runs, additional_peaks


def determine_which_files_to_sum(run_file, data_file_indicies):
    # Determeine which files are summed when reading a saved reduction file
    # The saved file has the correct run numbers (numors) in the line
    # that begins # Input file indices, however the file does not contain the corect paths
    # the way the file is read ignores any files that were summed in the processing from which the
    # saved file was created.

    if "+" in data_file_indicies:
        runs = str.split(str.split(data_file_indicies)[-1], "+")
    else:
        runs = str.split(str.split(data_file_indicies)[-1], ",")

    for run in runs:
        numors = str.split(run, ":")
        if len(numors) > 1 and (str.split(run, ":")[0] in run_file):
            outfile = ""
            for i in range(int(numors[0]), int(numors[-1]) + 1):
                outfile = outfile + "+" + run_file.replace(numors[0], str(i))
            outfile = outfile[1:]
        if len(numors) == 1 and (str.split(run, ":")[0] in run_file):
            outfile = run_file

    return outfile
