r"""
Fixtures for pytest
"""

# standard imports
# 3rd-party imports
import glob
import os
import sys
from pathlib import Path

import pytest
from PyQt5.QtCore import QSettings

from quicknxs.interfaces.data_handling.filepath import RunNumbers
from quicknxs.interfaces.data_handling.instrument import Instrument

pytest_plugins = ["mantid.fixtures"]

this_module_path = sys.modules[__name__].__file__


################################################
# FIXTURES AUTOMATICALLY APPLIED TO EVERY TEST #
################################################


@pytest.fixture(autouse=True)
def qsettings_tmp_path(tmp_path):
    """
    Set the location of the config file generated by QSettings to a temporary directory

    This avoids:
    - unit tests affecting the local user settings in ~/.config/.refredm.conf and vice versa
    - settings spilling over between tests by having a unique settings file location in each test
      (thanks to `tmp_path` creating a unique directory for each test)
    """
    QSettings.setPath(QSettings.NativeFormat, QSettings.UserScope, str(tmp_path))


##################################
# FIXTURES THAT CAN BE REQUESTED #
##################################


@pytest.fixture(scope="session")
def DATA_DIR():
    return Path(__file__).parent / "data"


Instrument.file_search_template = str(Path(__file__).parent / "data" / "quicknxs-data" / "REF_M_%s")


@pytest.fixture(scope="module")
def data_server(DATA_DIR):
    r"""Object containing info and functionality for data files"""

    class _DataServe(object):
        _directory = str(DATA_DIR)
        _h5_path = "quicknxs-data"

        @property
        def directory(self):
            r"""Directory where to find the data es"""
            return self._directory

        @property
        def h5_path(self):
            r"""Directory where to find h5 data files"""
            return self._h5_path

        @property
        def h5_full_path(self):
            r"""Full path to directory where to find h5 data files"""
            return os.path.join(self.directory, self.h5_path)

        def path_to(self, basename):
            r"""Absolute path to a data file. If it doesn't exist, try to find it in the remote repository"""
            # looking in test/data
            file_path = os.path.join(self._directory, basename)
            if os.path.isfile(file_path):
                return file_path
            # looking in test/data/quicknxs-data
            file_path = os.path.join(self.directory, self.h5_path)
            file_path = os.path.join(file_path, basename)

            for ext in [".nxs.h5", "", "_event.nxs"]:
                if os.path.isfile(file_path + ext):
                    return file_path + ext
            raise IOError(f"File {basename} not found in data directory {self._directory}")

        def get_file_paths(self, number):
            instrument = Instrument()

            run_numbers = RunNumbers(number)

            file_list = list()

            for run_number in run_numbers.numbers:
                search_string = instrument.file_search_template % run_number
                matches = glob.glob(search_string + ".nxs.h5")  # type: Optional[List[str]]
                if not matches:  # Look for old-style nexus file name
                    search_string = instrument.legacy_search_template % run_number
                    matches = glob.glob(search_string + "_event.nxs")
                if len(matches) >= 1:
                    file_list.append(matches[0])  # there should be only one match, since we query with one run number

            return file_list

    return _DataServe()
