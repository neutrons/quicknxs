"""
   Dialog to select reduction options to choose which outputs are needed
   and in which formats to write them.
"""
# pylint: disable=bare-except

import os
from PyQt5 import QtCore, QtWidgets
from reflectivity_ui.interfaces import load_ui


class ReductionDialog(QtWidgets.QDialog):
    """
    Reduction dialog
    """

    default_template = "{instrument}_{numbers}_{peak}_{item}_{state}.{type}"

    def __init__(self, parent):
        super(ReductionDialog, self).__init__(parent)

        self.ui = load_ui("ui_reduce_dialog.ui", baseinstance=self)

        self.settings = QtCore.QSettings(".refredm")

        self.ui.directoryEntry.setText(self.settings.value("output_directory", os.path.expanduser("~")))
        self.ui.fileNameEntry.setText(self.settings.value("output_file_template", ReductionDialog.default_template))

        # Outputs
        self.ui.exportSpecular.setChecked(self._verify_true("export_specular", True))
        self.ui.export_SA.setChecked(self._verify_true("export_asym", True))
        self.ui.exportGISANS.setChecked(self._verify_true("export_gisans", False))
        self.ui.exportOffSpecular.setChecked(self._verify_true("export_offspec", False))
        self.ui.exportOffSpecularSmoothed.setChecked(self._verify_true("export_offspec_smooth", False))

        # Formats
        self.ui.matlab.setChecked(self._verify_true("format_matlab", False))
        self.ui.numpy.setChecked(self._verify_true("format_numpy", False))
        self.ui.mantid_script_checkbox.setChecked(self._verify_true("format_mantid", False))
        self.ui.five_cols_checkbox.setChecked(self._verify_true("format_5cols", True))

        # Emails
        self.ui.emailSend.setChecked(self._verify_true("email_send", False))
        self.ui.emailZIPData.setChecked(self._verify_true("email_zip_data", True))
        self.ui.emailSendPlots.setChecked(self._verify_true("email_send_plots", False))
        self.ui.emailSendData.setChecked(self._verify_true("email_send_data", True))
        self.ui.emailTo.setText(self.settings.value("email_to", ""))
        self.ui.emailCc.setText(self.settings.value("email_cc", ""))
        self.ui.emailSubject.setText(self.settings.value("email_subject", ""))

        self.is_accepted = False

    def _verify_true(self, parameter, default):
        """Utility function to read a bool"""
        _value = self.settings.value(parameter, str(default))
        return str(_value).lower() == "true"

    def accept(self):
        """
        Save the current options and close dialog
        """
        self.save_settings()
        self.is_accepted = True
        self.close()

    def get_options(self):
        """Return the reduction options as a dict"""
        if self.is_accepted is False:
            return None
        return dict(
            export_specular=self.ui.exportSpecular.isChecked(),
            export_asym=self.ui.export_SA.isChecked(),
            export_gisans=self.ui.exportGISANS.isChecked(),
            export_offspec=self.ui.exportOffSpecular.isChecked(),
            export_offspec_smooth=self.ui.exportOffSpecularSmoothed.isChecked(),
            format_matlab=self.ui.matlab.isChecked(),
            format_mantid=self.ui.mantid_script_checkbox.isChecked(),
            format_numpy=self.ui.numpy.isChecked(),
            format_5cols=self.ui.five_cols_checkbox.isChecked(),
            output_directory=self.ui.directoryEntry.text(),
            output_file_template=self.ui.fileNameEntry.text(),
            email_send=self.ui.emailSend.isChecked(),
            email_zip_data=self.ui.emailZIPData.isChecked(),
            email_send_plots=self.ui.emailSendPlots.isChecked(),
            email_send_data=self.ui.emailSendData.isChecked(),
            email_to=self.ui.emailTo.text(),
            email_cc=self.ui.emailCc.text(),
            email_subject=self.ui.emailSubject.text(),
            email_text=self.ui.emailText.toPlainText(),
        )

    def change_directory(self):
        """
        Change the output directory
        """
        old_d = self.ui.directoryEntry.text()
        new_d = QtWidgets.QFileDialog.getExistingDirectory(
            parent=self, caption="Select new directory", directory=old_d
        )
        if new_d is not None:
            self.ui.directoryEntry.setText(new_d)

    def save_settings(self):
        """
        Save reduction options in QSettings
        """
        self.settings.setValue("output_directory", self.ui.directoryEntry.text())
        self.settings.setValue("output_file_template", self.ui.fileNameEntry.text())

        self.settings.setValue("export_specular", self.ui.exportSpecular.isChecked())
        self.settings.setValue("export_asym", self.ui.export_SA.isChecked())
        self.settings.setValue("export_gisans", self.ui.exportGISANS.isChecked())
        self.settings.setValue("export_offspec", self.ui.exportOffSpecular.isChecked())
        self.settings.setValue("export_offspec_smooth", self.ui.exportOffSpecularSmoothed.isChecked())

        self.settings.setValue("format_matlab", self.ui.matlab.isChecked())
        self.settings.setValue("format_numpy", self.ui.numpy.isChecked())
        self.settings.setValue("format_mantid", self.ui.mantid_script_checkbox.isChecked())
        self.settings.setValue("format_5cols", self.ui.five_cols_checkbox.isChecked())

        self.settings.setValue("email_send", self.ui.emailSend.isChecked())
        self.settings.setValue("email_zip_data", self.ui.emailZIPData.isChecked())
        self.settings.setValue("email_send_plots", self.ui.emailSendPlots.isChecked())
        self.settings.setValue("email_send_data", self.ui.emailSendData.isChecked())
        self.settings.setValue("email_to", self.ui.emailTo.text())
        self.settings.setValue("email_cc", self.ui.emailCc.text())
        self.settings.setValue("email_subject", self.ui.emailSubject.text())
