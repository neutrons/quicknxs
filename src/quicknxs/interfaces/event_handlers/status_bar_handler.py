from qtpy.QtWidgets import QStatusBar


class StatusBarHandler(object):
    """Status bar handler class"""

    def __init__(self, status_bar: QStatusBar):
        """Initialize the status message handler."""
        self.status_bar = status_bar

    def show_message(self, message: str, msecs: int = 10000):
        """Show a message in the status bar for a specified duration."""
        self.status_bar.showMessage(message, msecs=msecs)
