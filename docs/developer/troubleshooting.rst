.. _troubleshooting:

Troubleshooting
===============


PyQt5 and PySide6 collide when debugging with PyCharm
-----------------------------------------------------
When debugging gui.py::main with PyCharm, the following error may occur:

.. code-block:: python

   Matplotlib is using PySide6 which wraps 6.7.3 however an instantiated QApplication from PyQt5
   which wraps 5.15.8 exists.  Mixing Qt major versions may not work as expected.

Currently, QuickNXS contains PyQt5 and PiSide6 which are not compatible with each other.
Please refer to the section :ref:`developing_with_pycharm` in the Development Environment page
for instructions on how to select `PyQt5` as the default bindings to Qt in the `python debugger`.
