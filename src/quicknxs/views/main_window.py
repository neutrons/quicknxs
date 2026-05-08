import logging
import os
from contextlib import contextmanager

from qtpy import QtCore, QtWidgets

from quicknxs import __version__ as quicknxs_version
from quicknxs.models.processing_workflow import ProcessingWorkflow
from quicknxs.presenters.configuration_handler import ConfigurationHandler
from quicknxs.presenters.data_presenter import DataPresenter
from quicknxs.presenters.main_presenter import MainPresenter
from quicknxs.presenters.plot_presenter import PlotPresenter
from quicknxs.utils.filepath import FilePath
from quicknxs.views import load_ui
from quicknxs.views.deadtime_settings import DeadTimeSettingsView
from quicknxs.views.offspec_slice_dialog import OffSpecSliceDialog
from quicknxs.views.plotting import PlotView
from quicknxs.views.reduction_dialog import ReductionDialog
from quicknxs.views.smooth_dialog import OffSpecParametersDialog


@contextmanager
def disabled_widget(widget: QtWidgets.QWidget):
    """
    Temporarily disable a widget for the duration of the context.

    Restores the enabled state of the widget when the context exits.
    """
    prev_enabled = widget.isEnabled()
    widget.setEnabled(False)
    try:
        yield
    finally:
        widget.setEnabled(prev_enabled)


