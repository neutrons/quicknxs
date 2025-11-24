# pylint: disable=bare-except, too-many-locals, too-many-statements, too-many-branches, wrong-import-order, too-many-arguments
"""Read and write quicknxs reduced files."""

import copy
import inspect
import logging
import math
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Union

import mantid
import mr_reduction
import numpy as np
import pandas as pd

from quicknxs import __version__
from quicknxs.interfaces.configuration import Configuration
from quicknxs.interfaces.data_handling.data_set import CrossSectionData, NexusData

# Mapping of Configuration attributes to "common name" labels for the reduced file output.
CONFIG_LABELS = {
    "scaling_factor": "scale",
    "scaling_error": "scale_err",
    "cut_first_n_points": "P0",
    "cut_last_n_points": "PN",
    "peak_position": "x_pos",
    "peak_width": "x_width",
    "low_res_position": "y_pos",
    "low_res_width": "y_width",
    "bck_position": "bg_pos",
    "bck_width": "bg_width",
    "binning_type_global": "g_final_rebin",
    "binning_q_step_global": "g_Qsteps",
    "binning_type_run": "r_final_rebin",
    "binning_q_step_run": "r_Qsteps",
    "tof_bins": "bin_width",
    "total_reflectivity_q_cutoff": "critical_q_cutoff",
    "direct_pixel_overwrite": "dpix",
    "use_metadata_bck_roi": "force_bck_roi",  # Legacy name
}

LABEL_TO_CONFIG = {v: k for k, v in CONFIG_LABELS.items()}


def _find_h5_data(filename: str):
    """Get the correct data file for QuickNXS.

    Because we have legacy data and new data re-processed for QuickNXS,
    we have to ensure that we get the proper data file.
    """
    if filename.endswith(".nxs"):
        _new_filename = filename.replace("_histo.nxs", ".nxs.h5")
        _new_filename = _new_filename.replace("_event.nxs", ".nxs.h5")
        _new_filename = _new_filename.replace("data", "nexus")
        if os.path.isfile(_new_filename):
            logging.warning(f"Using {_new_filename}")
            return _new_filename
    return filename


def _sort_keys_with_file_last(keys: list[str]) -> list[str]:
    """Put 'File' at the end of the list of keys since the values can be long."""
    return sorted([k for k in keys if k.lower() != "file"]) + ["File"]


def _get_all_config_attributes(conf: Configuration):
    """Get all configuration attributes, including class and instance variables."""
    # Keys to exclude from output (UI-only or internal constants)
    EXCLUDE_KEYS = {
        "normalize_x_tof",  # UI options
        "x_wl_map",
        "angle_map",
        "log_1d",
        "log_2d",
        "QX_VS_QZ",  # Enum-style constants
        "KZI_VS_KZF",
        "DELTA_KZ_VS_QZ",
        "count_threshold",  # Internal constants
        "tof_overwrite",
        "nbr_events_min",
        "wl_bandwidth",
        "direct_pixel_overwrite",  # Writes from the run object
        "instrument",  # Instrument object, not a config option
        "setup_default_values",  # Class method, not an instance variable
    }

    GISANS_KEYS = {
        "gisans_wl_min",
        "gisans_wl_max",
        "gisans_wl_npts",
        "gisans_qy_npts",
        "gisans_qz_npts",
        "gisans_use_pf",
        "gisans_slice",
        "gisans_slice_qz_min",
        "gisans_slice_qz_max",
    }

    OFFSPEC_KEYS = {
        "off_spec_x_axis",
        "off_spec_slice",
        "off_spec_qz_list",
        "off_spec_slice_qz_min",
        "off_spec_slice_qz_max",
        "off_spec_err_weight",
        "off_spec_nxbins",
        "off_spec_nybins",
        "apply_smoothing",
        "off_spec_sigmas",
        "off_spec_sigmax",
        "off_spec_sigmay",
        "off_spec_x_min",
        "off_spec_x_max",
        "off_spec_y_min",
        "off_spec_y_max",
    }

    # Instance attributes
    all_instance_vars = vars(conf)

    # Filter GISANS, Offspec, and general instance vars
    gisans_vars = {k: v for k, v in all_instance_vars.items() if k in GISANS_KEYS}
    offspec_vars = {k: v for k, v in all_instance_vars.items() if k in OFFSPEC_KEYS}
    instance_vars = {
        k: v
        for k, v in all_instance_vars.items()
        if k not in GISANS_KEYS and k not in OFFSPEC_KEYS and k not in EXCLUDE_KEYS
    }

    # Class (global/static) attributes
    class_vars = {
        k: v
        for k, v in Configuration.__dict__.items()
        if not k.startswith("__")
        and not callable(v)
        and not isinstance(v, property)
        and k not in GISANS_KEYS
        and k not in OFFSPEC_KEYS
        and k not in EXCLUDE_KEYS
    }

    # Properties
    property_vars = {
        name: getattr(conf, name)
        for name, prop in inspect.getmembers(Configuration, lambda o: isinstance(o, property))
        if name not in GISANS_KEYS and name not in OFFSPEC_KEYS and name not in EXCLUDE_KEYS
    }

    return {
        "global": class_vars,
        "instance": {**instance_vars, **property_vars},
        "gisans": gisans_vars,
        "offspec": offspec_vars,
    }


