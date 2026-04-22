import pytest
from qtpy import QtWidgets

from quicknxs.interfaces.data_handling.quicknxs_io import read_reduced_file
from quicknxs.interfaces.main_window import MainWindow


def assert_config_equal(conf_a, conf_b):
    """Assert that two Configuration objects are equal."""
    for key in sorted(conf_a.__dict__):
        if key in ["instrument", "match_direct_beam", "tof_range"]:
            continue
        if key == "final_rebin_step_run" and not conf_a.do_final_rebin_run:
            continue
        if key == "direct_pixel_overwrite":
            # TODO: The direct_pixel_overwrite should be compared to the peak_position of the direct beam it's matched to. (Glass)
            continue
        val_a = getattr(conf_a, key)
        val_b = getattr(conf_b, key)
        print(f"Comparing {key}: {val_a} vs {val_b}")
        if key == "scaling_factor":
            assert round(val_a, 2) == round(val_b, 2)
        else:
            assert val_a == val_b, f"Config mismatch on '{key}':\n  GUI conf:  {val_a!r}\n  File conf: {val_b!r}"


@pytest.mark.parametrize(
    "filename", ["REF_M_42536+42537_peak1_Specular_On_Off.dat", "REF_M_42536+42537_peak1_Specular_Off_Off.dat"]
)
def test_reduced_file_matches_gui_config(filename, data_server, qtbot, monkeypatch):
    file_path = data_server.path_to(filename)

    # Load the file via the GUI pipeline
    main_window = MainWindow()
    qtbot.addWidget(main_window)

    monkeypatch.setattr(QtWidgets.QFileDialog, "getOpenFileName", lambda *args, **kwargs: (file_path, None))  # noqa: ARG005

    main_window.file_handler.open_reduced_file_dialog()

    gui_conf = main_window.file_handler.get_configuration_from_ui()

    # Load the expected config directly from the reduced file
    _, data, _, _ = read_reduced_file(file_path)
    file_conf = data[0][2]

    assert_config_equal(gui_conf, file_conf)
    main_window.auto_change_active = False


# TODO (GLASS): Add test for loading db as ref run reduced data file
def test_db_as_ref_run_reduced_file(data_server, qtbot, monkeypatch):
    filename = "db_as_ref_REF_M_42099+42100_peak1_Specular_Off_On.dat"
    file_path = data_server.path_to(filename)

    # Load the file via the GUI pipeline
    main_window = MainWindow()
    qtbot.addWidget(main_window)

    monkeypatch.setattr(QtWidgets.QFileDialog, "getOpenFileName", lambda *args, **kwargs: (file_path, None))  # noqa: ARG005

    main_window.file_handler.open_reduced_file_dialog()

    nexus_data = main_window.data_manager._nexus_data
    for xs in nexus_data.cross_sections:
        name = nexus_data.cross_sections[xs]._event_workspace
        assert name.endswith("_REFLECTED"), f"Expected workspace name to end with '_REFLECTED', got '{name}'"

    # Switch to direct beam tab and check that direct beam workspace is correctly named
    main_window.current_table_changed(0)
    nexus_data = main_window.data_manager._nexus_data
    for xs in nexus_data.cross_sections:
        name = nexus_data.cross_sections[xs]._event_workspace
        assert name.endswith("_DIRECT_BEAM"), f"Expected workspace name to end with '_DIRECT_BEAM', got '{name}'"


if __name__ == "__main__":
    pytest.main()
