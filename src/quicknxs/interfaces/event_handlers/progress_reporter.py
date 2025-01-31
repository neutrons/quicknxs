"""
Class used to report on progress. It allows for sub-tasks and
computes a meaningful progress status accordingly.
"""


class ProgressReporter(object):
    """
    Progress reporter class that allows for sub-tasks.
    """

    def __init__(self, max_value=100, call_back=None, status_bar=None, progress_bar=None):
        """

        Parameters
        ----------
        max_value: int
            max value
        call_back:
        status_bar:
            status bar
        progress_bar:
            progress bar
        """
        self.max_value = max_value
        self.message = ""
        self.call_back = call_back
        self.value = 0
        self.sub_tasks = []
        self.status_bar = status_bar
        self.progress_bar = progress_bar

    def __call__(self, value, message="", out_of=None):
        """Shortcut to set_value() so that the object can be used
        as a function to be compatible with QProgressDialog.setValue().

        Parameters
        ----------
        value
        message: str
            message to be displayed
        out_of

        Returns
        -------
        None

        """
        return self.set_value(value, message, out_of)

    def set_value(self, value, message="", out_of=None):
        """
        Set the value of a progress indicator
        :param int value: completion value, as a percentage
        """
        if out_of is not None:
            value = int(value / out_of * self.max_value)
        value = min(value, self.max_value)
        self.value = value
        self.update(message)

    def update(self, message=""):
        """
        Updates the progress status according to
        sub-tasks.

        :param str message: message to be displayed
        """
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

    def create_sub_task(self, max_value):
        """
        Create a sub-task, with max_value being its portion
        of the complete task. Returns a call-back function
        to be called by the worker to update the progress.

        :param int max_value: portion of the task
        """
        sub_task_progress = ProgressReporter(max_value, self.update)
        self.sub_tasks.append(sub_task_progress)
        return sub_task_progress
