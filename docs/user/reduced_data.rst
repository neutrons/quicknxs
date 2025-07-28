.. _reduced_data:

QuickNXS Output File Format
===========================

When QuickNXS reduces a dataset, it creates a plain text file containing all relevant
configuration settings, file paths, and reduction metadata. This file serves both as a
record of the reduction and as a reproducible input for future analyses.

The format is human-readable and structured in sections, each beginning with a header
like ``# [Section Name]``. All lines starting with ``#`` are treated as comments.

File Overview
-------------

The output file consists of several parts:

1. **Header Metadata** – General information about the reduction environment
2. **[Global Options]** – All global configuration parameters used in the reduction
3. **[Direct Beam Runs]** – Per-Run configuration information for each direct beam normalization file
4. **[Data Runs]** – Per-Run configuration information for each reduced data file

Example
-------

.. code-block::

    # Datafile created by QuickNXS 4.5.0
    # Datafile created using mr_reduction 2.2.0
    # Datafile created using Mantid 6.12.0
    # Date: 2025-07-16 09:17:38
    # Type: Specular
    # Input file indices: 42112,42113
    # Extracted states: +-
    #
    # [Direct Beam Runs]
    #  DB_ID  P0  PN  bck_position  bck_roi  bck_width  cut_first_n_points  cut_last_n_points  direct_angle_offset_overwrite direct_beam  do_final_rebin_run  dpix  final_rebin_step_run  low_res_position low_res_roi  low_res_width  match_direct_beam metadata_roi_bck metadata_roi_peak number  peak_position   peak_roi  peak_width  scaling_error  scaling_factor  set_direct_angle_offset  set_direct_pixel  subtract_background  tof_bin_type  tof_bins                                tof_range  tth  use_dangle                                           File
    #      1   0   0          30.0 [20, 40]       20.0                   1                  1                            0.0        None               False 194.0                 -0.01             167.0  [127, 207]           80.0               True           [0, 0]        [225, 246]  42099          235.5 [225, 246]        21.0            0.0             1.0                    False             False                 True             0       400 [11413.560217325685, 45388.809236341694]    0       False /SNS/REF_M/IPTS-30794/nexus/REF_M_42099.nxs.h5
    #
    # [Data Runs]
    #  DB_ID  bck_position  bck_roi  bck_width  cut_first_n_points  cut_last_n_points  direct_angle_offset_overwrite  direct_beam  do_final_rebin_run  dpix   fan  final_rebin_step_run  low_res_position low_res_roi  low_res_width  match_direct_beam metadata_roi_bck metadata_roi_peak number  peak_position   peak_roi  peak_width  scaling_error  scaling_factor  set_direct_angle_offset  set_direct_pixel  subtract_background  tof_bin_type  tof_bins                                tof_range      tth  use_dangle                                           File
    #      0          30.0 [20, 40]       20.0                   1                  1                            0.0          NaN               False 194.0 False                 -0.01             167.0  [127, 207]           80.0               True           [0, 0]        [163, 184]  42112          173.5 [163, 184]        21.0            0.0             1.0                    False             False                 True             0       400 [11413.560217325685, 45388.809236341694] 0.137407       False /SNS/REF_M/IPTS-30794/nexus/REF_M_42112.nxs.h5
    #      1          30.0 [20, 40]       20.0                   1                  1                            0.0      42099.0               False 194.0 False                 -0.01             167.0  [127, 207]           80.0               True           [0, 0]        [132, 152]  42113          142.0 [132, 152]        20.0            0.0             1.0                    False             False                 True             0       400 [11413.560217325685, 45388.809236341694] 0.379784       False /SNS/REF_M/IPTS-30794/nexus/REF_M_42113.nxs.h5
    #
    # [Peak 1 Runs]
    #  DB_ID  bck_position  bck_roi  bck_width  cut_first_n_points  cut_last_n_points  direct_angle_offset_overwrite  direct_beam  do_final_rebin_run  dpix   fan  final_rebin_step_run  low_res_position low_res_roi  low_res_width  match_direct_beam metadata_roi_bck metadata_roi_peak number  peak_position   peak_roi  peak_width  scaling_error  scaling_factor  set_direct_angle_offset  set_direct_pixel  subtract_background  tof_bin_type  tof_bins                                tof_range      tth  use_dangle                                           File
    #      0          30.0 [20, 40]       20.0                   1                  1                            0.0          NaN               False 194.0 False                 -0.01             167.0  [127, 207]           80.0               True           [0, 0]        [163, 184]  42112          173.5 [163, 184]        21.0            0.0             1.0                    False             False                 True             0       400 [11413.560217325685, 45388.809236341694] 0.137407       False /SNS/REF_M/IPTS-30794/nexus/REF_M_42112.nxs.h5
    #      1          30.0 [20, 40]       20.0                   1                  1                            0.0      42099.0               False 194.0 False                 -0.01             167.0  [127, 207]           80.0               True           [0, 0]        [132, 152]  42113          142.0 [132, 152]        20.0            0.0             1.0                    False             False                 True             0       400 [11413.560217325685, 45388.809236341694] 0.379784       False /SNS/REF_M/IPTS-30794/nexus/REF_M_42113.nxs.h5
    #
    # [Global Options]
    # name                        value
    # sample_size                  10.0
    # use_constant_q              False
    # do_final_rebin_global        True
    # final_rebin_step_global     -0.01
    # normalize_to_unity           True
    # total_reflectivity_q_cutoff  0.01
    # global_stitching            False
    # polynomial_stitching        False
    # polynomial_stitching_degree     3
    # polynomial_stitching_points     3
    # apply_deadtime              False
    # paralyzable_deadtime         True
    # deadtime_value                4.2
    # deadtime_tof_step             100
    # lock_direct_beam_y          False
    # use_roi                      True
    # update_peak_range           False
    # use_peak_finder             False
    # use_low_res_finder          False
    # use_roi_bck                 False
    # use_tight_bck               False
    # bck_offset                      5
    # force_bck_roi               False
    #
    # [Data]
    #     Qz [1/A]	    R [a.u.]	   dR [a.u.]	   dQz [1/A]	 theta [rad]
    6.460453e-03      	3.887723e-02      	1.326615e-02      	5.000970e-04      	4.322784e-03
    6.525057e-03      	4.349224e-02      	1.335389e-02      	5.051001e-04      	4.322784e-03
    6.590308e-03      	6.469506e-02      	1.598737e-02      	5.101532e-04      	4.322784e-03
    6.656211e-03      	7.656998e-02      	1.793673e-02      	5.152570e-04      	4.322784e-03
    ...


