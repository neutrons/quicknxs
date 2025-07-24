from copy import deepcopy

import pytest

from quicknxs.interfaces.configuration import Configuration
from quicknxs.interfaces.data_handling.quicknxs_io import read_reduced_file
from quicknxs.interfaces.main_window import MainWindow


def assert_config_equal(conf_a, conf_b):
    """Assert that two Configuration objects are equal."""
    for key in sorted(conf_a.__dict__):
        if key in ["instrument", "match_direct_beam", "tof_range"]:
            continue
        val_a = getattr(conf_a, key)
        val_b = getattr(conf_b, key)
        print(f"Comparing {key}: {val_a} vs {val_b}")
        if key == "scaling_factor":
            assert round(val_a, 2) == round(val_b, 2)
        else:
            assert val_a == val_b, f"Config mismatch on '{key}':\n  Expected: {val_b!r}\n  Got:      {val_a!r}"


@pytest.mark.parametrize(
    "filename", ["REF_M_42536+42537_peak1_Specular_On_Off.dat", "REF_M_42536+42537_peak1_Specular_Off_Off.dat"]
)
def test_reduced_file_matches_gui_config(filename, data_server, qtbot):
    file_path = data_server.path_to(filename)
    print(f"File path: {file_path}")

    # Load the file via the GUI pipeline
    main_window = MainWindow()
    qtbot.addWidget(main_window)
    config = deepcopy(Configuration())
    Configuration.force_bck_roi = False

    main_window.auto_change_active = True

    main_window.data_manager.load_data_from_reduced_file(file_path, configuration=config)
    if main_window.data_manager.active_cross_section is not None:
        main_window.file_handler.populate_from_configuration(
            main_window.data_manager.active_cross_section.configuration
        )
        main_window.file_handler.update_file_list(main_window.data_manager.current_file)
        main_window.auto_change_active = False
    gui_conf = main_window.file_handler.get_configuration()

    # Load the expected config directly from the reduced file
    _, data, _, _ = read_reduced_file(file_path)
    file_conf = data[1][2]

    assert_config_equal(gui_conf, file_conf)
    main_window.auto_change_active = False


if __name__ == "__main__":
    pytest.main()
