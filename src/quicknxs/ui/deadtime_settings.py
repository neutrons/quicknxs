# package imports
from quicknxs.interfaces.configuration import Configuration
from quicknxs.interfaces.event_handlers.widgets import AcceptRejectDialog

# third-party imports
from qtpy.QtCore import Signal
from qtpy.QtWidgets import QDialog, QWidget
from qtpy.uic import loadUi

# standard imports
import os


class DeadTimeSettingsView(QDialog):
    """
    Dialog to choose the dead time correction options.
    """

    reload_files_signal = Signal()

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        filepath = os.path.join(os.path.dirname(__file__), "deadtime_settings.ui")
        self.ui = loadUi(filepath, baseinstance=self)
        self.set_state_from_global_config()

    def set_state_from_global_config(self):
        """
        Populate the form with the current global configuration
        """
        self.ui.use_paralyzable.setChecked(Configuration.paralyzable_deadtime)
        self.ui.dead_time_value.setValue(Configuration.deadtime_value)
        self.ui.dead_time_tof.setValue(Configuration.deadtime_tof_step)

    def check_values_changed(self):
        """
        Check if the dialog settings entries have been changed by the user

        Returns
        -------
        bool: - True if dialog values are different from the global configuration
              - False if dialog values are the same as the global configuration
        """
        if not self.ui.use_paralyzable.isChecked() == Configuration.paralyzable_deadtime:
            return True
        if not self.ui.dead_time_value.value() == Configuration.deadtime_value:
            return True
        if not self.ui.dead_time_tof.value() == Configuration.deadtime_tof_step:
            return True
        return False

    def ask_user_ok_to_reload_files(self):
        """Shows dialog asking user to confirm reloading all files"""
        message = "Change dead-time settings and reload all files?"
        dialog = AcceptRejectDialog(self, title="Reload files", message=message)
        proceed = dialog.exec_()
        return proceed

    def accept(self):
        """
        Read in the options on the form when the OK button is
        clicked and update the global configuration.
        """
        if self.check_values_changed() and self.ask_user_ok_to_reload_files():
            Configuration.paralyzable_deadtime = self.ui.use_paralyzable.isChecked()
            Configuration.deadtime_value = self.ui.dead_time_value.value()
            Configuration.deadtime_tof_step = self.ui.dead_time_tof.value()
            # trigger reloading all files to apply the new dead-time settings
            self.reload_files_signal.emit()
        self.close()
