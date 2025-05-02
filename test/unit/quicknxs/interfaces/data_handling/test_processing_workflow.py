import os
from copy import deepcopy

import pytest

from quicknxs.interfaces.configuration import Configuration
from quicknxs.interfaces.data_handling.processing_workflow import DEFAULT_OPTIONS, ProcessingWorkflow
from quicknxs.interfaces.data_manager import DataManager


@pytest.mark.datarepo
def test_orso_output(data_server, tmpdir):
    """Test saving reflectivity curves to ORSO"""
    conf = Configuration()
    manager = DataManager(data_server.directory)
    output_options = deepcopy(DEFAULT_OPTIONS)
    output_options["output_directory"] = str(tmpdir)
    pw = ProcessingWorkflow(manager, output_options)

    def _load_to_reduction_list(filename):
        """Loads a Nexus file and adds it to the reduction list"""
        file_path = data_server.path_to(filename)
        manager.load(file_path, conf)
        manager.add_active_to_reduction()

    # load two runs
    _load_to_reduction_list("REF_M_42112.nxs.h5")
    _load_to_reduction_list("REF_M_42113.nxs.h5")

    # add a second peak
    manager.add_additional_reduction_list(2)

    # write output files for the two peaks
    for peak_index in manager.peak_reduction_lists.keys():
        manager.set_active_reduction_list_index(peak_index)
        manager.set_active_data_from_reduction_list(0)
        pw.specular_reflectivity()

    # check the output files
    for file in [
        "REF_M_42112_1.ort",
        "REF_M_42112_2.ort",
        "REF_M_42113_1.ort",
        "REF_M_42113_2.ort",
        "REF_M_42112+42113_1_combined.ort",
        "REF_M_42112+42113_2_combined.ort",
        "REF_M_42112+42113_peak1_Specular_all.py",
        "REF_M_42112+42113_peak2_Specular_all.py",
        "REF_M_42112+42113_peak1_Specular_Off_Off.dat",
        "REF_M_42112+42113_peak1_Specular_Off_On.dat",
        "REF_M_42112+42113_peak1_Specular_On_Off.dat",
        "REF_M_42112+42113_peak1_Specular_On_On.dat",
        "REF_M_42112+42113_peak2_Specular_Off_Off.dat",
        "REF_M_42112+42113_peak2_Specular_Off_On.dat",
        "REF_M_42112+42113_peak2_Specular_On_Off.dat",
        "REF_M_42112+42113_peak2_Specular_On_On.dat",
    ]:
        assert os.path.isfile(os.path.join(tmpdir, file))
