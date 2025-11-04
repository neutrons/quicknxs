import pytest

from quicknxs.config.gui import QColors
from quicknxs.interfaces.configuration import BinningType
from quicknxs.interfaces.enums import ReductionTableColumn
from quicknxs.interfaces.main_window import MainWindow
from test.ui import ui_utilities


def _populate_reduction_and_direct_beam_tables(main_window, final_rebin_enabled=False):
    # load file list
    ui_utilities.setText(main_window.numberSearchEntry, str(42100), press_enter=True)

    # select run in the file list
    ui_utilities.set_current_file_by_run_number(main_window, 42100)
    # add run to direct beams
    main_window.actionAddDirectBeam.triggered.emit()

    ui_utilities.set_current_file_by_run_number(main_window, 42112)
    main_window.actionAddRefl.triggered.emit()

    ui_utilities.set_current_file_by_run_number(main_window, 42113)
    main_window.actionAddRefl.triggered.emit()

    if final_rebin_enabled:
        main_window.ui.binning_type_selector_global.setCurrentIndex(1)
        main_window.ui.q_rebin_spinbox_global.setValue(-0.010)
        main_window.ui.propagate_binning_options_button.click()
    # set the first data run to active
    main_window.set_active_reduction_data(True, 0)


def test_clicking_apply_binning_button_updates_reduction_table(qtbot):
    """Test that the button to apply binning options globally updates the reduction table"""
    main_window = MainWindow()
    qtbot.addWidget(main_window)
    reduction_table1 = main_window.ui.reductionTable
    reduction_table2 = main_window.ui.reductionTable2

    _populate_reduction_and_direct_beam_tables(main_window, final_rebin_enabled=False)

    # Add a data tab - it is automatically initialized with the two runs from the first data tab
    main_window.addDataTable()

    # Change the "global" binning options and click the button "Apply to all runs"
    main_window.ui.binning_type_selector_global.setCurrentIndex(1)
    main_window.ui.q_rebin_spinbox_global.setValue(-0.010)
    main_window.ui.propagate_binning_options_button.click()

    # Verify that the reduction table was updated
    assert reduction_table1.cellWidget(0, ReductionTableColumn.BINNING_TYPE).currentIndex() == BinningType.NORMAL
    assert reduction_table1.cellWidget(1, ReductionTableColumn.BINNING_TYPE).currentIndex() == BinningType.NORMAL
    assert reduction_table1.item(0, ReductionTableColumn.Q_STEPS).text() == "-0.010"
    assert reduction_table1.item(1, ReductionTableColumn.Q_STEPS).text() == "-0.010"

    # Verify that the active run panel was updated
    assert main_window.ui.binning_type_selector_run.currentIndex() == BinningType.NORMAL
    assert main_window.ui.q_rebin_spinbox_run.value() == -0.010

    # Switch to the second data tab
    main_window.ui.tabWidget.setCurrentIndex(2)

    # Verify that the options were not applied to the second data tab
    assert reduction_table2.cellWidget(0, ReductionTableColumn.BINNING_TYPE).currentIndex() == BinningType.NONE
    assert reduction_table2.cellWidget(1, ReductionTableColumn.BINNING_TYPE).currentIndex() == BinningType.NONE
    assert reduction_table2.item(0, ReductionTableColumn.Q_STEPS).text() == "-0.020"
    assert reduction_table2.item(1, ReductionTableColumn.Q_STEPS).text() == "-0.020"
    assert main_window.ui.binning_type_selector_run.currentIndex() == BinningType.NONE
    assert main_window.ui.q_rebin_spinbox_run.value() == -0.020


def test_editing_run_rebin_spinbox_updates_reduction_table(qtbot):
    """Test that editing the run rebin Q-step spinbox updates the reduction table and vice versa."""

    main_window = MainWindow()
    qtbot.addWidget(main_window)
    reduction_table = main_window.ui.reductionTable
    q_spinbox = main_window.ui.q_rebin_spinbox_run

    _populate_reduction_and_direct_beam_tables(main_window, final_rebin_enabled=False)

    assert q_spinbox.value() == -0.020
    assert reduction_table.item(0, ReductionTableColumn.Q_STEPS).text() == "-0.020"
    assert reduction_table.item(1, ReductionTableColumn.Q_STEPS).text() == "-0.020"

    # Spinbox update
    ui_utilities.setValue(q_spinbox, q_spinbox.value() + q_spinbox.singleStep(), editing_finished=True)

    # Verify that the table was updated. The first row is the "active" run that should have been updated
    assert q_spinbox.value() == -0.019
    assert reduction_table.item(0, ReductionTableColumn.Q_STEPS).text() == "-0.019"
    assert reduction_table.item(1, ReductionTableColumn.Q_STEPS).text() == "-0.020"

    # Reduction table update
    ui_utilities.setText(reduction_table.item(0, ReductionTableColumn.Q_STEPS), "-0.018", press_enter=False)

    # Verify that the spinbox was updated
    assert q_spinbox.value() == -0.018
    assert reduction_table.item(0, ReductionTableColumn.Q_STEPS).text() == "-0.018"
    assert reduction_table.item(1, ReductionTableColumn.Q_STEPS).text() == "-0.020"


