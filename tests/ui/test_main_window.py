import pytest
from qtpy import QtCore, QtWidgets

from quicknxs.enums import QBinningType
from quicknxs.models.configuration import Configuration
from quicknxs.models.data_set import CrossSectionData, NexusData
from quicknxs.views.main_window import MainWindow, disabled_widget
from tests.ui import ui_utilities


class TestMainGui:
    """Test the main GUI of QuickNXS."""

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
        """Test that the configuration is updated based on the checkbox value."""
        window_main = MainWindow()
        qtbot.addWidget(window_main)
        window_main.global_fit_checkbox.setChecked(True)
        assert window_main.file_handler.get_configuration_from_ui().global_stitching is True
        window_main.global_fit_checkbox.setChecked(False)
        assert window_main.file_handler.get_configuration_from_ui().global_stitching is False

    def test_active_cross_section(self, mocker, qtbot):
        """Test that selecting a cross-section radio button updates the active cross section."""
        # mock updating the plots
        mocker.patch("quicknxs.views.main_window.MainWindow.plotActiveTab", return_value=True)
        mocker.patch("quicknxs.views.plotting.PlotView.plot_reflectivity_or_intensity", return_value=True)
        mocker.patch("quicknxs.views.plotting.PlotView.plot_projections", return_value=True)

        # create the SUT
        window_main = MainWindow()
        qtbot.addWidget(window_main)

        # set up data objects for two cross sections
        configuration = window_main.file_handler.get_configuration_from_ui()
        cross_section_0 = CrossSectionData("On_Off", configuration)
        cross_section_1 = CrossSectionData("On_On", configuration)
        nexus_data = NexusData("filepath", configuration)
        nexus_data.cross_sections = {cross_section_0.name: cross_section_0, cross_section_1.name: cross_section_1}
        window_main.data_presenter._nexus_data = nexus_data
        window_main.data_presenter.set_active_cross_section(0)

        assert window_main.data_presenter.active_cross_section.name == cross_section_0.name

        # change the selected cross section
        window_main.selectedCrossSection1.setChecked(True)

        # check the active cross section in the data manager
        assert window_main.data_presenter.active_cross_section.name == cross_section_1.name
        # check the current cross section name displayed in the UI
        assert cross_section_1.name in window_main.ui.currentCrossSection.text()

    @pytest.mark.parametrize("table_widget", ["reductionTable", "directBeamTable"])
    def test_reduction_table_right_click(self, table_widget, qtbot, mocker):
        mock_save_run_data = mocker.patch("quicknxs.presenters.main_presenter.MainPresenter.save_run_data")
        window_main = MainWindow()
        qtbot.addWidget(window_main)
        window_main.data_presenter.reduction_list = [NexusData("filepath", Configuration())]
        window_main.data_presenter.direct_beam_list = [NexusData("filepath", Configuration())]
        table = getattr(window_main.ui, table_widget)
        table.insertRow(0)

        def handle_menu():
            """Press Enter on item in menu and check that the function was called."""
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
        """Test the global vs per run reduction variables."""
        # mock updating the plots
        mocker.patch("quicknxs.views.main_window.MainWindow.plotActiveTab", return_value=True)
        mocker.patch("quicknxs.views.plotting.PlotView.plot_reflectivity_or_intensity", return_value=True)
        mocker.patch("quicknxs.views.plotting.PlotView.plot_projections", return_value=True)

        window_main = MainWindow()
        qtbot.addWidget(window_main)

        # set up data objects for two files

        Configuration.setup_default_values()
        configuration = Configuration()

        cross_section_1 = CrossSectionData("On_Off", configuration)
        nexus_data1 = NexusData("filepath1", configuration)
        nexus_data1.cross_sections = {cross_section_1.name: cross_section_1}
        cross_section_2 = CrossSectionData("On_Off", configuration)
        nexus_data2 = NexusData("filepath2", configuration)
        nexus_data2.cross_sections = {cross_section_2.name: cross_section_2}

        window_main.data_presenter.reduction_list.append(nexus_data1)
        window_main.data_presenter.reduction_list.append(nexus_data2)
        window_main.data_presenter.set_active_data_from_reduction_list(0)
        assert window_main.data_presenter.current_file == "filepath1"

        # check that the configuration is the default
        conf1 = window_main.data_presenter.active_cross_section.configuration

        # Reflectivity Extraction (Global)
        assert conf1.q_binning_type_global == QBinningType.NONE
        assert conf1.q_binning_step_global == -0.02
        assert conf1.normalize_to_unity is True
        assert conf1.total_reflectivity_q_cutoff == 0.01
        assert conf1.global_stitching is False
        assert conf1.polynomial_stitching is False
        assert conf1.polynomial_stitching_degree == 3
        assert conf1.polynomial_stitching_points == 3
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
        assert conf1.q_binning_type_run == QBinningType.NONE
        assert conf1.q_binning_step_run == -0.02

        # set UI elements to non-default

        # global
        window_main.ui.q_binning_type_selector_global.setCurrentIndex(QBinningType.NORMAL)
        window_main.ui.q_rebin_spinbox_global.setValue(-0.01)
        window_main.ui.normalize_to_unity_checkbox.setChecked(False)
        window_main.ui.normalization_q_cutoff_spinbox.setValue(0.02)
        window_main.ui.global_fit_checkbox.setChecked(True)
        window_main.ui.polynomial_stitching_checkbox.setChecked(True)
        window_main.ui.polynomial_stitching_degree_spinbox.setValue(4)
        window_main.ui.polynomial_stitching_points_spinbox.setValue(5)
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
        window_main.ui.q_binning_type_selector_run.setCurrentIndex(QBinningType.NORMAL)
        window_main.ui.q_rebin_spinbox_run.setValue(0.045)

        window_main.file_handler.get_configuration_from_ui()  # to update configuration from UI

        # check that the current config has been updated for both global and per run
        conf1 = window_main.data_presenter.active_cross_section.configuration

        # Reflectivity Extraction (Global)
        assert conf1.q_binning_type_global == QBinningType.NORMAL
        assert conf1.q_binning_step_global == -0.01
        assert conf1.normalize_to_unity is False
        assert conf1.total_reflectivity_q_cutoff == 0.02
        assert conf1.global_stitching is True
        assert conf1.polynomial_stitching is True
        assert conf1.polynomial_stitching_degree == 4
        assert conf1.polynomial_stitching_points == 5
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
        assert conf1.q_binning_type_run == QBinningType.NORMAL
        assert conf1.q_binning_step_run == 0.045

        # change selected data and check that global variables are carried over but not the per run ones

        window_main.data_presenter.set_active_data_from_reduction_list(1)
        assert window_main.data_presenter.current_file == "filepath2"

        # check that the configuration is the default
        conf2 = window_main.data_presenter.active_cross_section.configuration

        # Reflectivity Extraction (Global)
        assert conf2.q_binning_type_global == QBinningType.NORMAL
        assert conf2.q_binning_step_global == -0.01
        assert conf2.normalize_to_unity is False
        assert conf2.total_reflectivity_q_cutoff == 0.02
        assert conf2.global_stitching is True
        assert conf2.polynomial_stitching is True
        assert conf2.polynomial_stitching_degree == 4
        assert conf2.polynomial_stitching_points == 5
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
        """Test that the add data tab buttons reveal/hide tabs as expected.

        This test checks that the addTabButton and removeTabButton work correctly,
        and that the add/remove buttons are disabled when the max/min number of tabs is reached
        """
        window_main = MainWindow()
        qtbot.addWidget(window_main)

        def _assert_tabs_visible(tab_ids: list[bool]):
            for idx, is_visible in enumerate(tab_ids):
                assert window_main.ui.tabWidget.isTabVisible(idx) == is_visible

        # Assert addTabButton enabled and removeTabButton disabled to start
        assert window_main.ui.addTabButton.isEnabled()
        assert not window_main.ui.removeTabButton.isEnabled()

        _assert_tabs_visible([True, True, False, False, False])

        # Test adding tabs
        window_main.ui.addTabButton.clicked.emit()
        _assert_tabs_visible([True, True, True, False, False])
        assert window_main.ui.removeTabButton.isEnabled()
        window_main.ui.addTabButton.clicked.emit()
        _assert_tabs_visible([True, True, True, True, False])
        window_main.ui.addTabButton.clicked.emit()
        _assert_tabs_visible([True, True, True, True, True])

        # Reached max number of tabs, assert add button is now disabled
        assert not window_main.ui.addTabButton.isEnabled()

        # Test removing tabs
        window_main.ui.removeTabButton.clicked.emit()
        _assert_tabs_visible([True, True, True, True, False])
        assert window_main.ui.addTabButton.isEnabled()
        window_main.ui.removeTabButton.clicked.emit()
        _assert_tabs_visible([True, True, True, False, False])
        window_main.ui.removeTabButton.clicked.emit()
        _assert_tabs_visible([True, True, False, False, False])
        assert not window_main.ui.removeTabButton.isEnabled()

    @pytest.mark.datarepo
    def test_change_active_data_tab(self, mocker, qtbot, data_server):
        """Test that the internal state is updated when the active data tab is changed."""
        mock_plot_refl = mocker.patch(
            "quicknxs.views.plotting.PlotView.plot_reflectivity_or_intensity", return_value=True
        )

        window_main = MainWindow()
        qtbot.addWidget(window_main)

        manager = window_main.data_presenter
        manager.load(data_server.path_to("REF_M_40782"), Configuration())
        manager.add_active_to_reduction()
        manager.load(data_server.path_to("REF_M_40785"), Configuration())
        manager.add_active_to_reduction()

        # add second peak tab
        window_main.ui.addTabButton.clicked.emit()
        assert mock_plot_refl.call_count == 0
        # switch to second peak tab
        window_main.ui.tabWidget.setCurrentIndex(2)
        assert window_main.data_presenter.active_reduction_list_index == 2
        assert mock_plot_refl.call_count == 1
        # switch to first peak tab
        window_main.ui.tabWidget.setCurrentIndex(1)
        assert window_main.data_presenter.active_reduction_list_index == 1
        assert mock_plot_refl.call_count == 2

    @pytest.mark.datarepo
    def test_reduction_table_propagate_run(self, qtbot, data_server):
        """Test right-click action 'Propagate run'."""
        Configuration.setup_default_values()
        window_main = MainWindow()
        qtbot.addWidget(window_main)

        # add direct beam run
        window_main.file_handler.open_file(data_server.path_to("REF_M_42099"))
        window_main.actionAddDirectBeam.triggered.emit()

        # add reflectivity run
        window_main.file_handler.open_file(data_server.path_to("REF_M_42113"))
        window_main.actionAddRefl.triggered.emit()

        # add second peak tab
        window_main.ui.addTabButton.clicked.emit()

        # add another run to the primary data table
        window_main.file_handler.open_file(data_server.path_to("REF_M_42112"))
        window_main.actionAddRefl.triggered.emit()

        reduction_lists = window_main.data_presenter.peak_reduction_lists
        assert len(reduction_lists[1]) == 2
        assert reduction_lists[1][0].number == "42112"
        assert reduction_lists[1][1].number == "42113"
        assert len(reduction_lists[2]) == 1
        assert reduction_lists[2][0].number == "42113"

        # add new run to the second peak tab using right-click action
        table = getattr(window_main.ui, "reductionTable")

        def handle_menu():
            """Trigger propagate run action and check that the run was added to the second tab."""
            menu = table.findChild(QtWidgets.QMenu)
            action = menu.actions()[1]
            assert action.text() == "Propagate run to all tabs"
            qtbot.keyClick(menu, QtCore.Qt.Key_Down)
            qtbot.keyClick(menu, QtCore.Qt.Key_Down)
            qtbot.keyClick(menu, QtCore.Qt.Key_Enter)
            assert len(window_main.data_presenter.peak_reduction_lists[1]) == 2
            assert len(window_main.data_presenter.peak_reduction_lists[2]) == 2

        QtCore.QTimer.singleShot(200, handle_menu)
        table_item = table.item(0, 0)  # new run on row index 0
        table_item_rect = table.visualItemRect(table_item)
        table.customContextMenuRequested.emit(table_item_rect.topLeft())

    @pytest.mark.skip(reason="Need to figure out how to simulate mouse position")
    @pytest.mark.datarepo
    def test_remove_run_from_tables(self, qtbot, data_server):
        """Test right-click action 'Remove run'."""

        def handle_menu(table):
            """Trigger remove run action."""
            menu = table.findChild(QtWidgets.QMenu)
            action = menu.actions()[2]
            assert action.text() == "Remove run from this tab"
            qtbot.keyClick(menu, QtCore.Qt.Key_Down)
            qtbot.keyClick(menu, QtCore.Qt.Key_Down)
            qtbot.keyClick(menu, QtCore.Qt.Key_Down)
            qtbot.keyClick(menu, QtCore.Qt.Key_Enter)

        Configuration.setup_default_values()
        window_main = MainWindow()
        qtbot.addWidget(window_main)

        # Add direct beam run
        window_main.file_handler.open_file(data_server.path_to("REF_M_42099"))
        window_main.actionAddDirectBeam.triggered.emit()

        # Add reflectivity run
        window_main.file_handler.open_file(data_server.path_to("REF_M_42113"))
        window_main.actionAddRefl.triggered.emit()

        ### Simulate right-click -> remove run

        table = window_main.ui.reductionTable
        assert table.rowCount() == 1
        QtCore.QTimer.singleShot(500, lambda: handle_menu(table))
        table_item = table.item(0, 0)  # new run on row index 0
        table_item_rect = table.visualItemRect(table_item)
        table.customContextMenuRequested.emit(table_item_rect.topLeft())

        # table = getattr(window_main.ui, "directBeamTable")
        table = window_main.ui.directBeamTable
        assert table.rowCount() == 1
        QtCore.QTimer.singleShot(500, lambda: handle_menu(table))
        table_item = table.item(0, 0)  # new run on row index 0
        table_item_rect = table.visualItemRect(table_item)
        table.customContextMenuRequested.emit(table_item_rect.topLeft())

        # check that the run was removed from the tables
        assert len(window_main.data_presenter.reduction_list) == 0
        assert len(window_main.data_presenter.direct_beam_list) == 0


