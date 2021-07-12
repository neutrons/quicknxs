"""
    This instrument description contains information
    that is instrument-specific and abstracts out how we obtain
    information from the data file
"""
#pylint: disable=invalid-name, too-many-instance-attributes, line-too-long, bare-except
from __future__ import absolute_import, division, print_function

# local
from reflectivity_ui.interfaces.data_handling.filepath import FilePath
from . import ApplicationConfiguration

# 3rd party
import numpy as np

# standard
import logging
import math
import os
import random
import sys
import string

# Import mantid according to the application configuration
application_conf = ApplicationConfiguration()
if application_conf.mantid_path is not None:
    sys.path.insert(0, application_conf.mantid_path)
import mantid.simpleapi as api

# Option to use the slow flipper logs rather than the Analyzer/Polarizer logs
USE_SLOW_FLIPPER_LOG = True

# Constants
h = 6.626e-34  # m^2 kg s^-1
m = 1.675e-27  # kg


def get_cross_section_label(ws, entry_name):
    """
        Return the proper cross-section label.
    """
    entry_name = str(entry_name)
    pol_is_on = entry_name.lower().startswith('on')
    ana_is_on = entry_name.lower().endswith('on')

    pol_label = ''
    ana_label = ''

    # Look for log that define whether OFF or ON is +
    if 'PolarizerLabel' in ws.getRun():
        pol_id = ws.getRun().getProperty("PolarizerLabel").value
        if isinstance(pol_id, np.ndarray):
            pol_id = int(pol_id[0])
        if pol_id == 1:
            pol_label = '+' if pol_is_on else '-'
        elif pol_id == 0:
            pol_label = '-' if pol_is_on else '+'

    if 'AnalyzerLabel' in ws.getRun():
        ana_id = ws.getRun().getProperty("AnalyzerLabel").value
        if isinstance(ana_id, np.ndarray):
            ana_id = int(ana_id[0])
        if ana_id == 1:
            ana_label = '+' if ana_is_on else '-'
        elif ana_id == 0:
            ana_label = '-' if ana_is_on else '-'

    entry_name = entry_name.replace('_', '-')
    if ana_label == '' and pol_label == '':
        return entry_name
    else:
        return '%s%s' % (pol_label, ana_label)