def _build_config_row_dict(
    config: Configuration,
    item: Dict[str, Any],
    include_gisans: bool = False,
    include_offspec: bool = False,
) -> Dict[str, str]:
    """Build a dictionary of string-formatted values for config output."""

    all_config = _get_all_config_attributes(config)
    config_value_dict = {**all_config["instance"]}
    if include_gisans:
        config_value_dict.update(all_config["gisans"])
    if include_offspec:
        config_value_dict.update(all_config["offspec"])

    config_value_dict.update(item)

    return config_value_dict


def _build_table(config_values: List[Dict[str, str]], columns: List[str], section_header: str, ljust: str = ""):
    """Build a formatted table from configuration values."""
    df = pd.DataFrame(config_values, columns=columns)
    if df.empty:
        return ""
    df.rename(columns=CONFIG_LABELS, inplace=True)
    if ljust:
        max_len = df[ljust].astype(str).map(len).max()
        df_str = df.to_string(index=False, justify="left", formatters={ljust: lambda x: str(x).ljust(max_len)})
    else:
        df_str = df.to_string(index=False)
    table = "\n".join([f"# {line}" for line in df_str.splitlines() if line.strip()])
    return f"# [{section_header}]\n" + table + "\n"


def write_reflectivity_header(
    peak_reduction_lists: Dict[int, List[NexusData]],
    active_list_index: int,
    direct_beam_list: List[NexusData],
    output_path: str,
    pol_state: str,
    include_gisans: bool = False,
    include_offspec: bool = False,
):
    """
    Write out reflectivity header in a format readable by QuickNXS.

    Parameters
    ----------
    peak_reduction_lists:
        All reduction lists to include as additional peaks in the header
    active_list_index:
        The index of the reduction list that the output reflectivity data is for
    direct_beam_list:
        Direct beam list
    output_path:
        Output file path
    pol_state:
        Descriptor for the polarization state
    include_gisans:
        Include GISANS specific variables
    include_offspec:
        Include Offspec specific variables
    """
    # Sanity check
    if active_list_index not in peak_reduction_lists or not peak_reduction_lists[active_list_index]:
        return

    reduction_list = peak_reduction_lists[active_list_index]

    direct_beam_options = [
        "DB_ID",
        "P0",
        "PN",
        "dpix",
        "tth",
        "number",
        "File",
    ]
    dataset_options = [
        "fan",
        "dpix",
        "tth",
        "number",
        "DB_ID",
        "File",
    ]

    fd = open(output_path, "w")
    fd.write("# Datafile created by QuickNXS %s\n" % __version__)
    fd.write("# Datafile created using mr_reduction %s\n" % mr_reduction.__version__)
    fd.write("# Datafile created using Mantid %s\n" % mantid.__version__)
    fd.write("# Date: %s\n" % time.strftime("%Y-%m-%d %H:%M:%S"))
    fd.write("# Type: Specular\n")
    run_list = [str(item.number) for item in reduction_list]
    fd.write("# Input file indices: %s\n" % ",".join(run_list))
    fd.write("# Extracted states: %s\n" % pol_state)
    fd.write("#\n")

    g_conf = Configuration()
    conf_options = _get_all_config_attributes(g_conf)
    conf_instance_toks = list(conf_options["instance"].keys())

    if include_gisans:
        conf_instance_toks.extend(conf_options["gisans"].keys())
    if include_offspec:
        conf_instance_toks.extend(conf_options["offspec"].keys())

    direct_beam_options.extend(conf_instance_toks)
    direct_beam_options = _sort_keys_with_file_last(list(set(direct_beam_options)))

    # Get the list of cross-sections
    pol_list = list(reduction_list[0].cross_sections.keys())
    if not pol_list:
        logging.error("No data found in run %s", reduction_list[0].number)
        return

    # Direct beam section - save ALL direct beams in the list
    config_values = []
    normalization_run_to_db_id = {}  # Map normalization run number to DB_ID

    # Iterate through ALL direct beams in the direct_beam_list
    for direct_beam_idx, direct_beam in enumerate(direct_beam_list, start=1):
        db_pol = list(direct_beam.cross_sections.keys())[0]
        run_number = str(direct_beam.number)

        # Store the mapping for later use when writing data runs
        normalization_run_to_db_id[run_number] = direct_beam_idx

        # Get direct pixel and filename from the first data run that uses this direct beam
        # If no data run uses it, get it from the direct beam itself
        dpix = None
        filename = None
        for data_set in reduction_list:
            run_object = data_set.cross_sections[pol_list[0]].reflectivity_workspace.getRun()
            normalization_run = run_object.getProperty("normalization_run").value
            if str(normalization_run) == run_number:
                dpix = run_object.getProperty("normalization_dirpix").value
                filename = run_object.getProperty("normalization_file_path").value
                break

        # If this direct beam isn't used by any data run, use default values
        if dpix is None:
            dpix = direct_beam.cross_sections[db_pol].direct_pixel
        if filename is None:
            # Get filename from the direct beam's workspace
            ws = direct_beam.cross_sections[db_pol].reflectivity_workspace
            if ws:
                filename = ws.getRun().getProperty("Filename").value
            else:
                filename = f"REF_M_{run_number}.nxs.h5"  # fallback

        item = dict(
            DB_ID=direct_beam_idx,
            tth=0,
            P0=0,
            PN=0,
            dpix=dpix,
            number=run_number,
            File=filename,
        )

        config_value_dict = _build_config_row_dict(
            config=direct_beam.cross_sections[db_pol].configuration,
            item=item,
            include_gisans=include_gisans,
            include_offspec=include_offspec,
        )
        config_values.append(config_value_dict)

    fd.write(_build_table(config_values, direct_beam_options, "Direct Beam Runs"))

    # Peak for reflectivity data
    fd.write("#\n")
    dataset_options.extend(conf_instance_toks)
    dataset_options = _sort_keys_with_file_last(list(set(dataset_options)))

    config_values = []
    for data_set in reduction_list:
        cross_section_data = data_set.cross_sections[pol_list[0]]
        dataset_dict = _get_cross_section_config_values(cross_section_data, normalization_run_to_db_id)
        config_value_dict = _build_config_row_dict(
            config=cross_section_data.configuration,
            item=dataset_dict,
            include_gisans=include_gisans,
            include_offspec=include_offspec,
        )
        config_values.append(config_value_dict)
    fd.write(_build_table(config_values, dataset_options, "Data Runs"))

    # All peaks
    for peak_index, peak_reduction_list in peak_reduction_lists.items():
        fd.write("#\n")

        config_values = []
        for data_set in peak_reduction_list:
            cross_section_data = data_set.cross_sections[pol_list[0]]
            dataset_dict = _get_cross_section_config_values(cross_section_data, normalization_run_to_db_id)
            config_value_dict = _build_config_row_dict(
                config=cross_section_data.configuration,
                item=dataset_dict,
                include_gisans=include_gisans,
                include_offspec=include_offspec,
            )
            config_values.append(config_value_dict)
        fd.write(_build_table(config_values, dataset_options, f"Peak {peak_index} Runs"))

    fd.write("#\n")

    # Global Options
    fd.write(
        _build_table(
            list(conf_options["global"].items()),
            columns=["name", "value"],
            section_header="Global Options",
            ljust="name",
        )
    )

    fd.write("#\n")
    fd.close()


