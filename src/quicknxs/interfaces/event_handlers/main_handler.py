# -*- coding: utf-8 -*-
# pylint: disable=invalid-name, line-too-long, too-many-public-methods, too-many-instance-attributes, wrong-import-order, \
# bare-except, protected-access, too-many-arguments, too-many-statements
"""Manage file-related and UI events."""

import glob
import logging
import math
import os
import time
import traceback
from typing import List, Optional, Union

import numpy as np
from mantid.simpleapi import DeleteWorkspace, LoadEventNexus
from qtpy import QtCore, QtWidgets

from quicknxs.config import Settings
from quicknxs.config.gui import QColors
from quicknxs.interfaces.configuration import BinningType, Configuration
from quicknxs.interfaces.data_handling.data_manipulation import NormalizeToUnityQCutoffError
from quicknxs.interfaces.data_handling.data_set import CrossSectionData, NexusData
from quicknxs.interfaces.data_handling.filepath import FilePath, RunNumbers
from quicknxs.interfaces.data_handling.instrument import InsufficientEventCountError
from quicknxs.interfaces.data_manager import DataManager
from quicknxs.interfaces.enums import DirectBeamTableColumn, ReductionTableColumn
from quicknxs.interfaces.event_handlers.progress_reporter import ProgressReporter
from quicknxs.interfaces.event_handlers.status_bar_handler import StatusBarHandler
from quicknxs.interfaces.event_handlers.widgets import AcceptRejectDialog
from quicknxs.ui.active_radio_button import ActiveDataRadioButton
from quicknxs.ui.binningtype_combobox import BinningTypeSelection


