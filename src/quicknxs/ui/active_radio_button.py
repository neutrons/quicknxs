"""Miscellaneous custom Qt widgets for QuickNXS."""

from qtpy.QtCore import Qt
from qtpy.QtWidgets import QHBoxLayout, QRadioButton, QWidget


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

    def __init__(self, parent=None, is_active=False, idx=None, is_direct_beam=False):
        super().__init__()
        self.parent_handler = parent  # Renamed to avoid conflict with QWidget.parent()
        self.is_active = is_active
        self.idx = idx
        self.is_direct_beam = is_direct_beam
        self.initUI()

    def initUI(self):
        """Initialize the UI components."""

        self.radio_button = NoToggleRadioButton()
        self.radio_button.setChecked(self.is_active)

        # Connect to the appropriate method based on whether this is a direct beam or reduction table
        if self.is_direct_beam:
            self.radio_button.toggled.connect(
                lambda checked: self.parent_handler.main_window.set_active_direct_beam(checked, self.idx)
            )
        else:
            self.radio_button.toggled.connect(
                lambda checked: self.parent_handler.main_window.set_active_reduction_data(checked, self.idx)
            )

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.radio_button)
        self.setLayout(layout)
