#!/usr/bin/env python
"""
Start script for reduction application
"""

# Set Qt5Agg now so matplotlib doesn't complain later
import os

os.environ["QT_API"] = "pyqt5"
import matplotlib

matplotlib.use("Qt5Agg")

import logging
import logging.handlers
import sys

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