def test_editing_run_binning_type_updates_reduction_table(qtbot):
    """Test that editing the run binning type selection updates the reduction table and vice versa."""
    main_window = MainWindow()
    qtbot.addWidget(main_window)
    reduction_table = main_window.ui.reductionTable
    bin_type_combobox = main_window.ui.binning_type_selector_run

    _populate_reduction_and_direct_beam_tables(main_window, final_rebin_enabled=False)

    assert bin_type_combobox.currentIndex() == BinningType.NONE
    assert reduction_table.cellWidget(0, ReductionTableColumn.BINNING_TYPE).currentIndex() == BinningType.NONE

    # Update bin type in combobox in panel Reflectivity Extraction (Per Run)
    bin_type_combobox.setCurrentIndex(BinningType.NORMAL)

    # Verify that the table was updated. The first row is the "active" run that should have been updated
    assert reduction_table.cellWidget(0, ReductionTableColumn.BINNING_TYPE).currentIndex() == BinningType.NORMAL

    # Update bin type in reduction table column
    reduction_table.cellWidget(0, ReductionTableColumn.BINNING_TYPE).setCurrentIndex(BinningType.CONST_Q)

    # Verify that the combobox in the run panel was updated
    assert bin_type_combobox.currentIndex() == BinningType.CONST_Q


def test_editing_rebin_q_step_triggers_replotting(qtbot, mocker):
    """
    Test that editing the run Q-step spinbox value triggers replotting.

    This test verifies that when the Q-step spinbox value is edited,
    the reflectivity plot is redrawn. It uses a mock to track the call count of the plot
    redraw method and checks that it increments upon editing the spinbox value.
    """
    mock_plot_refl = mocker.patch(
        "quicknxs.interfaces.plotting.PlotManager.plot_reflectivity_or_intensity", return_value=True
    )

    main_window = MainWindow()
    qtbot.addWidget(main_window)

    _populate_reduction_and_direct_beam_tables(main_window)

    # Get call count before editing the Q-step configuration
    plot_refl_call_count = mock_plot_refl.call_count

    # Simulate editing the run final rebin spinbox
    q_step_spinbox = main_window.ui.q_rebin_spinbox_run
    ui_utilities.setValue(q_step_spinbox, q_step_spinbox.value() + q_step_spinbox.singleStep(), editing_finished=True)

    # Verify that the plot is redrawn
    assert mock_plot_refl.call_count == plot_refl_call_count + 1


def test_changing_binning_type_triggers_replotting(qtbot, mocker):
    """
    Test that changing the binning type triggers replotting.

    This test verifies that when the binning type is changed,
    the reflectivity plot is redrawn. It uses a mock to track the call count of the plot
    redraw method and checks that it increments upon editing the spinbox value.
    """
    mock_plot_refl = mocker.patch(
        "quicknxs.interfaces.plotting.PlotManager.plot_reflectivity_or_intensity", return_value=True
    )

    main_window = MainWindow()
    qtbot.addWidget(main_window)

    _populate_reduction_and_direct_beam_tables(main_window)

    # Get call count before
    plot_refl_call_count = mock_plot_refl.call_count

    # Simulate changing the binning type
    binning_type_combobox = main_window.ui.binning_type_selector_run
    binning_type_combobox.setCurrentIndex(1)

    # Verify that the plot is redrawn
    assert mock_plot_refl.call_count == plot_refl_call_count + 1


@pytest.mark.parametrize(
    "binning_type, foreground",
    [
        (BinningType.NONE, QColors.dark_grey),
        (BinningType.CONST_Q, QColors.black),
    ],
)
def test_setting_binning_type_none_disables_q_steps(qtbot, binning_type, foreground):
    """Test that the Q steps table entry is greyed out when the binning type is set to None."""
    main_window = MainWindow()
    qtbot.addWidget(main_window)
    reduction_table = main_window.ui.reductionTable

    _populate_reduction_and_direct_beam_tables(main_window, final_rebin_enabled=True)

    # Test that Q steps cell color is updated when changing binning type for the *active* run
    reduction_table.cellWidget(0, ReductionTableColumn.BINNING_TYPE).setCurrentIndex(binning_type)
    assert reduction_table.item(0, ReductionTableColumn.Q_STEPS).foreground().color() == foreground

    # Test that Q steps cell color is updated when changing binning type for the *non-active* run
    reduction_table.cellWidget(1, ReductionTableColumn.BINNING_TYPE).setCurrentIndex(binning_type)
    assert reduction_table.item(1, ReductionTableColumn.Q_STEPS).foreground().color() == foreground
