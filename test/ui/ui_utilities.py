# local imports


# third party imports
import matplotlib.pyplot as plt
from numpy.ma import MaskedArray
from PyQt5 import QtCore

# standard library imports


def setText(widget, text, press_enter=True):
    r"""Set the text of a widget and optionally press enter."""
    assert getattr(widget, "setText", None) is not None
    widget.setText(text)
    if press_enter:
        widget.setFocus(QtCore.Qt.MouseFocusReason)
        widget.returnPressed.emit()


def setValue(widget, value, editing_finished=True):
    r"""Set the value of a widget and optionally emit editing finished signal."""
    assert getattr(widget, "setValue", None) is not None
    widget.setValue(value)
    if editing_finished:
        widget.editingFinished.emit()


def data_from_plot1D(widget: "MplWidget", line_number=0) -> tuple:
    r"""Get the data from an MplWidget representing a 1D plot
    Returns
    -------
    X and Y data as a tuple of numpy arrays
    """
    figure = widget.canvas.fig
    axes = figure.get_axes()[0]
    return axes.get_lines()[line_number].get_data()


def data_from_plot2D(widget: "MplWidget") -> MaskedArray:
    r"""Get the data from an MplWidget representing a 1D plot
    Returns
    -------
    2D data as a masked numpy array
    """
    figure = widget.canvas.fig
    axes = figure.get_axes()[0]
    return axes.get_images()[0].get_array()


def text_from_plot1D(widget: "MplWidget", line_number=0) -> tuple:
    r"""Get the text from an MplWidget representing a 1D plot
    Returns
    -------
    X and Y data as a tuple of numpy arrays
    """
    figure = widget.canvas.fig
    axes = figure.get_axes()[0]
    texts = [
        child
        for child in axes.get_children()
        if isinstance(child, plt.Text) and child not in [axes.title, axes.xaxis.label, axes.yaxis.label]
    ]
    return texts[0].get_text()


def set_current_file_by_run_number(widget, run_number):
    r"""Set the selected file in the main window file list by the given run number"""
    list_item = widget.file_list.findItems(str(run_number), QtCore.Qt.MatchContains)[0]
    widget.file_list.setCurrentItem(list_item)
