"""
    Data processing workflow, taking results and writing them to files.
"""
# pylint: disable=bare-except, too-many-locals

import sys
import os
import math
import copy
import logging
import time
import numpy as np

import smtplib
from email import encoders
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
import zipfile
import io

from ..configuration import Configuration
from . import quicknxs_io, data_manipulation, off_specular, gisans


DEFAULT_OPTIONS = dict(
    export_specular=True,
    export_asym=False,
    export_gisans=False,
    export_offspec=False,
    export_offspec_smooth=False,
    format_matlab=False,
    format_mantid=True,
    format_numpy=False,
    format_5cols=False,
    output_sample_size=10,
    output_directory="",
    output_file_template="{instrument}_{numbers}_{peak}_{item}_{state}.{type}",
    email_send=False,
    email_zip_data=False,
    email_send_plots=False,
    email_send_data=False,
    email_to="",
    email_cc="",
    email_subject="",
    email_test="",
)


class ProcessingWorkflow(object):
    """
    Carry out the reduction process for a set of data runs and manages outputs
    """

    def __init__(self, data_manager, output_options=None):
        """
        :param data_manager: all the reduced data shall come from data manager
        """
        self.data_manager = data_manager
        self.output_options = output_options if output_options else DEFAULT_OPTIONS
        self.exported_data_files = []
        self.exported_data_plots = []

    def execute(self, progress=None):
        """
        Process data and write output files
        :param ProgressReporter progress: reporter object
        """
        if not self.data_manager.reduction_states:
            return

        # store current peak shown in the UI
        active_peak = self.data_manager.active_reduction_list_index

        for peak_index in self.data_manager.peak_reduction_lists.keys():
            # set active data based on peak index
            self.data_manager.set_active_reduction_list_index(peak_index)
            self.data_manager.set_active_data_from_reduction_list(0)

            if self.output_options["export_specular"]:
                if progress is not None:
                    progress(10, "Computing reflectivity")
                self.specular_reflectivity()

            if self.output_options["export_offspec"] or self.output_options["export_offspec_smooth"]:
                if progress is not None:
                    progress(20, "Computing off-specular reflectivity")
                self.offspec(
                    raw=self.output_options["export_offspec"], binned=self.output_options["export_offspec_smooth"]
                )

            if progress is not None:
                progress(60, "Computing GISANS")
            if self.output_options["export_gisans"]:
                # FIXME 66 - could be an AttributeError from self.gisans().  Catch it!
                self.gisans(progress=progress)

        # restore current peak shown in the UI
        self.data_manager.set_active_reduction_list_index(active_peak)

        if self.output_options["email_send"]:
            self.send_email()

        if progress is not None:
            progress(100, "Complete")

    def get_file_name(self, run_list=None, pol_state=None, data_type="dat", process_type="Specular"):
        """
        Construct a file name according to the measurement type.
        :param list run_list: list of run numbers
        :param str pol_state: name for the polarization state
        :param str data_type: file extension
        :param str process_type: descriptor for the process type
        """
        if run_list is None:
            run_list = []
        base_name = self.output_options["output_file_template"].replace("{numbers}", "+".join(run_list))
        base_name = base_name.replace(
            "{instrument}", self.data_manager.active_channel.configuration.instrument.instrument_name
        )
        base_name = base_name.replace("{item}", process_type)
        if pol_state is not None:
            base_name = base_name.replace("{state}", pol_state)
        base_name = base_name.replace("{type}", data_type)
        base_name = base_name.replace("{peak}", f"peak{self.data_manager.active_reduction_list_index}")
        return os.path.join(self.output_options["output_directory"], base_name)

    def write_quicknxs(self, output_data, output_file_base, xs=None):
        """
        Write QuickNXS output reflectivity file.
        :param dict output_data: dictionary of numpy arrays
        :param str output_file_base: template for output file paths
        :param list xs: list of cross sections available in the output_data
        """
        # Get the column names
        units = output_data["units"]
        cols = output_data["columns"]
        col_names = ["%s [%s]" % (cols[i], units[i]) for i in range(len(cols))]

        # List of all output states we have to deal with
        if xs is not None:
            output_states = xs
        else:
            output_states = copy.copy(self.data_manager.reduction_states)
            if self.output_options["export_asym"] and "SA" in output_data:
                output_states.append("SA")

        # Sanity check
        if len(output_states) == 0:
            return

        # Write out the cross-section data
        five_cols = self.output_options["format_5cols"]
        for pol_state in output_states:
            # The cross-sections might have different names
            if pol_state in self.data_manager.reduction_list[0].cross_sections:
                _pol_state = self.data_manager.reduction_list[0].cross_sections[pol_state].cross_section_label
            else:
                _pol_state = pol_state
            # We might not have data for a given cross-section
            if pol_state not in output_data:
                continue

            state_output_path = output_file_base.replace("{state}", pol_state)
            quicknxs_io.write_reflectivity_header(
                self.data_manager.peak_reduction_lists,
                self.data_manager.active_reduction_list_index,
                self.data_manager.direct_beam_list,
                state_output_path,
                _pol_state,
            )
            quicknxs_io.write_reflectivity_data(
                state_output_path, output_data[pol_state], col_names, as_5col=five_cols
            )
            self.exported_data_files.append(state_output_path)

    def specular_reflectivity(self):
        """
        Retrieve the computed reflectivity and save it to file
        """
        # The reflectivity should always be up to date, so we don't need to recalculate it.
        # The following would be used to recalculate it:
        #    self.data_manager.calculate_reflectivity(specular=True)

        # self.data_manager.merge_data_sets(asymmetry=self.output_options['export_asym'])

        run_list = [str(item.number) for item in self.data_manager.reduction_list]

        output_data = self.get_output_data()

        # QuickNXS format
        output_file_base = self.get_file_name(run_list)
        self.write_quicknxs(output_data, output_file_base)

        # Numpy arrays
        if self.output_options["format_numpy"]:
            output_file = self.get_file_name(run_list, data_type="npz", pol_state="all")
            np.savez(output_file, **output_data)
            self.exported_data_files.append(output_file)

        # Matlab output
        if self.output_options["format_matlab"]:
            try:
                from scipy.io import savemat

                output_file = self.get_file_name(run_list, data_type="mat", pol_state="all")
                savemat(output_file, output_data, oned_as="column")
                self.exported_data_files.append(output_file)
            except:
                logging.error("Could not save in matlab format: %s", sys.exc_info([1]))

        if self.output_options["format_mantid"]:
            output_file = self.get_file_name(run_list, data_type="py", pol_state="all")
            script = data_manipulation.generate_short_script(self.data_manager.reduction_list)
            with open(output_file, "w") as file_object:
                file_object.write(script)
            self.exported_data_files.append(output_file)

    def gisans(self, progress=None):
        """
        Export GISANS.
        """
        run_list = [str(item.number) for item in self.data_manager.reduction_list]

        # Refresh the reflectivity calculation
        if progress is not None:
            progress(65, "Reducing GISANS...")

        self.data_manager.cached_gisans = None
        self.data_manager.reduce_gisans(progress=None)

        if progress is not None:
            progress(75, "Binning GISANS...")

        data_dict, slice_data_dict = self.get_gisans_data(progress=None)
        self.data_manager.cached_gisans = data_dict

        if progress is not None:
            progress(90, "Writing data")

        output_file_base = self.get_file_name(run_list, process_type="GISANS")
        self.write_quicknxs(data_dict, output_file_base, xs=data_dict["cross_sections"].keys())

        # Write out slice data
        if slice_data_dict is not None and "cross_sections" in slice_data_dict:
            output_file_base = self.get_file_name(run_list, process_type="GISANSSlice")
            self.write_quicknxs(slice_data_dict, output_file_base, xs=slice_data_dict["cross_sections"].keys())

        if progress is not None:
            progress(100, "GISANS complete")

    def offspec(self, raw=True, binned=False):
        """
        Export off-specular reflectivity.
        :param bool raw: if true, the raw results will be saved
        :param bool binned: if true, the raw results will be binned and saved
        """
        run_list = [str(item.number) for item in self.data_manager.reduction_list]

        # Refresh the reflectivity calculation
        self.data_manager.cached_offspec = None
        self.data_manager.reduce_offspec()

        if raw or binned:
            output_data = self.get_offspec_data()
        # Export raw result
        if raw:
            # QuickNXS format
            output_file_base = self.get_file_name(run_list, process_type="OffSpec")
            self.write_quicknxs(output_data, output_file_base)

        # Export binned result
        if binned:
            if self.data_manager.active_channel.configuration.apply_smoothing:
                # "Smooth" version
                try:
                    smooth_output, slice_data_dict = self.smooth_offspec(output_data)
                    output_file_base = self.get_file_name(run_list, process_type="OffSpecSmooth")
                    self.write_quicknxs(smooth_output, output_file_base)
                    if slice_data_dict is not None and "cross_sections" in slice_data_dict:
                        output_file_base = self.get_file_name(run_list, process_type="OffSpecSmoothSlice")
                        self.write_quicknxs(
                            slice_data_dict, output_file_base, xs=slice_data_dict["cross_sections"].keys()
                        )
                    self.data_manager.cached_offspec = smooth_output
                except:
                    raise
                    logging.error("Problem writing smooth off-spec output")
            else:
                # Binned version
                binned_data, slice_data_dict = self.get_rebinned_offspec_data()
                # QuickNXS format ['smooth' is an odd name but we keep it for backward compatibility]
                output_file_base = self.get_file_name(run_list, process_type="OffSpecBinned")
                self.write_quicknxs(binned_data, output_file_base)
                if slice_data_dict is not None and "cross_sections" in slice_data_dict:
                    output_file_base = self.get_file_name(run_list, process_type="OffSpecSlice")
                    self.write_quicknxs(slice_data_dict, output_file_base, xs=slice_data_dict["cross_sections"].keys())
                self.data_manager.cached_offspec = binned_data

    def get_rebinned_offspec_data(self):
        """
        Get a data dictionary ready for saving
        """
        data_dict = None
        slice_data_dict = {}

        # Extract common information
        if len(self.data_manager.reduction_states) == 0:
            logging.error("List of cross-sections is empty")
            return {}

        for pol_state in self.data_manager.reduction_states:
            r, dr, x, y, labels = off_specular.rebin_extract(
                self.data_manager.reduction_list,
                pol_state,
                axes=self.data_manager.active_channel.configuration.off_spec_x_axis,
                use_weights=self.data_manager.active_channel.configuration.off_spec_err_weight,
                n_bins_x=self.data_manager.active_channel.configuration.off_spec_nxbins,
                n_bins_y=self.data_manager.active_channel.configuration.off_spec_nybins,
                x_min=self.data_manager.active_channel.configuration.off_spec_x_min,
                x_max=self.data_manager.active_channel.configuration.off_spec_x_max,
                y_min=self.data_manager.active_channel.configuration.off_spec_y_min,
                y_max=self.data_manager.active_channel.configuration.off_spec_y_max,
            )
            if data_dict is None:
                data_dict = dict(
                    units=["1/A", "1/A", "a.u.", "a.u."], columns=[labels[0], labels[1], "I", "dI"], cross_sections={}
                )

            # Create array of x-values
            x_tiled = np.tile(x, len(y))
            x_tiled = x_tiled.reshape([len(y), len(x)])

            # Create array of y-values
            y_tiled = np.tile(y, len(x))
            y_tiled = y_tiled.reshape([len(x), len(y)])
            y_tiled = y_tiled.T

            rdata = np.array([x_tiled, y_tiled, r, dr]).transpose((1, 2, 0))

            if pol_state in self.data_manager.reduction_list[0].cross_sections:
                _pol_state = self.data_manager.reduction_list[0].cross_sections[pol_state].cross_section_label
            else:
                _pol_state = pol_state
            data_dict[pol_state] = [np.nan_to_num(rdata)]
            data_dict["cross_sections"][pol_state] = _pol_state

            # Slices
            slice_data_dict = self.get_slice_output_data(x, y, r, dr, pol_state, labels[1], **slice_data_dict)

        return data_dict, slice_data_dict

    def get_gisans_data(self, progress=None):
        wl_npts = self.data_manager.active_channel.configuration.gisans_wl_npts
        wl_min = self.data_manager.active_channel.configuration.gisans_wl_min
        wl_max = self.data_manager.active_channel.configuration.gisans_wl_max
        qy_npts = self.data_manager.active_channel.configuration.gisans_qy_npts
        qz_npts = self.data_manager.active_channel.configuration.gisans_qz_npts
        use_pf = self.data_manager.active_channel.configuration.gisans_use_pf

        data_dict = dict(units=["1/A", "1/A", "a.u.", "a.u."], cross_sections={}, cross_section_bins={})
        if use_pf:
            data_dict["columns"] = ["Qy", "pf", "I", "dI"]
        else:
            data_dict["columns"] = ["Qy", "Qz", "I", "dI"]

        # Extract common information
        if not self.data_manager.reduction_states or not self.data_manager.reduction_list:
            logging.error("List of cross-sections is empty")
            return data_dict

        t_0 = time.time()
        _parallel = False
        slice_data_dict = {}
        for pol_state in self.data_manager.reduction_states:
            if _parallel:
                binned_data = gisans.rebin_parallel(
                    self.data_manager.reduction_list,
                    pol_state,
                    wl_min=wl_min,
                    wl_max=wl_max,
                    wl_npts=wl_npts,
                    qy_npts=qy_npts,
                    qz_npts=qz_npts,
                    use_pf=use_pf,
                )
            data_dict["cross_section_bins"][pol_state] = []
            for i in range(wl_npts):
                wl_step = (wl_max - wl_min) / wl_npts
                _wl_min = wl_min + i * wl_step
                _wl_max = wl_min + (i + 1) * wl_step
                if _parallel:
                    _intensity, _qy, _qz_axis, _intensity_err = binned_data[i]
                else:
                    _intensity, _qy, _qz_axis, _intensity_err = self.data_manager.rebin_gisans(
                        pol_state, wl_min=_wl_min, wl_max=_wl_max, qy_npts=qy_npts, qz_npts=qz_npts, use_pf=use_pf
                    )

                qz, qy = np.meshgrid(_qz_axis, _qy)
                rdata = np.array([qy, qz, _intensity, _intensity_err]).transpose((1, 2, 0))

                if pol_state in self.data_manager.reduction_list[0].cross_sections:
                    _pol_state = self.data_manager.reduction_list[0].cross_sections[pol_state].cross_section_label
                else:
                    _pol_state = pol_state

                _pol_state = "%.3f-%.3f_%s" % (_wl_min, _wl_max, pol_state)
                _pol_state_clean = "%.3f-%.3f_%s" % (_wl_min, _wl_max, _pol_state)
                data_dict[_pol_state] = [np.nan_to_num(rdata)]
                data_dict["cross_sections"][_pol_state] = _pol_state_clean
                data_dict["cross_section_bins"][pol_state].append(_pol_state)

                # Slices
                label = "pf" if use_pf else "Qz"
                slice_data_dict = self.get_gisans_slice_output_data(
                    _qy, _qz_axis, _intensity.T, _intensity_err.T, _pol_state, label, **slice_data_dict
                )

        logging.info("GISANS processing time: %s sec", (time.time() - t_0))
        return data_dict, slice_data_dict

    def get_offspec_data(self):
        """
        Get a data dictionary ready for saving
        """
        data_dict = dict(
            units=["1/A", "1/A", "1/A", "1/A", "1/A", "a.u.", "a.u."],
            columns=["Qx", "Qz", "ki_z", "kf_z", "ki_z-kf_z", "I", "dI"],
            cross_sections={},
        )

        # Extract common information
        if not self.data_manager.reduction_states or not self.data_manager.reduction_list:
            logging.error("List of cross-sections is empty")
            return data_dict

        first_state = self.data_manager.reduction_states[0]
        p_0 = [
            item.cross_sections[first_state].configuration.cut_first_n_points
            for item in self.data_manager.reduction_list
        ]
        p_n = [
            item.cross_sections[first_state].configuration.cut_last_n_points
            for item in self.data_manager.reduction_list
        ]

        ki_max = 0.01
        for pol_state in self.data_manager.reduction_states:
            # The scaling factors should have been determined at this point. Just use them
            # to merge the different runs in a set.

            combined_data = []

            for item in self.data_manager.reduction_list:
                offspec = item.cross_sections[pol_state].off_spec
                Qx, Qz, ki_z, kf_z, S, dS = (offspec.Qx, offspec.Qz, offspec.ki_z, offspec.kf_z, offspec.S, offspec.dS)

                n_total = len(S[0])
                # P_0 and P_N are the number of points to cut in TOF on each side
                p_0 = item.cross_sections[pol_state].configuration.cut_first_n_points
                p_n = n_total - item.cross_sections[pol_state].configuration.cut_last_n_points

                rdata = np.array(
                    [
                        Qx[:, p_0:p_n],
                        Qz[:, p_0:p_n],
                        ki_z[:, p_0:p_n],
                        kf_z[:, p_0:p_n],
                        ki_z[:, p_0:p_n] - kf_z[:, p_0:p_n],
                        S[:, p_0:p_n],
                        dS[:, p_0:p_n],
                    ]
                ).transpose((1, 2, 0))
                combined_data.append(rdata)
                ki_max = max(ki_max, ki_z.max())

            if pol_state in self.data_manager.reduction_list[0].cross_sections:
                _pol_state = self.data_manager.reduction_list[0].cross_sections[pol_state].cross_section_label
            else:
                _pol_state = pol_state
            data_dict[pol_state] = combined_data
            data_dict["cross_sections"][pol_state] = _pol_state
        data_dict["ki_max"] = ki_max
        return data_dict

    def smooth_offspec(self, data_dict):
        """
        NOTE:

        Create a smoothed dataset from the off-specular scattering.
        :param dict data_dict: the output of get_offspec_data()

        Note for my own integrity (MD):
           I don't think one should smooth data distributions and do any quantitative
           work with it following this process. The way this was implemented in the
           previouse QuickNXS, replicated here, is equivalent to adding an extra resolution,
           which then would have to be properly taken into account when fitting.
           In addition, the process doesn't produce errors in intensity.
           It effectively only produces a pretty picture and should only be used as such.
        """
        axes = self.data_manager.active_channel.configuration.off_spec_x_axis
        output_data = dict(cross_sections=dict())
        slice_data_dict = {}

        for channel in data_dict["cross_sections"].keys():
            data = np.hstack(data_dict[channel])
            I = data[:, :, 5].flatten()
            Qzmax = data[:, :, 2].max() * 2.0
            y_label = "Qz"
            if axes == Configuration.QX_VS_QZ:
                x = data[:, :, 0].flatten()
                y = data[:, :, 1].flatten()
                output_data["units"] = ["1/A", "1/A", "a.u."]
                output_data["columns"] = ["Qx", "Qz", "I"]
                axis_sigma_scaling = 2
                xysigma0 = Qzmax / 3.0
            elif axes == Configuration.KZI_VS_KZF:
                y_label = "kf_z"
                x = data[:, :, 2].flatten()
                y = data[:, :, 3].flatten()
                output_data["units"] = ["1/A", "1/A", "a.u."]
                output_data["columns"] = ["ki_z", "kf_z", "I"]
                axis_sigma_scaling = 3
                xysigma0 = Qzmax / 6.0
            else:
                x = data[:, :, 4].flatten()
                y = data[:, :, 1].flatten()
                output_data["units"] = ["1/A", "1/A", "a.u."]
                output_data["columns"] = ["ki_z-kf_z", "Qz", "I"]
                axis_sigma_scaling = 2
                xysigma0 = Qzmax / 3.0

            x, y, I = off_specular.smooth_data(
                x,
                y,
                I,
                sigmas=self.output_options["off_spec_sigmas"],
                gridx=self.output_options["off_spec_nxbins"],
                gridy=self.output_options["off_spec_nybins"],
                sigmax=self.output_options["off_spec_sigmax"],
                sigmay=self.output_options["off_spec_sigmay"],
                x1=self.output_options["off_spec_x_min"],
                x2=self.output_options["off_spec_x_max"],
                y1=self.output_options["off_spec_y_min"],
                y2=self.output_options["off_spec_y_max"],
                axis_sigma_scaling=axis_sigma_scaling,
                xysigma0=xysigma0,
            )
            output_data[channel] = [np.array([x, y, I]).transpose((1, 2, 0))]
            output_data["cross_sections"][channel] = data_dict["cross_sections"][channel]

            # Slices
            slice_data_dict = self.get_slice_output_data(x[0], y.T[0], I, None, channel, y_label, **slice_data_dict)

        output_data["ki_max"] = data_dict["ki_max"]
        return output_data, slice_data_dict

    def get_slice_output_data(self, qx, qz, r, dr, pol_state, label, **slice_data_dict):
        """
        Produce a data dictionary with a slice of the data.
        """
        if slice_data_dict == {}:
            slice_data_dict = dict(units=["1/A", "a.u.", "a.u."], columns=[label, "I", "dI"], cross_sections={})

        q_min = self.data_manager.active_channel.configuration.off_spec_slice_qz_min
        q_max = self.data_manager.active_channel.configuration.off_spec_slice_qz_max
        result, error = off_specular.get_slice(qz, r, dr, q_min, q_max)
        if error is not None:
            # Is x what we need here, or the middle of the bin
            _to_save = np.asarray([qx, result, error]).T
        else:
            _to_save = np.asarray([qx, result]).T
        slice_label = "%s_%s_%s-%s" % (pol_state, label, q_min, q_max)
        slice_data_dict["cross_sections"][slice_label] = slice_label
        slice_data_dict[slice_label] = _to_save
        return slice_data_dict

    def get_gisans_slice_output_data(self, qy, qz, r, dr, pol_state, label, **slice_data_dict):
        """
        Produce a data dictionary with a slice of the data.
        """
        if slice_data_dict == {}:
            slice_data_dict = dict(units=["1/A", "a.u.", "a.u."], columns=[label, "I", "dI"], cross_sections={})

        q_min = self.data_manager.active_channel.configuration.gisans_slice_qz_min
        q_max = self.data_manager.active_channel.configuration.gisans_slice_qz_max

        # We can use the off-specular get_slice() function because it's not specific to off-specular
        result, error = off_specular.get_slice(qz, r, dr, q_min, q_max)

        if error is not None:
            # Is x what we need here, or the middle of the bin
            _to_save = np.asarray([qy, result, error]).T
        else:
            _to_save = np.asarray([qy, result]).T
        slice_label = "%s_%s_%s-%s" % (pol_state, label, q_min, q_max)
        slice_data_dict["cross_sections"][slice_label] = slice_label
        slice_data_dict[slice_label] = _to_save
        return slice_data_dict

    def get_output_data(self):
        """
        The QuickNXS format cannot be written from the merged reflectivity, so we
        have to treat it differently and give it the workspaces for each angle.
        """
        data_dict = dict(
            units=["1/A", "a.u.", "a.u.", "1/A", "rad"], columns=["Qz", "R", "dR", "dQz", "theta"], cross_sections={}
        )

        # Extract common information
        if not self.data_manager.reduction_states or not self.data_manager.reduction_list:
            logging.error("List of cross-sections is empty")
            return data_dict
        first_state = self.data_manager.reduction_states[0]
        p_0 = [
            item.cross_sections[first_state].configuration.cut_first_n_points
            for item in self.data_manager.reduction_list
        ]
        p_n = [
            item.cross_sections[first_state].configuration.cut_last_n_points
            for item in self.data_manager.reduction_list
        ]

        for pol_state in self.data_manager.reduction_states:
            # The scaling factors should have been determined at this point. Just use them
            # to merge the different runs in a set.
            ws_list = data_manipulation.get_scaled_workspaces(self.data_manager.reduction_list, pol_state)

            # If the reflectivity calculation failed, we may not have data to work with
            # for this cross-section.
            if len(ws_list) == 0:
                continue

            combined_data = []
            for i, ws in enumerate(ws_list):
                _x = ws.readX(0)
                n_total = len(_x)
                x = ws.readX(0)[p_0[i] : n_total - p_n[i]]
                y = ws.readY(0)[p_0[i] : n_total - p_n[i]]
                dy = ws.readE(0)[p_0[i] : n_total - p_n[i]]
                dx = ws.readDx(0)[p_0[i] : n_total - p_n[i]]
                # This should be actual theta calculated
                tth_value = ws.getRun().getProperty("two_theta").value / 2.0 * np.pi / 180.0
                # tth_value = ws.getRun().getProperty("SANGLE").getStatistics().mean * math.pi / 180.0
                tth = np.ones(len(x)) * tth_value
                combined_data.append(np.vstack((x, y, dy, dx, tth)).transpose())

            _output_data = np.vstack(combined_data)
            ordered = np.argsort(_output_data, axis=0).transpose()[0]
            output_data = _output_data[ordered]

            if pol_state in self.data_manager.reduction_list[0].cross_sections:
                _pol_state = self.data_manager.reduction_list[0].cross_sections[pol_state].cross_section_label
            else:
                _pol_state = pol_state
            data_dict[pol_state] = output_data
            data_dict["cross_sections"][pol_state] = _pol_state

        # Asymmetry
        if self.output_options["export_asym"]:
            p_state, m_state = self.data_manager.determine_asymmetry_states()
            if p_state and m_state:
                # Get the list of workspaces
                asym_data = []
                if p_state in data_dict and m_state in data_dict:
                    # Sometimes the number of points may be different if the last few points had no signal.
                    for i in range(len(data_dict[p_state])):
                        p_point = data_dict[p_state][i]
                        i_m = len(data_dict[m_state][data_dict[m_state].T[0] < p_point[0]])
                        if i_m < len(data_dict[m_state]):
                            m_point = data_dict[m_state][i_m]
                            if p_point[1] > 0 and m_point[1] > 0:
                                ratio = (p_point[1] - m_point[1]) / (p_point[1] + m_point[1])
                                d_ratio = 2.0 / (p_point[1] + m_point[1]) ** 2
                                d_ratio *= math.sqrt(
                                    m_point[1] ** 2 * p_point[2] ** 2 + p_point[1] ** 2 * m_point[2] ** 2
                                )
                                asym_data.append([p_point[0], ratio, d_ratio, p_point[3], p_point[4]])
                    data_dict["SA"] = np.asarray(asym_data)
                else:
                    logging.error(
                        "Asym request but failed: %s %s %s %s",
                        p_state,
                        m_state,
                        len(data_dict[p_state]),
                        len(data_dict[m_state]),
                    )

        return data_dict

    def _email_replace(self, text):
        """
        Replace token templates in text
        """
        run_list = [str(item.number) for item in self.data_manager.reduction_list]
        return (
            text.replace("{ipts}", "")
            .replace("{numbers}", "+".join(run_list))
            .replace("{instrument}", self.data_manager.active_channel.configuration.instrument.instrument_name)
        )

    def send_email(self):
        """
        Collect all files and send them to the user via smtp mail.
        #TODO: Put smtp server info in config file.
        """
        SMTP_SERVER = "160.91.4.26"
        msg = MIMEMultipart()
        msg["Subject"] = self._email_replace(self.output_options["email_subject"])
        msg["From"] = "BL4A@ornl.gov"
        msg["To"] = self.output_options["email_to"].replace(";", ", ")
        msg["CC"] = self.output_options["email_cc"].replace(";", ", ")
        text = self._email_replace(self.output_options["email_text"])
        msg.preamble = text
        msg.attach(MIMEText(text))

        if self.output_options["email_send_data"]:
            exported_files = self.exported_data_files
        elif self.output_options["email_send_plots"]:
            exported_files = self.exported_data_plots
        else:
            exported_files = self.exported_data_files
            exported_files.extend(self.exported_data_plots)
        if self.output_options["email_zip_data"]:
            # Create an in-memory zip file which gets attached to the mail
            fobj = io.BytesIO()
            _file = zipfile.ZipFile(fobj, "w", zipfile.ZIP_DEFLATED)
            for item in exported_files:
                _file.write(item, arcname=os.path.basename(item))
            _file.close()
            fobj.seek(0)
            mitem = MIMEBase("application", "zip")
            mitem.set_payload(fobj.read())
            encoders.encode_base64(mitem)
            mitem.add_header(
                "Content-Disposition", "attachment", filename=self._email_replace("results_{numbers}.zip")
            )
            msg.attach(mitem)
        else:
            # read each file, which was exported and attach it to the mail
            for item in exported_files:
                try:
                    if item.endswith(".png"):
                        mitem = MIMEImage(open(item, "r").read(), "png")
                    elif item.endswith(".pdf"):
                        mitem = MIMEText(open(item, "r").read(), "pdf")
                    elif item.endswith(".dat") or item.endswith(".gp"):
                        mitem = MIMEText(open(item, "r").read())
                    else:
                        mitem = MIMEBase("application", item[-3:])
                        mitem.set_payload(open(item, "r").read())
                        encoders.encode_base64(mitem)
                except:
                    logging.error("Could not package files for email: %s", sys.exc_info()[1])
                mitem.add_header("Content-Disposition", "attachment", filename=os.path.basename(item))
                msg.attach(mitem)

        try:
            smtp = smtplib.SMTP(SMTP_SERVER, timeout=10)
            to_addr = msg["To"].replace(",", ";") + ";" + msg["CC"].replace(",", ";")
            smtp.sendmail(msg["From"], to_addr, msg.as_string())
            smtp.quit()
        except:
            logging.error("Could not send email: %s", sys.exc_info()[1])
