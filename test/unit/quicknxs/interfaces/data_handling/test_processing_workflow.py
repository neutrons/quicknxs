import os
from copy import deepcopy

import pytest
from orsopy.fileio import load_orso

from quicknxs.interfaces.configuration import Configuration
from quicknxs.interfaces.data_handling.processing_workflow import DEFAULT_OPTIONS, ProcessingWorkflow
from quicknxs.interfaces.data_manager import DataManager


@pytest.mark.datarepo
def test_orso_output(data_server, tmpdir):
    """Test saving reflectivity curves to ORSO"""
    conf = Configuration()
    conf.cut_first_n_points = 0
    conf.cut_last_n_points = 0
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

    # make the two peaks different by cutting data points from the first run of the first peak
    first_state = manager.reduction_states[0]
    manager.reduction_list[0].cross_sections[first_state].configuration.cut_last_n_points = 8

    # write output files for the two peaks
    for peak_index in manager.peak_reduction_lists.keys():
        manager.set_active_reduction_list_index(peak_index)
        manager.set_active_data_from_reduction_list(0)
        pw.specular_reflectivity()

    # load ORSO files and check the reflectivity data
    for file, reflectivity_data_lengths in [
        ("REF_M_42112_1.ort", [140, 139, 140, 139]),
        ("REF_M_42112_2.ort", [140, 139, 140, 139]),
        ("REF_M_42113_1.ort", [136, 139, 123, 140]),
        ("REF_M_42113_2.ort", [136, 139, 123, 140]),
        ("REF_M_42112+42113_1_combined.ort", [268, 270, 255, 271]),  # peak 1 - 8 data points removed
        ("REF_M_42112+42113_2_combined.ort", [276, 278, 263, 279]),  # peak 2 - no data points removed
    ]:
        datasets = load_orso(os.path.join(tmpdir, file))
        for i, dataset in enumerate(datasets):
            assert len(dataset.data) == reflectivity_data_lengths[i]
