# -*- coding: utf-8 -*-
# pylint: disable=bare-except
"""
  Widget to compare different reflectivities.
"""
import sys
import os
import logging
import numpy as np
import matplotlib.pyplot as plt

from PyQt5 import QtCore, QtWidgets, QtGui

from quicknxs.interfaces import load_ui
from ..interfaces.data_handling.processing_workflow import ProcessingWorkflow


class CompareWidget(QtWidgets.QWidget):
    changing_table = False

    def __init__(self, parent):
        QtWidgets.QWidget.__init__(self, parent)

        self._refl_color_map = plt.get_cmap("Set1")
        self.ui = load_ui("ui_compare_widget.ui", self)
        self.ui.compareList.verticalHeader().sectionMoved.connect(self.draw)
        self.file_paths = {}
        self.settings = QtCore.QSettings(".refredm")
        current_dir = self.settings.value("current_directory", os.path.expanduser("~"))
        self.active_folder = self.settings.value("compare_directory", current_dir)
        self.data_manager = None
        self.refl_data = None
        self.show_preview = False

    def refl_preview(self, checked=True):
        """
        Call-back method for when the user toggles the preview check box
        """
        self.show_preview = checked
        if checked:
            self.update_preview()
        self.draw()

    def update_preview(self):
        """
        Update the preview data
        """
        if self.data_manager:
            workflow = ProcessingWorkflow(self.data_manager)
            self.refl_data = workflow.get_output_data()
            self.draw()

    def open_file(self):
        """
        Show Open-File dialog
        """
        filter_ = "Reflectivity (*.dat *.txt);;All (*.*)"
        names, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self, "Open reflectivity file...", directory=self.active_folder, filter=filter_
        )

        if names:
            self.active_folder = os.path.abspath(os.path.dirname(names[0]))
            self.settings.setValue("compare_directory", self.active_folder)
            for name in names:
                self.read_file(name)
            self.ui.compareList.resizeColumnToContents(1)
            self.ui.compareList.resizeColumnToContents(2)
            self.draw()
        # Make sure the Open button is reset
        self.ui.pushButton_2.setDown(False)

    def read_file(self, file_path):
        """
        Read data file
        :param str file_path: file to load
        """
        label = os.path.basename(file_path)
        idx = self.ui.compareList.rowCount()

        # Find a color
        color_skip = 30
        color_offset = int(idx / 255.0 * color_skip / 2.0)
        color_id = (color_skip * idx + color_offset) % 255
        color = "#" + "".join([r"%02x" % int(f * 255) for f in self._refl_color_map(color_id)[:-1]])

        self.changing_table = True
        self.ui.compareList.setRowCount(idx + 1)
        item = QtWidgets.QTableWidgetItem(label)
        item.setFlags(QtCore.Qt.ItemIsEnabled)

        # Check that we can read the file
        data = np.loadtxt(file_path, comments="#").transpose()
        if len(data) == 0:
            plotlabel = "Empty file"
        else:
            try:
                plotlabel = label.split("REF_M_", 1)[1]
                plotlabel = plotlabel.split("_Specular")[0] + "  " + plotlabel.split("Specular_")[1].split(".")[0]
            except:
                plotlabel = label
        self.ui.compareList.setItem(idx, 0, item)
        item = QtWidgets.QTableWidgetItem(color)
        item.setBackground(QtGui.QColor(color))
        item.setForeground(QtGui.QColor("#ffffff"))
        item.setFlags(QtCore.Qt.ItemIsEnabled)
        self.ui.compareList.setItem(idx, 1, item)
        self.ui.compareList.setItem(idx, 2, QtWidgets.QTableWidgetItem(plotlabel))
        self.file_paths[label] = os.path.abspath(file_path)
        self.changing_table = False

    def clear_plot(self):
        """
        Remove all current plotted data
        """
        self.ui.compareList.setRowCount(0)
        self.draw()

    def clear_item(self):
        """
        Remove all current plotted data
        """
        logging.error(self.ui.compareList.currentRow())
        item_id = self.ui.compareList.currentRow()
        if item_id >= 0:
            self.ui.compareList.removeRow(item_id)
            self.draw()

    def draw(self):
        """
        Draw data
        """
        if self.changing_table:
            return
        try:
            self.ui.comparePlot.clear()
            if self.show_preview and self.refl_data:
                pol_states = self.refl_data["cross_sections"].keys()
                for key in pol_states:
                    _data = self.refl_data[key]
                    data = _data.T
                    self.ui.comparePlot.errorbar(data[0], data[1], data[2], capsize=1, label=key)
            header = self.ui.compareList.verticalHeader()
            for i in range(self.ui.compareList.rowCount()):
                idx = header.logicalIndex(i)
                name = self.file_paths[self.ui.compareList.item(idx, 0).text()]
                label = self.ui.compareList.item(idx, 2).text()
                color = self.ui.compareList.item(idx, 1).text()
                data = np.loadtxt(name, comments="#").transpose()
                if len(data) == 0:
                    logging.error("No data for %s", name)
                    continue
                self.ui.comparePlot.errorbar(data[0], data[1], data[2], capsize=1, label=label, color=color)
            if self.refl_data or self.ui.compareList.rowCount() > 0:
                self.ui.comparePlot.legend(frameon=False)
                self.ui.comparePlot.canvas.ax.set_yscale("log")
                self.ui.comparePlot.set_xlabel("Q$_z$ [Å$^{-1}$]")
                self.ui.comparePlot.set_ylabel("R")
            self.ui.comparePlot.draw()
        except:
            logging.error("CompareDialog: %s", sys.exc_info()[1])

    def edit_cell(self, row, column):
        """
        Cell editing call-back. Deal with color picking.
        """
        if column == 1:
            color_item = self.ui.compareList.item(row, column)
            color = QtGui.QColor(color_item.text())
            result = QtWidgets.QColorDialog.getColor(initial=color, parent=self)
            if result.isValid():
                color_item.setText(result.name())
                color_item.setBackground(result)


class CompareDialog(QtWidgets.QDialog):
    """
    A simple dialog window with a CompareWidget.
    """

    def __init__(self, *args, **kwargs):
        QtWidgets.QDialog.__init__(self, *args, **kwargs)
        self.setWindowTitle("Reflectivity comparison")
        self.cw = CompareWidget(self)
        vbox = QtWidgets.QVBoxLayout(self)
        vbox.addWidget(self.cw)
        self.setLayout(vbox)
        self.layout()
