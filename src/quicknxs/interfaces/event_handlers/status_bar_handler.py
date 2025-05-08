from PyQt5.QtWidgets import QStatusBar


class StatusBarHandler(object):
    """Status bar handler class"""

    def __init__(self, status_bar: QStatusBar):
        """
        Initialize the status message handler.

        Parameters
        ----------
        :param status_bar: The status bar to show messages in
        """
        self.status_bar = status_bar

    def show_message(self, message: str, msecs: int = 10000):
        """
        Show a message in the status bar.

        Parameters
        ----------
        :param message: The message to show
        :param msecs: The duration of the message in milliseconds
        """
        self.status_bar.showMessage(message, msecs=msecs)
