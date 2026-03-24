"""Miscellaneous custom Qt widgets for QuickNXS."""

from typing import TYPE_CHECKING

from qtpy.QtCore import Qt
from qtpy.QtWidgets import QHBoxLayout, QRadioButton, QTableWidget, QWidget

if TYPE_CHECKING:
    from quicknxs.interfaces.event_handlers.main_handler import MainHandler


class NoToggleRadioButton(QRadioButton):
    """A QRadioButton that cannot be toggled off once selected."""

    def mousePressEvent(self, event):
        """Override mouse press event to prevent toggling off."""
        if self.isChecked():
            event.ignore()
        else:
            super().mousePressEvent(event)


class ActiveDataRadioButton(QWidget):
    """A QWidget that represents the active data selection."""

    def __init__(
        self,
        parent: "MainHandler" = None,
        is_active: bool = False,
        idx: int = None,
        is_direct_beam: bool = False,
    ):
        super().__init__()
        self.parent_handler = parent  # Renamed to avoid conflict with QWidget.parent()
        self.is_active = is_active
        self.idx = idx
        self.is_direct_beam = is_direct_beam
        self.initUI()

    def initUI(self):
        """Initialize the UI components."""

        self.radio_button = NoToggleRadioButton()

        # Block signals during setChecked to prevent the toggled signal from firing
        # before the widget is added to its table (see _get_current_row).
        self.radio_button.blockSignals(True)
        self.radio_button.setChecked(self.is_active)
        self.radio_button.blockSignals(False)

        self.radio_button.toggled.connect(self._on_toggled)

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.radio_button)
        self.setLayout(layout)

    def _on_toggled(self, checked: bool):
        """Handle the toggled signal from the radio button."""
        row = self._get_current_row()
        if row < 0:
            return
        if self.is_direct_beam:
            self.parent_handler.main_window.set_active_direct_beam(checked, row)
        else:
            self.parent_handler.main_window.set_active_reduction_data(checked, row)

    def _get_current_row(self):
        """Find the current row index of this widget in the table."""
        if self.parent_handler is None:
            return -1
        table: QTableWidget = (
            self.parent_handler.direct_beam_table if self.is_direct_beam else self.parent_handler.reduction_table
        )
        for row in range(table.rowCount()):
            if table.cellWidget(row, 0) == self:
                return row
        return -1
