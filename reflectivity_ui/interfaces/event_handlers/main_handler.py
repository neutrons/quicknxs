# -*- coding: utf-8 -*-
# pylint: disable=invalid-name, line-too-long, too-many-public-methods, too-many-instance-attributes, wrong-import-order, \
# bare-except, protected-access, too-many-arguments, too-many-statements
"""
    Manage file-related and UI events
"""
import numpy as np

# package imports
from reflectivity_ui.interfaces.configuration import Configuration
from reflectivity_ui.interfaces.data_handling.data_manipulation import NormalizeToUnityQCutoffError
from reflectivity_ui.interfaces.data_handling.data_set import NexusData, CrossSectionData
from reflectivity_ui.interfaces.data_handling.filepath import FilePath, RunNumbers
from reflectivity_ui.interfaces.event_handlers.progress_reporter import ProgressReporter
from reflectivity_ui.interfaces.event_handlers.status_bar_handler import StatusBarHandler
from reflectivity_ui.interfaces.event_handlers.widgets import AcceptRejectDialog
from reflectivity_ui.config import Settings

# 3rd-party imports
from PyQt5 import QtGui, QtCore, QtWidgets
from mantid.simpleapi import DeleteWorkspace, LoadEventNexus

# standard imports
import glob
import logging
import math
import os
import sys
import time
import traceback


