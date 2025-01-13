import pytest

from quicknxs.interfaces.event_handlers.progress_reporter import ProgressReporter
from quicknxs.interfaces.main_window import MainWindow


class TestStatusBar:
    def test_report_message(self, qtbot):
        """Test that function report_message updates the status bar message"""
        window_main = MainWindow()
        qtbot.addWidget(window_main)
        assert window_main.ui.statusbar.currentMessage() == ""
        # Test that report_message updates the status bar message
        window_main.file_handler.report_message("Test report_message")
        assert window_main.ui.statusbar.currentMessage() == "Test report_message"
        window_main.file_handler.report_message("Different message")
        assert window_main.ui.statusbar.currentMessage() == "Different message"

    def test_progress_reporter(self, qtbot):
        """Test that the progress reporter updates the status bar message"""
        window_main = MainWindow()
        qtbot.addWidget(window_main)
        progress_reporter = ProgressReporter(
            100, None, window_main.file_handler.status_bar_handler, window_main.file_handler.progress_bar
        )
        assert window_main.ui.statusbar.currentMessage() == ""
        # Test that progress reporter update function updates the status bar message
        progress_reporter.update("Test progress reporter")
        assert window_main.ui.statusbar.currentMessage() == "Test progress reporter"
        # Test that progress reporter set_value function updates the status bar
        progress_reporter.set_value(2, "Loaded file", out_of=10)
        assert window_main.ui.statusbar.currentMessage() == "Loaded file"
        assert window_main.file_handler.progress_bar.value() == 20