class TestDisabledWidget:
    """Tests for the disabled_widget context manager."""

    def test_enabled_widget_reenabled(self, qtbot):
        """Test that an enabled widget is disabled inside the context and enabled after the context."""
        window_main = MainWindow()
        qtbot.addWidget(window_main)
        widget = window_main.ui.mainToolbar

        with disabled_widget(widget):
            assert not widget.isEnabled()

        assert widget.isEnabled()

    def test_disabled_widget_redisabled(self, qtbot):
        """Test that a disabled widget is still disabled after the context."""
        window_main = MainWindow()
        qtbot.addWidget(window_main)
        widget = window_main.ui.mainToolbar

        widget.setEnabled(False)
        with disabled_widget(widget):
            assert not widget.isEnabled()

        assert not widget.isEnabled()

    def test_disabled_widget_enabled_after_exception(self, qtbot):
        """Test that a widget is reenabled after an exception is raised inside the context."""
        window_main = MainWindow()
        qtbot.addWidget(window_main)
        widget = window_main.ui.mainToolbar

        with pytest.raises(ValueError):
            with disabled_widget(widget):
                assert not widget.isEnabled()
                raise ValueError("bad value")

        assert widget.isEnabled()

    def test_nested_contexts(self, qtbot):
        """Test that nested contexts work as expected."""
        window_main = MainWindow()
        qtbot.addWidget(window_main)
        widget = window_main.ui.mainToolbar

        with disabled_widget(widget):
            assert not widget.isEnabled()
            with disabled_widget(widget):
                assert not widget.isEnabled()
            assert not widget.isEnabled()

        assert widget.isEnabled()


if __name__ == "__main__":
    pytest.main([__file__])
