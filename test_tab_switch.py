#!/usr/bin/env python
"""Quick test to verify tab switching to direct beam tab works."""

import sys

from qtpy import QtWidgets

from quicknxs.interfaces.main_window import MainWindow


def test_direct_beam_tab_switch():
    """Test switching to direct beam tab updates UI."""
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication(sys.argv)

    window = MainWindow()
    window.show()

    # Switch to data tab 1
    window.ui.tabWidget.setCurrentIndex(1)

    # Switch to direct beam tab
    window.ui.tabWidget.setCurrentIndex(0)


if __name__ == "__main__":
    test_direct_beam_tab_switch()
