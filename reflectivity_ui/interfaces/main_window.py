# -*- coding: utf-8 -*-
# pylint: disable=invalid-name, line-too-long, too-many-public-methods, too-many-instance-attributes,
# pylint; disable=wrong-import-order, bare-except
r"""
    Main application window
"""

# package imports
from .data_manager import DataManager
from .plotting import PlotManager
from .reduction_dialog import ReductionDialog
from .smooth_dialog import SmoothDialog
import reflectivity_ui
from reflectivity_ui.interfaces.data_handling.filepath import FilePath
from reflectivity_ui.interfaces.event_handlers.configuration_handler import ConfigurationHandler
from reflectivity_ui.interfaces.event_handlers.plot_handler import PlotHandler
from reflectivity_ui.interfaces.event_handlers.main_handler import MainHandler
from reflectivity_ui.interfaces import load_ui
from reflectivity_ui.ui.deadtime_settings import DeadTimeSettingsView

# 3rd-party
from PyQt5 import QtCore, QtWidgets

# standard imports
import logging
import os
import sys
from enum import Enum


DataTabButtonMode = Enum('DataTabButtonMode', ['ADD', 'REMOVE'])

class MainWindow(QtWidgets.QMainWindow):
    """
    Main application window
    """

    # UI events
    file_loaded_signal = QtCore.pyqtSignal()
    """Signal emitted when a file is loaded."""

    initiate_projection_plot = QtCore.pyqtSignal(bool)
    """Signal to initiate the projection plot."""

    initiate_reflectivity_plot = QtCore.pyqtSignal(bool)
    """Signal to initiate the reflectivity plot."""

    update_specular_viewer = QtCore.pyqtSignal()
    """Signal to update the specular viewer."""

    update_off_specular_viewer = QtCore.pyqtSignal()
    """Signal to update the off-specular viewer."""

    update_gisans_viewer = QtCore.pyqtSignal()
    """Signal to update the GISANS viewer."""

    def __init__(self):
        """
        Initialization
        """
        # Base class
        QtWidgets.QMainWindow.__init__(self)

        # Initialize the UI widgets
        self.reduction_table_menu = None
        self.ui = load_ui("ui_main_window.ui", baseinstance=self)
        version = reflectivity_ui.__version__ if reflectivity_ui.__version__.lower() != "unknown" else ""
        self.setWindowTitle(f"QuickNXS Magnetic Reflectivity {version}")

        # Application settings
        self.settings = QtCore.QSettings(".refredm")
        # Object managers
        self.data_manager = DataManager(self.settings.value("current_directory", os.path.expanduser("~")))
        self.plot_manager = PlotManager(self)

        r"""Setting `auto_change_active = True` bypasses execution of:
        - MainWindow.file_open_from_list()
        - MainWindow.changeRegionValues()
        - MainHandler.reduction_table_changed()"""
        self.auto_change_active = False

        # Event handlers
        self.plot_handler = PlotHandler(self)
        self.file_handler = MainHandler(self)
        self.config_handler = ConfigurationHandler(self)
        self.ui.compare_widget.data_manager = self.data_manager

        # Initialization for specific instrument
        # Retrieve configuration from config and enable/disable features
        self.initialize_instrument()
        self.hide_unsupported()
        self.toggle_smoothing()

        self.file_loaded_signal.connect(self.file_handler.update_info)
        self.file_loaded_signal.connect(self.file_handler.update_daslog)
        self.file_loaded_signal.connect(self.plotActiveTab)
        self.initiate_projection_plot.connect(self.plot_manager.plot_projections)

        self.initiate_reflectivity_plot.connect(self.plot_manager.plot_refl)

        self.ui.deadtime_entry.settingsButton.clicked.connect(self.open_deadtime_settings)
        self.ui.deadtime_entry.reload_files_signal.connect(self.reload_all_files)

    def closeEvent(self, event):
        """Close UI event"""
        self.file_handler.get_configuration()
        event.accept()

    def keyPressEvent(self, event):
        """UI event"""
        if event.modifiers() == QtCore.Qt.ControlModifier:
            self.plot_handler.control_down = True
        else:
            self.plot_handler.control_down = False

    def keyReleaseEvent(self, event):
        """UI event"""
        self.plot_handler.control_down = False

    def initialize_instrument(self):
        """
        Initialize instrument according to the instrument
        and saved parameters
        """
        for i in range(1, 12):
            getattr(self.ui, "selectedChannel%i" % i).hide()
        self.ui.selectedChannel0.show()
        self.ui.selectedChannel0.setText("None")

        self.file_handler.populate_from_configuration()

    def hide_sidebar(self):
        self.file_handler.hide_sidebar()

    def hide_run_data(self):
        self.file_handler.hide_run_data()

    def hide_data_table(self):
        self.file_handler.hide_data_table()

    def hide_unsupported(self):
        """
        Hide what we don't support
        """
        # Hide event filtering (which is not really event filtering)
        for i in range(self.ui.event_filtering_layout.rowCount() * self.ui.event_filtering_layout.columnCount()):
            if self.ui.event_filtering_layout.itemAt(i):
                self.ui.event_filtering_layout.itemAt(i).widget().hide()

        # Hide format selectiuon since we're only using event data
        self.ui.oldFormatActive.hide()
        self.ui.histogramActive.hide()
        self.ui.counts_roi_label.hide()
        self.ui.eventActive.hide()

        # Initially hide the tabs used for multiple peaks
        self.min_data_tab_count = 1
        self.max_data_tab_count = 4
        self.data_tab_count = 1
        self.data_tab_button_mode = DataTabButtonMode.ADD
        self.ui.tabWidget.setTabVisible(2, False)
        self.ui.tabWidget.setTabVisible(3, False)
        self.ui.tabWidget.setTabVisible(4, False)

    # Actions defined in Qt Designer
    def file_open_dialog(self):
        """
        Show a dialog to open a new file.
        """
        self.file_handler.file_open_dialog()

    # Actions defined in Qt Designer
    def file_open_sum_dialog(self):
        r"""
        @brief Read a set of congruent file data sets.
        @details Select a list of event or histogram files, check their metadata is compatible, and read-in.
        """
        self.file_handler.file_open_sum_dialog()

    def file_loaded(self):
        """
        Update UI after a file is loaded
        """
        self.file_handler.file_loaded()

    def file_open_from_list(self):
        r"""Called when a new file is selected from the file list. This is an event call."""
        if self.auto_change_active:
            return
        QtWidgets.QApplication.instance().processEvents()
        item = self.ui.file_list.currentItem()  # type: QListWidgetItem
        name = str(item.text())  # e.g 'REF_M_38199.nxs.h5' or 'REF_M_38198.nxs.h5+REF_M_38199.nxs.h5'
        filepath = FilePath.join(self.data_manager.current_directory, name)
        self.file_handler.open_file(filepath)

    def reload_file(self):
        """
        Reload the file that is currently selected form the list.
        """
        self.file_handler.open_file(self.data_manager.current_file, force=True)

    def change_active_channel(self, is_checked):
        """
        The overview and reflectivity channel was changed. This updates the run
        information and plots in the Overview area

        The toggled() signal is emitted from both radio buttons whose states were changed,
        therefore, use the bool value to only perform channel update actions once.

        :param bool is_checked: the state of the radio button that emitted the signal
        """
        if is_checked:
            self.file_handler.active_channel_changed()

    def getNorm(self):
        """
        TODO: deal with this
        This is supposed to retrieve the normalization data for the active reflectivity
        data so that we can normalize the distributions we are plotting.
        See plotting.plot_xtof and plotting.plot_overview
        """
        return self.data_manager.get_active_direct_beam()

    def plotActiveTab(self):
        """
        Select the appropriate function to plot all visible images.
        """
        if self.data_manager.active_channel is None:
            return
        color = str(self.ui.color_selector.currentText())
        if color != self.plot_manager.color and self.plot_manager.color is not None:
            self.plot_manager.color = color
            plots = [
                self.ui.xy_pp,
                self.ui.xy_mp,
                self.ui.xy_pm,
                self.ui.xy_mm,
                self.ui.xtof_pp,
                self.ui.xtof_mp,
                self.ui.xtof_pm,
                self.ui.xtof_mm,
                self.ui.xy_overview,
                self.ui.xtof_overview,
            ]
            for plot in plots:
                plot.clear_fig()
        elif self.plot_manager.color is None:
            self.plot_manager.color = color
        if self.ui.plotTab.currentIndex() == 0:
            self.plot_manager.plot_overview()
        elif self.ui.plotTab.currentIndex() == 1:
            self.plot_manager.plot_xy()
        elif self.ui.plotTab.currentIndex() == 2:
            self.plot_manager.plot_xtof()
        elif self.ui.plotTab.currentIndex() == 3:
            self.file_handler.compute_offspec_on_change()
            self.plot_manager.plot_offspec()
        elif self.ui.plotTab.currentIndex() == 4:
            self.file_handler.compute_gisans_on_change(active_only=True)
            self.plot_manager.plot_gisans()
        elif self.ui.plotTab.currentIndex() == 6:
            self.ui.compare_widget.draw()

    def toggleColorbars(self):
        """Refresh plots because of a color or scale change"""
        plots = [
            self.ui.xy_pp,
            self.ui.xy_mp,
            self.ui.xy_pm,
            self.ui.xy_mm,
            self.ui.xtof_pp,
            self.ui.xtof_mp,
            self.ui.xtof_pm,
            self.ui.xtof_mm,
            self.ui.xy_overview,
            self.ui.xtof_overview,
            self.ui.offspec_pp,
            self.ui.offspec_mp,
            self.ui.offspec_pm,
            self.ui.offspec_mm,
        ]
        for plot in plots:
            plot.clear_fig()
        self.plotActiveTab()

    def changeRegionValues(self):
        """
        Called when the reflectivity extraction region has been changed.
        Sets up a trigger to replot the reflectivity with a delay so
        a subsequent change can occur without several replots.
        """
        if self.auto_change_active:
            return

        change_type = self.file_handler.check_region_values_changed()
        if change_type >= 0:
            configuration = self.file_handler.get_configuration()

            if self.data_manager.active_channel is not None:
                active_only = not self.ui.action_use_common_ranges.isChecked()
                self.data_manager.update_configuration(configuration=configuration, active_only=active_only)
                self.plot_handler.change_region_values()
                self.file_handler.update_calculated_data()

                # Update the reduction/direct beam tables if this data set is in it
                self.file_handler.update_tables()

                QtWidgets.QApplication.instance().processEvents()
                if change_type > 0:
                    try:
                        self.data_manager.calculate_reflectivity(configuration=configuration, active_only=active_only)
                    except Exception:
                        self.file_handler.report_message("There was a problem updating the reflectivity", pop_up=False)
                        logging.error("There was a problem updating the reflectivity")
                self.plot_manager.plot_refl()
                self.update_specular_viewer.emit()

    def global_reflectivity_config_changed(self):
        """
        Perform action upon change in global reflectivity configuration.
        """
        if self.auto_change_active:
            return

        self.data_manager.reduce_spec()
        self.initiate_reflectivity_plot.emit(True)
        self.update_specular_viewer.emit()

    def reductionTableChanged(self, item):
        """
        Perform action upon change in data reduction list.
        """
        self.file_handler.reduction_table_changed(item)

    def reduction_cell_activated(self, row, col):
        """
        Select a data set when the user double-clicks on a run number (col 0).
        in the reduction table.
        :param int row: row index
        :param int col: column index
        """
        if col == 0:
            self.data_manager.set_active_data_from_reduction_list(row)
            self.file_loaded()
            self.file_handler.active_data_changed()

    def reduction_table_right_click(self, pos):
        """
        Handle right-click on the reduction table.
        :param QPoint pos: mouse position
        """
        self.file_handler.reduction_table_right_click(pos, True)

    def direct_beam_table_right_click(self, pos):
        """
        Handle right-click on the direct beam table.
        :param QPoint pos: mouse position
        """
        self.file_handler.reduction_table_right_click(pos, False)

    def direct_beam_cell_activated(self, row, col):
        """
        Select a data set when the user double-clicks on a run number (col 0).
        in the direct beam table.
        :param int row: row index
        :param int col: column index
        """
        if col == 0:
            self.data_manager.set_active_data_from_direct_beam_list(row)
            self.file_loaded()
            # self.file_handler.active_data_changed()

    def replotProjections(self):
        """Signal handling"""
        self.initiate_projection_plot.emit(True)
        self.initiate_reflectivity_plot.emit(True)

    def addRefList(self):
        """Signal handling"""
        self.file_handler.add_reflectivity()

    def removeRefList(self):
        """Signal handling"""
        self.file_handler.remove_reflectivity()

    def clearRefList(self):
        """Signal handling"""
        self.file_handler.clear_reflectivity()

    def setNorm(self):
        """Signal handling"""
        self.file_handler.add_direct_beam()

    def remove_normalization(self):
        """Signal handling"""
        self.file_handler.remove_direct_beam()

    def clearNormList(self):
        """Signal handling"""
        self.file_handler.clear_direct_beams()

    def match_direct_beam_clicked(self):
        """
        Find the best direct beam run for the activate data set
        and compute the reflectivity as needed.
        """
        if self.data_manager.find_best_direct_beam():
            self.file_handler.update_tables()
            self.file_handler.update_calculated_data()
            QtWidgets.QApplication.instance().processEvents()
            try:
                self.data_manager.calculate_reflectivity()
            except Exception:
                self.file_handler.report_message("There was a problem updating the reflectivity", pop_up=False)
                logging.error("There was a problem updating the reflectivity")
            self.initiate_reflectivity_plot.emit(True)

    def openByNumber(self):
        """Signal handling"""
        self.file_handler.open_run_number()

    def refresh_offspec(self):
        """
        Refresh / recalculate the off-specular plots
        """
        self.file_handler.compute_offspec_on_change(force=True)
        self.plot_manager.plot_offspec()

    def change_offspec_colorscale(self):
        """
        Change the intensity limits for the color scale of the off-specular plots
        """
        self.plot_handler.change_offspec_colorscale()

    def cutPoints(self):
        """
        Cut the start and end of the active data set to 5% of its
        maximum intensity.
        """
        self.file_handler.trim_data_to_normalization()
        self.update_specular_viewer.emit()

    def stripOverlap(self):
        """
        Remove overlapping points in the reflecitviy, cutting always from the lower Qz
        measurements.
        """
        self.file_handler.strip_overlap()
        self.update_specular_viewer.emit()

    def normalizeTotalReflection(self):
        """
        Stitch the reflectivity parts and normalize to 1.
        """
        self.file_handler.stitch_reflectivity()
        self.update_specular_viewer.emit()

    def autoRef(self):
        self.file_handler.automated_file_selection()

    def addDataTable(self):
        """Add/remove data tabs for additional peaks/ROI:s"""
        if self.data_tab_button_mode == DataTabButtonMode.ADD:
            self.data_tab_count += 1
            self.ui.tabWidget.setTabVisible(self.data_tab_count, True)
            self.data_manager.add_additional_reduction_table(self.data_tab_count)

        elif self.data_tab_button_mode == DataTabButtonMode.REMOVE:
            self.ui.tabWidget.setTabVisible(self.data_tab_count, False)
            self.data_manager.remove_additional_reduction_table(self.data_tab_count)
            self.data_tab_count -= 1

        if self.data_tab_count == self.max_data_tab_count:
            self.ui.addTabButton.setText("-")
            self.data_tab_button_mode = DataTabButtonMode.REMOVE

        if self.data_tab_count == self.min_data_tab_count:
            self.ui.addTabButton.setText("+")
            self.data_tab_button_mode = DataTabButtonMode.ADD

    def setCurrentReductionTable(self, index):
        """Update the current reduction table"""
        self.data_manager.set_active_reduction_list_index(index)

    def reduceDatasets(self):
        r"""
        Open a dialog to select reduction options for the current list of
        reduction items.
        """
        if len(self.data_manager.reduction_list) == 0:
            self.file_handler.report_message(
                "The data to be reduced must be added to the reduction table", pop_up=True
            )
            return
        dialog = ReductionDialog(self)
        dialog.exec_()
        # get options as a dictionary
        output_options = dialog.get_options()
        dialog.destroy()

        if output_options is not None:
            self.file_handler.get_configuration()

            # Show smoothing dialog as needed
            if output_options["export_offspec_smooth"] and self.ui.offspec_smooth_checkbox.isChecked():
                # Make sure the off-specular has been calculated
                self.file_handler.compute_offspec_on_change()
                dia = SmoothDialog(self, self.data_manager)
                if not dia.exec_():
                    logging.info("Skipping smoothing options")
                    dia.destroy()
                    return
                else:
                    output_options = dia.update_output_options(output_options)
                    dia.destroy()

            # If we want to save images, we just need to cycle through
            # and call: self.canvas.print_figure(unicode(fname[0]))
            from .data_handling.processing_workflow import ProcessingWorkflow

            wrk = ProcessingWorkflow(self.data_manager, output_options)
            wrk.execute(self.file_handler.new_progress_reporter())

            # Show final results
            if output_options["export_offspec"]:
                self.update_off_specular_viewer.emit()
            if output_options["export_gisans"]:
                self.update_gisans_viewer.emit()

    def toggle_smoothing(self):
        if self.ui.offspec_smooth_checkbox.isChecked():
            self.ui.binning_frame.hide()
            self.ui.offspec_err_weight_checkbox.hide()
        else:
            self.ui.binning_frame.show()
            self.ui.offspec_err_weight_checkbox.show()

    def loadExtraction(self):
        self.file_handler.open_reduced_file_dialog()

    def refresh_file_list(self):
        self.file_handler.update_file_list()

    def show_results(self):
        self.file_handler.show_results()

    def apply_offspec_crop(self):
        self.plot_manager.plot_offspec(crop=True)

    def update_offspec_qz_bin_width(self, value=None):
        off_spec_nybins = self.ui.offspec_rebin_y_bins_spinbox.value()
        off_spec_y_min = self.ui.offspec_y_min_spinbox.value()
        off_spec_y_max = self.ui.offspec_y_max_spinbox.value()
        width = (off_spec_y_max - off_spec_y_min) / off_spec_nybins
        self.ui.offspec_qz_bin_width_label.setText("%8.6f 1/A" % width)

    def open_deadtime_settings(self):
        r"""Show the dialog for dead-time options. Update global configuration parameters upon
        closing the dialog."""
        view = DeadTimeSettingsView(parent=self)
        view.reload_files_signal.connect(self.reload_all_files)
        view.exec_()

    def reload_all_files(self):
        r"""Reload all previously loaded files upon change in loading configuration"""
        self.file_handler.reload_all_files()

    # Un-used UI signals
    # pylint: disable=missing-docstring, multiple-statements, no-self-use
    def change_gisans_colorscale(self):
        return NotImplemented

    # From the Advanced menu
    def open_advanced_background(self):
        return NotImplemented

    def open_polarization_window(self):
        return NotImplemented

    def open_rawdata_dialog(self):
        return NotImplemented
