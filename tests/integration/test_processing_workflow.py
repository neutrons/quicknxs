import os

import pytest
from orsopy.fileio import load_orso

from quicknxs.enums import OffSpecXAxis
from quicknxs.models.configuration import Configuration, OutputOptions
from quicknxs.models.processing_workflow import ProcessingWorkflow
from quicknxs.presenters.data_manager import DataManager


@pytest.mark.datarepo
def test_orso_output(data_server, tmpdir):
    """Test saving reflectivity curves to ORSO."""
    Configuration.setup_default_values()
    conf = Configuration()
    conf.cut_first_n_points = 0
    conf.cut_last_n_points = 0
    manager = DataManager(data_server.directory)
    output_options = OutputOptions()
    output_options.output_directory = str(tmpdir)
    pw = ProcessingWorkflow(manager, output_options)

    def _load_to_reduction_list(filename):
        """Load a Nexus file and add it to the reduction list."""
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
        ("REF_M_42112_peak1_Specular_all.ort", [85, 85, 85, 85]),
        ("REF_M_42112_peak2_Specular_all.ort", [85, 85, 85, 85]),
        ("REF_M_42113_peak1_Specular_all.ort", [85, 85, 85, 85]),
        ("REF_M_42113_peak2_Specular_all.ort", [85, 85, 85, 85]),
        ("REF_M_42112+42113_peak1_Specular_all.ort", [162, 162, 162, 162]),  # peak 1 - 8 data points removed
        ("REF_M_42112+42113_peak2_Specular_all.ort", [170, 170, 170, 170]),  # peak 2 - no data points removed
    ]:
        datasets = load_orso(os.path.join(tmpdir, file))
        for i, dataset in enumerate(datasets):
            assert len(dataset.data) == reflectivity_data_lengths[i]


@pytest.mark.datarepo
def test_smoothing_without_slice_export(data_server, tmpdir):
    """Regression test for error when smoothing without exporting slices.

    Reproduces the exact scenario reported by Marie:
    - User checks "Apply intensity smoothing" but NOT "Export off-spec slices"
    - Slice dialog does NOT open, so slice params (qz_min/max) come from OutputOptions defaults
    - smooth_offspec() internally needs slice params for internal calculations

    This verifies that OutputOptions default values cover the missing slice parameters.
    """
    Configuration.setup_default_values()
    conf = Configuration()
    conf.cut_first_n_points = 0
    conf.cut_last_n_points = 0
    manager = DataManager(data_server.directory)

    # Simulate the exact state after ReductionDialog + OffSpecParametersDialog:
    # User checked "Apply intensity smoothing" but NOT "Export off-spec slices"
    output_options = OutputOptions(
        export_specular=False,
        export_offspec=False,
        apply_smoothing=True,
        export_offspec_smooth=True,
        export_offspec_slices=False,  # User did NOT check this
        output_directory=str(tmpdir),
        # Off-spec params from OffSpecParametersDialog:
        off_spec_x_axis=OffSpecXAxis.DELTA_KZ_VS_QZ,
        off_spec_x_min=-0.1,
        off_spec_x_max=0.1,
        off_spec_y_min=0.0,
        off_spec_y_max=0.15,
        off_spec_nxbins=120,
        off_spec_nybins=120,
        off_spec_smooth_nxbins=100,
        off_spec_smooth_nybins=80,
        off_spec_sigmas=3,
        off_spec_sigmax=0.001,
        off_spec_sigmay=0.001,
        # off_spec_slice_qz_min/max come from OutputOptions defaults since
        # OffSpecSliceDialog never opened (export_offspec_slices=False)
    )

    pw = ProcessingWorkflow(manager, output_options)

    # Verify slice parameters are available via OutputOptions defaults
    assert pw.output_options.off_spec_slice_qz_min == 0.05
    assert pw.output_options.off_spec_slice_qz_max == 0.07

    # Verify user-provided values were preserved
    assert pw.output_options.off_spec_x_min == -0.1
    assert pw.output_options.off_spec_sigmas == 3

    # Load test data
    file_path = data_server.path_to("REF_M_42112.nxs.h5")
    manager.load(file_path, conf)
    manager.add_active_to_reduction()

    # This should NOT raise an error due to missing slice parameters
    pw.offspec(raw=False, binned=False, smooth=True, slices=False)

    # The smoothed output is on the requested regular grid
    smooth_output = manager.cached_offspec
    assert smooth_output is not None
    for xs in smooth_output["cross_sections"]:
        assert smooth_output[xs][0].shape == (80, 100, 3)
