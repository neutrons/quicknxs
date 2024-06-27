# local imports
from reflectivity_ui.interfaces.configuration import Configuration
from reflectivity_ui.interfaces.data_handling.data_set import CrossSectionData, NexusData
from reflectivity_ui.interfaces.main_window import MainWindow
from test.ui import ui_utilities

# third party imports
import pytest
from qtpy import QtCore, QtWidgets


# standard library imports


class TestMainGui:
    def test_init(self, qtbot):
        window_main = MainWindow()
        qtbot.addWidget(window_main)
        assert "QuickNXS Magnetic Reflectivity" in window_main.windowTitle()

    @pytest.mark.datarepo
    def test_enter_run_number(self, qtbot):
        window_main = MainWindow()
        qtbot.addWidget(window_main)
        ui_utilities.setText(window_main.numberSearchEntry, "42100", press_enter=True)

    def test_set_global_stitching(self, qtbot):
        """Test that the configuration is updated based on the checkbox value"""
        window_main = MainWindow()
        qtbot.addWidget(window_main)
        window_main.global_fit_checkbox.setChecked(True)
        assert window_main.file_handler.get_configuration().global_stitching is True
        window_main.global_fit_checkbox.setChecked(False)
        assert window_main.file_handler.get_configuration().global_stitching is False

    def test_active_channel(self, mocker, qtbot):
        """Test that selecting a cross-section radio button updates the active channel"""
        # mock updating the plots
        mocker.patch("reflectivity_ui.interfaces.main_window.MainWindow.plotActiveTab", return_value=True)
        mocker.patch("reflectivity_ui.interfaces.plotting.PlotManager.plot_refl", return_value=True)
        mocker.patch("reflectivity_ui.interfaces.plotting.PlotManager.plot_projections", return_value=True)

        # create the SUT
        window_main = MainWindow()
        qtbot.addWidget(window_main)

        # set up data objects for two channels
        configuration = window_main.file_handler.get_configuration()
        channel0 = CrossSectionData("On_Off", configuration)
        channel1 = CrossSectionData("On_On", configuration)
        nexus_data = NexusData("filepath", configuration)
        nexus_data.cross_sections = {channel0.name: channel0, channel1.name: channel1}
        window_main.data_manager._nexus_data = nexus_data
        window_main.data_manager.set_channel(0)

        assert window_main.data_manager.active_channel.name == channel0.name

        # change the selected channel
        window_main.selectedChannel1.setChecked(True)

        # check the active channel in the data manager
        assert window_main.data_manager.active_channel.name == channel1.name
        # check the current channel name displayed in the UI
        assert channel1.name in window_main.ui.currentChannel.text()

    @pytest.mark.parametrize("table_widget", ["reductionTable", "normalizeTable"])
    def test_reduction_table_right_click(self, table_widget, qtbot, mocker):
        mock_save_run_data = mocker.patch(
            "reflectivity_ui.interfaces.event_handlers.main_handler.MainHandler.save_run_data"
        )
        window_main = MainWindow()
        qtbot.addWidget(window_main)
        window_main.data_manager.reduction_list = [NexusData("filepath", Configuration())]
        window_main.data_manager.direct_beam_list = [NexusData("filepath", Configuration())]
        table = getattr(window_main.ui, table_widget)
        table.insertRow(0)

        def handle_menu():
            """Press Enter on item in menu and check that the function was called"""
            menu = table.findChild(QtWidgets.QMenu)
            action = menu.actions()[0]
            assert action.text() == "Export data"
            qtbot.keyClick(menu, QtCore.Qt.Key_Down)
            qtbot.keyClick(menu, QtCore.Qt.Key_Enter)
            mock_save_run_data.assert_called_once()

        QtCore.QTimer.singleShot(200, handle_menu)
        pos = QtCore.QPoint()
        table.customContextMenuRequested.emit(pos)

    def test_global_vs_per_run(self, qtbot, mocker):
        """Test the global vs per run reduction variables"""

        # mock updating the plots
        mocker.patch("reflectivity_ui.interfaces.main_window.MainWindow.plotActiveTab", return_value=True)
        mocker.patch("reflectivity_ui.interfaces.plotting.PlotManager.plot_refl", return_value=True)
        mocker.patch("reflectivity_ui.interfaces.plotting.PlotManager.plot_projections", return_value=True)

        window_main = MainWindow()
        qtbot.addWidget(window_main)

        # set up data objects for two files
        configuration = Configuration()
        # make sure these global properties start as the defult
        Configuration.wl_bandwidth = 3.2
        Configuration.use_constant_q = False
        Configuration.sample_size = 10
        Configuration.do_final_rebin = True
        Configuration.final_rebin_step = -0.01
        Configuration.normalize_to_unity = True
        Configuration.total_reflectivity_q_cutoff = 0.01
        Configuration.global_stitching = False
        Configuration.polynomial_stitching = False
        Configuration.polynomial_stitching_degree = 3
        Configuration.polynomial_stitching_points = 3
        Configuration.lock_direct_beam_y = False

        channel1 = CrossSectionData("On_Off", configuration)
        nexus_data1 = NexusData("filepath1", configuration)
        nexus_data1.cross_sections = {channel1.name: channel1, channel1.name: channel1}
        channel2 = CrossSectionData("On_Off", configuration)
        nexus_data2 = NexusData("filepath2", configuration)
        nexus_data2.cross_sections = {channel2.name: channel2, channel2.name: channel2}

        window_main.data_manager.reduction_list.append(nexus_data1)
        window_main.data_manager.reduction_list.append(nexus_data2)
        window_main.data_manager.set_active_data_from_reduction_list(0)
        assert window_main.data_manager.current_file == "filepath1"

        # check that the configuration is the default
        conf1 = window_main.data_manager.active_channel.configuration

        # Reflectivity Extraction (Global)
        assert conf1.do_final_rebin is True
        assert conf1.final_rebin_step == -0.01
        assert conf1.normalize_to_unity is True
        assert conf1.total_reflectivity_q_cutoff == 0.01
        assert conf1.global_stitching is False
        assert conf1.polynomial_stitching is False
        assert conf1.polynomial_stitching_degree == 3
        assert conf1.polynomial_stitching_points == 3
        assert conf1.use_constant_q is False
        assert conf1.sample_size == 10
        assert conf1.wl_bandwidth == 3.2
        assert conf1.lock_direct_beam_y is False

        # Reflectivity Extraction (Per Run)

        assert conf1.low_res_position == 130
        assert conf1.low_res_width == 20
        assert conf1.peak_position == 130
        assert conf1.peak_width == 20
        assert conf1.subtract_background is True
        assert conf1.bck_position == 30
        assert conf1.bck_width == 20
        assert conf1.scaling_factor == 1.0
        assert conf1.cut_first_n_points == 1
        assert conf1.cut_last_n_points == 1
        assert conf1.set_direct_pixel is False
        assert conf1.direct_pixel_overwrite == 0
        assert conf1.set_direct_angle_offset is False
        assert conf1.direct_angle_offset_overwrite == 0
        assert conf1.use_dangle is False

        # set UI elements to non-default

        # global
        window_main.ui.final_rebin_checkbox.setChecked(False)
        window_main.ui.q_rebin_spinbox.setValue(-0.02)
        window_main.ui.normalize_to_unity_checkbox.setChecked(False)
        window_main.ui.normalization_q_cutoff_spinbox.setValue(0.02)
        window_main.ui.global_fit_checkbox.setChecked(True)
        window_main.ui.polynomial_stitching_checkbox.setChecked(True)
        window_main.ui.polynomial_stitching_degree_spinbox.setValue(4)
        window_main.ui.polynomial_stitching_points_spinbox.setValue(5)
        window_main.ui.fanReflectivity.setChecked(True)
        window_main.ui.sample_size_spinbox.setValue(12)
        window_main.ui.bandwidth_spinbox.setValue(2.3)
        window_main.ui.direct_beam_y_lock_checkbox.setChecked(True)
        # per run
        window_main.ui.refYPos.setValue(120)
        window_main.ui.refYWidth.setValue(30)
        window_main.ui.refXPos.setValue(120)
        window_main.ui.refXWidth.setValue(30)
        window_main.ui.bgActive.setChecked(False)
        window_main.ui.bgCenter.setValue(20)
        window_main.ui.bgWidth.setValue(15)
        window_main.ui.refScale.setValue(1.0)
        window_main.ui.rangeStart.setValue(2)
        window_main.ui.rangeEnd.setValue(3)
        window_main.ui.set_dirpix_checkbox.setChecked(True)
        window_main.ui.directPixelOverwrite.setValue(1.0)
        window_main.ui.set_dangle0_checkbox.setChecked(True)
        window_main.ui.dangle0Overwrite.setValue(2.0)
        window_main.ui.trustDANGLE.setChecked(True)

        window_main.file_handler.get_configuration()  # to update configuration from UI

        # check that the current config has been updated for both global and per run
        conf1 = window_main.data_manager.active_channel.configuration

        # Reflectivity Extraction (Global)
        assert conf1.do_final_rebin is False
        assert conf1.final_rebin_step == -0.02
        assert conf1.normalize_to_unity is False
        assert conf1.total_reflectivity_q_cutoff == 0.02
        assert conf1.global_stitching is True
        assert conf1.polynomial_stitching is True
        assert conf1.polynomial_stitching_degree == 4
        assert conf1.polynomial_stitching_points == 5
        assert conf1.use_constant_q is True
        assert conf1.sample_size == 12
        assert conf1.wl_bandwidth == 2.3
        assert conf1.lock_direct_beam_y is True

        # Reflectivity Extraction (Per Run)

        assert conf1.low_res_position == 120
        assert conf1.low_res_width == 30
        assert conf1.peak_position == 120
        assert conf1.peak_width == 30
        assert conf1.subtract_background is False
        assert conf1.bck_position == 20
        assert conf1.bck_width == 15
        assert conf1.scaling_factor == 10.0
        assert conf1.cut_first_n_points == 2
        assert conf1.cut_last_n_points == 3
        assert conf1.set_direct_pixel is True
        assert conf1.direct_pixel_overwrite == 1.0
        assert conf1.set_direct_angle_offset is True
        assert conf1.direct_angle_offset_overwrite == 2.0
        assert conf1.use_dangle is True

        # change selected data and check that global variables are carried over but not the per run ones

        window_main.data_manager.set_active_data_from_reduction_list(1)
        assert window_main.data_manager.current_file == "filepath2"

        # check that the configuration is the default
        conf2 = window_main.data_manager.active_channel.configuration

        # Reflectivity Extraction (Global)
        assert conf2.do_final_rebin is False
        assert conf2.final_rebin_step == -0.02
        assert conf2.normalize_to_unity is False
        assert conf2.total_reflectivity_q_cutoff == 0.02
        assert conf2.global_stitching is True
        assert conf2.polynomial_stitching is True
        assert conf2.polynomial_stitching_degree == 4
        assert conf2.polynomial_stitching_points == 5
        assert conf2.use_constant_q is True
        assert conf2.sample_size == 12
        assert conf2.wl_bandwidth == 2.3
        assert conf2.lock_direct_beam_y is True

        # Reflectivity Extraction (Per Run)

        assert conf2.low_res_position == 130
        assert conf2.low_res_width == 20
        assert conf2.peak_position == 130
        assert conf2.peak_width == 20
        assert conf2.subtract_background is True
        assert conf2.bck_position == 30
        assert conf2.bck_width == 20
        assert conf2.scaling_factor == 1.0
        assert conf2.cut_first_n_points == 1
        assert conf2.cut_last_n_points == 1
        assert conf2.set_direct_pixel is False
        assert conf2.direct_pixel_overwrite == 0
        assert conf2.set_direct_angle_offset is False
        assert conf2.direct_angle_offset_overwrite == 0
        assert conf2.use_dangle is False

    def test_add_remove_data_tab(self, qtbot):
        """Test that the add data tab button reveals/hides tabs as expected"""
        window_main = MainWindow()
        qtbot.addWidget(window_main)

        def _assert_tabs_visible(tab_ids: list[bool]):
            for idx, is_visible in enumerate(tab_ids):
                assert window_main.ui.tabWidget.isTabVisible(idx) == is_visible

        _assert_tabs_visible([True, True, False, False, False])

        window_main.ui.addTabButton.clicked.emit()
        _assert_tabs_visible([True, True, True, False, False])
        window_main.ui.addTabButton.clicked.emit()
        _assert_tabs_visible([True, True, True, True, False])
        window_main.ui.addTabButton.clicked.emit()
        _assert_tabs_visible([True, True, True, True, True])

        # reached max number of tabs, button function changes to remove/hide tabs
        window_main.ui.addTabButton.clicked.emit()
        _assert_tabs_visible([True, True, True, True, False])
        window_main.ui.addTabButton.clicked.emit()
        _assert_tabs_visible([True, True, True, False, False])
        window_main.ui.addTabButton.clicked.emit()
        _assert_tabs_visible([True, True, False, False, False])

    @pytest.mark.datarepo
    def test_change_active_data_tab(self, mocker, qtbot, data_server):
        """Test that the internal state is updated when the active data tab is changed"""
        mock_plot_refl = mocker.patch("reflectivity_ui.interfaces.plotting.PlotManager.plot_refl", return_value=True)

        window_main = MainWindow()
        qtbot.addWidget(window_main)

        manager = window_main.data_manager
        manager.load(data_server.path_to("REF_M_40782"), Configuration())
        manager.add_active_to_reduction()
        manager.load(data_server.path_to("REF_M_40785"), Configuration())
        manager.add_active_to_reduction()

        # add second peak tab
        window_main.ui.addTabButton.clicked.emit()
        assert mock_plot_refl.call_count == 0
        # switch to second peak tab
        window_main.ui.tabWidget.setCurrentIndex(2)
        assert window_main.data_manager.active_reduction_list_index == 2
        assert mock_plot_refl.call_count == 1
        # switch to first peak tab
        window_main.ui.tabWidget.setCurrentIndex(1)
        assert window_main.data_manager.active_reduction_list_index == 1
        assert mock_plot_refl.call_count == 2

    def test_reduction_table_propagate_run(self):
        """Test right-click action 'Propagate run'"""
        pass

    def test_reduction_table_remove_run(self):
        """Test right-click action 'Remove run'"""
        pass


if __name__ == "__main__":
    pytest.main([__file__])
