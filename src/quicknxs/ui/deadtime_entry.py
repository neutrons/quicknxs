# package imports
from quicknxs.interfaces.configuration import Configuration
from quicknxs.interfaces.event_handlers.widgets import AcceptRejectDialog

# third party imports
from qtpy.QtCore import Qt, Signal
from qtpy.QtWidgets import QGroupBox, QHBoxLayout, QCheckBox, QPushButton


class DeadTimeEntryPoint(QGroupBox):

    reload_files_signal = Signal()

    def __init__(self, title="Dead Time Correction"):
        super().__init__(title)
        self.initUI()

    def initUI(self):
        # Set the stylesheet for the group box to have a border
        self.setStyleSheet(
            "QGroupBox {"
            "  border: 1px solid gray;"
            "  border-radius: 5px;"
            "  margin-top: 1ex;"  # space above the group box
            "} "
            "QGroupBox::title {"
            "  subcontrol-origin: margin;"
            "  subcontrol-position: top center;"  # align the title to the center
            "  padding: 0 3px;"
            "}"
        )

        self.applyCheckBox = self.VerifyChangeCheckBox("Apply", self)
        self.applyCheckBox.stateChanged.connect(self.toggleSettingsButton)
        self.settingsButton = QPushButton("Settings", self)
        self.settingsButton.setEnabled(self.applyCheckBox.isChecked())  # enabled if we use the correction

        # Create a horizontal layout for the checkbox and settings button
        hbox = QHBoxLayout()
        hbox.addWidget(self.applyCheckBox)
        hbox.addWidget(self.settingsButton)
        hbox.addStretch(1)  # This adds a stretchable space after the button (optional)

        # Set the layout for the group box
        self.setLayout(hbox)

    class VerifyChangeCheckBox(QCheckBox):
        """
        Checkbox that intercepts the state change to ask user to confirm the change in
        dead-time settings, since it requires reloading all files
        """

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

        def ask_user_ok_to_reload_files(self):
            """Shows dialog asking user to confirm reloading all files"""
            message = "Change dead-time settings and reload all files?"
            dialog = AcceptRejectDialog(self, title="Reload files", message=message)
            proceed = dialog.exec_()
            return proceed

        def mousePressEvent(self, event):
            # Ask user to confirm before changing the state
            if self.ask_user_ok_to_reload_files():
                # Manually toggle the checkbox state
                self.setChecked(not self.isChecked())
            # Ignore the original event since it is handled above
            event.ignore()

    def toggleSettingsButton(self, state):
        # Enable the settings button if the checkbox is checked, disable otherwise
        self.settingsButton.setEnabled(state)
        # Update the global configuration state
        Configuration.apply_deadtime = state == Qt.CheckState.Checked
        # Trigger reloading all files to apply the new dead-time settings
        self.reload_files_signal.emit()