def _get_cross_section_config_values(
    cross_section_data: CrossSectionData, normalization_run_to_db_id: Dict[str, int]
) -> Dict[str, str]:
    """Get dict of cross-section data configuration to write to QuickNXS file.

    Parameters
    ----------
    cross_section_data : CrossSectionData
        The cross-section data to extract config values from
    normalization_run_to_db_id : Dict[str, int]
        Mapping from normalization run number (as string) to DB_ID

    Returns
    -------
    Dict[str, str]
        Dictionary of configuration values
    """
    ws = cross_section_data.reflectivity_workspace
    run_object = ws.getRun()
    dpix = run_object.getProperty("DIRPIX").getStatistics().mean
    filename = run_object.getProperty("Filename").value
    constant_q_binning = run_object.getProperty("constant_q_binning").value
    scatt_pos = run_object.getProperty("specular_pixel").value
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
        # Look up the DB_ID from the mapping
        db_id = normalization_run_to_db_id.get(normalization_run, 0)

    item = dict(
        DB_ID=db_id,
        tth=tth,
        fan=constant_q_binning,
        dpix=dpix,
        number=str(ws.getRunNumber()),
        File=filename,
    )

    return item


def write_reflectivity_data(
    output_path: str, data: Union[list, np.ndarray], col_names: List[str], as_5col: bool = True
):
    """Write out reflectivity header in a format readable by QuickNXS.

    If `as_5col` is False, only the first four columns passed will be written.
    """
    with open(output_path, "a") as fd:
        # Determine how many columns to write
        if isinstance(data, list):
            four_cols = True
        else:
            four_cols = not as_5col and data.shape[1] > 4

        # write header
        fd.write("# [Data]\n")
        if four_cols:
            toks = ["%12s" % item for item in col_names[:4]]
        else:
            toks = ["%12s" % item for item in col_names]
        fd.write("# %s\n" % "\t".join(toks))

        # write numerical columns
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


