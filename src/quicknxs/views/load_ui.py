"""Python interface for the Qt UI files."""

import os
from typing import TypeVar

from qtpy.QtWidgets import QDialog, QMainWindow, QWidget
from qtpy.uic import loadUi

from quicknxs.views import qt

Q = TypeVar("Q", QMainWindow, QDialog, QWidget)
"""Generic type for QMainWindow, QDialog, or QWidget."""


def load_ui(ui_filename: str, base_instance: Q) -> Q:
    ui_filename = os.path.split(ui_filename)[-1]
    ui_path = os.path.dirname(qt.__file__)
    filename = os.path.join(ui_path, ui_filename)
    return loadUi(filename, baseinstance=base_instance)
