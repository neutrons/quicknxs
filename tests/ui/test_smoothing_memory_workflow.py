"""End to end: the steps from the defect report, driven through the real main window.

Load a run, add it to the Data table, press Reduce, tick "Off-Specular Intensity Smoothing",
change the smoothing radius, switch output type and back, press OK, then press Reduce again.
The reduction itself is mocked; only the parameters it receives are checked here.
"""

import pytest
from qtpy import QtCore, QtWidgets

from quicknxs.enums import OffSpecXAxis
from quicknxs.models.configuration import Configuration
from quicknxs.views.main_window import MainWindow
from quicknxs.views.reduction_dialog import ReductionDialog
from quicknxs.views.smooth_dialog import OffSpecParametersDialog

POLL_MS = 50
MAX_POLLS = 200  # ten seconds before giving up and closing whatever is open


def _when_modal(dialog_type, action, observed, max_polls=MAX_POLLS):
    """Run `action` on the modal dialog of `dialog_type` once it is open and has drawn.

    Modal dialogs block in exec_, so the test acts on them from a timer. The action always
    ends by closing the dialog, and a dialog that never shows up is closed anyway, so a
    failing step cannot leave the test hanging in exec_. Errors are recorded rather than
    raised, because an exception inside a timer callback does not fail the test.
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
        except Exception as error:  # recorded and asserted on after exec_ returns
            observed.setdefault("errors", []).append(f"{dialog_type.__name__}: {error!r}")
            dialog.reject()

    QtCore.QTimer.singleShot(POLL_MS, lambda: _poll(max_polls))


def _press_reduce(main_window, smoothing_action, observed):
    """Press Reduce, tick only the smoothing output, then hand the smoothing dialog to the action."""

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
    # Keep the reduction dialog's output directory away from the user's home directory
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

    # The defect: switching output type used to throw away what the user entered
    assert observed["opened_on_default_view"]
    assert observed["qx_radius"] != chosen, "the radius should be rescaled to the Qx box"
    assert observed["radius_after_coming_back"] == chosen

    # The reduction received what the user left in the dialog
    assert workflow.call_count == 1, "the second visit was cancelled, so only one reduction ran"
    output_options = workflow.call_args.args[1]
    assert output_options.apply_smoothing
    assert output_options.off_spec_x_axis == OffSpecXAxis.DELTA_KZ_VS_QZ
    assert output_options.off_spec_sigmax == chosen

    # Remembered for the rest of the session, and still opening on the default view
    assert observed["reopened_on_default_view"]
    assert observed["radius_on_reopening"] == chosen
