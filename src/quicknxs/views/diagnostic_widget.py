from qtpy import QtWidgets

from quicknxs.config.gui import QColors
from quicknxs.models.configuration import Configuration
from quicknxs.models.diagnostic_data import DiagnosticData


class DiagnosticWidget:
    """Standalone widget for displaying diagnostic information when cross-sections cannot be loaded."""

    def __init__(self, parent=None):
        """Initialize the diagnostic widget.

        Parameters
        ----------
        parent:
            Parent widget (typically the main window)
        """
        self.parent = parent

    def show(self, diag_data: DiagnosticData):
        """Show diagnostic dialog with run information.

        Parameters
        ----------
        diag_data:
            DiagnosticData containing information from the run
        """

        def format_value(value, fmt=None):
            """Format a value as a string with optional formatting."""
            if value == "N/A":
                return "N/A"
            try:
                if fmt == "scientific":
                    return f"{float(value):.2e}"
                elif fmt == "float":
                    return f"{float(value):.3f}"
                elif fmt == "time":
                    return f"{float(value):.2f} s"
                elif fmt == "angle":
                    return f"{float(value):.3f}°"
                elif fmt == "wavelength":
                    return f"{float(value):.3f} Å"
                elif fmt == "cps":
                    return f"{float(value):.2f} cps"
                else:
                    return str(value)
            except (ValueError, TypeError):
                return str(value)

        # Create diagnostic dialog
        dialog = QtWidgets.QDialog(self.parent)
        dialog.setWindowTitle("No Valid Cross-Sections - Diagnostic Information")
        layout = QtWidgets.QVBoxLayout()

        # Add informative text
        info_text = f"<b>Error: {diag_data.message}</b><br>"
        info_text += f"Number of runs analyzed: {len(diag_data.diagnostic_data)}"

        info_label = QtWidgets.QLabel(info_text)
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        # Create table for diagnostic information
        table = QtWidgets.QTableWidget()

        # Define columns
        headers = [
            "Run",
            "λ",
            "Direct Pixel",
            "Proton Charge",
            "Sample Angle",
            "DANGLE",
            "DANGLE0",
            "Counting Time",
            "Event Count",
            "Count Rate",
        ]
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setRowCount(len(diag_data.diagnostic_data))

        # Fill table with formatted data
        for i, data in enumerate(diag_data.diagnostic_data):
            table.setItem(i, 0, QtWidgets.QTableWidgetItem(str(data["cross_section_id"])))
            table.setItem(i, 1, QtWidgets.QTableWidgetItem(format_value(data["lambda_center"], fmt="wavelength")))
            table.setItem(i, 2, QtWidgets.QTableWidgetItem(format_value(data["direct_pixel"], fmt="float")))
            table.setItem(i, 3, QtWidgets.QTableWidgetItem(format_value(data["proton_charge"], fmt="scientific")))
            table.setItem(i, 4, QtWidgets.QTableWidgetItem(format_value(data["sample_angle"], fmt="angle")))
            table.setItem(i, 5, QtWidgets.QTableWidgetItem(format_value(data["dangle"], fmt="angle")))
            table.setItem(i, 6, QtWidgets.QTableWidgetItem(format_value(data["dangle0"], fmt="angle")))
            table.setItem(i, 7, QtWidgets.QTableWidgetItem(format_value(data["counting_time"], fmt="time")))
            event_count = QtWidgets.QTableWidgetItem(str(data["event_count"]))
            try:
                if float(data["event_count"]) < Configuration.nbr_events_min:
                    event_count.setForeground(QColors.red)
            except (ValueError, TypeError):
                pass
            table.setItem(i, 8, event_count)
            table.setItem(i, 9, QtWidgets.QTableWidgetItem(format_value(data["count_rate"], fmt="cps")))

        table.resizeColumnsToContents()
        table.resizeRowsToContents()

        header = table.horizontalHeader()
        header.setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
        header.setStretchLastSection(True)

        table.setSizeAdjustPolicy(QtWidgets.QAbstractScrollArea.AdjustToContents)
        layout.addWidget(table)

        logs_button = QtWidgets.QPushButton("Open Sample Logs Table")
        logs_button.clicked.connect(lambda: self._open_sample_logs_table(diag_data, dialog))
        layout.addWidget(logs_button)

        close_button = QtWidgets.QPushButton("Close")
        close_button.clicked.connect(dialog.accept)
        layout.addWidget(close_button)

        dialog.setLayout(layout)
        dialog.adjustSize()
        dialog.exec_()

    def _open_sample_logs_table(self, diag_data: DiagnosticData, parent=None):
        """Open a table view of all sample logs from the workspaces.

        Parameters
        ----------
        diag_data:
            DiagnosticData containing sample log data
        parent:
            Parent widget for the dialog
        """
        dialog = QtWidgets.QDialog(parent)
        dialog.setWindowTitle("Sample Logs - All Properties")
        layout = QtWidgets.QVBoxLayout()
        table = QtWidgets.QTableWidget()

        sample_logs = diag_data.sample_logs

        total_rows = sum(len(log_data["logs"]) for log_data in sample_logs)
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(["Run", "Property", "Value"])
        table.setRowCount(total_rows)

        current_row = 0
        for log_data in sample_logs:
            run_id = str(log_data["run_id"])

            for prop_name, prop_value in log_data["logs"]:
                table.setItem(current_row, 0, QtWidgets.QTableWidgetItem(run_id))
                table.setItem(current_row, 1, QtWidgets.QTableWidgetItem(prop_name))
                table.setItem(current_row, 2, QtWidgets.QTableWidgetItem(prop_value))
                current_row += 1

        table.resizeColumnsToContents()
        table.resizeRowsToContents()

        header = table.horizontalHeader()
        header.setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
        header.setStretchLastSection(True)

        table.setSizeAdjustPolicy(QtWidgets.QAbstractScrollArea.AdjustToContents)
        layout.addWidget(table)

        close_button = QtWidgets.QPushButton("Close")
        close_button.clicked.connect(dialog.accept)
        layout.addWidget(close_button)

        dialog.setLayout(layout)
        dialog.adjustSize()
        dialog.exec_()