def _assign_config_value(conf: Configuration, attr: str, value_str: str):
    """Assign a string value to a Configuration attribute with type inference."""
    if not hasattr(conf, attr):
        return  # silently ignore unknown attributes

    value_str = value_str.strip()
    try:
        current_value = getattr(conf, attr)
        if isinstance(current_value, bool):
            value = value_str.lower() in ("true", "1", "yes")
        elif isinstance(current_value, float):
            value = float(value_str)
        elif isinstance(current_value, int):
            try:
                value = int(value_str)
            except:
                value = float(value_str)
        elif value_str == "None":
            value = None
        elif isinstance(current_value, list) or ("[" in value_str and "]" in value_str):
            value_str = value_str.replace("[", "").replace("]", "")
            if value_str == "":
                value = []
            else:
                value = [float(x) for x in value_str.split(",") if x.strip()]
        else:
            value = value_str
        setattr(conf, attr, value)
    except (AttributeError, ValueError, TypeError) as e:
        logging.error(f"Failed to assign config value: {attr} = {value_str} -> {e}")


def read_reduced_file(file_path: str, configuration=None):
    """Read in configurations from a reduced data file."""
    direct_beam_runs = []
    data_runs = []
    additional_peaks = []
    config_properties = [name for name, _ in inspect.getmembers(Configuration, lambda o: isinstance(o, property))]

    def _get_tok(col_name: str, cols: List[str], toks: List) -> Union[int, None]:
        """Get the item in a list of index matching the column name."""
        try:
            idx = cols.index(col_name)
            return toks[idx]
        except ValueError:
            return None

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
        has_scaling_error = False
        for line in file_content.readlines():
            if _file_start and not line.startswith("# Datafile created by QuickNXS"):
                raise RuntimeError("The selected file does not conform to the QuickNXS format")
            _file_start = False
            if "Input file indices" in line:
                data_file_indices = line
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
            elif "[Data]" in line:
                _in_section = 0
                continue

            # Process direct beam runs
            if _in_section == 1:
                toks = line.replace(", ", ",").split()
                if "DB_ID" in toks:
                    cols = toks
                    continue
                if len(toks) < 14:
                    continue
                try:
                    if configuration is not None:
                        conf = copy.deepcopy(configuration)
                    else:
                        conf = Configuration()
                    for label in cols:
                        attr = LABEL_TO_CONFIG.get(label, label)
                        value_str = _get_tok(label, cols, toks)
                        if value_str is not None and attr not in config_properties:
                            _assign_config_value(conf, attr, value_str)

                    run_number = int(_get_tok("number", cols, toks))
                    run_file = _get_tok("File", cols, toks)
                    if not Path(str(run_file)).is_absolute():
                        run_file = str(Path(file_path).parent / f"{run_file}")
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
                except ValueError:
                    logging.error("Unable to parse line '%s' in run file %s", line, run_file)

            # Process data runs and additional peaks
            if _in_section == 2 or _in_section == 3:
                toks = line.replace(", ", ",").split()
                if "DB_ID" in toks:
                    cols = toks
                    continue
                if len(toks) < 16:
                    continue
                try:
                    if configuration is not None:
                        conf = copy.deepcopy(configuration)
                    else:
                        conf = copy.deepcopy(Configuration())

                    for label in cols:
                        attr = LABEL_TO_CONFIG.get(label, label)
                        value_str = _get_tok(label, cols, toks)
                        if value_str is not None and attr not in config_properties:
                            _assign_config_value(conf, attr, value_str)
                            if label == "scale_err":
                                has_scaling_error = True

                    DB_ID = int(_get_tok("DB_ID", cols, toks))
                    if DB_ID > 0 and len(direct_beam_runs) > DB_ID - 1:
                        conf.direct_beam = direct_beam_runs[DB_ID - 1][0]
                    run_number = int(_get_tok("number", cols, toks))
                    run_file = _get_tok("File", cols, toks)
                    if not Path(run_file).is_absolute():
                        run_file = str(Path(file_path).parent / run_file)
                    if run_file.endswith("histo.nxs"):
                        run_file = run_file.replace("histo.", "event.")
                        # conf.cut_first_n_points = 0
                        # conf.cut_last_n_points = 0
                    run_file = _find_h5_data(run_file)
                    run_file = determine_which_files_to_sum(run_file, data_file_indices)

                    if _in_section == 2:
                        data_runs.append([run_number, run_file, conf])
                    else:
                        additional_peaks.append([peak_index, run_number, run_file, conf])
                except ValueError:
                    logging.error("Unable to parse line '%s' in run file %s", line, run_file)

            # Global Config Options
            if _in_section == 4 and line.startswith("# "):
                try:
                    label, value = line[2:].strip().split(" ", 1)
                except ValueError:
                    logging.error("Unable to parse line '%s' in run file %s", line, run_file)
                attr = LABEL_TO_CONFIG.get(label, label)
                _assign_config_value(Configuration, attr, value)

    return direct_beam_runs, data_runs, additional_peaks, has_scaling_error


def determine_which_files_to_sum(run_file, data_file_indices):
    """Determine which files are summed when reading a saved reduction file.

    The saved file has the correct run numbers (numors) in the line that
    starts with: `# Input file indices`, however the file does not contain
    the correct paths the way the file is read ignores any files that were
    summed in the processing from which the saved file was created.
    """

    if "+" in data_file_indices:
        runs = str.split(str.split(data_file_indices)[-1], "+")
    else:
        runs = str.split(str.split(data_file_indices)[-1], ",")

    outfile = run_file
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
