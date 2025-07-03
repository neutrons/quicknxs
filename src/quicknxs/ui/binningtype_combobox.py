from qtpy.QtWidgets import QComboBox

from quicknxs.interfaces.configuration import BinningType


class BinningTypeSelection(QComboBox):
    """Combo box for binning types."""

    def __init__(self, on_change_handler=None, row=None, parent=None):
        super().__init__(parent)

        for binning_type in BinningType:
            self.addItem(str(binning_type))

        self.setCurrentIndex(0)
        self.setToolTip("Select the binning type used in the reflectometry reduction.")

        self.row = row
        self.on_change_handler = on_change_handler

        # optionally set handler when creating a new instance, e.g. when a new table row is added
        if callable(self.on_change_handler):
            self.currentIndexChanged.connect(self._on_index_change)

    def _on_index_change(self, index):
        self.on_change_handler(index, self.row)