Section Details
---------------

Global Metadata
^^^^^^^^^^^^^^^

The header lines provide metadata about the reduction process:

- **QuickNXS / Mantid versions**: Tools used to produce the file
- **Date**: Timestamp of when the file was created
- **Type**: Reduction mode (e.g., Specular, GISANS) but always Specular for now
- **Input file indices**: List of reduced run numbers
- **Extracted states**: Polarization cross-sections used

[Global Options]
^^^^^^^^^^^^^^^^

This section contains all configuration values used for the reduction. These are grouped from the QuickNXS settings panel and internal options.

Key notes:

- Boolean values appear as ``True`` or ``False``
- Floating-point numbers use general numeric formatting
- Lists (e.g., for Q values or ranges) are shown in square brackets: ``[0.05, 0.07]``
- The list of parameters may grow or shrink depending on whether the reduction includes GISANS or Off-specular options

[Direct Beam Runs]
^^^^^^^^^^^^^^^^^^

Each row in this section represents a direct beam (normalization) file used in the reduction.

Common fields:

- ``DB_ID``: A sequential ID assigned during reduction
- ``P0``, ``PN``: Number of points trimmed from the beginning/end
- ``x_pos``, ``x_width``: Horizontal peak region center and width
- ``y_pos``, ``y_width``: Vertical peak region center and width
- ``bg_pos``, ``bg_width``: Background region center and width
- ``dpix``: Direct pixel position
- ``tth``: Two-theta angle (if available)
- ``number``: Run number
- ``File``: Full file path to the NeXus file

[Data Runs]
^^^^^^^^^^^

This section mirrors the format of the direct beam section, but for each reflectivity or GISANS data file. Additional fields include:

- ``scale``: Normalization scaling factor (applied to this file)
- ``scale_err``: Uncertainty in the scaling
- ``number`` and ``File``: As above

Column Formatting
-----------------

- Each section uses aligned, fixed-width columns
- Values are aligned to the column headers for readability
- The final column is always ``File``, which may contain long absolute paths

Reusing the File
----------------

This file can be reused to re-import reduced data for further analysis.

The file is designed to be both:

- **Human-readable**: For logging, sharing, or reviewing
- **Machine-readable**: For round-trip parsing by QuickNXS

To reload the file use the **“Load Reduced File”** option in the GUI.
QuickNXS will automatically reconstruct all configuration values, run links, and references.
