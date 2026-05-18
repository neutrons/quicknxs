#!/usr/bin/env python
"""Start script for reduction application."""

import logging
import os
import sys

import matplotlib

from quicknxs.config.logging import setup_logging

# Set Qt5Agg now so matplotlib doesn't complain later
os.environ["QT_API"] = "pyqt5"
matplotlib.use("Qt5Agg")


setup_logging()


def no_abort_excepthook(exc_type, value, tback):
    """Catch uncaught exceptions and log them instead of aborting."""
    logging.error(
        "Encountered uncaught exception:",
        exc_info=(exc_type, value, tback),
    )


# Override the default sys.excepthook to prevent the application from aborting on uncaught exceptions
# and instead log the exception details to the log file and console.
sys.excepthook = no_abort_excepthook


import mantid
import mr_reduction

import quicknxs

print(f"""##################################################
# QuickNXS {quicknxs.__version__}
#    with mr_reduction: {mr_reduction.__version__}
#    with Mantid:       {mantid.__version__}
##################################################
""")

from qtpy.QtWidgets import QApplication

from quicknxs.views.main_window import MainWindow


def gui():
    app = QApplication(sys.argv)
    application = MainWindow()
    application.show()
    app.exec_()


if __name__ == "__main__":
    gui()
