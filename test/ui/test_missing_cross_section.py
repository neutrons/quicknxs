# local imports
# third party imports
import numpy as np
import pytest

from quicknxs.interfaces.configuration import Configuration
from quicknxs.interfaces.main_window import MainWindow
from test.ui import ui_utilities

# standard library imports

TEST_REFLECTIVITY_THRESHOLD_VALUE = 0.01


@pytest.mark.datarepo
def test_missing_cross_section(qtbot):
    r"""Test a run where the crossection corresponding to the On-On spin combination has no integrated
    proton charge. The application produces and empty reflectivity curve for On-On."""
    Configuration.setup_default_values()
    main_window = MainWindow()
    qtbot.addWidget(main_window)
    # load the run and find the total "intensity" of the x vs TOF plot
    ui_utilities.setText(main_window.numberSearchEntry, "42100", press_enter=True)
    intensity_off_on = np.sum(ui_utilities.data_from_plot2D(main_window.xtof_overview))
    # select the On-On spin combination
    main_window.selectedChannel1.click()
    # check that no reflectivity curve is displayed
    plot_text = ui_utilities.text_from_plot1D(main_window.refl)
    assert plot_text == "No data"
    # check the x vs TOF plot has changed
    intensity_on_on = np.sum(ui_utilities.data_from_plot2D(main_window.xtof_overview))
    assert intensity_on_on / intensity_off_on < TEST_REFLECTIVITY_THRESHOLD_VALUE


if __name__ == "__main__":
    pytest.main([__file__])
