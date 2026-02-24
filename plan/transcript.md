# Prompts used in this development

## Prompt 1

You are working in the quicknxsv2 project, in the bvacaliuc/ewm15204-triage branch. Examine the git log on this branch and consider the files added and the modifications made. There is a requirement to properly implement the save_data() in src/quicknxs/ui/mplwidget.py. Compare this function on the next branch. Observe that it only works for a certain class of 1D line plots. It does not work for 2D image plots. The bvacaliuc/ewm15204-triage branch added the ability to write .npz and .pkl files to help understand the varied array structure that apply. The goal is to enable the output of 1) ASCII table data to .dat, 2) Pickled datasets to .pkl, 3) Compressed numpy arrays to .npz from any visual plot that uses the NavigateToolbar class, or raise an exception if unable to do so properly. This task will require a detailed plan and very careful introspection of the code base in order to succeed in adding the function without introducing errors. There may need to be tests that should be added. The machine you are running on may not be setup to perform the tests reliably, so you may need layers upon layers of development. Please limit your work to the bvacaliuc/ewm15204-triage branch so as not to interfere with institutional developers and the strict process that the quicknxsv2 project. I would like to review the development plan before you implement it.

The plan that Claude developed from this prompt is [rewrite-save-data.md](rewrite-save-data.md)

## Prompt 2

Good! This is nice code, thank you. I would like that .dat files that are made from pcolormesh data to be emitted in gnuplot xyz ascii format. The x and y values should be taken from x and y centers that were computed in _extract_pcolormesh_data(). Leave a blank line after a major axes transition. Please keep test/show.py updated to interpret this format. Please limit your work to the bvacaliuc/ewm15204-triage branch so as not to interfere with institutional developers and the strict process used by the quicknxsv2 project.

## Prompt 3

Does the gnuplot xyz ascii format exclude multiline comments? If not then please restore the header detail that was present in the .dat file output before the last edit. Double-check the source of the z_data. Specifically, when exporting the Off-Specular plot, it appears to get the data from the Overview x vs ToF plot. Review the plot code carefully to make sure that the data plotted is assocated with the plot that the button refers to.

## Prompt 4

You are working in the quicknxsv2 project, in the bvacaliuc/ewm15204-triage branch. Examine the git log on this branch and consider the files added and the modifications made. There is a requirement to properly implement the save_data() in src/quicknxs/ui/mplwidget.py. Compare this function on the next branch. Observe that it only works for a certain class of 1D line plots. It does not work for 2D image plots. The bvacaliuc/ewm15204-triage branch added the ability to write .npz and .pkl files to help understand the varied array structure that apply. The goal is to enable the output of 1) ASCII table data to .dat, 2) Pickled datasets to .pkl, 3) Compressed numpy arrays to .npz from any visual plot that uses the NavigateToolbar class, or raise an exception if unable to do so properly. This task will require a detailed plan and very careful introspection of the code base in order to succeed in adding the function without introducing errors. There may need to be tests that should be added. The machine you are running on may not be setup to perform the tests reliably, so you may need layers upon layers of development. Please limit your work to the bvacaliuc/ewm15204-triage branch so as not to interfere with institutional developers and the strict process that the quicknxsv2 project. I would like to review the development plan before you implement it.

The plan that Claude developed from this prompt is [data-export-validation.md](data-export-validation.md)

## Prompt 5

Good! This is nice code, thank you. I would like that .dat files that are made from pcolormesh data to be emitted in gnuplot xyz ascii format. The x and y values should be taken from x and y centers that were computed in `_extract_pcolormesh_data()`. Leave a blank line after a major axes transition. Please keep test/show.py updated to interpret this format. Please limit your work to the bvacaliuc/ewm15204-triage branch so as not to interfere with institutional developers and the strict process used by the quicknxsv2 project.

## Prompt 6

Does the gnuplot xyz ascii format exclude multiline comments? If not then please restore the header detail that was present in the .dat file output before the last edit. Double-check the source of the z_data. Specifically, when exporting the Off-Specular plot, it appears to get the data from the Overview x vs ToF plot. Review the plot code carefully to make sure that the data plotted is assocated with the plot that the button refers to.

## Prompt 7

Please review the `/SNS/REF_M/IPTS-32745/shared/autoreduce/*.dat` files that were produced from each of the plots. The file names reflect the plot that was saved. Ignore the files with Specular in the name, however as they were produced earlier. Each one has some issue in that using test/show.py does not reproduce the original plot. Do you see now where the data is not matching the plot from the UI? I suggest that you add additional tests to export data from the plot windows, then verify that data is correctly read back with code such as test/show.py to ensure that every plot output can be read-in. Use agents to help perform the tasking efficiently. Make a plan if that is the best course of action. Be extremely thorough because this is a critical part that quicknxsv2 performs and it has to be correct. Thank you for making the effort!

The plan that claude proded is referenced in [fix-data-extraction-and-round-trip-verification.md](fix-data-extraction-and-round-trip-verification.md)

## Prompt 8

For the Off-Specular plots, using the 'Save plot data' does not match the plot. Consider `/SNS/REF_M/IPTS-32745/shared/autoreduce/try2/REF_M_43279+43280+43281-OffSpec-Qz-vs-Ki-Kf-Off_Off.dat` as compared with `/SNS/REF_M/IPTS-32745/shared/autoreduce/try2/REF_M_43279+43280+43281-OffSpec-Qz-vs-Ki-Kf-Off_Off.png` obtained with 'Save the figure'. Extend the testing to compare the result of using test/show.py to reconstruct the exported plot data versus exporting the figure data. A successful test for every plot is when the reconstructed plot from a data export matches the saved figure. You will need to carry thru the axes labels because they will be significant when making image comparisons.

## Prompt 6 

Very nice! Please make sure that the logarithmic scale is preserved on plots rendered with test/show.py. Please make sure that all plot elements (title, axes titles, legends, etc.) are written to the header and extracted by test/show.py. Review the .dat and .png files in /home/bvacaliuc/shared/REF_M/QuickNXSv2/session8/ to see what I mean.