class MainHandler(object):
    """
    Event handler for the main application window.
    """

    DIRECT_BEAM_TAB_INDEX = 0
    MAIN_DATA_TAB_INDEX = 1

    def __init__(self, main_window):
        self.ui = main_window.ui
        self.main_window = main_window
        self._data_manager = main_window.data_manager

        # Update file list when changes are made
        self._path_watcher = QtCore.QFileSystemWatcher([self._data_manager.current_directory], self.main_window)
        self._path_watcher.directoryChanged.connect(self.update_file_list)

        self.cache_indicator = QtWidgets.QLabel("Files loaded: 0")
        self.cache_indicator.setMargin(5)
        self.cache_indicator.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Preferred)
        self.cache_indicator.setMinimumWidth(110)
        self.ui.statusbar.addPermanentWidget(self.cache_indicator)
        button = QtWidgets.QPushButton("Empty Cache")
        self.ui.statusbar.addPermanentWidget(button)
        button.pressed.connect(self.empty_cache)
        button.setFlat(False)
        button.setMaximumSize(150, 20)

        # Create progress bar in statusbar
        self.progress_bar = QtWidgets.QProgressBar(self.ui.statusbar)
        self.progress_bar.setMinimumSize(20, 14)
        self.progress_bar.setMaximumSize(140, 100)
        self.ui.statusbar.addPermanentWidget(self.progress_bar)

        self.status_bar_handler = StatusBarHandler(self.ui.statusbar)

    @property
    def reduction_table(self):
        if self.ui.tabWidget.currentIndex == self.DIRECT_BEAM_TAB_INDEX:
            # get the table for the main data tab
            current_table = self.ui.tabWidget.widget(self.MAIN_DATA_TAB_INDEX).findChild(QtWidgets.QTableWidget)
        else:
            current_table = self.ui.tabWidget.currentWidget().findChild(QtWidgets.QTableWidget)
        return current_table

    # @property
    # def reductionTableIndex(self):
    #     return self.ui.tabWidget.currentIndex()

    def get_reduction_table_by_index(self, tab_index: int) -> QtWidgets.QTableWidget:
        """Return the QTableWidget for the data tab with the given index"""
        return self.ui.tabWidget.widget(tab_index).findChild(QtWidgets.QTableWidget)

    def get_active_reduction_table(self):
        """Return the QTableWidget for the active data tab"""
        return self.ui.tabWidget.currentWidget().findChild(QtWidgets.QTableWidget)

    def new_progress_reporter(self):
        """Return a progress reporter"""
        return ProgressReporter(progress_bar=self.progress_bar, status_bar=self.status_bar_handler)

    def empty_cache(self):
        """
        Empty the data cache
        """
        self._data_manager.clear_cache()
        self.cache_indicator.setText("Files loaded: 0")

    def hide_sidebar(self):
        if self.main_window.leftEntries.isHidden():
            self.main_window.leftEntries.show()
        else:
            self.main_window.leftEntries.hide()

    def hide_run_data(self):
        if self.main_window.runDataFrame.isHidden():
            self.main_window.runDataFrame.show()
        else:
            self.main_window.runDataFrame.hide()

    def hide_data_table(self):
        if self.main_window.frame_2.isHidden():
            self.main_window.frame_2.show()
        else:
            self.main_window.frame_2.hide()

    def open_file(self, file_path, force=False, silent=False):
        # type: (str, Optional[bool], Optional[bool]) -> None
        r"""
        @brief Read one or more data files. If more than one, merge their data.
        @param file_path: absolute path to data files. If more than one file, paths are joined with
        the plus symbol '+'
        @param force: if true, the file will be reloaded even if it was loaded previously
        @param silent: if true, the plots currently shown in the interface will NOT be updated
        """
        # Actions carried out:
        # 1. check the file exists
        # 2. Invoke DataManager.load()
        # 3. if silent==False, invoke DataManager.file_loaded()

        for single_file_path in file_path.split(
            FilePath.merge_symbol
        ):  # also works when file_path is just the path to one file
            if not os.path.isfile(single_file_path):
                self.report_message(
                    "File does not exist",
                    detailed_message="The following file does not exist:\n  %s" % single_file_path,
                    pop_up=True,
                    is_error=True,
                )
                return

        t_0 = time.time()
        self.main_window.auto_change_active = True
        try:
            self.report_message("Loading file(s) %s" % file_path)
            prog = ProgressReporter(progress_bar=self.progress_bar, status_bar=self.status_bar_handler)
            configuration = self.get_configuration()
            self._data_manager.load(file_path, configuration, force=force, progress=prog)
            self.report_message("Loaded file(s) %s" % self._data_manager.current_file_name)
        except RuntimeError as run_err:
            # FIXME - need to find out what kind of error it could have
            self.report_message(
                "Error loading file(s) {} due to {}".format(self._data_manager.current_file_name, run_err),
                detailed_message=str(traceback.format_exc()),
                pop_up=False,
                is_error=True,
            )

        if not silent:
            self.file_loaded()
        self.main_window.auto_change_active = False
        logging.info("DONE: %s sec", time.time() - t_0)

    def file_loaded(self):
        """
        Update UI after a file is loaded
        """
        self.main_window.auto_change_active = True
        self._set_data_manager_active_channel()

        channels = list(self._data_manager.data_sets.keys())
        for i, channel in enumerate(channels):
            getattr(self.ui, "selectedChannel%i" % i).show()
            good_label = channel.replace("_", "-")
            if not good_label == self._data_manager.data_sets[channel].cross_section_label:
                good_label = "%s: %s" % (good_label, self._data_manager.data_sets[channel].cross_section_label)
            getattr(self.ui, "selectedChannel%i" % i).setText(good_label)
        for i in range(len(channels), 12):
            getattr(self.ui, "selectedChannel%i" % i).hide()
        self.main_window.auto_change_active = False

        self.main_window.file_loaded_signal.emit()
        self.main_window.initiate_reflectivity_plot.emit(False)
        self.main_window.initiate_projection_plot.emit(False)

        self.cache_indicator.setText("Files loaded: %s" % (self._data_manager.get_cachesize()))

    def active_channel_changed(self):
        """
        Update UI metadata and plots after the active channel is changed
        """
        self._set_data_manager_active_channel()
        self.update_channel_info()
        self.main_window.plotActiveTab()
        self.main_window.initiate_reflectivity_plot.emit(False)
        self.main_window.initiate_projection_plot.emit(False)

    def _set_data_manager_active_channel(self):
        """
        Set the data manager's active channel from the active channel in the UI
        """
        self.main_window.auto_change_active = True
        current_channel = 0
        for i in range(12):
            if getattr(self.ui, "selectedChannel%i" % i).isChecked():
                current_channel = i
                break

        success = self._data_manager.set_channel(current_channel)
        if not success:
            self.ui.selectedChannel0.setChecked(True)
        self.main_window.auto_change_active = False

    def _congruency_fail_report(self, file_paths, log_names=None):
        r"""
        # type: List[str], Optional(List[str]) -> str
        @brief Check whether these files can be merged
        @param file_paths : List of Nexus files (full paths)
        @returns str : Error message; empty string if no error is found,
        """
        assert len(file_paths) > 1, "We require more than one data file in order to compare their metadata"
        # Log names validation and collect tolerances
        tolerances = dict()  # store the tolerance value for each log name
        all_tolerances = Settings()["OpenSum"]["Tolerances"]  # type: List[float]
        all_log_names = Settings()["OpenSum"]["LogNames"]  # type: List[str]
        assert all_log_names  # failsafe if structure of settings.json changes
        if log_names is None:
            log_names = all_log_names
        for log_name in log_names:
            try:
                i = all_log_names.index(log_name)
            except ValueError:
                return "{} is not a valid Log for comparison".format(log_name)
            tolerances[log_name] = all_tolerances[i]

        # simple data structure to collect the log values from all files
        log_values = {name: list() for name in log_names}
        for file_path in file_paths:
            for entry in ["", "-Off_Off", "-On_Off", "-Off_On", "-On_On"]:  # for new and old nexus files
                workspace = None
                try:
                    workspace = LoadEventNexus(Filename=file_path, NXentryName="entry" + entry, MetaDataOnly=True)
                    break
                except RuntimeError:
                    continue
            if workspace is None:
                return "Could not load {}".format(file_path)
            metadata = workspace.getRun()
            for log_name in log_names:
                try:
                    log_property = metadata.getProperty(log_name)
                except RuntimeError as e:
                    return e.message
                log_values[log_name].append(log_property.getStatistics().mean)
            DeleteWorkspace(workspace)

        # Find the minimum and maximum values for each log, and compare to the tolerance
        message = ""
        for log_name, values in log_values.items():
            if max(values) - min(values) > tolerances[log_name]:
                runs = FilePath(file_paths).run_numbers(string_representation="statement")
                message_template = "Runs {0} contain values for log {1} that differ above tolerance {2}"
                message = message + message_template.format(runs, log_name, tolerances[log_name]) + "\n"

        return message  # empty string if no failures

    def update_tables(self):
        """
        Update a data set that may be in the reduction table or the
        direct beam table.
        """
        # Update the reduction table if this data set is in it
        idx = self._data_manager.find_active_data_id()
        if idx is not None:
            table_widget = self.get_active_reduction_table()
            self.update_reduction_table(table_widget, idx, self._data_manager.active_channel)

        # Update the direct beam table if this data set is in it
        idx = self._data_manager.find_active_direct_beam_id()
        if idx is not None:
            self.update_direct_beam_table(idx, self._data_manager.active_channel)

    def update_calculated_data(self):
        """
        Update the calculated entries in the overview tab.
        We should call this after the peak ranges change, or
        after a change is made that will affect the displayed results.
        """
        d = self._data_manager.active_channel
        self.ui.datasetAi.setText("%.3f°" % (d.scattering_angle))

        try:
            wl_min, wl_max = d.wavelength_range
        except ZeroDivisionError:
            wl_min, wl_max = float("NaN"), float("NaN")
        self.ui.datasetLambda.setText("%.2f (%.2f-%.2f) Å" % (d.lambda_center, wl_min, wl_max))

        # DIRPIX and DANGLE0 overwrite
        if self.ui.set_dangle0_checkbox.isChecked():
            dangle0 = "%.3f° (%.3f°)" % (float(self.ui.dangle0Overwrite.text()), d._angle_offset)
        else:
            dangle0 = "%.3f°" % (d.angle_offset)
        self.ui.datasetDangle0.setText(dangle0)

        if self.ui.set_dirpix_checkbox.isChecked():
            dpix = "%.1f (%.1f)" % (float(self.ui.directPixelOverwrite.value()), d._direct_pixel)
        else:
            dpix = "%.1f" % d.direct_pixel
        self.ui.datasetDirectPixel.setText(dpix)

        if d.configuration.normalization is not None:
            self.ui.matched_direct_beam_label.setText("%s" % d.configuration.normalization)
        else:
            self.ui.matched_direct_beam_label.setText("None")

    def update_info(self):
        """
        Update metadata shown in the overview tab.
        """
        self.main_window.auto_change_active = True
        d = self._data_manager.active_channel
        self.populate_from_configuration(d.configuration)
        self.main_window.initiate_projection_plot.emit(False)
        QtWidgets.QApplication.instance().processEvents()

        if self.ui.set_dangle0_checkbox.isChecked():
            dangle0 = "%.3f° (%.3f°)" % (float(self.ui.dangle0Overwrite.text()), d.angle_offset)
        else:
            dangle0 = "%.3f°" % (d.angle_offset)

        if self.ui.set_dirpix_checkbox.isChecked():
            dpix = "%.1f (%.1f)" % (float(self.ui.directPixelOverwrite.value()), d.direct_pixel)
        else:
            dpix = "%.1f" % d.direct_pixel

        wl_min, wl_max = d.wavelength_range
        self.ui.datasetLambda.setText("%.2f (%.2f-%.2f) Å" % (d.lambda_center, wl_min, wl_max))
        self.ui.datasetPCharge.setText("%.3e" % d.proton_charge)
        self.ui.datasetTime.setText("%i s" % d.total_time)
        self.ui.datasetTotCounts.setText("%.4e" % d.total_counts)
        try:
            self.ui.datasetRate.setText("%.1f cps" % (d.total_counts / d.total_time))
        except ZeroDivisionError:
            self.ui.datasetRate.setText("NaN")
        self.ui.datasetDangle.setText("%.3f°" % d.dangle)
        self.ui.datasetDangle0.setText(dangle0)
        self.ui.datasetSangle.setText("%.3f°" % d.sangle)
        self.ui.datasetDirectPixel.setText(dpix)
        self.ui.currentChannel.setText(
            "<b>%s</b> (%s)&nbsp;&nbsp;&nbsp;Type: %s&nbsp;&nbsp;&nbsp;Current State: "
            "<b>%s</b>" % (d.number, d.experiment, d.measurement_type, d.name)
        )

        # Update direct beam indicator
        if d.is_direct_beam:
            self.ui.is_direct_beam_label.setText("Direct beam")
        else:
            self.ui.is_direct_beam_label.setText("")

        # Update the calculated data
        self.update_calculated_data()

        self.ui.roi_used_label.setText("%s" % d.use_roi_actual)
        self.ui.roi_peak_label.setText("%s" % str(d.meta_data_roi_peak))
        self.ui.roi_bck_label.setText("%s" % str(d.meta_data_roi_bck))

        # Update reduction tables
        self.update_tables()

        self.active_data_changed()

        self.main_window.auto_change_active = False

    def update_channel_info(self):
        """
        Update channel metadata shown in the overview tab.
        """
        # Update cross-section specific information in the overview tab
        d = self._data_manager.active_channel
        self.ui.datasetPCharge.setText("%.3e" % d.proton_charge)
        self.ui.datasetTime.setText("%i s" % d.total_time)
        self.ui.datasetTotCounts.setText("%.4e" % d.total_counts)
        try:
            self.ui.datasetRate.setText("%.1f cps" % (d.total_counts / d.total_time))
        except ZeroDivisionError:
            self.ui.datasetRate.setText("NaN")
        self.ui.currentChannel.setText(
            "<b>%s</b> (%s)&nbsp;&nbsp;&nbsp;Type: %s&nbsp;&nbsp;&nbsp;Current State: "
            "<b>%s</b>" % (d.number, d.experiment, d.measurement_type, d.name)
        )

        # Update the calculated data
        self.update_calculated_data()

    def update_file_list(self, query_path=None):
        # type: (Optional[str]) -> None
        r"""
        @brief Update the list of data files
        @param query_path: full path of a directory, a Nexus file, or a list of Nexus files. If a list of files,
        their paths are joined by the plus symbol '+'.
        """

        def _split_composites():
            r"""Split the list of files in widget self.ui.file_list into a list of single files and
            a list of composite files"""
            singles, composites = list(), list()
            for i in range(self.ui.file_list.count()):
                file_base_name = self.ui.file_list.item(i).text()
                if FilePath.merge_symbol in file_base_name:
                    composites.append(file_base_name)
                else:
                    singles.append(file_base_name)
            return singles, composites

        def _updated_current_list():
            r"""Most updated list of single and composite files from the current directory"""
            _, composites = _split_composites()
            return sorted(self._data_manager.current_event_files + composites)

        def _reset_ui_file_list(fresh_list):
            r"""reset widget self.ui.file_list and highlight the current file_name"""
            self.ui.file_list.clear()  # Reset ui.file_list, a QtWidgets.QListWidget object
            assert isinstance(fresh_list, list), "fresh_list must be list but not {}".format(type(fresh_list))
            for item in fresh_list:
                listitem = QtWidgets.QListWidgetItem(item, self.ui.file_list)
                if item == self._data_manager.current_file_name:
                    # Changing the current selection will trigger self.main_window.file_open_from_list() to be called,
                    # however, the current setting self.main_window.auto_change_active == True will cause
                    # self.main_window.file_open_from_list() to return before any statement is executed
                    self.ui.file_list.setCurrentItem(listitem)

        def _update_current_directory(new_dir):
            r"""Update the directory path in the main window and the path watcher"""
            self.main_window.settings.setValue("current_directory", new_dir)
            self._path_watcher.removePath(self._data_manager.current_directory)
            self._data_manager.current_directory = new_dir
            self._path_watcher.addPath(self._data_manager.current_directory)

        # This setting prevents automatic read-in of the currently selected item in the list
        # when the currently selected items changes due to the list update.
        self.main_window.auto_change_active = True

        file_path = None if query_path is None else FilePath(query_path)

        # Use case 1: the contents of the current directory may have changed with the addition of new
        # event files. This could happen if the experiment is running, producing new event files.
        if file_path is None:
            new_list = _updated_current_list()
        # Use case 2: a composite from using Open Sum
        elif file_path.is_composite:
            file_dir, file_name = file_path.split()
            self._data_manager.current_file_name = file_path.basename
            # Use case 2.1: the composite is made up of files in the current directory
            if file_dir == self._data_manager.current_directory:
                new_list = sorted(_updated_current_list() + [file_path.basename])
            # Use case 2.2: the composite is made up of files in a new directory
            else:
                _update_current_directory(file_dir)
                new_list = sorted(self._data_manager.current_event_files + [file_path.basename])
        # Use case 3: a single path pointing to a file or a directory
        else:
            # Use case 3.1: a single path pointing to a new directory
            if os.path.isdir(query_path):
                file_dir = query_path
                if file_dir != self._data_manager.current_directory:  # User changed directory
                    _update_current_directory(file_dir)
                    self._data_manager.current_file_name = self._data_manager.current_event_files[0]
                    new_list = self._data_manager.current_event_files
                else:
                    # TODO FIXME discovered from #93.  This path is not checked and thus problematic
                    new_list = None
            # Use case 3.2: a single path pointing to a file in the current or new directory
            else:
                file_dir, file_name = file_path.split()
                self._data_manager.current_file_name = file_name
                if file_dir == self._data_manager.current_directory:  # User selected a new file in the directory
                    new_list = _updated_current_list()
                else:  # User selected a new file in a new directory
                    _update_current_directory(file_dir)
                    new_list = self._data_manager.current_event_files
        # TODO FIXME  - new_list is not None has not been defined by stakeholder
        if new_list is not None:
            _reset_ui_file_list(new_list)
            self.main_window.auto_change_active = False

    def automated_file_selection(self):
        """
        Go through the files in the current in order of run numbers, and
        load files until the incident angle is no longer increasing.
        """
        self.main_window.auto_change_active = True
        # Update the list of files
        event_file_list = glob.glob(os.path.join(self._data_manager.current_directory, "*event.nxs"))
        h5_file_list = glob.glob(os.path.join(self._data_manager.current_directory, "*.nxs.h5"))
        event_file_list.extend(h5_file_list)
        event_file_list.sort()
        event_file_list = [os.path.basename(name) for name in event_file_list]

        current_file_found = False
        n_count = 0
        logging.error("Current file: %s", self._data_manager.current_file_name)

        q_current = self._data_manager.extract_meta_data().mid_q

        # Add the current data set to the reduction table
        # Do nothing if the data is incompatible
        is_direct_beam = self._data_manager.active_channel.is_direct_beam
        if is_direct_beam:
            if not self.add_direct_beam():
                return
        else:
            if not self.add_reflectivity():
                return

        for f in event_file_list:
            file_path = str(os.path.join(self._data_manager.current_directory, f))
            if current_file_found and n_count < 10:
                n_count += 1
                meta_data = self._data_manager.extract_meta_data(file_path)

                if q_current <= meta_data.mid_q and is_direct_beam == meta_data.is_direct_beam:
                    q_current = meta_data.mid_q
                    self.open_file(file_path, silent=True)
                    d = self._data_manager.active_channel
                    # If we find data of another type, stop here
                    if not is_direct_beam == self._data_manager.active_channel.is_direct_beam:
                        break
                    self.main_window.auto_change_active = True
                    self.populate_from_configuration(d.configuration)
                    if self._data_manager.active_channel.is_direct_beam:
                        self.add_direct_beam()
                    else:
                        self.add_reflectivity()

            if f == self._data_manager.current_file_name:
                current_file_found = True

        # At the very end, update the UI and plot reflectivity
        if n_count > 0:
            self.main_window.auto_change_active = True
            self.file_loaded()
        self.main_window.auto_change_active = False

    def open_reduced_file_dialog(self):
        """
        Open a reduced file and all the data files needed to reproduce it.
        """
        # Open file dialog
        filter_ = "QuickNXS files (*.dat);;All (*.*)"
        output_dir = self.main_window.settings.value("output_directory", os.path.expanduser("~"))
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self.main_window, "Open reduced file...", directory=output_dir, filter=filter_
        )

        t_0 = time.time()
        if file_path:
            # Clear the reduction list first so that we don't create problems later
            self.clear_direct_beams()
            self.clear_reflectivity()
            configuration = self.get_configuration()
            prog = self.new_progress_reporter()
            self._data_manager.load_data_from_reduced_file(file_path, configuration=configuration, progress=prog)

            # Update output directory
            file_dir, _ = os.path.split(str(file_path))
            self.main_window.settings.setValue("output_directory", file_dir)

            self.main_window.auto_change_active = True

            self.ui.normalizeTable.setRowCount(len(self._data_manager.direct_beam_list))
            for idx, _ in enumerate(self._data_manager.direct_beam_list):
                self._data_manager.set_active_data_from_direct_beam_list(idx)
                self.update_direct_beam_table(idx, self._data_manager.active_channel)
            self.reduction_table.setRowCount(len(self._data_manager.reduction_list))
            for idx, _ in enumerate(self._data_manager.reduction_list):
                self._data_manager.set_active_data_from_reduction_list(idx)
                self.update_reduction_table(self.get_active_reduction_table(), idx, self._data_manager.active_channel)

            direct_beam_ids = [str(r.number) for r in self._data_manager.direct_beam_list]
            self.ui.normalization_list_label.setText(", ".join(direct_beam_ids))

            self.file_loaded()

            if self._data_manager.active_channel is not None:
                self.populate_from_configuration(self._data_manager.active_channel.configuration)
                self.update_file_list(self._data_manager.current_file)
            self.main_window.auto_change_active = False

            logging.info("UI updated: %s", time.time() - t_0)

    def initialize_additional_reduction_table(self, tab_index: int):
        """
        Initialize new reduction table from the main reduction table
        """
        table_widget = self.get_reduction_table_by_index(tab_index)
        table_widget.setRowCount(len(self._data_manager.main_reduction_list))
        active_cross_section = self._data_manager.active_channel.name
        for idx, nexus_data in enumerate(self._data_manager.main_reduction_list):
            active_channel = nexus_data.cross_sections[active_cross_section]
            self.update_reduction_table(table_widget, idx, active_channel)

    def _file_open_dialog(self, filter_=None):
        # type: (Optional[str]) -> Optional[str]
        r"""
        @brief Pop a File dialog window for the user to select one file
        @param filter_: show files with only selected extensions
        @returns absolute path to the selected file
        """
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self.main_window, "Open NXS file...", directory=self._data_manager.current_directory, filter=filter_
        )
        return file_path

    def _file_open_sum_dialog(self, filter_=None):
        # type: (Optional[str]) -> Optional[unicode]
        r"""
        @brief Pop a File dialog Window for the user to select two or more files
        @details Congruency among the selected files is checked by comparing the values of selected metadata. User
        is asked to override if congruency fails.
        @param filter_: show files with only selected extensions
        @returns absolute paths to the selected files, joined by the plus symbol '+'
        """
        file_paths, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self.main_window,
            "Select multiple NXS files to sum before data reduction.",
            directory=self._data_manager.current_directory,
            filter=filter_,
        )
        # user cancel operation
        if len(file_paths) == 0:
            return
        elif len(file_paths) == 1:
            self.report_message("Merge mode must have more than 1 file selected")
            return

        # check whether files can be merged without further notice
        message = self._congruency_fail_report(file_paths, log_names=None)
        if message and not self._user_gives_permission(message):
            return

        return FilePath(file_paths).path

    def _process_file_path(self, dialog_opening_method):
        # type: (str) -> None
        r"""
        @brief Wrapper of the opening-file dialogs
        @details This wrapper defines the extension of the files to be shown by the file dialog, and process the
        file(s) selected by the user. It updates the file list widget as well as reads-in the file(s)
        """
        if self.ui.histogramActive.isChecked():
            filter_ = "All (*.*);;histo.nxs (*histo.nxs)"
        else:
            filter_ = "All (*.*);;nxs.h5 (*nxs.h5);;event.nxs (*event.nxs)"

        file_path = getattr(self, dialog_opening_method)(filter_=filter_)

        if file_path:
            self.update_file_list(file_path)
            self.open_file(file_path)

    def file_open_dialog(self):
        r"""GUI callback for backend MainHandler._file_open_dialog."""
        self._process_file_path("_file_open_dialog")

    def file_open_sum_dialog(self):
        r"""GUI callback for backend MainHandler._file_open_sum_dialog."""
        self._process_file_path("_file_open_sum_dialog")

    def _user_gives_permission(self, message):
        # type: (str) -> bool
        r"""
        @brief Ask user's permission to proceed or quit if the select runs do not have same sample logs
        @param message: message to show in the dialog box
        """
        message += ".\nProceed with Open Sum?"
        dialog = AcceptRejectDialog(self.main_window, title="Open Sum Confirmation", message=message)
        proceed = dialog.exec_()
        return proceed

    def open_run_number(self, number=None):
        r"""
        @brief Open a data file by typing a run number or a composite run number for merging data sets
        @details Example: 120:123+125+127:132 opens files with run numbers from 120 to 132 except 124 and 126
        """
        self.main_window.auto_change_active = True
        if number is None:
            number = str(self.ui.numberSearchEntry.text())  # cast from unicode to string
        QtWidgets.QApplication.instance().processEvents()
        run_numbers = RunNumbers(number)
        file_list = list()
        # Look for new-style nexus file name
        configuration = self.get_configuration()
        for run_number in run_numbers.numbers:
            search_string = configuration.instrument.file_search_template % run_number
            matches = glob.glob(search_string + ".nxs.h5")  # type: Optional[List[str]]
            if not matches:  # Look for old-style nexus file name
                search_string = configuration.instrument.legacy_search_template % run_number
                matches = glob.glob(search_string + "_event.nxs")
            file_list.append(matches[0])  # there should be only one match, since we query with one run number

        self.ui.numberSearchEntry.setText("")  # empty the contents of in the LineEdit widget
        success = False
        if len(file_list) > 0:
            file_path = FilePath(file_list).path  # single path or a composite of file paths
            # If opening more than one file, check whether files can be merged
            if len(file_list) > 1:
                message = self._congruency_fail_report(file_list, log_names=None)
                if message and not self._user_gives_permission(message):
                    return
            self.update_file_list(file_path)
            self.open_file(file_path)
            success = True
        else:
            self.report_message("Could not locate one or more of file(s) %s" % run_numbers.short, pop_up=True)

        self.main_window.auto_change_active = False
        return success

    def update_daslog(self):
        """
        Write parameters from all file daslogs to the table in the
        daslog tab.
        """
        table = self.ui.daslogTableBox
        table.setRowCount(0)
        table.sortItems(-1)
        table.setColumnCount(len(self._data_manager.data_sets) + 2)
        table.setHorizontalHeaderLabels(["Name"] + list(self._data_manager.data_sets.keys()) + ["Unit"])
        for j, key in enumerate(sorted(self._data_manager.active_channel.logs.keys(), key=lambda s: s.lower())):
            table.insertRow(j)
            table.setItem(j, 0, QtWidgets.QTableWidgetItem(key))
            table.setItem(
                j,
                len(self._data_manager.data_sets) + 1,
                QtWidgets.QTableWidgetItem(self._data_manager.active_channel.log_units[key]),
            )
            i = 0
            for xs in self._data_manager.data_sets:
                item = QtWidgets.QTableWidgetItem("%g" % self._data_manager.data_sets[xs].logs[key])
                item.setToolTip("MIN: %g   MAX: %g" % (self._data_manager.data_sets[xs].log_minmax[key]))
                table.setItem(j, i + 1, item)
                i += 1
        table.resizeColumnsToContents()

    def add_reflectivity(self, silent=False):
        """
        Collect information about the current extraction settings and store them
        in the list of reduction items.

        Returns true if everything is ok, false otherwise.
        """
        # Update the configuration according to current parameters
        # Note that when a data set is first loaded, the peaks may have a different
        # range for each cross-section. If the option to use a common set of ranges
        # was turned on, we pick the ranges from the currently active cross-section
        # and apply then to all cross-sections.
        if self.ui.action_use_common_ranges.isChecked():
            config = self.get_configuration()
            self._data_manager.update_configuration(configuration=config, active_only=False)

        # Verify that the new data is consistent with existing data in the table
        if not self._data_manager.add_active_to_reduction():
            if not silent:
                self.report_message("(Add reflectivity) Data incompatible or already in the list.", pop_up=True)
            return False
        self.main_window.auto_change_active = True

        idx = self._data_manager.find_data_in_reduction_list(self._data_manager._nexus_data)
        if idx is None:
            raise RuntimeError("It could be None but not likely")
        self.ui.reductionTable.insertRow(idx)
        self.update_tables()

        self.main_window.initiate_reflectivity_plot.emit(True)
        self.main_window.update_specular_viewer.emit()
        self.main_window.auto_change_active = False
        return True

    def update_reduction_table(self, table_widget, idx, d):
        """
        Update the reduction tale
        """
        self.main_window.auto_change_active = True
        item = QtWidgets.QTableWidgetItem(str(d.number))
        if d == self._data_manager.active_channel:
            item.setBackground(QtGui.QColor(246, 213, 16))
        else:
            item.setBackground(QtGui.QColor(255, 255, 255))
        item.setFlags(item.flags() & ~QtCore.Qt.ItemIsEditable)
        table_widget.setItem(idx, 0, item)
        table_widget.setItem(idx, 1, QtWidgets.QTableWidgetItem("%.4f" % (d.configuration.scaling_factor)))
        table_widget.setItem(idx, 2, QtWidgets.QTableWidgetItem(str(d.configuration.cut_first_n_points)))
        table_widget.setItem(idx, 3, QtWidgets.QTableWidgetItem(str(d.configuration.cut_last_n_points)))
        item = QtWidgets.QTableWidgetItem(str(d.configuration.peak_position))
        item.setBackground(QtGui.QColor(200, 200, 200))
        table_widget.setItem(idx, 4, item)
        table_widget.setItem(idx, 5, QtWidgets.QTableWidgetItem(str(d.configuration.peak_width)))
        item = QtWidgets.QTableWidgetItem(str(d.configuration.low_res_position))
        item.setBackground(QtGui.QColor(200, 200, 200))
        table_widget.setItem(idx, 6, item)
        table_widget.setItem(idx, 7, QtWidgets.QTableWidgetItem(str(d.configuration.low_res_width)))
        item = QtWidgets.QTableWidgetItem(str(d.configuration.bck_position))
        item.setBackground(QtGui.QColor(200, 200, 200))
        table_widget.setItem(idx, 8, item)
        table_widget.setItem(idx, 9, QtWidgets.QTableWidgetItem(str(d.configuration.bck_width)))
        table_widget.setItem(idx, 10, QtWidgets.QTableWidgetItem(str(d.direct_pixel)))
        table_widget.setItem(idx, 11, QtWidgets.QTableWidgetItem("%.4f" % d.scattering_angle))
        norma = "none"
        if d.configuration.normalization is not None:
            norma = d.configuration.normalization
        table_widget.setItem(idx, 12, QtWidgets.QTableWidgetItem(str(norma)))
        self.main_window.auto_change_active = False

    def clear_reflectivity(self):
        """
        Remove all items from the reduction list.
        """
        self._data_manager.reduction_list = []
        self.reduction_table.setRowCount(0)
        self.main_window.initiate_reflectivity_plot.emit(False)

    def clear_direct_beams(self):
        """
        Remove all items from the direct beam list.
        """
        self._data_manager.clear_direct_beam_list()
        self.ui.normalizeTable.setRowCount(0)
        self.ui.normalization_list_label.setText("None")
        self.main_window.initiate_reflectivity_plot.emit(False)

    def remove_reflectivity(self):
        """
        Remove one item from the reduction list.
        """
        index = self.reduction_table.currentRow()
        if index < 0:
            return
        self._data_manager.reduction_list.pop(index)
        self.reduction_table.removeRow(index)
        self.main_window.initiate_reflectivity_plot.emit(False)

    def remove_direct_beam(self):
        """
        Remove one item from the direct beam list.
        """
        index = self.ui.normalizeTable.currentRow()
        if index < 0:
            return
        self._data_manager.direct_beam_list.pop(index)
        self.ui.normalizeTable.removeRow(index)
        self.main_window.initiate_reflectivity_plot.emit(False)

    def reduction_table_changed(self, item):
        """
        Perform action upon change in data reduction list.
        """
        if self.main_window.auto_change_active:
            return

        entry = item.row()
        column = item.column()

        refl = self._data_manager.reduction_list[entry]

        # TODO: If we changed the normalization run, make sure it's in the list
        # of direct beams we know about.

        keys = [
            "number",
            "scaling_factor",
            "cut_first_n_points",
            "cut_last_n_points",
            "peak_position",
            "peak_width",
            "low_res_position",
            "low_res_width",
            "bck_position",
            "bck_width",
            "direct_pixel",
            "scattering_angle",
            "normalization",
        ]

        # Update settings from selected option
        if column in [1, 4, 5, 6, 7, 8, 9, 10]:
            refl.set_parameter(keys[column], float(item.text()))
        elif column in [2, 3]:
            refl.set_parameter(keys[column], int(item.text()))
        elif column == 12:
            try:
                refl.set_parameter(keys[column], item.text())
            except:
                refl.set_parameter(keys[column], None)
                item.setText("none")

        # Update calculated data
        refl.update_calculated_values()

        # If the changed data set is the active data, also change the UI
        if self._data_manager.is_active(refl):
            self.main_window.auto_change_active = True
            self.update_info()
            self.main_window.auto_change_active = False

        # Update the direct beam table if this data set is in it
        idx = self._data_manager.find_data_in_direct_beam_list(refl)
        if idx is not None:
            channels = list(refl.cross_sections.keys())
            self.update_direct_beam_table(idx, refl.cross_sections[channels[0]])

        # Only recalculate if we need to, otherwise just replot
        if not column in [1, 2, 3]:
            try:
                self._data_manager.calculate_reflectivity(nexus_data=refl)
            except:
                self.report_message(
                    "Could not compute reflectivity for %s" % self._data_manager.current_file_name,
                    detailed_message=str(traceback.format_exc()),
                    pop_up=False,
                    is_error=False,
                )

        self.main_window.initiate_reflectivity_plot.emit(True)
        self.main_window.update_specular_viewer.emit()

    def add_direct_beam(self, silent=False):
        """
        Add / remove dataset to the available normalizations or clear the normalization list.
        """
        # Update all cross-section parameters as needed.
        if self.ui.action_use_common_ranges.isChecked():
            config = self.get_configuration()
            self._data_manager.update_configuration(configuration=config, active_only=False)

        # Verify that the new data is consistent with existing data in the table
        if not self._data_manager.add_active_to_normalization():
            if not silent:
                self.report_message("(Add direct beam) Data incompatible or already in the list.", pop_up=True)
            return False

        self.ui.normalizeTable.setRowCount(len(self._data_manager.direct_beam_list))
        self.update_tables()

        direct_beam_ids = [str(r.number) for r in self._data_manager.direct_beam_list]
        self.ui.normalization_list_label.setText(", ".join(direct_beam_ids))

        self.main_window.initiate_reflectivity_plot.emit(False)
        return True

    def update_direct_beam_table(self, idx, d):
        """
        Update a direct beam table entry
        :param int idx: row index
        :param CrossSectionData d: data object
        """
        self.main_window.auto_change_active = True
        item = QtWidgets.QTableWidgetItem(str(d.number))
        item.setFlags(item.flags() & ~QtCore.Qt.ItemIsEditable)
        if d == self._data_manager.active_channel:
            item.setBackground(QtGui.QColor(246, 213, 16))
        else:
            item.setBackground(QtGui.QColor(255, 255, 255))

        self.ui.normalizeTable.setItem(idx, 0, QtWidgets.QTableWidgetItem(item))
        wl = "%s - %s" % (d.wavelength[0], d.wavelength[-1])
        self.ui.normalizeTable.setItem(idx, 7, QtWidgets.QTableWidgetItem(wl))
        item = QtWidgets.QTableWidgetItem(str(d.configuration.peak_position))
        item.setBackground(QtGui.QColor(200, 200, 200))
        self.ui.normalizeTable.setItem(idx, 1, QtWidgets.QTableWidgetItem(item))
        self.ui.normalizeTable.setItem(idx, 2, QtWidgets.QTableWidgetItem(str(d.configuration.peak_width)))
        item = QtWidgets.QTableWidgetItem(str(d.configuration.low_res_position))
        item.setBackground(QtGui.QColor(200, 200, 200))
        self.ui.normalizeTable.setItem(idx, 3, QtWidgets.QTableWidgetItem(item))
        self.ui.normalizeTable.setItem(idx, 4, QtWidgets.QTableWidgetItem(str(d.configuration.low_res_width)))
        item = QtWidgets.QTableWidgetItem(str(d.configuration.bck_position))
        item.setBackground(QtGui.QColor(200, 200, 200))
        self.ui.normalizeTable.setItem(idx, 5, QtWidgets.QTableWidgetItem(item))
        self.ui.normalizeTable.setItem(idx, 6, QtWidgets.QTableWidgetItem(str(d.configuration.bck_width)))
        self.main_window.auto_change_active = False

    def active_data_changed(self):
        """
        Actions to be taken once the active data set has changed
        """
        # If we update an entry, it's because that data is currently active.
        # Highlight it and un-highlight the other ones.
        self.main_window.auto_change_active = True
        idx = self._data_manager.find_active_data_id()
        for i in range(self.reduction_table.rowCount()):
            item = self.reduction_table.item(i, 0)
            if item is not None:
                if i == idx:
                    item.setBackground(QtGui.QColor(246, 213, 16))
                else:
                    item.setBackground(QtGui.QColor(255, 255, 255))

        idx = self._data_manager.find_active_direct_beam_id()
        for i in range(self.ui.normalizeTable.rowCount()):
            item = self.ui.normalizeTable.item(i, 0)
            if item is not None:
                if i == idx:
                    item.setBackground(QtGui.QColor(246, 213, 16))
                else:
                    item.setBackground(QtGui.QColor(255, 255, 255))
        self.main_window.auto_change_active = False

    def reduction_table_right_click(self, pos, is_reduction_table=True):
        """
        Handle right-click on the reduction table.
        :param QPoint pos: mouse position
        :param bool is_reduction_table: True if the reduction table is active, False if the direct beam table is active
        """
        if is_reduction_table:
            table_widget = self.get_active_reduction_table()
            data_table = self._data_manager.reduction_list
        else:
            table_widget = self.ui.normalizeTable
            data_table = self._data_manager.direct_beam_list

        def _export_data(_pos):
            """callback function to right-click action: Export data"""
            row = table_widget.rowAt(pos.y())
            if 0 <= row < len(data_table):
                nexus_data = data_table[row]
                self.save_run_data(nexus_data)

        def _propagate_run(_pos):
            """callback function to right-click action: Propagate run to all tabs"""
            # row = table_widget.rowAt(pos.y())
            # if 0 <= row < len(data_table):
            #     nexus_data = data_table[row]
            pass

        def _remove_run(_pos):
            """callback function to right-click action: Remove run from this tab"""
            self.remove_reflectivity()

        reduction_table_menu = QtWidgets.QMenu(table_widget)

        export_data_action = QtWidgets.QAction("Export data")
        export_data_action.triggered.connect(lambda: _export_data(pos))
        reduction_table_menu.addAction(export_data_action)

        propagate_run_action = QtWidgets.QAction("Propagate run to all tabs")
        propagate_run_action.triggered.connect(lambda: _propagate_run(pos))
        reduction_table_menu.addAction(propagate_run_action)

        remove_run_action = QtWidgets.QAction("Remove run from this tab")
        remove_run_action.triggered.connect(lambda: _remove_run(pos))
        reduction_table_menu.addAction(remove_run_action)

        reduction_table_menu.exec_(table_widget.mapToGlobal(pos))

    def save_run_data(self, nexus_data: NexusData):
        """
        Save run data to file
        :param NexusData nexus_data: run data object
        """
        path = QtWidgets.QFileDialog.getExistingDirectory(self.main_window, "Select directory")
        if not path:
            return
        # ask user for base name for files (one file for each cross-section, e.g. "REF_M_1234_data_Off-Off.dat")
        default_basename = f"REF_M_{nexus_data.number}_data"
        while True:  # to ask again for new basename if the user does not want to overwrite existing files
            basename, ok = QtWidgets.QInputDialog.getText(
                self.main_window, "Base name", "Save file base name:", text=default_basename
            )
            if not (ok and basename):
                # user cancels
                return
            save_filepaths = {}
            existing_filenames = []
            for xs in nexus_data.cross_sections.keys():
                filename = f"{basename}_{xs}.dat"
                filepath = os.path.join(path, filename)
                save_filepaths[xs] = filepath
                if os.path.isfile(filepath):
                    existing_filenames.append(filename)
            newline = "\n"
            if len(existing_filenames) == 0 or self.ask_question(
                "Overwrite existing file(s):\n{}?".format(newline.join(existing_filenames))
            ):
                break
        # save one file per cross-section
        for xs, filepath in save_filepaths.items():
            cross_section = nexus_data.cross_sections[xs]
            data_to_save, header = cross_section.get_tof_counts_table()
            np.savetxt(filepath, data_to_save, header=header)

    def compute_offspec_on_change(self, force=False):
        """
        Compute off-specular as needed
        """
        prog = self.new_progress_reporter()
        has_changed_values = self.check_region_values_changed()
        offspec_data_exists = self._data_manager.is_offspec_available()
        logging.info("Exists %s %s", has_changed_values, offspec_data_exists)
        if force or has_changed_values >= 0 or not offspec_data_exists:
            logging.info("Updating....")
            config = self.get_configuration()
            self._data_manager.update_configuration(configuration=config, active_only=False)
            self._data_manager.reduce_offspec(progress=prog)

    def compute_gisans_on_change(self, force=False, active_only=True):
        """
        Compute GISANS as needed
        """
        prog = self.new_progress_reporter()
        has_changed_values = self.check_region_values_changed()
        gisans_data_exists = self._data_manager.is_gisans_available(active_only=active_only)
        logging.info("Exists %s %s %s", force, has_changed_values, gisans_data_exists)
        if force or has_changed_values >= 0 or not gisans_data_exists:
            logging.info("Updating....")
            config = self.get_configuration()
            self._data_manager.update_configuration(configuration=config, active_only=False)
            if active_only:
                self._data_manager.calculate_gisans(progress=prog)
            else:
                self._data_manager.reduce_gisans(active_only=active_only, progress=prog)

    def check_region_values_changed(self):
        """
        Return true if any of the parameters tied to a particular slot
        has changed.

        Some parameters are tied to the changeRegionValues() slot.
        There are time-consuming actions that we only want to take
        if those values actually changed, as opposed to the use simply
        clicking outside the box.

        Some parameters don't require a recalculation but simply a
        refreshing of the plots. Those are parameters such as scaling
        factors or the number of points clipped.

        Return values:
            -1 = no valid change
             0 = replot needed
             1 = recalculation needed
        """
        if self._data_manager.active_channel is None:
            return -1

        configuration = self._data_manager.active_channel.configuration
        valid_change = False
        replot_change = False

        # ROI parameters
        x_pos = self.ui.refXPos.value()
        x_width = self.ui.refXWidth.value()
        y_pos = self.ui.refYPos.value()
        y_width = self.ui.refYWidth.value()
        bck_pos = self.ui.bgCenter.value()
        bck_width = self.ui.bgWidth.value()

        valid_change = (
            valid_change or not configuration.peak_position == x_pos or not configuration.peak_width == x_width
        )

        valid_change = (
            valid_change or not configuration.low_res_position == y_pos or not configuration.low_res_width == y_width
        )

        valid_change = (
            valid_change or not configuration.bck_position == bck_pos or not configuration.bck_width == bck_width
        )

        try:
            scale = math.pow(10.0, self.ui.refScale.value())
        except:
            scale = 1
        replot_change = replot_change or not configuration.scaling_factor == scale

        replot_change = replot_change or not configuration.cut_first_n_points == self.ui.rangeStart.value()

        replot_change = replot_change or not configuration.cut_last_n_points == self.ui.rangeEnd.value()

        valid_change = valid_change or not configuration.subtract_background == self.ui.bgActive.isChecked()

        valid_change = valid_change or not configuration.use_constant_q == self.ui.fanReflectivity.isChecked()

        valid_change = valid_change or not configuration.use_dangle == self.ui.trustDANGLE.isChecked()

        valid_change = valid_change or not configuration.set_direct_pixel == self.ui.set_dirpix_checkbox.isChecked()

        valid_change = (
            valid_change or not configuration.set_direct_angle_offset == self.ui.set_dangle0_checkbox.isChecked()
        )

        if configuration.set_direct_pixel:
            valid_change = (
                valid_change or not configuration.direct_pixel_overwrite == self.ui.directPixelOverwrite.value()
            )

        if configuration.set_direct_angle_offset:
            valid_change = (
                valid_change or not configuration.direct_angle_offset_overwrite == self.ui.dangle0Overwrite.value()
            )

        # Final rebin
        valid_change = valid_change or not configuration.do_final_rebin == self.ui.final_rebin_checkbox.isChecked()

        valid_change = valid_change or not configuration.final_rebin_step == self.ui.q_rebin_spinbox.value()

        if valid_change:
            return 1
        if replot_change:
            return 0
        return -1

    def get_configuration(self):
        # type: () -> Configuration
        r"""
        @brief Gather the reduction options.
        @details Retrieve the reduction options either from the active channel or from the current settings
        in the graphical interface.
        """
        if self._data_manager.active_channel is not None:
            configuration = self._data_manager.active_channel.configuration
        else:
            configuration = Configuration(self.main_window.settings)
        configuration.tof_bins = self.ui.eventTofBins.value()
        configuration.tof_bin_type = self.ui.eventBinMode.currentIndex()
        configuration.use_roi = self.ui.use_roi_checkbox.isChecked()
        configuration.update_peak_range = self.ui.fit_within_roi_checkbox.isChecked()
        configuration.use_roi_bck = self.ui.use_bck_roi_checkbox.isChecked()

        # Default ranges, using the current values
        x_pos = self.ui.refXPos.value()
        x_width = self.ui.refXWidth.value()
        y_pos = self.ui.refYPos.value()
        y_width = self.ui.refYWidth.value()
        bck_pos = self.ui.bgCenter.value()
        bck_width = self.ui.bgWidth.value()

        configuration.peak_position = x_pos
        configuration.peak_width = x_width
        configuration.low_res_position = y_pos
        configuration.low_res_width = y_width
        configuration.bck_position = bck_pos
        configuration.bck_width = bck_width

        configuration.force_peak_roi = not self.ui.actionAutomaticXPeak.isChecked()
        configuration.force_low_res_roi = not self.ui.actionAutoYLimits.isChecked()
        configuration.force_bck_roi = self.ui.use_bck_roi_checkbox.isChecked()
        configuration.match_direct_beam = self.ui.actionAutoNorm.isChecked()

        # Use background on each side of the peak
        configuration.use_tight_bck = self.ui.use_side_bck_checkbox.isChecked()
        configuration.bck_offset = self.ui.side_bck_width.value()

        # Other reduction options
        configuration.subtract_background = self.ui.bgActive.isChecked()
        try:
            scale = math.pow(10.0, self.ui.refScale.value())
        except:
            scale = 1
        configuration.scaling_factor = scale
        configuration.cut_first_n_points = self.ui.rangeStart.value()
        configuration.cut_last_n_points = self.ui.rangeEnd.value()
        Configuration.normalize_to_unity = self.ui.normalize_to_unity_checkbox.isChecked()
        Configuration.total_reflectivity_q_cutoff = self.ui.normalization_q_cutoff_spinbox.value()
        Configuration.global_stitching = self.ui.global_fit_checkbox.isChecked()
        Configuration.polynomial_stitching = self.ui.polynomial_stitching_checkbox.isChecked()
        Configuration.polynomial_stitching_degree = self.ui.polynomial_stitching_degree_spinbox.value()
        Configuration.polynomial_stitching_points = self.ui.polynomial_stitching_points_spinbox.value()
        Configuration.wl_bandwidth = self.ui.bandwidth_spinbox.value()

        Configuration.use_constant_q = self.ui.fanReflectivity.isChecked()
        configuration.use_dangle = self.ui.trustDANGLE.isChecked()
        configuration.set_direct_pixel = self.ui.set_dirpix_checkbox.isChecked()
        configuration.set_direct_angle_offset = self.ui.set_dangle0_checkbox.isChecked()
        configuration.direct_pixel_overwrite = self.ui.directPixelOverwrite.value()
        configuration.direct_angle_offset_overwrite = self.ui.dangle0Overwrite.value()
        Configuration.sample_size = self.ui.sample_size_spinbox.value()
        Configuration.do_final_rebin = self.ui.final_rebin_checkbox.isChecked()
        Configuration.final_rebin_step = self.ui.q_rebin_spinbox.value()

        Configuration.apply_deadtime = self.ui.deadtime_entry.applyCheckBox.isChecked()

        Configuration.lock_direct_beam_y = self.ui.direct_beam_y_lock_checkbox.isChecked()

        # UI elements
        configuration.normalize_x_tof = self.ui.normalizeXTof.isChecked()
        configuration.x_wl_map = self.ui.xLamda.isChecked()
        configuration.angle_map = self.ui.tthPhi.isChecked()
        configuration.log_1d = self.ui.logarithmic_y.isChecked()
        configuration.log_2d = self.ui.logarithmic_colorscale.isChecked()

        # Off-specular options
        if self.ui.kizmkfzVSqz.isChecked():
            configuration.off_spec_x_axis = Configuration.DELTA_KZ_VS_QZ
        elif self.ui.qxVSqz.isChecked():
            configuration.off_spec_x_axis = Configuration.QX_VS_QZ
        else:
            configuration.off_spec_x_axis = Configuration.KZI_VS_KZF
        configuration.off_spec_slice = self.ui.offspec_slice_checkbox.isChecked()
        configuration.off_spec_slice_qz_min = self.ui.slice_qz_min_spinbox.value()
        configuration.off_spec_slice_qz_max = self.ui.slice_qz_max_spinbox.value()
        # try:
        #    qz_list = self.ui.offspec_qz_list_edit.text()
        #    if len(qz_list) > 0:
        #        configuration.off_spec_qz_list = [float(x) for x in self.ui.offspec_qz_list_edit.text().split(',')]
        # except:
        #    logging.error("Could not parse off_spec_qz_list: %s", configuration.off_spec_qz_list)
        configuration.off_spec_err_weight = self.ui.offspec_err_weight_checkbox.isChecked()
        configuration.off_spec_nxbins = self.ui.offspec_rebin_x_bins_spinbox.value()
        configuration.off_spec_nybins = self.ui.offspec_rebin_y_bins_spinbox.value()
        configuration.off_spec_x_min = self.ui.offspec_x_min_spinbox.value()
        configuration.off_spec_x_max = self.ui.offspec_x_max_spinbox.value()
        configuration.off_spec_y_min = self.ui.offspec_y_min_spinbox.value()
        configuration.off_spec_y_max = self.ui.offspec_y_max_spinbox.value()

        # Off-spec smoothing options
        configuration.apply_smoothing = self.ui.offspec_smooth_checkbox.isChecked()

        # GISANS options
        configuration.gisans_wl_min = self.ui.gisans_wl_min_spinbox.value()
        configuration.gisans_wl_max = self.ui.gisans_wl_max_spinbox.value()
        configuration.gisans_wl_npts = self.ui.gisans_wl_npts_spinbox.value()
        configuration.gisans_qz_npts = self.ui.gisans_qz_npts_spinbox.value()
        configuration.gisans_qy_npts = self.ui.gisans_qy_npts_spinbox.value()
        configuration.gisans_use_pf = self.ui.gisans_pf_radio.isChecked()
        configuration.gisans_slice = self.ui.gisans_slice_checkbox.isChecked()
        configuration.gisans_slice_qz_min = self.ui.gisans_qz_min_spinbox.value()
        configuration.gisans_slice_qz_max = self.ui.gisans_qz_max_spinbox.value()

        # Make the changes persistent
        configuration.to_q_settings(self.main_window.settings)
        return configuration

    def populate_from_configuration(self, configuration=None):
        """
        Set reduction options in UI, usually after loading
        a reduced data set.
        """
        if configuration is None:
            configuration = Configuration(self.main_window.settings)

        self.ui.eventTofBins.setValue(configuration.tof_bins)
        self.ui.eventBinMode.setCurrentIndex(configuration.tof_bin_type)
        self.ui.use_roi_checkbox.setChecked(configuration.use_roi)
        self.ui.fit_within_roi_checkbox.setChecked(configuration.update_peak_range)
        self.ui.use_bck_roi_checkbox.setChecked(configuration.use_roi_bck)

        self.ui.actionAutomaticXPeak.setChecked(not configuration.force_peak_roi)
        self.ui.actionAutoYLimits.setChecked(not configuration.force_low_res_roi)

        # Update reduction parameters
        self.ui.refXPos.setValue(configuration.peak_position)
        self.ui.refXWidth.setValue(configuration.peak_width)

        self.ui.refYPos.setValue(configuration.low_res_position)
        self.ui.refYWidth.setValue(configuration.low_res_width)

        self.ui.bgCenter.setValue(configuration.bck_position)
        self.ui.bgWidth.setValue(configuration.bck_width)

        # Use background on each side of the peak
        self.ui.use_side_bck_checkbox.setChecked(configuration.use_tight_bck)
        self.ui.side_bck_width.setValue(configuration.bck_offset)

        # Subtract background
        self.ui.bgActive.setChecked(configuration.subtract_background)
        # Scaling factor
        try:
            scale = math.log10(configuration.scaling_factor)
        except:
            scale = 0.0
        self.ui.refScale.setValue(scale)
        # Cut first and last points
        self.ui.rangeStart.setValue(configuration.cut_first_n_points)
        self.ui.rangeEnd.setValue(configuration.cut_last_n_points)
        self.ui.normalize_to_unity_checkbox.setChecked(configuration.normalize_to_unity)
        self.ui.normalization_q_cutoff_spinbox.setValue(configuration.total_reflectivity_q_cutoff)
        self.ui.global_fit_checkbox.setChecked(configuration.global_stitching)
        self.ui.polynomial_stitching_checkbox.setChecked(configuration.polynomial_stitching)
        self.ui.polynomial_stitching_degree_spinbox.setValue(configuration.polynomial_stitching_degree)
        self.ui.polynomial_stitching_points_spinbox.setValue(configuration.polynomial_stitching_points)
        self.ui.bandwidth_spinbox.setValue(configuration.wl_bandwidth)

        self.ui.fanReflectivity.setChecked(configuration.use_constant_q)
        self.ui.trustDANGLE.setChecked(configuration.use_dangle)
        self.ui.set_dirpix_checkbox.setChecked(configuration.set_direct_pixel)
        self.ui.set_dangle0_checkbox.setChecked(configuration.set_direct_angle_offset)
        self.ui.directPixelOverwrite.setValue(configuration.direct_pixel_overwrite)
        self.ui.dangle0Overwrite.setValue(configuration.direct_angle_offset_overwrite)
        self.ui.sample_size_spinbox.setValue(configuration.sample_size)
        self.ui.final_rebin_checkbox.setChecked(configuration.do_final_rebin)
        self.ui.q_rebin_spinbox.setValue(configuration.final_rebin_step)

        self.ui.deadtime_entry.applyCheckBox.setChecked(configuration.apply_deadtime)

        self.ui.direct_beam_y_lock_checkbox.setChecked(configuration.lock_direct_beam_y)

        # UI elements
        self.ui.normalizeXTof.setChecked(configuration.normalize_x_tof)
        self.ui.xLamda.setChecked(configuration.x_wl_map)
        self.ui.tthPhi.setChecked(configuration.angle_map)
        self.ui.logarithmic_y.setChecked(configuration.log_1d)
        self.ui.logarithmic_colorscale.setChecked(configuration.log_2d)

        # Off-specular options
        if configuration.off_spec_x_axis == Configuration.DELTA_KZ_VS_QZ:
            self.ui.kizmkfzVSqz.setChecked(True)
        elif configuration.off_spec_x_axis == Configuration.QX_VS_QZ:
            self.ui.qxVSqz.setChecked(True)
        else:
            self.ui.kizVSkfz.setChecked(True)
        self.ui.offspec_slice_checkbox.setChecked(configuration.off_spec_slice)
        # self.ui.offspec_qz_list_edit.setText(','.join([str(x) for x in configuration.off_spec_qz_list]))
        self.ui.slice_qz_min_spinbox.setValue(configuration.off_spec_slice_qz_min)
        self.ui.slice_qz_max_spinbox.setValue(configuration.off_spec_slice_qz_max)
        self.ui.offspec_err_weight_checkbox.setChecked(configuration.off_spec_err_weight)
        self.ui.offspec_rebin_x_bins_spinbox.setValue(configuration.off_spec_nxbins)
        self.ui.offspec_rebin_y_bins_spinbox.setValue(configuration.off_spec_nybins)
        self.ui.offspec_x_min_spinbox.setValue(configuration.off_spec_x_min)
        self.ui.offspec_x_max_spinbox.setValue(configuration.off_spec_x_max)
        self.ui.offspec_y_min_spinbox.setValue(configuration.off_spec_y_min)
        self.ui.offspec_y_max_spinbox.setValue(configuration.off_spec_y_max)

        # Off-spec smoothing options
        self.ui.offspec_smooth_checkbox.setChecked(configuration.apply_smoothing)

        # GISANS options
        self.ui.gisans_wl_min_spinbox.setValue(configuration.gisans_wl_min)
        self.ui.gisans_wl_max_spinbox.setValue(configuration.gisans_wl_max)
        self.ui.gisans_wl_npts_spinbox.setValue(configuration.gisans_wl_npts)
        self.ui.gisans_qz_npts_spinbox.setValue(configuration.gisans_qz_npts)
        self.ui.gisans_qy_npts_spinbox.setValue(configuration.gisans_qy_npts)
        self.ui.gisans_pf_radio.setChecked(configuration.gisans_use_pf)
        self.ui.gisans_slice_checkbox.setChecked(configuration.gisans_slice)
        self.ui.gisans_qz_min_spinbox.setValue(configuration.gisans_slice_qz_min)
        self.ui.gisans_qz_max_spinbox.setValue(configuration.gisans_slice_qz_max)

    def stitch_reflectivity(self):
        """
        Stitch the reflectivity parts and normalize to 1.
        """
        # Update the configuration so we can remember the cutoff value
        # later if it was changed
        self.get_configuration()
        if self.ui.polynomial_stitching_checkbox.isChecked():
            poly_degree = self.ui.polynomial_stitching_degree_spinbox.value()
        else:
            poly_degree = None

        try:
            self._data_manager.stitch_data_sets(
                normalize_to_unity=self.ui.normalize_to_unity_checkbox.isChecked(),
                q_cutoff=self.ui.normalization_q_cutoff_spinbox.value(),
                global_stitching=self.ui.global_fit_checkbox.isChecked(),
                poly_degree=poly_degree,
                poly_points=self.ui.polynomial_stitching_points_spinbox.value(),
            )
        except (RuntimeError, ValueError) as err:
            self.report_message(
                "Error in stitching:\n{}".format(str(err)),
                detailed_message=str(traceback.format_exc()),
                pop_up=True,
                is_error=True,
            )
        except NormalizeToUnityQCutoffError as err:
            self.report_message(
                "Error in normalize to unity when stitching:\n{}".format(str(err)),
                detailed_message=str(traceback.format_exc()),
                pop_up=True,
                is_error=True,
            )
        else:
            for i in range(len(self._data_manager.reduction_list)):
                xs = self._data_manager.active_channel.name
                d = self._data_manager.reduction_list[i].cross_sections[xs]
                self.reduction_table.setItem(
                    i, 1, QtWidgets.QTableWidgetItem("%.4f" % (d.configuration.scaling_factor))
                )

            self.main_window.initiate_reflectivity_plot.emit(False)

    def trim_data_to_normalization(self):
        """
        Cut the start and end of the active data set to 5% of its
        maximum intensity.
        """
        trim_points = self._data_manager.get_trim_values()
        if trim_points is not None:
            self.ui.rangeStart.setValue(trim_points[0])
            self.ui.rangeEnd.setValue(trim_points[1])
            self.update_tables()
            self.main_window.initiate_reflectivity_plot.emit(False)
        else:
            self.report_message("No direct beam found to trim data", pop_up=False)

    def strip_overlap(self):
        """
        Remove overlapping points in the reflectivity, cutting always from the lower Qz
        measurements.
        """
        self._data_manager.strip_overlap()

        for i in range(len(self._data_manager.reduction_list)):
            xs = self._data_manager.active_channel.name
            d = self._data_manager.reduction_list[i].cross_sections[xs]
            self.reduction_table.setItem(i, 3, QtWidgets.QTableWidgetItem(str(d.configuration.cut_last_n_points)))

        self.main_window.initiate_reflectivity_plot.emit(False)

    def reload_all_files(self):
        """
        Reload all files upon change in loading configuration

        To speed up reloading, the file cache is first cleared of files that are not used in the
        reduction list or direct beam list.
        """
        if self._data_manager.get_cachesize() == 0:
            return

        # Store the active (plotted) run index
        active_idx = self._data_manager.find_active_data_id()
        if active_idx is not None:
            is_active_data_direct_beam = False
        else:
            is_active_data_direct_beam = True
            active_idx = self._data_manager.find_active_direct_beam_id()

        # Reload files
        self._data_manager.clear_cached_unused_data()
        configuration = self.get_configuration()
        prog = ProgressReporter(progress_bar=self.progress_bar, status_bar=self.status_bar_handler)
        self._data_manager.reload_files(configuration, prog)

        # Update the tables in the UI
        self.main_window.auto_change_active = True

        self.ui.normalizeTable.setRowCount(len(self._data_manager.direct_beam_list))
        for idx, _ in enumerate(self._data_manager.direct_beam_list):
            self._data_manager.set_active_data_from_direct_beam_list(idx)
            self.update_direct_beam_table(idx, self._data_manager.active_channel)
        self.ui.reductionTable.setRowCount(len(self._data_manager.reduction_list))
        for idx, _ in enumerate(self._data_manager.reduction_list):
            self._data_manager.set_active_data_from_reduction_list(idx)
            self.update_reduction_table(idx, self._data_manager.active_channel)

        direct_beam_ids = [str(r.number) for r in self._data_manager.direct_beam_list]
        self.ui.normalization_list_label.setText(", ".join(direct_beam_ids))

        # Restore the active run
        if is_active_data_direct_beam:
            self._data_manager.set_active_data_from_direct_beam_list(active_idx)
        else:
            self._data_manager.set_active_data_from_reduction_list(active_idx)

        # Update plots
        self.file_loaded()

        self.main_window.auto_change_active = False

    def report_message(self, message, informative_message=None, detailed_message=None, pop_up=False, is_error=False):
        r"""
        Report an error.
        :param str message: message string to be reported
        :param str informative_message: extra information
        :param str detailed_message: detailed message for the log
        :param bool pop_up: if True, a dialog will pop up
        :param bool is_error: if True, the message is logged on the error channel
        """
        self.status_bar_handler.show_message(message)
        if is_error:
            logging.error(message)
            if detailed_message is not None:
                logging.error(detailed_message)
        elif pop_up:
            logging.warning(message)
        else:
            logging.info(message)

        if pop_up:
            msg = QtWidgets.QMessageBox()
            msg.setIcon(QtWidgets.QMessageBox.Warning)

            msg.setText(message)
            msg.setWindowTitle("Information")
            if informative_message is not None:
                msg.setInformativeText(informative_message)
            if detailed_message is not None:
                msg.setDetailedText(detailed_message)
            msg.setStandardButtons(QtWidgets.QMessageBox.Ok)
            msg.exec_()

    def ask_question(self, message):
        """
        Display a popup dialog with a message and choices "Ok" and "Cancel"
        :param str message: question to ask
        :returns: bool
        """
        ret = QtWidgets.QMessageBox.warning(
            self.main_window,
            "Warning",
            message,
            buttons=QtWidgets.QMessageBox.Ok | QtWidgets.QMessageBox.Cancel,
            defaultButton=QtWidgets.QMessageBox.Ok,
        )
        if ret == QtWidgets.QMessageBox.Cancel:
            return False
        return True

    def show_results(self):
        """
        Pop up the result viewer
        """
        from ..result_viewer import ResultViewer

        dialog = ResultViewer(self.main_window, self._data_manager)
        dialog.specular_compare_widget.ui.refl_preview_checkbox.setChecked(True)
        self.main_window.update_specular_viewer.connect(dialog.update_specular)
        self.main_window.update_off_specular_viewer.connect(dialog.update_off_specular)
        self.main_window.update_gisans_viewer.connect(dialog.update_gisans)
        dialog.show()
