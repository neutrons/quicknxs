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

.. include:: ./example_reduced_data.dat
    :literal:
    :end-line: 50


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
- ``slice``: Slice index for multiple slices per run (defaults to 0)
- ``File``: Full file path to the NeXus file

[Data Runs]
^^^^^^^^^^^

This section mirrors the format of the direct beam section, but for each reflectivity or GISANS data file. Additional fields include:

- ``scale``: Normalization scaling factor (applied to this file)
- ``scale_err``: Uncertainty in the scaling
- ``number``: Run number
- ``slice``: Slice index for multiple slices per run (defaults to 0)
- ``File``: Full file path to the NeXus file

Column Formatting
-----------------

- Each section uses aligned, fixed-width columns
- Values are aligned to the column headers for readability
- The final column is always ``File``, which may contain long absolute paths

Slice Column in the UI
----------------------

The ``Slice`` column also appears in the reduction table in the main QuickNXS interface,
positioned immediately after the ``Run No.`` column. This column is not editable from the UI
and displays the slice index associated with each data run. Currently, all runs have a slice
value of 0 (default), but this column supports future functionality for handling multiple
slices per run.

.. note::
   The ``Slice`` column does not appear in the normalization (direct beam) table, as multiple
   slices are not supported for direct beam runs.

Reusing the File
----------------

This file can be reused to re-import reduced data for further analysis.

The file is designed to be both:

- **Human-readable**: For logging, sharing, or reviewing
- **Machine-readable**: For round-trip parsing by QuickNXS

To reload the file use the **“Load Reduced File”** option in the GUI.
QuickNXS will automatically reconstruct all configuration values, run links, and references.
