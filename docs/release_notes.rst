.. release_notes


Release Notes
=============

For release notes after `v4.7.0`,
see the `GitHub release notes <https://github.com/neutrons/quicknxs/releases>`_.

4.7.0
-----
2025-07-15

QuickNXS now uses Pixi for package builds and :ref:`developer environment<development_environment>` setup and tasks (#174).

v4.6.0
------
2025-06-24

This release add some fixes to the GUI: removing data tabs no longer causes an error (#171),
a problem with plots after going to the Off-Specular tab is fixed (#172), and the metadata ROI
information is now shown consistently (PR #173).

v4.5.0
------
2025-06-10

This release adds the ability to edit cells in the direct beam table (PR #164),
a new utility class for reusing QColors (PR #167),
updates mr_reduction to 2.5.0 (PR #169),
and updates the variable names to improve consistency (PR #170).

v4.4.0
------
2025-05-20

New features in this release include :ref:`reduction output<reduction>` in
`ORSO format <https://www.reflectometry.org/file_format/specification>`_ (PR #158),
the ability to load v1 (pre-EPICS) NeXus data files (PR #147) and plotting the intensity vs ToF for
direct beam runs (PR #153). The behavior of the :ref:`peak finder settings<peak_finder>` are changed
to make it more clear whether the peak region of interest is found from the metadata or using
automatic peak finding (PR #143). The release also includes bug fixes to the off-specular preview
plot (PR #156) and the plot home button (PR #160).

v4.3.0
------
2025-04-15

Updates in this release include saving the scale factor error to the reduced data file and
reducing the number of configuration parameters that are saved to the users's local environment.

v4.2.0
------
2025-03-31

This release updates the Mantid version to 6.12 to address a security vulnerability.

v4.1.0
------
2025-03-18

Updates in this release include fixing an issue where the Python script output from reduction was the
same for multiple samples (PR #140), adding the ability to remove added sample tabs (PR #139),
providing user documentation for how binning parameters are used (PR #138), and updating the
final rebin and Q-Steps to be configurable per run or globally (PR #137).

v4.0.0
------
2025-01-17

In this new major version, the name of the application was changed to `quicknxs`. New improvements include
skipping the reflectivity calculation for direct beam runs and the dead-time correction to account for
detector saturation.

**Of interest to the User**:

- PR #124: Hides the "Sample Size" and "Bandwidth" configurations
- PR #120: rename the launcher script to "quicknxs-gui"
- PR #119: Rename the repository to "quicknxs"
- PR #115: Skip reflectivity calculation for direct beams
- PR #118: Skip plotting "Active" line when direct beam selected
- PR #112: Make the minimum number of events cut-off configurable in ~/.config/.refredm.conf
- PR #104: Update Mantid version to 6.10
- PR #95: Optional dead-time correction (disabled by default)
- PR #91: Add ability to reduce multiple samples from the same run

**Of interest to the Developer:**

- PR #109: Add test fixture that fixes tests changing settings in ~/.config/.refredm.conf
- PR #108: Replace build with python-build in environment.yml
- PR #106: Enable tests using the data repo git LFS files in the CI pipeline
- PR #XYZ: one-liner description


v3.2.0
------
2023-11-04

**Of interest to the User**:

- PR #96  drop functionality to save files in genx format
- PR #94  fallback option for loading old data runs
- PR #93  change the default size of the smoothing area, and to change the color map on the preview plot
- PR #77  Clearly distinguish global and per-run options
- PR #75  Export direct beam data
- PR #74  Add plot toolbar buttons for log x-axis, log y-axis and R*Q^4
- PR #73  Make messages in status bar disappear after 10 seconds


**Of interest to the Developer:**

- PR #88  Recalculate and replot reflectivity when global config is changed
- PR #79  Update codecov version and add token in actions.yml
- PR #78  Add ConfigurationHandler which connects signals from global configuration parameter UI widgets to callbacks
- PR #71  disable automatic Conda deployments


v3.1.0
------
2023-10-13

**Of interest to the User**:

- PR #67  Adjust the reduction table to make all data visible
- PR #66  Display error message when "Normalize to unity when stitching" fails
- PR #64  Stitching by fitting a polynomial
- PR #63  Bugfix: Losing direct beam run
- PR #61  Correct error bars of stitched reflectivity curves
- PR #60 Publish documentation
- PR #58 Global stitching
- PR #52 Bugfix error in the x vs TOF plot for empty reflectivity curves
- PR #51 Fix plot of smooth off-specular area
- PR #48 Fix broken IO when saving off-specular data


**Of interest to the Developer:**

- PR #57 Remove class ApplicationConfiguration
- PR #54 Unit testing for stitching
- PR #46 Update enviroment.yml with mantidworkbench


v3.0.0
------
2023-04-25
