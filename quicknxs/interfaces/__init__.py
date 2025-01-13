import os
from PyQt5.uic import loadUi
from quicknxs import ui


def load_ui(ui_filename, baseinstance):
    ui_filename = os.path.split(ui_filename)[-1]
    ui_path = os.path.dirname(ui.__file__)

    filename = os.path.join(ui_path, ui_filename)

    return loadUi(filename, baseinstance=baseinstance)