class MainWindow(QtWidgets.QMainWindow):
    """Main application window."""

    # UI events
    file_loaded_signal = QtCore.Signal()
    """Signal emitted when a file is loaded."""

    initiate_projection_plot = QtCore.Signal(bool)
    """Signal to initiate the projection plot."""

    initiate_reflectivity_or_intensity_plot = QtCore.Signal()
    """Signal to initiate the reflectivity or intensity plot."""

    update_specular_viewer = QtCore.Signal()
    """Signal to update the specular viewer."""

    update_off_specular_viewer = QtCore.Signal()
    """Signal to update the off-specular viewer."""

    update_gisans_viewer = QtCore.Signal()
    """Signal to update the GISANS viewer."""

    def __init__(self):
        """Initialization."""
        # Base class
        QtWidgets.QMainWindow.__init__(self)

        # Initialize the UI widgets
        self.reduction_table_menu = None
        self.ui = load_ui("ui_main_window.ui", base_instance=self)
        version = quicknxs_version if quicknxs_version.lower() != "unknown" else ""
        self.setWindowTitle(f"QuickNXS Magnetic Reflectivity {version}")

        # Application settings
        self.settings = QtCore.QSettings(".quicknxs")

        # Object managers
        self.data_presenter = DataPresenter(self.settings.value("current_directory", os.path.expanduser("~")))
        self.plot_view = PlotView(self)

        r"""Setting `auto_change_active = True` bypasses execution of:
        - MainWindow.file_open_from_list()
        - MainWindow.changeRegionValues()
        - MainPresenter.reduction_table_changed()
        - MainPresenter.direct_beam_table_changed()
        """
        self.auto_change_active = False

        # Event handlers
        self.plot_presenter = PlotPresenter(self)
        self.file_handler = MainPresenter(self)
        self.config_handler = ConfigurationHandler(self)
        self.ui.compare_widget.data_presenter = self.data_presenter

        # Initialization for specific instrument
        # Retrieve configuration from config and enable/disable features
        self.initialize_instrument()
        self.hide_unsupported()

        self.file_loaded_signal.connect(self.file_handler.update_overview_run_info_from_active_run)
        self.file_loaded_signal.connect(self.file_handler.update_daslog)
        self.file_loaded_signal.connect(self.plotActiveTab)

        self.initiate_projection_plot.connect(self.plot_view.plot_projections)
        self.initiate_reflectivity_or_intensity_plot.connect(self.plot_view.plot_reflectivity_or_intensity)

        self.ui.deadtime_entry.settingsButton.clicked.connect(self.open_deadtime_settings)
        self.ui.deadtime_entry.reload_files_signal.connect(self.reload_all_files)

    def closeEvent(self, event):
        """Close UI event."""
        self.file_handler.get_configuration_from_ui()
        event.accept()

    def keyPressEvent(self, event):
        """UI event."""
        if event.modifiers() == QtCore.Qt.ControlModifier:
            self.plot_presenter.control_down = True
        else:
            self.plot_presenter.control_down = False

    def keyReleaseEvent(self, event):
        """UI event."""
        self.plot_presenter.control_down = False

    def initialize_instrument(self):
        """Initialize instrument according to the instrument and saved parameters."""
        for i in range(1, 12):
            getattr(self.ui, "selectedCrossSection%i" % i).hide()
        self.ui.selectedCrossSection0.show()
        self.ui.selectedCrossSection0.setText("None")

        self.file_handler.populate_from_configuration()

    def handle_roi_checkbox(self, state):
        """Handle the ROI checkbox state change."""
        # Enable/disable the automatic x and y peak finding
        use_metadata_roi = state == QtCore.Qt.Checked
        if use_metadata_roi:
            self.ui.actionAutoXROI.setChecked(False)
            self.ui.actionAutoYROI.setChecked(False)
        self.ui.actionAutoXROI.setEnabled(not use_metadata_roi)
        self.ui.actionAutoYROI.setEnabled(not use_metadata_roi)

    def hide_sidebar(self):
        self.file_handler.hide_sidebar()

    def hide_run_data(self):
        self.file_handler.hide_run_data()

    def hide_data_table(self):
        self.file_handler.hide_data_table()

    def hide_unsupported(self):
        """Hide what we don't support."""
        # Hide event filtering (which is not really event filtering)
        for i in range(self.ui.event_filtering_layout.rowCount() * self.ui.event_filtering_layout.columnCount()):
            if self.ui.event_filtering_layout.itemAt(i):
                self.ui.event_filtering_layout.itemAt(i).widget().hide()

        # Hide format selectiuon since we're only using event data
        self.ui.oldFormatActive.hide()
        self.ui.histogramActive.hide()
        self.ui.counts_roi_label.hide()
        self.ui.eventActive.hide()

        self.reset_data_tabs()

    # Actions defined in Qt Designer
    def file_open_dialog(self):
        """Show a dialog to open a new file."""
        self.file_handler.file_open_dialog()

    # Actions defined in Qt Designer
    def file_open_sum_dialog(self):
        """Read a set of congruent file data sets.

        Select a list of event or histogram files, check their metadata is compatible, and read-in.
        """
        self.file_handler.file_open_sum_dialog()

    def file_loaded(self):
        """Update UI after a file is loaded."""
        self.file_handler.file_loaded()

    def file_open_from_list(self):
        r"""Called when a new file is selected from the file list. This is an event call."""
        if self.auto_change_active:
            return
        QtWidgets.QApplication.instance().processEvents()
        item = self.ui.file_list.currentItem()  # type: QListWidgetItem
        name = str(item.text())  # e.g 'REF_M_38199.nxs.h5' or 'REF_M_38198.nxs.h5+REF_M_38199.nxs.h5'
        filepath = FilePath.join(self.data_presenter.current_directory, name)

        # disable adding file to reduction or direct beam list before it has been successfully loaded
        with disabled_widget(self.ui.mainToolbar):
            self.file_handler.open_file(filepath)

    def reload_file(self):
        """Reload the file that is currently selected form the list."""
        self.file_handler.open_file(self.data_presenter.current_file, force=True)

    def change_active_cross_section(self, is_checked: bool):
        """Update the run info and overview plots when the active cross section is changed.

        The toggled() signal is emitted from both radio buttons whose states were changed,
        therefore, use the bool value to only perform update actions once.

        Parameters
        ----------
        is_checked: bool
            The state of the radio button that emitted the signal.
        """
        if is_checked:
            self.file_handler.active_cross_section_changed()

    def plotActiveTab(self):
        """Select the appropriate function to plot all visible images."""
        if self.data_presenter.active_cross_section is None:
            return

        color = str(self.ui.color_selector.currentText())
        if color != self.plot_view.color and self.plot_view.color is not None:
            self.plot_view.color = color
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
        elif self.plot_view.color is None:
            self.plot_view.color = color
        if self.ui.plotTab.currentIndex() == 0:
            self.plot_view.plot_overview()
        elif self.ui.plotTab.currentIndex() == 1:
            self.plot_view.plot_xy()
        elif self.ui.plotTab.currentIndex() == 2:
            self.plot_view.plot_xtof()
        elif self.ui.plotTab.currentIndex() == 3:
            self.file_handler.compute_offspec_on_change()
            self.plot_view.plot_offspec()
        elif self.ui.plotTab.currentIndex() == 4:
            self.file_handler.compute_gisans_on_change(active_only=True)
            self.plot_view.plot_gisans()
        elif self.ui.plotTab.currentIndex() == 6:
            self.ui.compare_widget.draw()

    def toggleColorbars(self):
        """Refresh plots because of a color or scale change."""
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

        if self.data_presenter.active_cross_section.is_direct_beam:
            # Update the intensity plot in case the scale was toggled between ToF and Wavelength
            self.initiate_reflectivity_or_intensity_plot.emit()

    def changeRegionValues(self):
        """Called when the reflectivity extraction region has been changed.

        Sets up a trigger to replot the reflectivity with a delay so
        a subsequent change can occur without several replots.
        """
        if self.auto_change_active:
            return

        change_type = self.file_handler.check_region_values_changed()
        if change_type >= 0:
            configuration = self.file_handler.get_configuration_from_ui()

            if self.data_presenter.active_cross_section is not None:
                active_only = not self.ui.action_use_common_ranges.isChecked()
                self.data_presenter.update_configuration(configuration=configuration, active_only=active_only)
                self.plot_presenter.change_region_values()
                self.file_handler.update_calculated_data()

                # Update the reduction/direct beam tables if this data set is in it
                self.file_handler.update_tables()

                QtWidgets.QApplication.instance().processEvents()
                if change_type > 0:
                    try:
                        self.data_presenter.calculate_reflectivity(configuration=configuration, active_only=active_only)
                    except Exception:
                        self.file_handler.report_message(
                            "There was a problem updating the reflectivity", pop_up=False, is_error=True
                        )
                self.initiate_reflectivity_or_intensity_plot.emit()
                self.update_specular_viewer.emit()

    def global_reflectivity_config_changed(self):
        """Perform action upon change in global reflectivity configuration."""
        if self.auto_change_active:
            return

        self.data_presenter.reduce_spec()
        self.initiate_reflectivity_or_intensity_plot.emit()
        self.update_specular_viewer.emit()

    def set_active_reduction_data(self, checked: bool, row: int):
        """Select a data set (when checking the active box in the normalization/reduction table)."""
        if not checked:
            return
        self.data_presenter.set_active_data_from_reduction_list(row)
        self.file_loaded()

    def reductionTableChanged(self, item):
        """Perform action upon change in data reduction list."""
        self.file_handler.reduction_table_changed(item)

    def reduction_table_right_click(self, pos: QtCore.QPoint):
        """Handle right-click on the reduction table."""
        self.file_handler.reduction_table_right_click(pos, True)

    def set_active_direct_beam(self, checked: bool, row: int):
        """Select a data set when the user changes the active run radio button (col 0) in the direct beam table."""
        if not checked:
            return
        self.data_presenter.set_active_data_from_direct_beam_list(row)
        self.file_loaded()

    def direct_beam_table_right_click(self, pos: QtCore.QPoint):
        """Handle right-click on the direct beam table."""
        self.file_handler.reduction_table_right_click(pos, False)

    def replotProjections(self):
        """Signal handling to replot the projections."""
        self.initiate_projection_plot.emit(True)
        self.initiate_reflectivity_or_intensity_plot.emit()

    def addRefl(self):
        """Signal handling to add a new reflectivity data set."""
        self.file_handler.add_reflectivity()

    def removeRefl(self):
        """Signal handling to remove a reflectivity data set."""
        self.file_handler.remove_reflectivity()

    def clearRefList(self):
        """Signal handling to clear the reflectivity data set list."""
        self.file_handler.clear_reflectivity()

    ### Direct beam table management

    # TODO: deal with this (what does this comment mean?)
    def get_direct_beam(self):
        """Retrieve the direct beam data for the active reflectivity data.

        This is used to normalize the distributions we are plotting.
        See `plotting.plot_xtof` and `plotting.plot_overview`
        """
        return self.data_presenter.get_active_direct_beam()

    def add_direct_beam(self):
        self.file_handler.add_direct_beam()

    def direct_beam_table_changed(self, item: QtWidgets.QTableWidgetItem):
        self.file_handler.direct_beam_table_changed(item)

    def remove_direct_beam(self):
        """Signal handling."""
        self.file_handler.remove_direct_beam()

    def clear_direct_beam_list(self):
        """Signal handling."""
        self.file_handler.clear_direct_beams()

    def match_direct_beam_clicked(self):
        """Find the best direct beam run for the activate data set and compute the reflectivity as needed."""
        if self.data_presenter.find_best_direct_beam():
            dpix = self.data_presenter.update_direct_pixel_from_direct_beam()
            if dpix is not None:
                self.ui.directPixelOverwrite.setValue(dpix)
            # self.file_handler.direct_beam_matched()
            self.file_handler.update_tables()
            self.file_handler.update_calculated_data()
            QtWidgets.QApplication.instance().processEvents()
            try:
                self.data_presenter.calculate_reflectivity()
            except Exception:
                self.file_handler.report_message(
                    "There was a problem updating the reflectivity", pop_up=False, is_error=True
                )

            self.initiate_reflectivity_or_intensity_plot.emit()

    def openByNumber(self):
        """Signal handling to open a file by run number."""
        self.file_handler.open_run_number()

    def refresh_offspec(self):
        """Refresh / recalculate the off-specular plots."""
        self.file_handler.compute_offspec_on_change(force=True)
        self.plot_view.plot_offspec()

    def change_offspec_colorscale(self):
        """Change the intensity limits for the color scale of the off-specular plots."""
        self.plot_presenter.change_offspec_colorscale()

    def cutPoints(self):
        """Cut the start and end of the active data set to 5% of its maximum intensity."""
        self.file_handler.trim_data_to_normalization()
        self.update_specular_viewer.emit()

    def stripOverlap(self):
        """Remove overlapping points in the reflectivity.

        Cutting is done from the lower Qz measurements.
        """
        self.file_handler.strip_overlap()
        self.update_specular_viewer.emit()

    def normalizeTotalReflection(self):
        """Stitch the reflectivity parts and normalize to 1."""
        self.file_handler.stitch_reflectivity()
        self.update_specular_viewer.emit()

    def autoRef(self):
        """Signal handling to run automated file selection."""
        self.file_handler.automated_file_selection()

    ### Data tab management

    def addDataTable(self):
        """Add data tab for additional peaks/ROIs."""
        self.ui.addTabButton.setEnabled(False)  # Disable the `addTabButton` at the beginning
        try:
            next_tab_idx = self.data_tab_count + 1
            self.ui.tabWidget.setTabVisible(next_tab_idx, True)
            self.data_presenter.add_additional_reduction_list(next_tab_idx)
            self.file_handler.initialize_additional_reduction_table(next_tab_idx)
            self.data_tab_count += 1
            self.ui.removeTabButton.setEnabled(True)
            if self.data_tab_count == self.max_data_tab_count:
                self.ui.addTabButton.setEnabled(False)
        finally:
            # Re-enable the `addTabButton` if tabs still remain and no exceptions occurred
            if self.data_tab_count > self.min_data_tab_count and self.data_tab_count < self.max_data_tab_count:
                self.ui.addTabButton.setEnabled(True)

    def removeDataTable(self):
        """Remove last data tab for additional peaks/ROI:s"""
        self.ui.removeTabButton.setEnabled(False)  # Disable the `removeTabButton` at the beginning
        try:
            self.ui.tabWidget.setTabVisible(self.data_tab_count, False)
            self.data_presenter.remove_additional_reduction_list(self.data_tab_count)
            self.data_tab_count -= 1
            self.ui.addTabButton.setEnabled(True)
            if self.data_tab_count == self.min_data_tab_count:
                self.ui.removeTabButton.setEnabled(False)
        finally:
            # Re-enable the `removeTabButton` if tabs still remain and no exceptions occurred
            if self.data_tab_count > self.min_data_tab_count:
                self.ui.removeTabButton.setEnabled(True)

    def add_data_tab_by_index(self, tab_index: int):
        """Add/update a specific data tab."""
        if self.data_tab_count < tab_index <= self.max_data_tab_count:
            self.ui.tabWidget.setTabVisible(tab_index, True)
            self.data_tab_count = tab_index
        if self.data_tab_count > self.min_data_tab_count:
            self.ui.removeTabButton.setEnabled(True)
        if self.data_tab_count == self.max_data_tab_count:
            self.ui.addTabButton.setEnabled(False)

    def reset_data_tabs(self):
        """Reset UI to one visible data tab."""
        self.min_data_tab_count = 1
        self.max_data_tab_count = max(self.min_data_tab_count, self.ui.tabWidget.count() - 1)
        self.data_tab_count = 1

        # Initially enable the add button and disable the remove button
        self.ui.addTabButton.setEnabled(True)
        self.ui.removeTabButton.setEnabled(False)

        # Ensure the current tab remains visible while hiding the optional peak tabs.
        if self.ui.tabWidget.currentIndex() > self.data_tab_count:
            self.ui.tabWidget.setCurrentIndex(self.data_tab_count)

        # Initially hide the tabs used for multiple peaks
        for tab_index in range(self.data_tab_count + 1, self.ui.tabWidget.count()):
            self.ui.tabWidget.setTabVisible(tab_index, False)

    def current_table_changed(self, tab_index: int):
        """Update the state for active data set and the UI."""
        if tab_index != 0:  # not direct beam tab
            # Update the active reduction list index
            self.data_presenter.update_active_reduction_list(tab_index)
        else:
            # When switching to direct beam tab, update active direct beam
            # This maintains the previously selected direct beam row if possible
            self.data_presenter.update_active_direct_beam()

        if self.data_presenter.data_sets:
            self.file_loaded()

    ### End of data tab management

    def reduceDatasets(self):
        """Open a dialog to select reduction options for the current list of reduction items."""
        if len(self.data_presenter.reduction_list) == 0:
            self.file_handler.report_message("The data to be reduced must be added to the reduction table", pop_up=True)
            return
        dialog = ReductionDialog(self)
        dialog.exec_()
        # get options as a dictionary
        output_options = dialog.get_options()
        dialog.destroy()

        if output_options is not None:
            self.file_handler.get_configuration_from_ui()

            # Make sure the off-specular has been calculated if needed
            if output_options.apply_smoothing or output_options.export_offspec_slices:
                self.file_handler.compute_offspec_on_change()

            # Show combined parameters dialog when smoothing or binned output is requested
            show_smoothing = output_options.apply_smoothing

            if show_smoothing:
                dia = OffSpecParametersDialog(
                    self,
                    self.data_presenter,
                    show_smoothing=show_smoothing,
                )
                if not dia.exec_():
                    logging.info("Skipping off-specular parameters")
                    dia.destroy()
                    return
                else:
                    # Get parameters and add to output options
                    params = dia.get_parameters()
                    for k, v in params.items():
                        setattr(output_options, k, v)
                    dia.destroy()

            # Show slice parameters dialog when off-specular slices are requested
            if output_options.export_offspec_slices:
                dia = OffSpecSliceDialog(self, self.data_presenter)
                if not dia.exec_():
                    logging.info("Skipping slice parameters")
                    dia.destroy()
                    return
                else:
                    # Get slice parameters and add to output options
                    slice_params = dia.get_parameters()
                    for k, v in slice_params.items():
                        setattr(output_options, k, v)
                    dia.destroy()

            # If we want to save images, we just need to cycle through
            # and call: self.canvas.print_figure(unicode(fname[0]))
            wrk = ProcessingWorkflow(self.data_presenter, output_options)
            wrk.execute(self.file_handler.new_progress_reporter())

            # Show final results
            if output_options.export_offspec:
                self.update_off_specular_viewer.emit()
            if output_options.export_gisans:
                self.update_gisans_viewer.emit()

    def loadExtraction(self):
        self.file_handler.open_reduced_file_dialog()

    def refresh_file_list(self):
        self.file_handler.update_file_list()

    def show_results(self):
        self.file_handler.show_results()

    def apply_offspec_crop(self):
        self.plot_view.plot_offspec(crop=True)

    def open_deadtime_settings(self):
        """Show the dialog for dead-time options.

        Update global configuration parameters upon closing the dialog.
        """
        view = DeadTimeSettingsView(parent=self)
        view.reload_files_signal.connect(self.reload_all_files)
        view.exec_()

    def reload_all_files(self):
        """Reload all previously loaded files upon change in loading configuration."""
        self.file_handler.reload_all_files()

    def propagate_binning_options_to_runs(self):
        """Apply the binning options in the global reflectivity extraction panel to all runs."""
        # update the internal configuration state
        self.file_handler.propagate_binning_options_to_run_config()
        # recalculate and replot reflectivity
        self.global_reflectivity_config_changed()

    # Un-used UI signals
    def change_gisans_colorscale(self):
        return NotImplemented

    # From the Advanced menu
    def open_advanced_background(self):
        return NotImplemented

    def open_polarization_window(self):
        return NotImplemented

    def open_rawdata_dialog(self):
        return NotImplemented
