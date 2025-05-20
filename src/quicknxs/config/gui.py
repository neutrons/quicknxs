# -*- coding: utf-8 -*-
# pylint: disable=invalid-name
"""
GUI configuration settings
"""

from qtpy import QtGui

config_file = "gui"

# UI geometry
interface = "default"
geometry = None
state = None
splitters = ([240, 505, 239], [298, 438], [240, 169, 360])

# plot options
color_selection = 0
show_colorbars = False
normalizeXTof = False
# plot borders
figure_params = [
    {"top": 0.95, "right": 0.95, "bottom": 0.1, "left": 0.15},  # xy_overview
    {"top": 0.95, "right": 0.95, "bottom": 0.1, "left": 0.15},  # xtof_overview
    {"top": 0.95, "right": 0.95, "bottom": 0.1, "left": 0.15},  # refl
    {"top": 0.95, "right": 0.95, "bottom": 0.1, "left": 0.15},  # x_project
    {"top": 0.95, "right": 0.95, "bottom": 0.1, "left": 0.15},  # y_project
]


# QColors
class QColors:
    black = QtGui.QColor(0, 0, 0)
    dark_grey = QtGui.QColor(200, 200, 200)
    light_grey = QtGui.QColor(220, 220, 220)
    white = QtGui.QColor(255, 255, 255)
    yellow = QtGui.QColor(246, 213, 16)
