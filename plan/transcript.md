# Prompts used in this development

## Prompt 1

You are working in the quicknxsv2 project, in the bvacaliuc/ewm15204-triage branch. Examine the git log on this branch and consider the files added and the modifications made. There is a requirement to properly implement the save_data() in src/quicknxs/ui/mplwidget.py. Compare this function on the next branch. Observe that it only works for a certain class of 1D line plots. It does not work for 2D image plots. The bvacaliuc/ewm15204-triage branch added the ability to write .npz and .pkl files to help understand the varied array structure that apply. The goal is to enable the output of 1) ASCII table data to .dat, 2) Pickled datasets to .pkl, 3) Compressed numpy arrays to .npz from any visual plot that uses the NavigateToolbar class, or raise an exception if unable to do so properly. This task will require a detailed plan and very careful introspection of the code base in order to succeed in adding the function without introducing errors. There may need to be tests that should be added. The machine you are running on may not be setup to perform the tests reliably, so you may need layers upon layers of development. Please limit your work to the bvacaliuc/ewm15204-triage branch so as not to interfere with institutional developers and the strict process that the quicknxsv2 project. I would like to review the development plan before you implement it.

The plan that Claude developed from this prompt is [rewrite-save-data.md](rewrite-save-data.md)

## Prompt 2

Good! This is nice code, thank you. I would like that .dat files that are made from pcolormesh data to be emitted in gnuplot xyz ascii format. The x and y values should be taken from x and y centers that were computed in _extract_pcolormesh_data(). Leave a blank line after a major axes transition. Please keep test/show.py updated to interpret this format. Please limit your work to the bvacaliuc/ewm15204-triage branch so as not to interfere with institutional developers and the strict process used by the quicknxsv2 project.

## Prompt 3

Does the gnuplot xyz ascii format exclude multiline comments? If not then please restore the header detail that was present in the .dat file output before the last edit. Double-check the source of the z_data. Specifically, when exporting the Off-Specular plot, it appears to get the data from the Overview x vs ToF plot. Review the plot code carefully to make sure that the data plotted is assocated with the plot that the button refers to.

## Prompt 4

TBD

The plan that Claude developed from this prompt is [data-export-validation.md](data-export-validation.md)

