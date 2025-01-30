r"""
General settings
"""


# standard imports
import json
import os
import sys

this_module_path = sys.modules[__name__].__file__


class Settings(object):
    r"""Singleton object containing the GUI settings as a dictionary"""
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not isinstance(cls._instance, cls):
            cls._instance = object.__new__(cls, *args, **kwargs)
            cls._instance._settings = {}  # empty configuration
        return cls._instance

    def __init__(self):
        r"""Load default configuration"""
        if not self._settings:  # will load only once, since this is a singleton
            self.update(os.path.join(os.path.dirname(this_module_path), "settings.json"))

    def __getitem__(self, item):
        return self._settings.get(item, None)

    def __str__(self):
        return str(self._settings)

    def update(self, file_json):
        # type: (str) -> dict
        r"""
        @brief Update the configuration with a JSON file containing settings of interest
        """
        with open(file_json) as file_handle:
            self._settings.update(json.load(file_handle))
