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
    # log the exception here
    logging.error("Abort-type of error %s:\n%s", value, tback)
    # then call the default handler
    sys.__excepthook__(exc_type, value, tback)


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

from quicknxs.interfaces.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    application = MainWindow()
    application.show()
    app.exec_()


if __name__ == "__main__":
    main()
