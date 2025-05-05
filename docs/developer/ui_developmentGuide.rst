.. _graphic_user_interface_development_guide:

Graphic User Interface Development Guide
========================================


Learning Videos
---------------
The following video recordings of meetings are useful for learning how to use the GUI as a User.
A UCAMS account is required to access the videos.


Stitching
+++++++++
`link to video <https://ornl-my.sharepoint.com/:v:/r/personal/jbq_ornl_gov/Documents/Recordings/QuickNxs%20Stitching%20Hands-on-20230523_130254-Meeting%20Recording.mp4?csf=1&web=1&e=p9c7hy>`_ and
Points dicussed in the video:

- loading a run corresponging to a experiment with a sample.
- matching a direct beam run to a sample run, with a discussion of the conditions for a good match/
- opening a "reduced file" containing all necessary metada to carry out a reduction workflow.
- selecting peak and background regions for a sample run.
- explanation of columns "I0", "NL", "NR", "x0", "xw", "y0", "yw", "bg0", "bgw", "Dpix", "Theta",
  and "Dir. run" in the table of loaded runs.
- the "polarizer mirror" selector for upstream polarization and "analyzer" selector for downstream polarization.
- (desired) selecting a polarization state will determine the input state for the stitching.
- (desired) a stitching using all polarization states, i.e., a global fit. In the global fit, the
  scaling factors are the same for all polarization states, i.e, they are constrained among
  polarization states.


Useful resources for GUI development
------------------------------------

- ``Qt Designer`` is the Qt tool for designing and building graphical user interfaces (GUIs)
  with ``Qt Widgets`` (https://doc.qt.io/qt-6/qtdesigner-manual.html)


Developing with PyCharm
-----------------------
Please refer to section :ref:`developing_with_pycharm` in the Development Environment page..
