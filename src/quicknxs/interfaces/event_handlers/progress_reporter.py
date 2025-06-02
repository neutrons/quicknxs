"""
Class used to report on progress.

It allows for sub-tasks and computes a meaningful progress status accordingly.
"""

from typing import Callable, Optional

from qtpy.QtWidgets import QProgressBar

from quicknxs.interfaces.event_handlers.status_bar_handler import StatusBarHandler


class ProgressReporter(object):
    """Progress reporter class that allows for sub-tasks."""

    def __init__(
        self,
        max_value: int = 100,
        call_back: Optional[Callable] = None,
        status_bar: Optional[StatusBarHandler] = None,
        progress_bar: Optional[QProgressBar] = None,
    ):
        """Initialize the progress reporter."""
        self.max_value = max_value
        self.message = ""
        self.call_back = call_back
        self.value = 0
        self.sub_tasks = []
        self.status_bar = status_bar
        self.progress_bar = progress_bar

    def __call__(self, value: int, message: str = "", out_of: Optional[int] = None):
        """Shortcut to set_value() so that the object can be used.

        as a function to be compatible with QProgressDialog.setValue().

        Parameters
        ----------
        value:
            completion value, as a percentage
        message:
            message to be displayed
        out_of:
            if provided, the value is scaled to the max_value of the progress reporter
        """
        return self.set_value(value, message, out_of)

    def set_value(self, value: int, message: str = "", out_of: Optional[int] = None):
        """Set the value of a progress indicator."""
        if out_of is not None:
            value = int(value / out_of * self.max_value)
        value = min(value, self.max_value)
        self.value = value
        self.update(message)

    def update(self, message: str = ""):
        """Updates the progress status according to sub-tasks."""
        _value = self.value
        for item in self.sub_tasks:
            _value += min(item.value, item.max_value)
        _value = min(_value, self.max_value)

        if self.call_back is not None:
            self.call_back(message)

        if self.status_bar:
            self.progress_bar.setValue(_value)

        if message and self.status_bar:
            self.status_bar.show_message(message)

    def create_sub_task(self, max_value: int) -> "ProgressReporter":
        """Create a sub-task, with max_value being its portion of the complete task.

        Parameters
        ----------
        max_value :
            The maximum value for the sub-task, representing its portion of the total task.

        Returns
        -------
        ProgressReporter
            A new ProgressReporter instance representing the sub-task,
            to be called by the worker to update the progress.
        """
        sub_task_progress = ProgressReporter(max_value, self.update)
        self.sub_tasks.append(sub_task_progress)
        return sub_task_progress
