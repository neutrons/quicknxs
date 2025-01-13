from quicknxs.interfaces.event_handlers.widgets import AcceptRejectDialog
from PyQt5 import QtCore
from PyQt5.QtWidgets import QPushButton

wait = 100


def test_customized_dialog(qtbot):
    """Test customized dialog box"""
    window = AcceptRejectDialog(None, "pyqt test", "Hello World")

    # Add widget and launch
    qtbot.addWidget(window)

    # OK button
    window.show()
    qtbot.wait(wait)

    # Note: buttonBox.Ok is QStandardButton and not accepted by mouseClick()
    # buttonBox.button() can convert the QStandardButton to a QWidget for mouseClick()
    qtbot.mouseClick(window.buttonBox.button(window.buttonBox.Ok), QtCore.Qt.LeftButton)
    qtbot.wait(wait)

    assert window.is_accepted()
    assert window.isVisible() is False

    # Cancel button
    window.show()
    qtbot.wait(wait)

    qtbot.mouseClick(window.buttonBox.button(window.buttonBox.Cancel), QtCore.Qt.LeftButton)
    qtbot.wait(wait)

    assert window.is_accepted() is False
