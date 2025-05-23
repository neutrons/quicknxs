import pytest
from qtpy import QtWidgets

from quicknxs.interfaces.configuration import Configuration
from quicknxs.interfaces.main_window import MainWindow


@pytest.mark.datarepo
def test_direct_beam_table(qtbot, data_server):
    """Test that the direct beam table is connected to other UI elements.

    The table content should change when elements elsewhere are changed,
    and vice-versa (such as peak_position and peak_width).

    TODO: This test should also check that the table and overview plot limits are connected, if possible.
    """
    main_window = MainWindow()
    qtbot.addWidget(main_window)
    Configuration.setup_default_values()

    # Load direct beam run and add to the table
    main_window.file_handler.open_file(data_server.path_to("REF_M_42099"))
    main_window.actionAddDirectBeam.triggered.emit()

    # Get the direct beam table
    table: QtWidgets.QTableWidget = main_window.ui.directBeamTable
    assert table is not None
    assert table.rowCount() == 1

    assert main_window.ui.refXPos.value() == float(table.item(0, 1).text())
    assert main_window.ui.refXWidth.value() == float(table.item(0, 2).text())

    # Change the reference position and width in the table
    table.item(0, 1).setText("100")
    table.item(0, 2).setText("50")
    assert main_window.ui.refXPos.value() == float(table.item(0, 1).text())
    assert main_window.ui.refXWidth.value() == float(table.item(0, 2).text())

    # Change the reference position and width in the main window
    main_window.ui.refXPos.setValue(200)
    main_window.ui.refXWidth.setValue(100)
    assert main_window.ui.refXPos.value() == float(table.item(0, 1).text())
    assert main_window.ui.refXWidth.value() == float(table.item(0, 2).text())


if __name__ == "__main__":
    pytest.main([__file__])
