# local imports
from quicknxs.interfaces.configuration import Configuration

# third party imports
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QSpinBox, QCheckBox, QDoubleSpinBox, QWidget

# standard imports
from dataclasses import dataclass


class ConfigurationHandler:
    """
    Handles events upon changes in the configuration

    Configuration state that is global to all runs is stored as class variables in the class
    `Configuration`. This class handles updating the configuration state upon changes in the UI
    configuration elements, as well as triggering any recalculation and replotting needed as a
    consequence of the changed configuration.
    """

    def __init__(self, main_window):
        self.main_window = main_window
        self.ui = main_window.ui
        self.connect_config_events()

    def config_setter_factory(self, qwidget: QWidget, config_name: str):
        """
        Generate anonymous functions to serve as callback when any of the global configurations
        (`Configuration` class variables) are updated in the UI.

        Each callback will be associated to one configuration parameter. Upon invoked,
        the `Configuration` class variable value will be updated.

        Parameters
        ----------
        qwidget: QWidget
            UI widget
        config_name: str
            Name of the Configuration variable to update
        """

        def config_setter():
            if isinstance(qwidget, QCheckBox):
                value = qwidget.checkState()
                bool_value = value == Qt.CheckState.Checked
                setattr(Configuration, config_name, bool_value)
            else:
                value = qwidget.value()
                setattr(Configuration, config_name, value)

        return config_setter

    def global_reflectivity_updater(self):
        """
        Recalculate and replot reflectivity upon change in global reflectivity configuration
        """
        self.main_window.global_reflectivity_config_changed()

    def connect_config_events(self):
        """Connect configuration widget events"""

        @dataclass
        class ConfigWidget:
            """Class to help connect UI configuration widgets to events

            Holds widget name and the `Configuration` class variable it represents, as well
            as information about any events the widget triggers

            Args:
                widget_name (str): name of a QWidget
                config_name (str): name of a `Configuration` class variable
                recalc_reflectivity (bool): if True, trigger global reflectivity recalculation
            """

            widget_name: str
            config_name: str
            recalc_reflectivity: bool = False

        config_widgets = [
            ConfigWidget("final_rebin_checkbox", "do_final_rebin", recalc_reflectivity=True),
            ConfigWidget("q_rebin_spinbox", "final_rebin_step", recalc_reflectivity=True),
            ConfigWidget("normalize_to_unity_checkbox", "normalize_to_unity"),
            ConfigWidget("normalization_q_cutoff_spinbox", "total_reflectivity_q_cutoff"),
            ConfigWidget("global_fit_checkbox", "global_stitching"),
            ConfigWidget("polynomial_stitching_degree_spinbox", "polynomial_stitching_degree"),
            ConfigWidget("polynomial_stitching_points_spinbox", "polynomial_stitching_points"),
            ConfigWidget("polynomial_stitching_checkbox", "polynomial_stitching"),
            ConfigWidget("fanReflectivity", "use_constant_q", recalc_reflectivity=True),
            ConfigWidget("sample_size_spinbox", "sample_size"),
            ConfigWidget("bandwidth_spinbox", "wl_bandwidth"),
            ConfigWidget("direct_beam_y_lock_checkbox", "lock_direct_beam_y", recalc_reflectivity=True),
        ]

        for config_widget in config_widgets:
            # get the widget signal to connect
            qwidget = getattr(self.ui, config_widget.widget_name)
            if isinstance(qwidget, (QSpinBox, QDoubleSpinBox)):
                signal_name = "editingFinished"
            elif isinstance(qwidget, QCheckBox):
                signal_name = "stateChanged"
            else:
                raise ValueError(f"{type(qwidget)} not supported by ConfigurationHandler")
            signal = getattr(qwidget, signal_name)

            # connect config setter
            signal.connect(self.config_setter_factory(qwidget, config_widget.config_name))
            # connect reflectivity recalculation (order matters, must be connected after config setter)
            if config_widget.recalc_reflectivity:
                signal.connect(self.global_reflectivity_updater)
