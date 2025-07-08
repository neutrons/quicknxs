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

    # Datafile created by QuickNXS 1.3.0
    # Datafile created using mr_reduction 0.5.2
    # Datafile created using Mantid 6.3.0
    # Date: 2025-07-01 14:30:11
    # Type: Specular
    # Input file indices: 30201,30202,30203
    # Extracted states: Off_Off, On_Off
    #
    # [Global Options]
    # sample_length             10
    # use_constant_q           True
    # normalize_to_unity       True
    # off_spec_qz_list         [0.05, 0.07]
    # gisans_qz_npts           50
    #
    # [Direct Beam Runs]
    # DB_ID  P0  PN  x_pos  x_width  y_pos  y_width  bg_pos  bg_width  dpix  tth  number  File
    # 1      0   0   214.5  12       109.5  98       97.5    164       213   0    30200   /path/to/REF_M_30200.nxs
    #
    # [Data Runs]
    # P0  PN  x_pos  x_width  y_pos  y_width  bg_pos  bg_width  scale  scale_err  dpix  tth  number  File
    # 0   0   214.5  12       110.5  100      99.5    160       1.0    0.0         213   0    30201   /path/to/REF_M_30201.nxs

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

This file can be reused to re-import reduced data, either manually or by scripting.

The file is designed to be both:

- **Human-readable**: For logging, sharing, or reviewing
- **Machine-readable**: For round-trip parsing by QuickNXS

To reload the file use the **“Load Reduced File”** option in the GUI.
QuickNXS will automatically reconstruct all configuration values, run links, and references.
