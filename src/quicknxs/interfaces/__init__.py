import os
from typing import TypeVar

from qtpy.QtWidgets import QDialog, QMainWindow
from qtpy.uic import loadUi

from quicknxs import ui

Q = TypeVar("Q", QMainWindow, QDialog)


def load_ui(ui_filename: str, baseinstance: Q) -> Q:
    ui_filename = os.path.split(ui_filename)[-1]
    ui_path = os.path.dirname(ui.__file__)

    filename = os.path.join(ui_path, ui_filename)

    return loadUi(filename, baseinstance=baseinstance)
