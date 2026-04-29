from unittest import mock

import pytest

from quicknxs.views.main_window import MainWindow


def test_metadata_roi_updates_ui(data_server, qtbot):
    main_window = MainWindow()
    qtbot.addWidget(main_window)

    # add direct beam run
    main_window.file_handler.open_file(data_server.path_to("REF_M_42099"))
    main_window.actionAddDirectBeam.triggered.emit()

    config = main_window.file_handler.get_configuration_from_ui()

    assert main_window.ui.roi_peak_value.text() == str(config.metadata_roi_peak)
    assert main_window.ui.roi_bck_value.text() == str(config.metadata_roi_bck)


def test_metadata_roi_disables_peak_finder(qtbot):
    """Test that the metadata ROI option disables the peak finder buttons."""
    main_window = MainWindow()
    qtbot.addWidget(main_window)

    metadata_roi_checkbox = main_window.ui.use_roi_checkbox
    metadata_roi_checkbox.setChecked(True)
    assert main_window.ui.actionAutoXROI.isEnabled() is False
    assert main_window.ui.actionAutoYROI.isEnabled() is False

    metadata_roi_checkbox.setChecked(False)
    assert main_window.ui.actionAutoXROI.isEnabled() is True
    assert main_window.ui.actionAutoYROI.isEnabled() is True


def test_peak_finder_settings_persist(data_server, qtbot):
    def _assert_peak_finder_config():
        """Assert that the peak finder config is as expected."""
        config = main_window.file_handler.get_configuration_from_ui()
        assert config.use_roi is False
        assert config.use_metadata_bck_roi is True
        assert config.update_peak_range is True
        assert config.use_tight_bck is True
        assert config.bck_offset == 10

    def _assert_peak_finder_settings():
        """Assert that the peak finder settings are as expected."""
        assert main_window.ui.use_roi_checkbox.isChecked() is False
        assert main_window.ui.use_bck_roi_checkbox.isChecked() is True
        assert main_window.ui.fit_within_roi_checkbox.isChecked() is True
        assert main_window.ui.use_side_bck_checkbox.isChecked() is True
        assert main_window.ui.side_bck_width.value() == 10

    main_window = MainWindow()
    qtbot.addWidget(main_window)

    # Change peak finder settings
    main_window.ui.use_roi_checkbox.setChecked(False)
    main_window.ui.use_bck_roi_checkbox.setChecked(True)
    main_window.ui.fit_within_roi_checkbox.setChecked(True)
    main_window.ui.use_side_bck_checkbox.setChecked(True)
    main_window.ui.side_bck_width.setValue(10)

    _assert_peak_finder_config()

    # Load a reduced data file
    data_file = data_server.path_to(
        # "REF_M_42536+42537_peak1_Specular_Off_Off.dat"
        "REF_M_test_file.dat"
    )
    with mock.patch("qtpy.QtWidgets.QFileDialog.getOpenFileName") as mock_get_file:
        mock_get_file.return_value = (data_file, "")
        main_window.file_handler.open_reduced_file_dialog()

    _assert_peak_finder_settings()

    # Select a different run
    main_window.set_active_reduction_data(True, 1)
    _assert_peak_finder_settings()
    _assert_peak_finder_config()


if __name__ == "__main__":
    pytest.main([__file__])