class Instrument(object):
    """
        Instrument class. Holds the data handling that is unique to a specific instrument.
    """
    n_x_pixel = 304
    n_y_pixel = 256
    huber_x_cut = 6.5
    peak_range_offset = 50
    tolerance = 0.05
    pixel_width = 0.0007
    instrument_name = "REF_M"
    instrument_dir = "/SNS/REF_M"
    file_search_template = "/SNS/REF_M/*/nexus/REF_M_%s"
    legacy_search_template = "/SNS/REF_M/*/data/REF_M_%s"

    def __init__(self):
        # Filtering
        self.pol_state = application_conf.POL_STATE
        self.pol_veto = application_conf.POL_VETO
        self.ana_state = application_conf.ANA_STATE
        self.ana_veto = application_conf.ANA_VETO

    def dummy_filter_cross_sections(self, ws, name_prefix=None):
        # type: (EventWorkspace, Optional[str]) -> WorkspaceGroup
        r"""
        @brief Filter events according to an aggregated state log.
        @details  BL4A:SF:ICP:getDI
          015 (0000 1111): SF1=OFF, SF2=OFF, SF1Veto=OFF, SF2Veto=OFF
          047 (0010 1111): SF1=ON, SF2=OFF, SF1Veto=OFF, SF2Veto=OFF
          031 (0001 1111): SF1=OFF, SF2=ON, SF1Veto=OFF, SF2Veto=OFF
          063 (0011 1111): SF1=ON, SF2=ON, SF1Veto=OFF, SF2Veto=OFF
        @param ws: workspace containing the unfiltered events
        @param name_prefix: root name of the output WorkspaceGroup. If None, the run number of the workspace is chosen
        as the root name.
        @return a group workspace for each of the four different filter/analyzer conbinations
        """
        state_log = "BL4A:SF:ICP:getDI"
        states = {'Off_Off': 15,
                  'On_Off': 47,
                  'Off_On': 31,
                  'On_On': 63}
        cross_sections = []
        if name_prefix is None:
            name_prefix = str(ws.getRunNumber())
        for pol_state in ['Off_Off', 'On_On', 'Off_On', 'On_Off']:
            try:
                _ws = api.FilterByLogValue(InputWorkspace=ws, LogName=state_log, TimeTolerance=0.1,
                                           MinimumValue=states[pol_state],
                                           MaximumValue=states[pol_state],
                                           LogBoundary='Left',
                                           # FIXME 64 - the merged workspace only shows the first run's number
                                           #  Thus this method won't give a merged workspace a unique name
                                           #  And potentially it could confuse the program with single-run workspace
                                           OutputWorkspace='%s_entry-%s' % (name_prefix, pol_state))
                _ws.getRun()['cross_section_id'] = pol_state
                cross_sections.append(_ws)
            except RuntimeError as run_err:
                logging.error("Could not filter {}: {}\nError: {}".format(pol_state, sys.exc_info()[1], run_err))

        return cross_sections

    def load_data(self, file_path):
        r"""
        # type: (unicode) -> WorkspaceGroup
        @brief Load one or more data sets according to the needs ot the instrument.
        @details This function assumes that when loading more than one data file, the files are congruent and their
        events will be added together.
        @param file_path: absolute path to one or more data files. If more than one, paths should be concatenated
        with the plus symbol '+'.
        @returns WorkspaceGroup with any number of cross-sections
        """
        print('*********************************************************')
        print('[DEBUG instrument.load_data] file_path = {}'.format(file_path))
        fp_instance = FilePath(file_path)
        xs_list = list()
        temp_workspace_root_name = ''.join(random.sample(string.ascii_letters, 12))  # random string of 12 characters
        workspace_root_name = fp_instance.run_numbers(string_representation='short')
        for path in fp_instance.single_paths:
            is_legacy = path.endswith(".nxs")
            if is_legacy or not USE_SLOW_FLIPPER_LOG:
                # TODO get a temporary workspace name to prevent overwriting an existing workpsace. For instance,
                # TODO if we loaded run 12345 there will be workspaces 12345_entry-POLSTATE1, 12334_entry_POLSTATE2,...
                # TODO but if we now want to load data for runs 12345 + 12346 together, we should avoid overwriting
                # TODO the previous workspaces when loading the data for the first run of the pair, run 12345.
                _path_xs_list = api.MRFilterCrossSections(Filename=path,
                                                          PolState=self.pol_state,
                                                          AnaState=self.ana_state,
                                                          PolVeto=self.pol_veto,
                                                          AnaVeto=self.ana_veto,
                                                          CrossSectionWorkspaces="%s_entry" % temp_workspace_root_name)
                # Only keep good workspaces, and get rid of the rejected events
                path_xs_list = [ws for ws in _path_xs_list if not ws.getRun()['cross_section_id'].value == 'unfiltered']
            else:
                ws = api.LoadEventNexus(Filename=path, OutputWorkspace="raw_events")
                print('[DEBUG instrument.load_data] LoadEventNexus({} has {} events)'.format(path, ws.getNumberEvents()))

                path_xs_list = self.dummy_filter_cross_sections(ws, name_prefix=temp_workspace_root_name)
            if len(xs_list) == 0:  # initialize xs_list with the cross sections of the first data file
                xs_list = path_xs_list
                for ws in xs_list:  # replace the temporary names with the run number(s)
                    name_new = str(ws).replace(temp_workspace_root_name, workspace_root_name)
                    api.RenameWorkspace(str(ws), name_new)
            else:
                for i, ws in enumerate(xs_list):
                    api.Plus(LHSWorkspace=str(ws), RHSWorkspace=str(path_xs_list[i]), OutputWorkspace=str(ws))
        # Insert a log indicating which run numbers contributed to this cross-section
        for ws in xs_list:
            api.AddSampleLog(Workspace=str(ws),
                             LogName='run_numbers',
                             LogText=fp_instance.run_numbers(string_representation='short'),
                             LogType='String')
            print('[DEBUG instrument.load_data] Workspace {} has {} events'.format(str(ws), ws.getNumberEvents()))
        return xs_list

    # TODO 64 - Implement (in progress) NEW of Task 64
    def load_merge_data(self, file_paths):
        """Load a data set according to the needs ot the instrument.
        Returns a WorkspaceGroup with any number of cross-sections.

        Parameters
        ----------
        file_paths: ~list
            list of file path

        Returns
        -------
        WorkspaceGroup
            with any number of cross-secitons

        """
        print('[DEBUG 64] Am I called? file paths: {}'.format(file_paths))

        # sanity check
        if not isinstance(file_paths, list):
            raise TypeError('Method load_merge_data accepts list (of file path) only but not {}'.format(file_paths))
        elif len(file_paths) < 2:
            raise NotImplementedError('Method load_merge_data only work on more than 1 file path.')

        # Be careful with legacy data
        is_legacy = file_paths[0].endswith(".nxs")
        if is_legacy or not USE_SLOW_FLIPPER_LOG:
            # TODO 64 FIXME 64 - Need test data for legacy data (can they be merged????)
            base_name = os.path.basename(file_path)
            _xs_list = api.MRFilterCrossSections(Filename=file_path,
                                                 PolState=self.pol_state,
                                                 AnaState=self.ana_state,
                                                 PolVeto=self.pol_veto,
                                                 AnaVeto=self.ana_veto,
                                                 CrossSectionWorkspaces="%s_entry" % base_name)
            # Only keep good workspaced and get rid of the rejected events
            xs_list = [ws for ws in _xs_list if not ws.getRun()['cross_section_id'].value == 'unfiltered']
        else:
            # Load first data file
            ws = api.LoadEventNexus(Filename=file_paths[0], OutputWorkspace="raw_events")
            for ipath in range(1, len(file_paths)):
                file_path = file_paths[ipath]
                ws_new = api.LoadEventNexus(Filename=file_path, OutputWorkspace="raw_events_merged")
                ws = ws + ws_new
            xs_list = self.dummy_filter_cross_sections(ws)

        return xs_list

    @classmethod
    def mid_q_value(cls, ws):
        """
            Get the mid q value, at the requested wl mid-point.
            This is used when sorting out data sets and doesn't need any overwrites.
            :param workspace ws: Mantid workspace
        """
        wl = ws.getRun().getProperty('LambdaRequest').value[0]
        theta_d = api.MRGetTheta(ws)
        return 4.0*math.pi*math.sin(theta_d) / wl

    @classmethod
    def scattering_angle_from_data(cls, data_object):
        """
            Compute the scattering angle from a CrossSectionData object, in degrees.
            @param data_object: CrossSectionData object
        """
        _dirpix = data_object.configuration.direct_pixel_overwrite if data_object.configuration.set_direct_pixel else None
        _dangle0 = data_object.configuration.direct_angle_offset_overwrite if data_object.configuration.set_direct_angle_offset else None

        return api.MRGetTheta(data_object.event_workspace,
                              SpecularPixel=data_object.configuration.peak_position,
                              DAngle0Overwrite=_dangle0,
                              DirectPixelOverwrite=_dirpix) * 180.0 / math.pi

    @classmethod
    def check_direct_beam(cls, ws):
        """
            Determine whether this data is a direct beam
        """
        try:
            return ws.getRun().getProperty("data_type").value[0] == 1
        except:
            return False

    def direct_beam_match(self, scattering, direct_beam, skip_slits=False):
        """
            Verify whether two data sets are compatible.
        """
        if math.fabs(scattering.lambda_center-direct_beam.lambda_center) < self.tolerance \
            and (skip_slits or \
            (math.fabs(scattering.slit1_width-direct_beam.slit1_width) < self.tolerance \
            and math.fabs(scattering.slit2_width-direct_beam.slit2_width) < self.tolerance \
            and math.fabs(scattering.slit3_width-direct_beam.slit3_width) < self.tolerance)):
            return True
        return False

    @classmethod
    def get_info(cls, workspace, data_object):
        """
            Retrieve information that is specific to this particular instrument

            @param workspace: Mantid workspace
            @param data_object: CrossSectionData object
        """
        data = workspace.getRun()
        data_object.lambda_center = data['LambdaRequest'].value[0]
        data_object.dangle = data['DANGLE'].getStatistics().mean
        if 'BL4A:Mot:S1:X:Gap' in data:
            data_object.slit1_width = data['BL4A:Mot:S1:X:Gap'].value[0]
            data_object.slit2_width = data['BL4A:Mot:S2:X:Gap'].value[0]
            data_object.slit3_width = data['BL4A:Mot:S3:X:Gap'].value[0]
        else:
            data_object.slit1_width = data['S1HWidth'].value[0]
            data_object.slit2_width = data['S2HWidth'].value[0]
            data_object.slit3_width = data['S3HWidth'].value[0]
        data_object.huber_x = data['HuberX'].getStatistics().mean

        data_object.sangle = data['SANGLE'].getStatistics().mean

        data_object.dist_sam_det = data['SampleDetDis'].value[0]*1e-3
        data_object.dist_mod_det = data['ModeratorSamDis'].value[0]*1e-3+data_object.dist_sam_det
        data_object.dist_mod_mon = data['ModeratorSamDis'].value[0]*1e-3-2.75

        # Get these from instrument
        data_object.pixel_width = float(workspace.getInstrument().getNumberParameter("pixel-width")[0]) / 1000.0
        data_object.n_det_size_x = int(workspace.getInstrument().getNumberParameter("number-of-x-pixels")[0]) # 304
        data_object.n_det_size_y = int(workspace.getInstrument().getNumberParameter("number-of-y-pixels")[0]) # 256
        data_object.det_size_x = data_object.n_det_size_x * data_object.pixel_width # horizontal size of detector [m]
        data_object.det_size_y = data_object.n_det_size_y * data_object.pixel_width # vertical size of detector [m]

        # The following active area used to be taken from instrument.DETECTOR_REGION
        data_object.active_area_x = (8, 295)
        data_object.active_area_y = (8, 246)

        # Convert to standard names
        data_object.direct_pixel = data['DIRPIX'].getStatistics().mean
        data_object.angle_offset = data['DANGLE0'].getStatistics().mean

        # Get proper cross-section label
        data_object.cross_section_label = get_cross_section_label(workspace, data_object.entry_name)
        try:
            data_object.is_direct_beam = data["data_type"].value[0] == 1
        except:
            data_object.is_direct_beam = False

    def integrate_detector(self, ws, specular=True):
        """
            Integrate a workspace along either the main direction (specular=False) or
            the low-resolution direction (specular=True.

            :param ws: Mantid workspace
            :param specular bool: if True, the low-resolution direction is integrated over
        """
        ws_summed = api.RefRoi(InputWorkspace=ws, IntegrateY=specular,
                               NXPixel=self.n_x_pixel, NYPixel=self.n_y_pixel,
                               ConvertToQ=False,
                               OutputWorkspace="ws_summed")

        integrated = api.Integration(ws_summed)
        integrated = api.Transpose(integrated)
        return integrated
