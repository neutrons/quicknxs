from quicknxs.interfaces.configuration import BinningType
from quicknxs.ui.binningtype_combobox import BinningTypeSelection


class TestBinningTypeSelection:
    """Unit tests for the BinningTypeSelection class."""

    def test_init(self, qtbot):
        """Test that the combo box is initialized correctly."""
        combo = BinningTypeSelection()
        assert combo.count() == len(BinningType)
        assert combo.currentText() == str(BinningType.NONE)

    def test_on_change_handler(self, qtbot):
        """Test that the on change handler is called when the index changes."""
        called = False

        def on_change_handler(index, row):
            nonlocal called
            called = True

        combo = BinningTypeSelection(on_change_handler=on_change_handler)
        combo.setCurrentIndex(1)
        assert called

    def test_current_text(self, qtbot):
        """Test that currentText returns the correct binning type."""
        combo = BinningTypeSelection()
        for binning_type in BinningType:
            combo.setCurrentIndex(binning_type.value)
            assert combo.currentText() == str(binning_type)
