.. release_notes


Release Notes
=============
Notes for major and minor releases. Notes for Patch releases are deferred.


<Next Major or Minor Release>
-----------------------------
(date of release, format YYYY-MM-DD)

**Of interest to the User**:

- PR #104: Update Mantid version to 6.10
- PR #95: Optional dead-time correction (disabled by default)

**Of interest to the Developer:**

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
