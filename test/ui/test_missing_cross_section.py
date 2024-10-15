# local imports
from reflectivity_ui.interfaces.configuration import Configuration
from reflectivity_ui.interfaces.main_window import MainWindow
from test.ui import ui_utilities

# third party imports
import numpy as np
import pytest

# standard library imports

TEST_REFLECTIVITY_THRESHOLD_VALUE = 0.01


@pytest.mark.skip("Test fails in the CI pipeline, see EWM 7743")
@pytest.mark.datarepo
def test_missing_cross_section(qtbot):
    r"""Test a run where the crossection corresponding to the On-On spin combination has no integrated
    proton charge. The application produces and empty reflectivity curve for On-On."""
    main_window = MainWindow()
    qtbot.addWidget(main_window)
    Configuration.setup_default_values()
    # load the run and find the total "intensity" of the x vs TOF plot
    ui_utilities.setText(main_window.numberSearchEntry, "42100", press_enter=True)
    intensity_off_on = np.sum(ui_utilities.data_from_plot2D(main_window.xtof_overview))
    # select the On-On spin combination
    main_window.selectedChannel1.click()
    # check that the reflectivity curve is empty
    _, data_y = ui_utilities.data_from_plot1D(main_window.refl)
    test = data_y.data - data_y.data[0]
    assert np.all(test <= TEST_REFLECTIVITY_THRESHOLD_VALUE)
    tmp = ui_utilities.data_from_plot2D(main_window.xtof_overview)
    # check the x vs TOF plot has changed
    intensity_on_on = np.sum(ui_utilities.data_from_plot2D(main_window.xtof_overview))
    assert intensity_on_on / intensity_off_on < TEST_REFLECTIVITY_THRESHOLD_VALUE


if __name__ == "__main__":
    pytest.main([__file__])
