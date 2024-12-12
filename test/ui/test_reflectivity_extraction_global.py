# local imports
from reflectivity_ui.interfaces.configuration import Configuration
from reflectivity_ui.interfaces.data_handling.data_set import NexusData, CrossSectionData
from reflectivity_ui.interfaces.main_window import MainWindow
from test.ui import ui_utilities


# third party imports
import pytest

# standard library imports


def _initialize_test_data(main_window):
    """Add one run with two cross-sections to the data manager"""
    config = Configuration()
    nexus_data = NexusData("file/path", config)
    off_off = CrossSectionData("Off_Off", config)
    on_off = CrossSectionData("On_Off", config)
    nexus_data.cross_sections["Off_Off"] = off_off
    nexus_data.cross_sections["On_Off"] = on_off
    main_window.data_manager._nexus_data = nexus_data
    main_window.data_manager.set_channel(0)
    main_window.data_manager.add_active_to_reduction()


def _assert_configuration_value(main_window, param_name, gold_value):
    """Check parameter value through the data hierarchy"""
    assert getattr(main_window.data_manager.active_channel.configuration, param_name) is gold_value
    for nexus_data in main_window.data_manager.reduction_list:
        assert getattr(nexus_data.configuration, param_name) is gold_value
        for xs_data in nexus_data.cross_sections.values():
            assert getattr(xs_data.configuration, param_name) is gold_value


def _assert_configuration_float_value(main_window, param_name, gold_value):
    """Check float parameter value through the data hierarchy"""
    assert getattr(main_window.data_manager.active_channel.configuration, param_name) == pytest.approx(gold_value)
    for nexus_data in main_window.data_manager.reduction_list:
        assert getattr(nexus_data.configuration, param_name) == pytest.approx(gold_value)
        for xs_data in nexus_data.cross_sections.values():
            assert getattr(xs_data.configuration, param_name) == pytest.approx(gold_value)


@pytest.mark.parametrize(
    "widget, config_param",
    [
        ("final_rebin_checkbox", "do_final_rebin"),
        ("normalize_to_unity_checkbox", "normalize_to_unity"),
        ("global_fit_checkbox", "global_stitching"),
        ("polynomial_stitching_checkbox", "polynomial_stitching"),
        ("fanReflectivity", "use_constant_q"),
        ("direct_beam_y_lock_checkbox", "lock_direct_beam_y"),
    ],
)
def test_global_checkboxes(qtbot, widget, config_param):
    """Test that UI global config checkbox changes get propagated to all configuration levels"""
    main_window = MainWindow()
    qtbot.addWidget(main_window)
    _initialize_test_data(main_window)

    getattr(main_window.ui, widget).setChecked(True)
    _assert_configuration_value(main_window, config_param, True)

    getattr(main_window.ui, widget).setChecked(False)
    _assert_configuration_value(main_window, config_param, False)


@pytest.mark.parametrize(
    "widget, config_param, gold_value",
    [
        ("q_rebin_spinbox", "final_rebin_step", 0.01),
        ("normalization_q_cutoff_spinbox", "total_reflectivity_q_cutoff", 0.02),
        ("polynomial_stitching_degree_spinbox", "polynomial_stitching_degree", 2),
        ("polynomial_stitching_points_spinbox", "polynomial_stitching_points", 5),
        ("sample_size_spinbox", "sample_size", 15.0),
        ("bandwidth_spinbox", "wl_bandwidth", 2.5),
    ],
)
def test_global_spinboxes(qtbot, widget, config_param, gold_value):
    """Test that UI global config spinbox changes get propagated to all configuration levels"""
    main_window = MainWindow()
    qtbot.addWidget(main_window)
    _initialize_test_data(main_window)

    qwidget = getattr(main_window.ui, widget)
    ui_utilities.setValue(qwidget, gold_value)
    _assert_configuration_float_value(main_window, config_param, gold_value)


@pytest.mark.datarepo
def test_reflectivity_recalculated_on_config_change(mocker, qtbot):
    """Test that changing global binning configuration triggers recalculating reflectivity for all runs"""
    main_window = MainWindow()
    qtbot.addWidget(main_window)

    # use mock and wrap to call function while also getting call count
    data_manager = main_window.data_manager
    mock_calculate_reflectivity = mocker.patch.object(
        data_manager, "calculate_reflectivity", wraps=data_manager.calculate_reflectivity
    )

    # add two runs to the reduction table
    ui_utilities.setText(main_window.numberSearchEntry, str(40785), press_enter=True)
    ui_utilities.set_current_file_by_run_number(main_window, 40785)
    main_window.actionAddPlot.triggered.emit()
    assert mock_calculate_reflectivity.call_count == 1
    ui_utilities.set_current_file_by_run_number(main_window, 40782)
    main_window.actionAddPlot.triggered.emit()
    assert mock_calculate_reflectivity.call_count == 2

    # add a data tab - it is automatically initialized with the two runs from the first data tab
    main_window.addDataTable()
    nbr_data_tabs = main_window.data_tab_count
    assert nbr_data_tabs == 2

    # check that all reflectivity curves are recalculated when global binning configuration is changed

    num_runs = 2 * nbr_data_tabs

    # test toggling `fanReflectivity`
    prev_call_count = mock_calculate_reflectivity.call_count
    main_window.ui.fanReflectivity.nextCheckState()
    assert mock_calculate_reflectivity.call_count == prev_call_count + num_runs

    # test toggling `final_rebin_checkbox`
    prev_call_count = mock_calculate_reflectivity.call_count
    main_window.ui.final_rebin_checkbox.nextCheckState()
    assert mock_calculate_reflectivity.call_count == prev_call_count + num_runs

    # test editing `q_rebin_spinbox`
    prev_call_count = mock_calculate_reflectivity.call_count
    q_spinbox = main_window.ui.q_rebin_spinbox
    q_delta = q_spinbox.singleStep() if q_spinbox.value() < 0 else -q_spinbox.singleStep()
    ui_utilities.setValue(q_spinbox, q_spinbox.value() + q_delta, editing_finished=True)
    assert mock_calculate_reflectivity.call_count == prev_call_count + num_runs