class MainHandler:
    """Event handler for the main application window."""

    # Index of the direct beam tab in the reduction table tab widget
    DIRECT_BEAM_TAB_INDEX = 0
    # Index of the first (and always visible) data tab in the reduction table tab widget
    MAIN_DATA_TAB_INDEX = 1

    def __init__(self, main_window):
        self.ui = main_window.ui
        self.main_window = main_window
        self._data_manager: DataManager = main_window.data_manager

        # Create button groups for radio buttons to ensure mutual exclusivity
        self.reduction_table_button_groups = {}  # {tab_index: QButtonGroup}
        self.direct_beam_button_group = QtWidgets.QButtonGroup(self.main_window)

        # Initialize button group for the main reduction table
        self.reduction_table_button_groups[self.MAIN_DATA_TAB_INDEX] = QtWidgets.QButtonGroup(self.main_window)

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

        # Log Level dropdown in statusbar
        self.log_level = QtWidgets.QComboBox(self.ui.statusbar)
        self.LOG_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        self.log_level.addItems(self.LOG_LEVELS)
        self.log_level.setCurrentText(self.get_log_level())
        self.log_level.setToolTip(
            "Set the logging level\nDefault log level can be set with environment variable QUICKNXS_LOGLEVEL"
        )
        self.log_level.currentTextChanged.connect(self.change_log_level)

        self.ui.statusbar.addWidget(QtWidgets.QLabel("Log Level:"))
        self.ui.statusbar.addWidget(self.log_level)

    @property
    def reduction_table(self) -> QtWidgets.QTableWidget:
        """Returns the active reduction table widget if one of the data tabs is active, else the first one."""
        if self.ui.tabWidget.currentIndex() == self.DIRECT_BEAM_TAB_INDEX:
            # get the table for the main data tab
            current_table = self.ui.tabWidget.widget(self.MAIN_DATA_TAB_INDEX).findChild(QtWidgets.QTableWidget)
        else:
            current_table = self.ui.tabWidget.currentWidget().findChild(QtWidgets.QTableWidget)
        return current_table

    @property
    def direct_beam_table(self) -> QtWidgets.QTableWidget:
        """Returns the direct beam table widget."""
        return self.ui.directBeamTable

    def get_reduction_table_by_index(self, tab_index: int) -> QtWidgets.QTableWidget:
        """Return the QTableWidget for the data tab with the given index."""
        return self.ui.tabWidget.widget(tab_index).findChild(QtWidgets.QTableWidget)

    def new_progress_reporter(self):
        """Return a progress reporter."""
        return ProgressReporter(progress_bar=self.progress_bar, status_bar=self.status_bar_handler)

    def empty_cache(self):
        """Empty the data cache."""
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

    def open_file(self, file_path: str, force: bool = False, silent: bool = False) -> None:
        """Read one or more data files. If more than one, merge their data.

        Parameters
        ----------
        file_path:
            Absolute path to data files.
            If more than one file, paths are joined with the plus symbol '+'
        force:
            if true, the file will be reloaded even if it was loaded previously
        silent:
            if true, the plots currently shown in the interface will NOT be updated
        """
        # Actions carried out:
        # 1. check the file exists
        # 2. Invoke DataManager.load()
        # 3. if silent==False, invoke DataManager.file_loaded()

        if file_path is None:
            self.report_message("No file selected", pop_up=True)
            return

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
        prog = None
        self.main_window.auto_change_active = True
        try:
            self.report_message(f"Loading file(s) {file_path}")
            prog = ProgressReporter(progress_bar=self.progress_bar, status_bar=self.status_bar_handler)
            configuration = self.get_configuration_from_ui()
            self._data_manager.load(file_path, configuration, force=force, progress=prog)
            self.report_message(f"Loaded file(s) {self._data_manager.current_file_name}")
        except (RuntimeError, InsufficientEventCountError) as run_err:
            self.report_message(
                f"Error loading file(s) {self._data_manager.current_file_name} due to:\n{run_err}",
                detailed_message=str(traceback.format_exc()),
                pop_up=True,
                is_error=True,
            )
            self.main_window.auto_change_active = False
            # reset progress bar
            if prog is not None:
                prog.reset()
            return

        if not silent:
            self.file_loaded()
        self.main_window.auto_change_active = False
        logging.info("DONE: %s sec", time.time() - t_0)

    def file_loaded(self):
        """Update UI after a file is loaded."""
        self.main_window.auto_change_active = True
        self._set_data_manager_active_cross_section()

        cross_sections = list(self._data_manager.data_sets.keys())
        for i, xs in enumerate(cross_sections):
            getattr(self.ui, "selectedCrossSection%i" % i).show()
            good_label = xs.replace("_", "-")
            cross_section_label = self._data_manager.data_sets[xs].cross_section_label
            if good_label != cross_section_label:
                good_label = f"{good_label}: {cross_section_label}"
            getattr(self.ui, "selectedCrossSection%i" % i).setText(good_label)
        for i in range(len(cross_sections), 12):
            getattr(self.ui, "selectedCrossSection%i" % i).hide()
        self.main_window.auto_change_active = False

        # Emit signals to update the UI and plots
        self.main_window.file_loaded_signal.emit()
        self.main_window.initiate_reflectivity_or_intensity_plot.emit()
        self.main_window.initiate_projection_plot.emit(False)
        self.cache_indicator.setText("Files loaded: %s" % (self._data_manager.get_cachesize()))

    def active_cross_section_changed(self):
        """Update UI metadata and plots after the active cross section is changed."""
        self._set_data_manager_active_cross_section()
        self.update_cross_section_info()
        self.main_window.plotActiveTab()
        self.main_window.initiate_reflectivity_or_intensity_plot.emit()
        self.main_window.initiate_projection_plot.emit(False)

    def _set_data_manager_active_cross_section(self):
        """Set the data manager's active cross section to the one in the UI."""
        self.main_window.auto_change_active = True
        current_cross_section = 0
        for i in range(12):
            if getattr(self.ui, "selectedCrossSection%i" % i).isChecked():
                current_cross_section = i
                break

        success = self._data_manager.set_active_cross_section(current_cross_section)
        if not success:
            self.ui.selectedCrossSection0.setChecked(True)
        self.main_window.auto_change_active = False

    def _congruency_fail_report(self, file_paths: List[str], log_names: Optional[List[str]] = None):
        """Check whether these files can be merged.

        Parameters
        ----------
        file_paths:
            List of Nexus files (full paths)
        log_names:
            List of log names to compare. If None, all logs from Settings are used.
            If a log name is not in Settings, an error message is returned.

        Returns
        -------
        str:
            Error message; empty string if no error is found,
        """
        assert len(file_paths) > 1, "We require more than one data file in order to compare their metadata"
        # Log names validation and collect tolerances
        tolerances = dict()  # store the tolerance value for each log name
        all_tolerances: List[float] = Settings()["OpenSum"]["Tolerances"]
        all_log_names: List[str] = Settings()["OpenSum"]["LogNames"]
        assert all_log_names  # failsafe if structure of settings.json changes
        if log_names is None:
            log_names = all_log_names
        for log_name in log_names:
            try:
                i = all_log_names.index(log_name)
            except ValueError:
                return f"{log_name} is not a valid Log for comparison"
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
                return f"Could not load {file_path}"
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
        """Update a data set that may be in the reduction table or the direct beam table."""
        # Update the reduction table if this data set is in it
        idx = self._data_manager.find_active_data_id()
        if idx is not None:
            table_widget = self.reduction_table
            self.update_reduction_table(table_widget, idx, self._data_manager.active_cross_section)

        # Update the direct beam table if this data set is in it
        idx = self._data_manager.find_active_direct_beam_id()
        if idx is not None:
            self.update_direct_beam_table(idx, self._data_manager.active_cross_section)
            direct_beam = self._data_manager.direct_beam_list[idx]
            self.update_reduction_table_from_direct_beam(direct_beam)

    def update_calculated_data(self):
        """Update the calculated entries in the overview tab.

        We should call this after the peak ranges change,
        or after a change is made that will affect the displayed results.
        """
        d = self._data_manager.active_cross_section
        if d is None:
            return

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

        if d.configuration.direct_beam is not None:
            self.ui.matched_direct_beam_label.setText("%s" % d.configuration.direct_beam)
        else:
            self.ui.matched_direct_beam_label.setText("None")

    def update_info(self):
        """Update metadata shown in the overview tab."""
        self.main_window.auto_change_active = True
        d = self._data_manager.active_cross_section
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
        self.ui.currentCrossSection.setText(
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

        self.ui.roi_used_value.setText("%s" % d.use_roi_actual)
        self.ui.roi_peak_value.setText(str(d.configuration.metadata_roi_peak))
        self.ui.roi_bck_value.setText(str(d.configuration.metadata_roi_bck))

        # Update reduction tables
        self.update_tables()

        self.active_data_changed()

        self.main_window.auto_change_active = False

    def update_cross_section_info(self):
        """Update cross section metadata shown in the overview tab."""
        # Update cross-section specific information in the overview tab
        d = self._data_manager.active_cross_section
        self.ui.datasetPCharge.setText("%.3e" % d.proton_charge)
        self.ui.datasetTime.setText("%i s" % d.total_time)
        self.ui.datasetTotCounts.setText("%.4e" % d.total_counts)
        try:
            self.ui.datasetRate.setText("%.1f cps" % (d.total_counts / d.total_time))
        except ZeroDivisionError:
            self.ui.datasetRate.setText("NaN")
        self.ui.currentCrossSection.setText(
            "<b>%s</b> (%s)&nbsp;&nbsp;&nbsp;Type: %s&nbsp;&nbsp;&nbsp;Current State: "
            "<b>%s</b>" % (d.number, d.experiment, d.measurement_type, d.name)
        )

        # Update the calculated data
        self.update_calculated_data()

    def update_file_list(self, query_path: Optional[str] = None) -> None:
        """Update the list of data files.

        Parameters
        ----------
        query_path:
            Full path of a directory, a Nexus file, or a list of Nexus files.
            If a list of files, their paths are joined by the plus symbol '+'.
        """

        def _split_composites():
            """Split the list of files in widget self.ui.file_list into a list of single files and a list of composite files."""
            singles, composites = list(), list()
            for i in range(self.ui.file_list.count()):
                file_base_name = self.ui.file_list.item(i).text()
                if FilePath.merge_symbol in file_base_name:
                    composites.append(file_base_name)
                else:
                    singles.append(file_base_name)
            return singles, composites

        def _updated_current_list():
            r"""Most updated list of single and composite files from the current directory."""
            _, composites = _split_composites()
            return sorted(self._data_manager.current_event_files + composites)

        def _reset_ui_file_list(fresh_list):
            r"""Reset widget self.ui.file_list and highlight the current file_name."""
            self.ui.file_list.clear()  # Reset ui.file_list, a QtWidgets.QListWidget object
            assert isinstance(fresh_list, list), f"fresh_list must be list but not {type(fresh_list)}"
            for item in fresh_list:
                listitem = QtWidgets.QListWidgetItem(item, self.ui.file_list)
                if item == self._data_manager.current_file_name:
                    # Changing the current selection will trigger self.main_window.file_open_from_list() to be called,
                    # however, the current setting self.main_window.auto_change_active == True will cause
                    # self.main_window.file_open_from_list() to return before any statement is executed
                    self.ui.file_list.setCurrentItem(listitem)

        def _update_current_directory(new_dir):
            r"""Update the directory path in the main window and the path watcher."""
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
        """Automatically select files in the current directory based on incident angle.

        Go through the files in the current in order of run numbers,
        and load files until the incident angle is no longer increasing.
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

        q_current = self._data_manager.extract_metadata().mid_q

        # Add the current data set to the reduction table
        # Do nothing if the data is incompatible
        is_direct_beam = self._data_manager.active_cross_section.is_direct_beam
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
                metadata = self._data_manager.extract_metadata(file_path)

                if q_current <= metadata.mid_q and is_direct_beam == metadata.is_direct_beam:
                    q_current = metadata.mid_q
                    self.open_file(file_path, silent=True)
                    d = self._data_manager.active_cross_section
                    # If we find data of another type, stop here
                    if not is_direct_beam == self._data_manager.active_cross_section.is_direct_beam:
                        break
                    self.main_window.auto_change_active = True
                    self.populate_from_configuration(d.configuration)
                    if self._data_manager.active_cross_section.is_direct_beam:
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
        """Open a reduced file and all the data files needed to reproduce it."""
        # Open file dialog
        filter_ = "QuickNXS files (*.dat);;All (*.*)"
        output_dir = self.main_window.settings.value("output_directory", os.path.expanduser("~"))
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self.main_window, "Open reduced file...", directory=output_dir, filter=filter_
        )

        if file_path:
            t_0 = time.time()

            # Clear the reduction lists first so that we don't create problems later
            self.main_window.reset_data_tabs()
            self.clear_direct_beams()
            self.clear_reflectivity()
            configuration = self.get_configuration_from_ui()
            prog = self.new_progress_reporter()
            self._data_manager.load_data_from_reduced_file(file_path, configuration=configuration, progress=prog)

            # Update output directory
            file_dir, _ = os.path.split(str(file_path))
            self.main_window.settings.setValue("output_directory", file_dir)

            self.main_window.auto_change_active = True

            # Update UI direct beam table
            self.ui.directBeamTable.setRowCount(len(self._data_manager.direct_beam_list))
            for idx, _ in enumerate(self._data_manager.direct_beam_list):
                self._data_manager.set_active_data_from_direct_beam_list(idx)
                self.update_direct_beam_table(idx, self._data_manager.active_cross_section)
            # Update UI data table(s) with the loaded data
            for ipeak, _ in self._data_manager.peak_reduction_lists.items():
                self._data_manager.set_active_reduction_list_index(ipeak)
                self.main_window.add_data_tab_by_index(ipeak)
                table_widget = self.get_reduction_table_by_index(ipeak)
                table_widget.setRowCount(len(self._data_manager.reduction_list))
                for idx, _ in enumerate(self._data_manager.reduction_list):
                    self._data_manager.set_active_data_from_reduction_list(idx)
                    self.update_reduction_table(table_widget, idx, self._data_manager.active_cross_section)

            # Set the first reduction table and its first run as the active (plotted) data
            self._data_manager.set_active_reduction_list_index(self._data_manager.MAIN_REDUCTION_LIST_INDEX)
            self._data_manager.set_active_data_from_reduction_list(0)

            direct_beam_ids = [str(r.number) for r in self._data_manager.direct_beam_list]
            self.ui.direct_beam_list_label.setText(", ".join(direct_beam_ids))

            self.file_loaded()

            if self._data_manager.active_cross_section is not None:
                self.populate_from_configuration(self._data_manager.active_cross_section.configuration)
                self.update_file_list(self._data_manager.current_file)
            self.main_window.auto_change_active = False

            logging.info("UI updated: %s", time.time() - t_0)

    def initialize_additional_reduction_table(self, tab_index: int):
        """Initialize new reduction table from the main reduction table.

        Parameters
        ----------
        tab_index: int
            Index of the additional tab/peak
        """
        # Create a new button group for this reduction table
        if tab_index not in self.reduction_table_button_groups:
            self.reduction_table_button_groups[tab_index] = QtWidgets.QButtonGroup(self.main_window)

        if self._data_manager.main_reduction_list:
            table_widget = self.get_reduction_table_by_index(tab_index)
            table_widget.setRowCount(len(self._data_manager.main_reduction_list))
            active_cross_section_name: str = self._data_manager.active_cross_section.name
            for idx, nexus_data in enumerate(self._data_manager.main_reduction_list):
                active_cross_section = nexus_data.cross_sections[active_cross_section_name]
                self.update_reduction_table(table_widget, idx, active_cross_section)

    def _file_open_dialog(self, filter_: Optional[str] = None) -> Optional[str]:
        """Pop a File dialog window for the user to select one file.

        Parameters
        ----------
        filter_:
            Show files with only selected extensions

        Returns
        -------
        str:
            Absolute path to the selected file
        """
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self.main_window, "Open NXS file...", directory=self._data_manager.current_directory, filter=filter_
        )
        return file_path

    def _file_open_sum_dialog(self, filter_: Optional[str] = None) -> Optional[str]:
        """Open a File dialog Window for the user to select two or more files.

        Congruency among the selected files is checked by comparing the values of selected metadata.
        User is asked to override if congruency fails.

        Parameters
        ----------
        filter_:
            Show files with only selected extensions

        Returns
        -------
        str:
            Absolute paths to the selected files, joined by the plus symbol '+'
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

    def _process_file_path(self, dialog_opening_method: str) -> None:
        """Wrapper of the opening-file dialogs.

        This wrapper defines the extension of the files to be shown by the file dialog,
        and process the file(s) selected by the user.
        It updates the file list widget as well as reads-in the file(s)
        """
        if self.ui.histogramActive.isChecked():
            filter_ = "All (*.*);;histo.nxs (*histo.nxs);;QuickNXS (*.dat)"
        else:
            filter_ = "All (*.*);;nxs.h5 (*nxs.h5);;event.nxs (*event.nxs);;QuickNXS (*.dat)"

        file_path = getattr(self, dialog_opening_method)(filter_=filter_)

        if file_path:
            # Check if this is a reduced data file (.dat) - handle it differently
            if file_path.endswith(".dat"):
                # For reduced data files, skip update_file_list and open_file
                # and instead load via the reduced file loader
                t_0 = time.time()
                # Clear the reduction lists first
                self.main_window.reset_data_tabs()
                self.clear_direct_beams()
                self.clear_reflectivity()
                configuration = self.get_configuration_from_ui()
                prog = self.new_progress_reporter()
                self._data_manager.load_data_from_reduced_file(file_path, configuration=configuration, progress=prog)
                self.report_message("Loaded reduced file: %s" % file_path)
                logging.info("Reduced file loaded in %s sec", time.time() - t_0)
            else:
                # For nexus files, use the normal loading path
                self.update_file_list(file_path)
                self.open_file(file_path)

    def file_open_dialog(self):
        """GUI callback for backend MainHandler._file_open_dialog."""
        self._process_file_path("_file_open_dialog")

    def file_open_sum_dialog(self):
        """GUI callback for backend MainHandler._file_open_sum_dialog."""
        self._process_file_path("_file_open_sum_dialog")

    def _user_gives_permission(self, message: str) -> bool:
        """Ask user's permission to proceed or quit if the select runs do not have same sample logs."""
        message += ".\nProceed with Open Sum?"
        dialog = AcceptRejectDialog(self.main_window, title="Open Sum Confirmation", message=message)
        proceed = dialog.exec_()
        return proceed

    def open_run_number(self, number: Union[List[int], List[str], int, str, None] = None):
        """Open a data file by typing a run number or a composite run number for merging data sets.

        Example
        -------
        "120:123+125+127:132" opens files with run numbers from 120 to 132 except 124 and 126
        """
        self.main_window.auto_change_active = True
        if number is None:
            number = str(self.ui.numberSearchEntry.text())  # cast from unicode to string
        if number == "":
            self.report_message("No run number entered", pop_up=True)
            return
        QtWidgets.QApplication.instance().processEvents()
        run_numbers = RunNumbers(number)
        file_list = list()
        # Look for new-style nexus file name
        configuration = self.get_configuration_from_ui()
        for run_number in run_numbers.numbers:
            search_string = configuration.instrument.file_search_template % run_number
            matches = glob.glob(search_string + ".nxs.h5")  # type: Optional[List[str]]
            if not matches:  # Look for old-style nexus file name
                search_string = configuration.instrument.legacy_search_template % run_number
                matches = glob.glob(search_string + "_event.nxs")
            if not matches:
                self.report_message("Could not locate run number %s" % run_number, pop_up=True)
                return
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
        """Write parameters from all file daslogs to the table in the daslog tab."""
        table = self.ui.daslogTableBox
        table.setRowCount(0)
        table.sortItems(-1)
        table.setColumnCount(len(self._data_manager.data_sets) + 2)
        table.setHorizontalHeaderLabels(["Name"] + list(self._data_manager.data_sets.keys()) + ["Unit"])
        for j, key in enumerate(sorted(self._data_manager.active_cross_section.logs.keys(), key=lambda s: s.lower())):
            table.insertRow(j)
            table.setItem(j, 0, QtWidgets.QTableWidgetItem(key))
            table.setItem(
                j,
                len(self._data_manager.data_sets) + 1,
                QtWidgets.QTableWidgetItem(self._data_manager.active_cross_section.log_units[key]),
            )
            i = 0
            for xs in self._data_manager.data_sets:
                item = QtWidgets.QTableWidgetItem("%g" % self._data_manager.data_sets[xs].logs[key])
                item.setToolTip("MIN: %g   MAX: %g" % (self._data_manager.data_sets[xs].log_minmax[key]))
                table.setItem(j, i + 1, item)
                i += 1
        table.resizeColumnsToContents()

    def add_reflectivity(self, silent=False):
        """Collect information about the current extraction settings and store them in the list of reduction items.

        Returns
        -------
        bool:
            True if everything is ok, false otherwise.
        """
        # Update the configuration according to current parameters
        # Note that when a data set is first loaded, the peaks may have a different
        # range for each cross-section. If the option to use a common set of ranges
        # was turned on, we pick the ranges from the currently active cross-section
        # and apply then to all cross-sections.
        if self.ui.action_use_common_ranges.isChecked():
            config = self.get_configuration_from_ui()
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

        self.main_window.initiate_reflectivity_or_intensity_plot.emit()
        self.main_window.update_specular_viewer.emit()
        self.main_window.auto_change_active = False
        return True

    def update_reduction_table(self, table_widget: QtWidgets.QTableWidget, idx: int, data: CrossSectionData):
        """Update the reduction table.

        Parameters
        ----------
        table_widget:
            Table widget of the table to update
        idx:
            Row to update
        data:
            Cross-section data
        """
        self.main_window.auto_change_active = True

        # Get the current tab index to use the correct button group
        current_tab_index = self.ui.tabWidget.currentIndex()
        if current_tab_index not in self.reduction_table_button_groups:
            self.reduction_table_button_groups[current_tab_index] = QtWidgets.QButtonGroup(self.main_window)

        button_group = self.reduction_table_button_groups[current_tab_index]

        # radio button for active data (layout inside a widget to center it)
        radio_widget = ActiveDataRadioButton(self, is_active=(data == self._data_manager.active_cross_section), idx=idx)
        button_group.addButton(radio_widget.radio_button)
        table_widget.setCellWidget(idx, ReductionTableColumn.ACTIVE, radio_widget)

        item = QtWidgets.QTableWidgetItem(str(data.number))
        if data == self._data_manager.active_cross_section:
            item.setBackground(QColors.yellow)
        else:
            item.setBackground(QColors.white)
        # Set the item to be non-editable (bitwise AND with the negation of the editable flag)
        item.setFlags(item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
        table_widget.setItem(idx, ReductionTableColumn.RUN_NUMBER, item)

        # Slice column (non-editable)
        if idx < len(self._data_manager.reduction_list):
            nexus_data = self._data_manager.reduction_list[idx]
            slice_item = QtWidgets.QTableWidgetItem(str(nexus_data.slice))
        else:
            # Fallback if index is out of bounds (shouldn't happen but defensive programming)
            slice_item = QtWidgets.QTableWidgetItem("0")
        slice_item.setFlags(slice_item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
        table_widget.setItem(idx, ReductionTableColumn.SLICE, slice_item)

        table_widget.setItem(
            idx,
            ReductionTableColumn.SCALE_FACTOR,
            QtWidgets.QTableWidgetItem("%.4f" % (data.configuration.scaling_factor)),
        )
        table_widget.setItem(
            idx, ReductionTableColumn.NUM_LEFT, QtWidgets.QTableWidgetItem(str(data.configuration.cut_first_n_points))
        )
        table_widget.setItem(
            idx, ReductionTableColumn.NUM_RIGHT, QtWidgets.QTableWidgetItem(str(data.configuration.cut_last_n_points))
        )
        item = QtWidgets.QTableWidgetItem(str(data.configuration.peak_position))
        item.setBackground(QColors.dark_grey)
        table_widget.setItem(idx, ReductionTableColumn.PEAK_POSITION, item)
        table_widget.setItem(
            idx, ReductionTableColumn.PEAK_WIDTH, QtWidgets.QTableWidgetItem(str(data.configuration.peak_width))
        )
        item = QtWidgets.QTableWidgetItem(str(data.configuration.low_res_position))
        item.setBackground(QColors.dark_grey)
        table_widget.setItem(idx, ReductionTableColumn.LOW_RES_POSITION, item)
        table_widget.setItem(
            idx, ReductionTableColumn.LOW_RES_WIDTH, QtWidgets.QTableWidgetItem(str(data.configuration.low_res_width))
        )
        item = QtWidgets.QTableWidgetItem(str(data.configuration.bck_position))
        item.setBackground(QColors.dark_grey)
        table_widget.setItem(idx, ReductionTableColumn.BCK_POSITION, item)
        table_widget.setItem(
            idx, ReductionTableColumn.BCK_WIDTH, QtWidgets.QTableWidgetItem(str(data.configuration.bck_width))
        )
        table_widget.setItem(idx, ReductionTableColumn.DPIX, QtWidgets.QTableWidgetItem(str(data.direct_pixel)))
        item = QtWidgets.QTableWidgetItem("%.4f" % data.scattering_angle)
        item.setFlags(item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
        table_widget.setItem(idx, ReductionTableColumn.THETA, item)
        direct_beam = "none"
        if data.configuration.direct_beam is not None:
            direct_beam = data.configuration.direct_beam
        table_widget.setItem(idx, ReductionTableColumn.DIRECT_BEAM, QtWidgets.QTableWidgetItem(str(direct_beam)))
        # Binning type column
        combobox = BinningTypeSelection(on_change_handler=self.reduction_table_binning_type_changed, row=idx)
        combobox.blockSignals(True)
        combobox.setCurrentIndex(data.configuration.binning_type_run)
        combobox.blockSignals(False)
        table_widget.setCellWidget(idx, ReductionTableColumn.BINNING_TYPE, combobox)
        # Q steps column
        item = QtWidgets.QTableWidgetItem(f"{data.configuration.binning_q_step_run:.3f}")
        if data.configuration.binning_type_run == BinningType.NONE:
            # indicate Q steps is not used
            item.setForeground(QColors.dark_grey)
            item.setBackground(QColors.light_grey)
        table_widget.setItem(idx, ReductionTableColumn.Q_STEPS, item)

        self.main_window.auto_change_active = False

    def clear_reflectivity(self):
        """Remove all items from the reduction lists."""
        # clear the reduction lists in the data manager
        self._data_manager.clear_reduction_lists()
        # clear the reflectivity UI table widgets
        for itab in range(self.ui.tabWidget.count()):
            if itab == self.DIRECT_BEAM_TAB_INDEX:
                continue
            tab_widget = self.get_reduction_table_by_index(itab)
            tab_widget.setRowCount(0)
        # remove additional data tabs
        self.main_window.reset_data_tabs()

        self.main_window.initiate_reflectivity_or_intensity_plot.emit()

    def remove_reflectivity(self):
        """Remove one item from the reduction list."""
        index = self.reduction_table.currentRow()
        if index < 0:
            return
        self._data_manager.reduction_list.pop(index)
        self.reduction_table.removeRow(index)
        self.main_window.initiate_reflectivity_or_intensity_plot.emit()

    def reduction_table_changed(self, item: QtWidgets.QTableWidgetItem):
        """Perform action upon change in data reduction list.

        Parameters
        ----------
        item : QtWidgets.QTableWidgetItem
            The changed table item
        """
        if self.main_window.auto_change_active:
            return

        row = item.row()
        column = item.column()
        column = ReductionTableColumn(column)

        refl = self._data_manager.reduction_list[row]

        keys = {
            # ReductionTableColumn.ACTIVE: "active",
            # ReductionTableColumn.RUN_NUMBER: "number",  ## run number, not editable
            ReductionTableColumn.SCALE_FACTOR: "scaling_factor",
            ReductionTableColumn.NUM_LEFT: "cut_first_n_points",
            ReductionTableColumn.NUM_RIGHT: "cut_last_n_points",
            ReductionTableColumn.PEAK_POSITION: "peak_position",
            ReductionTableColumn.PEAK_WIDTH: "peak_width",
            ReductionTableColumn.LOW_RES_POSITION: "low_res_position",
            ReductionTableColumn.LOW_RES_WIDTH: "low_res_width",
            ReductionTableColumn.BCK_POSITION: "bck_position",
            ReductionTableColumn.BCK_WIDTH: "bck_width",
            ReductionTableColumn.DPIX: "direct_pixel_overwrite",
            # ReductionTableColumn.THETA: "scattering_angle",
            ReductionTableColumn.DIRECT_BEAM: "direct_beam",
            # ReductionTableColumn.BINNING_TYPE: "binning_type_run",  ## handled by combobox
            ReductionTableColumn.Q_STEPS: "binning_q_step_run",
        }

        if column not in keys:
            return

        # Update settings from selected option using match/case
        match column:
            case (
                ReductionTableColumn.SCALE_FACTOR
                | ReductionTableColumn.PEAK_POSITION
                | ReductionTableColumn.PEAK_WIDTH
                | ReductionTableColumn.LOW_RES_POSITION
                | ReductionTableColumn.LOW_RES_WIDTH
                | ReductionTableColumn.BCK_POSITION
                | ReductionTableColumn.BCK_WIDTH
                | ReductionTableColumn.DPIX
            ):
                refl.set_parameter(keys[column], float(item.text()))

            case ReductionTableColumn.NUM_LEFT | ReductionTableColumn.NUM_RIGHT:
                refl.set_parameter(keys[column], int(item.text()))

            case ReductionTableColumn.DIRECT_BEAM:
                direct_beam_name = item.text()
                direct_beam = self._data_manager.find_direct_beam_by_name(direct_beam_name)
                if direct_beam:
                    refl.set_parameter(keys[column], direct_beam_name)
                    # use direct beam peak position as dpix overwrite for matched ref runs
                    dpix = direct_beam.get_parameter("peak_position")
                    refl.set_parameter("direct_pixel_overwrite", dpix)
                    dpix_item = self.reduction_table.item(row, ReductionTableColumn.DPIX)
                    dpix_item.setText(str(dpix))
                else:
                    self.report_message("Not a valid direct beam run number, or the direct beam is not in the list.")
                    refl.set_parameter(keys[column], None)
                    self.main_window.auto_change_active = True
                    item.setText("none")
                    self.main_window.auto_change_active = False
                    # TODO: reset dpix overwrite to DAS value? (Glass)

            case ReductionTableColumn.Q_STEPS:
                try:
                    new_value = round(float(item.text()), 3)
                    if -0.1 <= new_value <= 0.1:
                        refl.set_parameter(keys[column], new_value)
                except:
                    refl.set_parameter(keys[column], None)

        recalculate = (
            False
            if column
            in [
                ReductionTableColumn.SCALE_FACTOR,
                ReductionTableColumn.NUM_LEFT,
                ReductionTableColumn.NUM_RIGHT,
            ]
            else True
        )

        # Recalculate and replot
        self.reduction_table_cell_changed(refl, recalculate)

    def reduction_table_binning_type_changed(self, combobox_index: int, row: int):
        """Perform action upon change in binning type column in the UI reduction table.

        Parameters
        ----------
        combobox_index : int
            The selected index in the combobox
        row : int
            The row in the reduction table to update.
        """
        # update the configuration state
        binning_type = BinningType(combobox_index)
        nexus_data = self._data_manager.reduction_list[row]
        nexus_data.set_parameter("binning_type_run", binning_type)

        # recalculate and replot
        self.reduction_table_cell_changed(nexus_data, recalculate=True)

    def reduction_table_cell_changed(self, refl: NexusData, recalculate: bool = True):
        """Perform action upon change in UI reduction table.

        Updates the internal configuration state and recalculates the reflectivity.

        Parameters
        ----------
        refl : NexusData
            The data set to update.
        recalculate : bool, optional
            Whether to recalculate the reflectivity, by default True
        """
        # Update calculated data
        refl.update_calculated_values()

        # If the changed data set is the active data, also change the UI
        if self._data_manager.is_active(refl):
            self.main_window.auto_change_active = True
            self.update_info()
            self.main_window.auto_change_active = False
        elif not refl.is_direct_beam():
            # If the changed data set is another data run, only need to update the UI reduction table,
            # to take into account changes in one column affecting another column
            table_widget = self.reduction_table
            idx = self._data_manager.find_data_in_reduction_list(refl)
            active_cross_section_name: str = self._data_manager.active_cross_section.name
            active_cross_section = refl.cross_sections[active_cross_section_name]
            self.update_reduction_table(table_widget, idx, active_cross_section)

        # Update the direct beam table if this data set is in it
        idx = self._data_manager.find_data_in_direct_beam_list(refl)
        if idx is not None:
            cross_sections = list(refl.cross_sections.keys())
            self.update_direct_beam_table(idx, refl.cross_sections[cross_sections[0]])

        # Only recalculate if we need to, otherwise just replot
        if recalculate:
            try:
                self._data_manager.calculate_reflectivity(nexus_data=refl)
            except:
                self.report_message(
                    "Could not compute reflectivity for %s" % self._data_manager.current_file_name,
                    detailed_message=str(traceback.format_exc()),
                    pop_up=False,
                    is_error=False,
                )

        self.main_window.plotActiveTab()
        self.main_window.initiate_reflectivity_or_intensity_plot.emit()
        self.main_window.update_specular_viewer.emit()

    def add_direct_beam(self, silent=False):
        """Add dataset to the direct beam table."""
        # Update all cross-section parameters as needed.
        if self.ui.action_use_common_ranges.isChecked():
            config = self.get_configuration_from_ui()
            self._data_manager.update_configuration(configuration=config, active_only=False)

        # Verify that the new data is consistent with existing data in the table
        add_result = self._data_manager.add_active_to_direct_beam_list()

        if add_result == 0:
            # Run was not added (already in the list)
            if not silent:
                self.report_message("(Add direct beam) Data already in the list.", pop_up=True)
            return False
        elif add_result == 1:
            # Run was added but is not a true direct beam
            if not silent:
                self.report_message(
                    f"Run {self._data_manager._nexus_data.number} added to direct beam list.\n\n"
                    "Note: This run is not labeled as a direct beam in the metadata "
                    "(data_type PV ≠ 1). This may occur for runs started with 'Start RUN' "
                    "command in EPICS.",
                    pop_up=False,
                )
        # else: add_result == 2, run was added and is a true direct beam (no warning needed)

        # The direct beam list has been appended with a new direct beam - add it to the UI table
        direct_beam_count = len(self._data_manager.direct_beam_list)
        self.ui.directBeamTable.setRowCount(direct_beam_count)
        idx = direct_beam_count - 1
        direct_beam_data = self._data_manager.direct_beam_list[idx].get_main_cross_section_data()
        self.update_direct_beam_table(idx, direct_beam_data)

        direct_beam_ids = [str(r.number) for r in self._data_manager.direct_beam_list]
        self.ui.direct_beam_list_label.setText(", ".join(direct_beam_ids))

        self.main_window.initiate_reflectivity_or_intensity_plot.emit()
        return True

    def remove_direct_beam(self):
        """Remove one item from the direct beam list."""
        index = self.ui.directBeamTable.currentRow()
        if index < 0:
            return
        self._data_manager.direct_beam_list.pop(index)
        self.ui.directBeamTable.removeRow(index)
        self.main_window.initiate_reflectivity_or_intensity_plot.emit()

    def clear_direct_beams(self):
        """Remove all items from the direct beam list."""
        self._data_manager.clear_direct_beam_list()
        self.ui.directBeamTable.setRowCount(0)
        self.ui.direct_beam_list_label.setText("None")
        self.main_window.initiate_reflectivity_or_intensity_plot.emit()

    def update_reduction_table_from_direct_beam(self, direct_beam: NexusData):
        """Update all reflectivity runs that use the given direct beam.

        Parameters
        ----------
        direct_beam:
            Direct beam data
        """
        matched_runs = [
            refl
            for refl in self._data_manager.reduction_list
            if str(refl.get_parameter("direct_beam")) == str(direct_beam.number)
        ]
        dpix = direct_beam.get_parameter("peak_position")
        for refl in matched_runs:
            # update the overwrite value for all runs with this direct beam
            refl.set_parameter("direct_pixel_overwrite", dpix)
            # only update the UI table for runs with set_direct_pixel ("overwrite") enabled,
            # if it is disabled, the value from the DAS will be used and shown instead
            if refl.get_parameter("set_direct_pixel"):
                idx = self._data_manager.find_data_in_reduction_list(refl)
                dpix_item = self.reduction_table.item(idx, ReductionTableColumn.DPIX)
                self.main_window.auto_change_active = True
                dpix_item.setText(str(dpix))
                self.main_window.auto_change_active = False

    def update_direct_beam_table(self, idx: int, data: CrossSectionData) -> None:
        """Update a direct beam table entry with cross-section data.

        Parameters
        ----------
        idx:
            Row to update
        data:
            Cross-section data
        """
        # Block signals to prevent recursion
        self.main_window.auto_change_active = True

        # radio button for active data (layout inside a widget to center it)
        radio_widget = ActiveDataRadioButton(
            self, is_active=(data == self._data_manager.active_cross_section), idx=idx, is_direct_beam=True
        )
        self.direct_beam_button_group.addButton(radio_widget.radio_button)
        self.ui.directBeamTable.setCellWidget(idx, DirectBeamTableColumn.ACTIVE, radio_widget)

        item = QtWidgets.QTableWidgetItem(str(data.number))
        item.setFlags(item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
        if data == self._data_manager.active_cross_section:
            item.setBackground(QColors.yellow)
        else:
            item.setBackground(QColors.white)

        self.ui.directBeamTable.setItem(idx, DirectBeamTableColumn.RUN_NUMBER, item)
        item = QtWidgets.QTableWidgetItem(str(data.configuration.peak_position))
        item.setBackground(QColors.dark_grey)
        self.ui.directBeamTable.setItem(idx, DirectBeamTableColumn.PEAK_POSITION, item)
        self.ui.directBeamTable.setItem(
            idx, DirectBeamTableColumn.PEAK_WIDTH, QtWidgets.QTableWidgetItem(str(data.configuration.peak_width))
        )
        item = QtWidgets.QTableWidgetItem(str(data.configuration.low_res_position))
        item.setBackground(QColors.dark_grey)
        self.ui.directBeamTable.setItem(idx, DirectBeamTableColumn.LOW_RES_POSITION, item)
        self.ui.directBeamTable.setItem(
            idx, DirectBeamTableColumn.LOW_RES_WIDTH, QtWidgets.QTableWidgetItem(str(data.configuration.low_res_width))
        )
        item = QtWidgets.QTableWidgetItem(str(data.configuration.bck_position))
        item.setBackground(QColors.dark_grey)
        self.ui.directBeamTable.setItem(idx, DirectBeamTableColumn.BCK_POSITION, item)
        self.ui.directBeamTable.setItem(
            idx, DirectBeamTableColumn.BCK_WIDTH, QtWidgets.QTableWidgetItem(str(data.configuration.bck_width))
        )
        wl = "%s - %s" % (data.wavelength[0], data.wavelength[-1])
        item = QtWidgets.QTableWidgetItem(wl)
        item.setFlags(item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
        self.ui.directBeamTable.setItem(idx, DirectBeamTableColumn.WAVELENGTH, item)

        # Unblock signals
        self.main_window.auto_change_active = False

    def direct_beam_table_changed(self, item: QtWidgets.QTableWidgetItem):
        """Perform action upon change in direct beam list."""
        if self.main_window.auto_change_active:
            return

        data = self._data_manager.direct_beam_list[item.row()]

        keys = {
            # DirectBeamTableColumn.ACTIVE: "active",
            # DirectBeamTableColumn.RUN_NUMBER: "number",  ## run number, not editable
            DirectBeamTableColumn.PEAK_POSITION: "peak_position",
            DirectBeamTableColumn.PEAK_WIDTH: "peak_width",
            DirectBeamTableColumn.LOW_RES_POSITION: "low_res_position",
            DirectBeamTableColumn.LOW_RES_WIDTH: "low_res_width",
            DirectBeamTableColumn.BCK_POSITION: "bck_position",
            DirectBeamTableColumn.BCK_WIDTH: "bck_width",
            # DirectBeamTableColumn.WAVELENGTH: "wavelength",  ## not editable
        }

        col = DirectBeamTableColumn(item.column())
        if col not in keys:
            return

        try:
            data.set_parameter(keys[col], float(item.text()))
        except ValueError:
            self.report_message(
                f"Invalid value for {keys[col]}:\n\t{item.text()}\nPlease enter a valid number.",
                pop_up=True,
                is_error=True,
            )
            # Reset to old value if conversion fails
            old_value = getattr(self._data_manager.active_cross_section.configuration, keys[col])
            item.setText(str(old_value))
            return

        # If peak position changed, also update direct pixel overwrite in all reflectivity runs using this direct beam
        if col == DirectBeamTableColumn.PEAK_POSITION:
            self.update_reduction_table_from_direct_beam(data)

        # Update calculated data
        data.update_calculated_values()

        # Update UI if this data set is the active one
        if self._data_manager.is_active(data):
            self.main_window.auto_change_active = True
            self.update_info()
            self.main_window.auto_change_active = False

        # Recalculate reflectivity for runs with this direct beam
        try:
            self._data_manager.reduce_spec(direct_beam=data.number)
        except:
            self.report_message(
                "Could not compute reflectivity for %s" % self._data_manager.current_file_name,
                detailed_message=str(traceback.format_exc()),
                pop_up=False,
                is_error=False,
            )

        self.main_window.plotActiveTab()
        self.main_window.initiate_reflectivity_or_intensity_plot.emit()
        self.main_window.initiate_projection_plot.emit(True)

    def active_data_changed(self):
        """Actions to be taken once the active data set has changed."""
        # If we update an entry, it's because that data is currently active.
        # Highlight it and un-highlight the other ones.
        self.main_window.auto_change_active = True
        idx = self._data_manager.find_active_data_id()
        for i in range(self.reduction_table.rowCount()):
            # Highlight the active data row, un-highlight the others
            run_num = self.reduction_table.item(i, ReductionTableColumn.RUN_NUMBER)
            if run_num is not None:
                if i == idx:
                    run_num.setBackground(QColors.yellow)
                else:
                    run_num.setBackground(QColors.white)
            # Set the radio button states
            active_cell = self.reduction_table.cellWidget(i, ReductionTableColumn.ACTIVE)
            if active_cell is not None:
                radio_button = active_cell.findChild(QtWidgets.QRadioButton)
                radio_button.setChecked(i == idx)

        idx = self._data_manager.find_active_direct_beam_id()
        for i in range(self.ui.directBeamTable.rowCount()):
            # Highlight the active data row, un-highlight the others
            item = self.ui.directBeamTable.item(i, DirectBeamTableColumn.RUN_NUMBER)
            if item is not None:
                if i == idx:
                    item.setBackground(QColors.yellow)
                else:
                    item.setBackground(QColors.white)
            # Set the radio button states
            active_cell = self.ui.directBeamTable.cellWidget(i, DirectBeamTableColumn.ACTIVE)
            if active_cell is not None:
                radio_button = active_cell.findChild(QtWidgets.QRadioButton)
                radio_button.setChecked(i == idx)

        self.main_window.auto_change_active = False

    def reduction_table_right_click(self, pos: QtCore.QPoint, is_reduction_table: bool = True):
        """Handle right-click on the reduction table.

        Parameters
        ----------
        pos:
            Mouse position
        is_reduction_table:
            True if the reduction table is active, False if the direct beam table is active
        """

        # Callbacks for the actions in the context menu
        def _export_data(_pos):
            row = table_widget.rowAt(pos.y())
            if 0 <= row < len(data_table):
                nexus_data = data_table[row]
                self.save_run_data(nexus_data)

        def _propagate_run(_pos):
            # If direct beam, make sure the user
            if not is_reduction_table and not self.ask_question(
                "Run is labeled as direct beam. Do you still want to add it to the list of reflectivity runs?"
            ):
                return

            row = table_widget.rowAt(pos.y())
            if 0 <= row < len(data_table):
                nexus_data = data_table[row]
                active_cross_section = self._data_manager.active_cross_section.name
                active_cross_section = nexus_data.cross_sections[active_cross_section]
                for ipeak, peak_data in self._data_manager.peak_reduction_lists.items():
                    if self._data_manager.copy_nexus_data_to_reduction(nexus_data, ipeak):
                        # get widget for target reduction table
                        target_widget = self.get_reduction_table_by_index(ipeak)
                        idx = self._data_manager.find_run_number_in_reduction_list(nexus_data.number, peak_data)
                        if idx is None:
                            raise RuntimeError("Run number not in reduction list")
                        target_widget.insertRow(idx)
                        # update UI table widget
                        self.update_reduction_table(target_widget, idx, active_cross_section)

        def _remove_run(_pos):
            if is_reduction_table:
                self.remove_reflectivity()
            else:
                self.remove_direct_beam()

        # Get the table widget and data table
        if is_reduction_table:
            table_widget = self.reduction_table
            data_table = self._data_manager.reduction_list
        else:
            table_widget = self.ui.directBeamTable
            data_table = self._data_manager.direct_beam_list

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
        """Save run data to file."""
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
                f"Overwrite existing file(s):\n{newline.join(existing_filenames)}?"
            ):
                break
        # save one file per cross-section
        for xs, filepath in save_filepaths.items():
            cross_section = nexus_data.cross_sections[xs]
            data_to_save, header = cross_section.get_tof_counts_table()
            np.savetxt(filepath, data_to_save, header=header)

    def compute_offspec_on_change(self, force=False):
        """Compute off-specular as needed."""
        prog = self.new_progress_reporter()
        has_changed_values = self.check_region_values_changed()
        offspec_data_exists = self._data_manager.is_offspec_available()
        logging.info("Exists %s %s", has_changed_values, offspec_data_exists)
        if force or has_changed_values >= 0 or not offspec_data_exists:
            logging.info("Updating....")
            config = self.get_configuration_from_ui()
            self._data_manager.update_configuration(configuration=config, active_only=False)
            self._data_manager.reduce_offspec(progress=prog)

    def compute_gisans_on_change(self, force=False, active_only=True):
        """Compute GISANS as needed."""
        prog = self.new_progress_reporter()
        has_changed_values = self.check_region_values_changed()
        gisans_data_exists = self._data_manager.is_gisans_available(active_only=active_only)
        logging.info("Exists %s %s %s", force, has_changed_values, gisans_data_exists)
        if force or has_changed_values >= 0 or not gisans_data_exists:
            logging.info("Updating....")
            config = self.get_configuration_from_ui()
            self._data_manager.update_configuration(configuration=config, active_only=False)
            if active_only:
                result = self._data_manager.calculate_gisans(progress=prog)
                if not result:
                    self.report_message(
                        f"Could not compute GISANS for {self._data_manager.current_file_name}",
                        detailed_message=str(traceback.format_exc()),
                        pop_up=True,
                        is_error=True,
                    )
            else:
                self._data_manager.reduce_gisans(progress=prog)

    def check_region_values_changed(self):
        """Return true if any of the parameters tied to a particular slot has changed.

        Some parameters are tied to the changeRegionValues() slot.
        There are time-consuming actions that we only want to take
        if those values actually changed, as opposed to the use simply
        clicking outside the box.

        Some parameters don't require a recalculation but simply a
        refreshing of the plots. Those are parameters such as scaling
        factors or the number of points clipped.

        Returns
        -------
        int:
            -1 = no valid change,
             0 = replot needed,
             1 = recalculation needed
        """
        if self._data_manager.active_cross_section is None:
            return -1

        configuration = self._data_manager.active_cross_section.configuration
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

        valid_change = (
            valid_change or configuration.binning_type_run != self.ui.binning_type_selector_run.currentIndex()
        )

        valid_change = valid_change or configuration.binning_q_step_run != self.ui.q_rebin_spinbox_run.value()

        if valid_change:
            return 1
        if replot_change:
            return 0
        return -1

    def get_configuration_from_ui(self) -> Configuration:
        """Gather the reduction options.

        Retrieve the reduction options either from the active cross section,
        or from the current settings in the graphical interface.

        Note that some options are global (static members of Configuration class),
        while others are per-cross-section (members of Configuration instance).
        This is because some options are applied to all cross-sections
        (e.g. whether to use a ROI or not), while others are specific to each cross-section
        (e.g. the peak position and width).
        """
        if self._data_manager.active_cross_section is not None:
            configuration = self._data_manager.active_cross_section.configuration
        else:
            configuration = Configuration()
        configuration.tof_bins = self.ui.eventTofBins.value()
        configuration.tof_bin_type = self.ui.eventBinMode.currentIndex()

        # Peak finder options
        Configuration.use_roi = self.ui.use_roi_checkbox.isChecked()
        Configuration.update_peak_range = self.ui.fit_within_roi_checkbox.isChecked()
        Configuration.use_peak_finder = self.ui.actionAutoXROI.isChecked()
        Configuration.use_low_res_finder = self.ui.actionAutoYROI.isChecked()
        Configuration.use_metadata_bck_roi = self.ui.use_bck_roi_checkbox.isChecked()
        Configuration.use_tight_bck = self.ui.use_side_bck_checkbox.isChecked()
        Configuration.bck_offset = self.ui.side_bck_width.value()

        # Default ranges, using the current values
        configuration.peak_position = self.ui.refXPos.value()
        configuration.peak_width = self.ui.refXWidth.value()
        configuration.low_res_position = self.ui.refYPos.value()
        configuration.low_res_width = self.ui.refYWidth.value()
        configuration.bck_position = self.ui.bgCenter.value()
        configuration.bck_width = self.ui.bgWidth.value()
        configuration.match_direct_beam = self.ui.actionAutoNorm.isChecked()
        configuration.binning_type_run = self.ui.binning_type_selector_run.currentIndex()
        configuration.binning_q_step_run = self.ui.q_rebin_spinbox_run.value()

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

        configuration.use_dangle = self.ui.trustDANGLE.isChecked()
        configuration.set_direct_pixel = self.ui.set_dirpix_checkbox.isChecked()
        configuration.set_direct_angle_offset = self.ui.set_dangle0_checkbox.isChecked()
        configuration.direct_pixel_overwrite = self.ui.directPixelOverwrite.value()
        configuration.direct_angle_offset_overwrite = self.ui.dangle0Overwrite.value()
        Configuration.sample_size = self.ui.sample_size_spinbox.value()
        Configuration.binning_q_step_global = self.ui.q_rebin_spinbox_global.value()

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

        return configuration

    def populate_from_configuration(self, configuration=None):
        """Set reduction options in UI, usually after loading a reduced data set."""
        if configuration is None:
            configuration = Configuration()

        self.ui.eventTofBins.setValue(configuration.tof_bins)
        self.ui.eventBinMode.setCurrentIndex(configuration.tof_bin_type)

        # Peak finder settings
        self.ui.use_roi_checkbox.setChecked(configuration.use_roi)
        self.ui.use_bck_roi_checkbox.setChecked(configuration.use_metadata_bck_roi)
        self.ui.fit_within_roi_checkbox.setChecked(configuration.update_peak_range)
        self.ui.actionAutoXROI.setChecked(False if configuration.use_roi else configuration.use_peak_finder)
        self.ui.actionAutoYROI.setChecked(False if configuration.use_roi else configuration.use_low_res_finder)
        # Use background on each side of the peak
        self.ui.use_side_bck_checkbox.setChecked(configuration.use_tight_bck)
        self.ui.side_bck_width.setValue(configuration.bck_offset)

        # Update reduction parameters
        self.ui.refXPos.setValue(configuration.peak_position)
        self.ui.refXWidth.setValue(configuration.peak_width)

        self.ui.refYPos.setValue(configuration.low_res_position)
        self.ui.refYWidth.setValue(configuration.low_res_width)

        self.ui.bgCenter.setValue(configuration.bck_position)
        self.ui.bgWidth.setValue(configuration.bck_width)

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

        self.ui.trustDANGLE.setChecked(configuration.use_dangle)
        self.ui.set_dirpix_checkbox.setChecked(configuration.set_direct_pixel)
        self.ui.set_dangle0_checkbox.setChecked(configuration.set_direct_angle_offset)
        self.ui.directPixelOverwrite.setValue(configuration.direct_pixel_overwrite)
        self.ui.dangle0Overwrite.setValue(configuration.direct_angle_offset_overwrite)
        self.ui.sample_size_spinbox.setValue(configuration.sample_size)
        self.ui.q_rebin_spinbox_global.setValue(configuration.binning_q_step_global)

        self.ui.deadtime_entry.applyCheckBox.setChecked(configuration.apply_deadtime)

        self.ui.direct_beam_y_lock_checkbox.setChecked(configuration.lock_direct_beam_y)

        self.ui.binning_type_selector_run.setCurrentIndex(configuration.binning_type_run)
        if configuration.binning_q_step_run:
            self.ui.q_rebin_spinbox_run.setValue(configuration.binning_q_step_run)

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
        """Stitch the reflectivity parts and normalize to 1."""
        # Update the configuration so we can remember the cutoff value
        # later if it was changed
        self.get_configuration_from_ui()
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
                f"Error in stitching:\n{str(err)}",
                detailed_message=str(traceback.format_exc()),
                pop_up=True,
                is_error=True,
            )
        except NormalizeToUnityQCutoffError as err:
            self.report_message(
                f"Error in normalize to unity when stitching:\n{str(err)}",
                detailed_message=str(traceback.format_exc()),
                pop_up=True,
                is_error=True,
            )
        else:
            for i in range(len(self._data_manager.reduction_list)):
                xs = self._data_manager.active_cross_section.name
                d = self._data_manager.reduction_list[i].cross_sections[xs]
                self.reduction_table.setItem(
                    i,
                    ReductionTableColumn.SCALE_FACTOR,
                    QtWidgets.QTableWidgetItem("%.4f" % (d.configuration.scaling_factor)),
                )

            self.main_window.initiate_reflectivity_or_intensity_plot.emit()

    def trim_data_to_normalization(self):
        """Cut the start and end of the active data set to 5% of its maximum intensity."""
        trim_points = self._data_manager.get_trim_values()
        if trim_points is not None:
            self.ui.rangeStart.setValue(trim_points[0])
            self.ui.rangeEnd.setValue(trim_points[1])
            self.update_tables()
            self.main_window.initiate_reflectivity_or_intensity_plot.emit()
        else:
            self.report_message("No direct beam found to trim data", pop_up=False)

    def strip_overlap(self):
        """Remove overlapping points in the reflectivity, cutting always from the lower Qz measurements."""
        self._data_manager.strip_overlap()

        for i in range(len(self._data_manager.reduction_list)):
            xs = self._data_manager.active_cross_section.name
            d = self._data_manager.reduction_list[i].cross_sections[xs]
            self.reduction_table.setItem(
                i, ReductionTableColumn.NUM_RIGHT, QtWidgets.QTableWidgetItem(str(d.configuration.cut_last_n_points))
            )

        self.main_window.initiate_reflectivity_or_intensity_plot.emit()

    def reload_all_files(self):
        """Reload all files upon change in loading configuration.

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

        # Store the active data tab
        active_data_tab = self._data_manager.active_reduction_list_index

        # Reload files
        self._data_manager.clear_cached_unused_data()
        configuration = self.get_configuration_from_ui()
        prog = ProgressReporter(progress_bar=self.progress_bar, status_bar=self.status_bar_handler)
        self._data_manager.reload_files(configuration, prog)

        # Update the tables in the UI
        self.main_window.auto_change_active = True

        self.ui.directBeamTable.setRowCount(len(self._data_manager.direct_beam_list))
        for idx, _ in enumerate(self._data_manager.direct_beam_list):
            self._data_manager.set_active_data_from_direct_beam_list(idx)
            self.update_direct_beam_table(idx, self._data_manager.active_cross_section)
        self.ui.reductionTable.setRowCount(len(self._data_manager.reduction_list))
        for ipeak, peak_data in self._data_manager.peak_reduction_lists.items():
            self._data_manager.set_active_reduction_list_index(ipeak)
            table_widget = self.get_reduction_table_by_index(ipeak)
            table_widget.setRowCount(len(self._data_manager.reduction_list))
            for idx, _ in enumerate(self._data_manager.reduction_list):
                self._data_manager.set_active_data_from_reduction_list(idx)
                self.update_reduction_table(table_widget, idx, self._data_manager.active_cross_section)

        direct_beam_ids = [str(r.number) for r in self._data_manager.direct_beam_list]
        self.ui.direct_beam_list_label.setText(", ".join(direct_beam_ids))

        # Restore the active data tab
        self._data_manager.set_active_reduction_list_index(active_data_tab)

        # Restore the active run
        if is_active_data_direct_beam:
            self._data_manager.set_active_data_from_direct_beam_list(active_idx)
        else:
            self._data_manager.set_active_data_from_reduction_list(active_idx)

        # Update plots
        self.file_loaded()

        self.main_window.auto_change_active = False

    def report_message(
        self,
        message: str,
        informative_message: Optional[str] = None,
        detailed_message: Optional[str] = None,
        pop_up: bool = False,
        is_error: bool = False,
    ):
        """Report a message or error to the status bar at the bottom of the window.

        If `is_error` is True, the message is also logged on the error channel.
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

    def ask_question(self, message: str) -> bool:
        """Display a popup dialog with a message and choices "Ok" and "Cancel"."""
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
        """Pop up the result viewer."""
        from quicknxs.interfaces.result_viewer import ResultViewer

        dialog = ResultViewer(self.main_window, self._data_manager)
        dialog.specular_compare_widget.ui.refl_preview_checkbox.setChecked(True)
        self.main_window.update_specular_viewer.connect(dialog.update_specular)
        self.main_window.update_off_specular_viewer.connect(dialog.update_off_specular)
        self.main_window.update_gisans_viewer.connect(dialog.update_gisans)
        dialog.show()

    def propagate_binning_options_to_run_config(self):
        """Enable the selected binning type with the given Q-step for all runs in the active data tab.

        Note: This function updates the UI and internal configuration state while blocking all signals.
        The caller is responsible for triggering recalculation and replotting.
        """
        bin_type_global = self.ui.binning_type_selector_global.currentIndex()
        q_step_global = self.ui.q_rebin_spinbox_global.value()

        # loop over runs in the active data tab to update internal state and UI state
        reduct_list = self._data_manager.reduction_list
        for idx, nexus_data in enumerate(reduct_list):
            active_cross_section_name: str = self._data_manager.active_cross_section.name
            active_cross_section = nexus_data.cross_sections[active_cross_section_name]
            # get the current configuration state
            conf = active_cross_section.configuration
            # update the run final rebin configuration state
            conf.binning_type_run = bin_type_global
            conf.binning_q_step_run = q_step_global
            nexus_data.update_configuration(conf)
            # update the UI reduction table to reflect the configuration state (signals are blocked)
            self.update_reduction_table(self.reduction_table, idx, active_cross_section)

        # update the run Q step spinbox value
        self.ui.q_rebin_spinbox_run.blockSignals(True)
        self.ui.q_rebin_spinbox_run.setValue(q_step_global)
        self.ui.q_rebin_spinbox_run.blockSignals(False)

        # update the run binning type combobox
        self.ui.binning_type_selector_run.blockSignals(True)
        self.ui.binning_type_selector_run.setCurrentIndex(bin_type_global)
        self.ui.binning_type_selector_run.blockSignals(False)

    def get_log_level(self):
        """Return current root logger level as a string for GUI dropdown."""
        level = logging.getLogger().getEffectiveLevel()
        return logging.getLevelName(level)

    def change_log_level(self, level: str):
        """Update all handlers + root logger to new level."""
        lvl = level.upper()
        if lvl not in (self.LOG_LEVELS):
            lvl = "INFO"
        root = logging.getLogger()
        root.setLevel(lvl)
        for handler in root.handlers:
            handler.setLevel(lvl)
