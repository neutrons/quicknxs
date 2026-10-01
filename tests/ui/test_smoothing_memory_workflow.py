"""End to end test of the defect report steps through the main window.

The reduction is mocked, only the parameters it receives are checked.
"""

import pytest
from qtpy import QtCore, QtWidgets

from quicknxs.enums import OffSpecXAxis
from quicknxs.models.configuration import Configuration
from quicknxs.views.main_window import MainWindow
from quicknxs.views.reduction_dialog import ReductionDialog
from quicknxs.views.smooth_dialog import OffSpecParametersDialog

POLL_MS = 50
MAX_POLLS = 200  # 10 s


def _when_modal(dialog_type, action, observed, max_polls=MAX_POLLS):
    """Run `action` on a modal dialog once it's open and drawn.

    The dialog is always closed so the test can't hang in exec_. Errors are recorded in
    `observed` because exceptions in a timer callback don't fail the test.
    """

    def _poll(remaining):
        dialog = QtWidgets.QApplication.activeModalWidget()
        ready = isinstance(dialog, dialog_type) and getattr(dialog, "_plot_runs", True) is not None
        if not ready:
            if remaining > 0:
                QtCore.QTimer.singleShot(POLL_MS, lambda: _poll(remaining - 1))
            else:
                observed.setdefault("errors", []).append(f"{dialog_type.__name__} never became ready")
                if dialog is not None:
                    dialog.reject()
            return
        try:
            action(dialog)
        except Exception as error:
            observed.setdefault("errors", []).append(f"{dialog_type.__name__}: {error!r}")
            dialog.reject()

    QtCore.QTimer.singleShot(POLL_MS, lambda: _poll(max_polls))


def _press_reduce(main_window, smoothing_action, observed):
    """Press Reduce with only smoothing ticked and run `smoothing_action` on the smoothing dialog."""

    def _reduction_options(dialog):
        for name in ("exportSpecular", "export_SA", "exportGISANS", "exportOffSpecular", "exportOffSpecularSlices"):
            getattr(dialog.ui, name).setChecked(False)
        dialog.ui.intensitySmoothingCheckbox.setChecked(True)
        _when_modal(OffSpecParametersDialog, smoothing_action, observed)
        dialog.accept()

    _when_modal(ReductionDialog, _reduction_options, observed)
    main_window.reduceDatasets()


@pytest.mark.datarepo
def test_smoothing_settings_survive_switching_output_type_and_reopening(qtbot, mocker, data_server, tmp_path):
    Configuration.setup_default_values()
    # Don't point the output directory at the home directory
    QtCore.QSettings(".quicknxs").setValue("output_directory", str(tmp_path))
    workflow = mocker.patch("quicknxs.views.main_window.ProcessingWorkflow")

    main_window = MainWindow()
    qtbot.addWidget(main_window)
    main_window.file_handler.open_file(data_server.path_to("REF_M_42112"))
    main_window.actionAddRefl.triggered.emit()
    observed = {}
    chosen = 0.0012

    def _first_visit(dialog):
        observed["opened_on_default_view"] = dialog.ui.kizmkfzVSqz.isChecked()
        dialog.ui.sigmaX.setValue(chosen)
        dialog.ui.qxVSqz.setChecked(True)
        observed["qx_radius"] = dialog.ui.sigmaX.value()
        dialog.ui.kizmkfzVSqz.setChecked(True)
        observed["radius_after_coming_back"] = dialog.ui.sigmaX.value()
        dialog.accept()

    _press_reduce(main_window, _first_visit, observed)

    def _second_visit(dialog):
        observed["reopened_on_default_view"] = dialog.ui.kizmkfzVSqz.isChecked()
        observed["radius_on_reopening"] = dialog.ui.sigmaX.value()
        dialog.reject()

    _press_reduce(main_window, _second_visit, observed)

    assert observed.get("errors") is None, observed.get("errors")

    # The defect: switching output type lost the user's values
    assert observed["opened_on_default_view"]
    assert observed["qx_radius"] != chosen, "the radius should be rescaled to the Qx box"
    assert observed["radius_after_coming_back"] == chosen

    # The reduction got the values left in the dialog
    assert workflow.call_count == 1, "the second visit was cancelled, so only one reduction ran"
    output_options = workflow.call_args.args[1]
    assert output_options.apply_smoothing
    assert output_options.off_spec_x_axis == OffSpecXAxis.DELTA_KZ_VS_QZ
    assert output_options.off_spec_sigmax == chosen

    # Remembered for the session, still opening on the default view
    assert observed["reopened_on_default_view"]
    assert observed["radius_on_reopening"] == chosen
