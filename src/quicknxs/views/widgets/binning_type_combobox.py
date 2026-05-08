from qtpy.QtWidgets import QComboBox

from quicknxs.enums import QBinningType


class BinningTypeSelection(QComboBox):
    """Combo box for binning types."""

    def __init__(self, on_change_handler=None, row=None, parent=None):
        """
        Initialize the BinningTypeSelection combo box.

        Parameters
        ----------
        on_change_handler: Optional[Callable]
            A function to be called when the selection changes.
            It should accept two arguments: the new index and the row identifier.
        row : Optional[int]
            An identifier for the row associated with this combo box, useful when
            the combo box is used in a table or list context.
        parent : Optional[QWidget]
            The parent widget.
        """
        super().__init__(parent)

        for binning_type in QBinningType:
            self.addItem(str(binning_type))

        self.setCurrentIndex(QBinningType.NONE)
        self.setToolTip("Select the binning type used in the reflectometry reduction.")

        self.row = row
        self.on_change_handler = on_change_handler

        # optionally set handler when creating a new instance, e.g. when a new table row is added
        if callable(self.on_change_handler):
            self.currentIndexChanged.connect(self._on_index_change)

    def _on_index_change(self, index):
        """
        Handle the change of the combo box index.

        Parameters
        ----------
        index : int
            The new index selected in the combo box.

        Behavior
        --------
        Calls the on_change_handler callback with the new index and the associated row.
        """
        self.on_change_handler(index, self.row)
