# TEST Components

## Comparison

A series of notebooks are available to see comparison plots between this version of QuickNXS and the old version.

* The following is a mix of comparisons of specular and off-specular data with various options:
http://nbviewer.jupyter.org/github/neutrons/quicknxs/blob/next/test/comparison/general_comparison.ipynb

* The following shows comparison plots for off-specular data:
http://nbviewer.jupyter.org/github/neutrons/quicknxs/blob/next/test/comparison/Offspec_comparison.ipynb

* The following shows comparison plots for GISANS data:
http://nbviewer.jupyter.org/github/neutrons/quicknxs/blob/next/test/comparison/gisans_comparison.ipynb

## Export of XYE Data

Every plot has a button that can be used to export XYE data to a file. Only 1D line plots are working for this feature.

[EWM15204]() is defined to fix and repair this.
This branch [bvacaliuc/ewm15204-triage]() has a modification that emits the full datasets as `.npz` or `.pkl` (pickle) files in the [~NavigationToolbar.save_data()](https://github.com/neutrons/quicknxs/blob/next/src/quicknxs/ui/mplwidget.py#L151) function.

### [show.py](show.py)

A python routine that can read the `.pkl` ( *working* ) or `.npz` ( *not-working* ) files produced and regenerate the figure. The purpose is to work out the specific instructions needed to generate the correct ASCII `.dat` file when that output format is requested.
