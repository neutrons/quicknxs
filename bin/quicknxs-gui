#!/usr/bin/env python
"""
    Start script for reduction application
"""
import sys
import os
import types

import logging
import logging.handlers

# Set log level
logging.getLogger().setLevel(logging.INFO)

# Formatter
ft = logging.Formatter("%(levelname)s:%(asctime)-15s %(message)s")
# Create a log file handler
fh = logging.handlers.TimedRotatingFileHandler(
    os.path.join(os.path.expanduser("~"), "refred_m.log"), when="midnight", backupCount=15
)
fh.setLevel(logging.INFO)
fh.setFormatter(ft)
logging.getLogger().addHandler(fh)


def no_abort_excepthook(exc_type, value, tback):
    # log the exception here
    logging.error("Abort-type of error %s:\n%s", value, tback)
    # then call the default handler
    sys.__excepthook__(exc_type, value, tback)


sys.excepthook = no_abort_excepthook

# Set Qt5Agg now so matplotlib doesn't complain later
import matplotlib

matplotlib.use("Qt5Agg")

import mantid
import quicknxs

print("##################################################")
print("# QuickNXS %s " % quicknxs.__version__)
print("#    with Mantid: %s " % mantid.__version__)
print("##################################################")

from PyQt5.QtWidgets import QApplication
from quicknxs.interfaces.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    application = MainWindow()
    application.show()
    app.exec_()


if __name__ == "__main__":
    main()
