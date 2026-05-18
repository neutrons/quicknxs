import numpy as np
import pytest

from quicknxs.models.configuration import Configuration
from quicknxs.views.main_window import MainWindow
from tests.ui import ui_utilities

TEST_REFLECTIVITY_THRESHOLD_VALUE = 0.01


@pytest.mark.datarepo
def test_missing_cross_section(qtbot):
    """Missing cross section test.

    Test a run where the crossection corresponding to the On-On spin combination has no integrated
    proton charge. The application produces the intensity curve with counts < 1 for all On-On tof.
    """
    Configuration.setup_default_values()
    main_window = MainWindow()
    qtbot.addWidget(main_window)
    # load the run and find the total "intensity" of the x vs TOF plot
    ui_utilities.setText(main_window.numberSearchEntry, "42100", press_enter=True)
    intensity_off_on = np.sum(ui_utilities.data_from_plot2D(main_window.xtof_overview))
    # select the On-On spin combination
    main_window.selectedCrossSection1.click()
    # check that counts is < 1 for entire tof
    assert np.max(ui_utilities.data_from_plot1D(main_window.refl)[1]) < 1
    # check the x vs TOF plot has changed
    intensity_on_on = np.sum(ui_utilities.data_from_plot2D(main_window.xtof_overview))
    assert intensity_on_on / intensity_off_on < TEST_REFLECTIVITY_THRESHOLD_VALUE


if __name__ == "__main__":
    pytest.main([__file__])
