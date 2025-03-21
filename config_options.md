# Configuration Options

QuickNXS stores/reads configuration options in the `~/.quicknxs.conf` file.
By default, it only stores the `current_directory` and `output_directory` options.

If you would like to override the default options for QuickNXS, you can manually add them to the `~/.quicknxs.conf` file.
Available options are detailed in `quicknxs.interfaces.configuration.Configuration`, and are listed below.

### Q Settings:

| Name                          | Type    | Description                                                                                                         |
| ----------------------------- | ------- | ------------------------------------------------------------------------------------------------------------------- |
| use_roi                       | boolean | Use range of interest for ???                                                                                       |
| tof_bins                      | int     | Number of time-of-flight bins                                                                                       |
| tof_range                     | string  | Time-of-flight range, comma-separated start and stop, (ex. "11413.560217325685,45388.809236341694")                 |
| tof_bin_type                  | int     | Time-of-flight binning type (0 = Constant bin width, 1 = Constant Q-bin width, 2 = Constant 1/wavelength bin width) |
| update_peak_range             | boolean | ???                                                                                                                 |
| use_roi_bck                   | boolean | ???                                                                                                                 |
| use_tight_bck                 | boolean | ???                                                                                                                 |
| bck_offset                    | int     | ???                                                                                                                 |
| wl_bandwidth                  | float   | ???                                                                                                                 |
| --                            | --      | --                                                                                                                  |
| force_peak_roi                | boolean | ???                                                                                                                 |
| peak_roi                      | string  | ???, comma-separated start and stop (ex. "154,172")                                                                 |
| force_low_res_roi             | boolean | ???                                                                                                                 |
| low_res_roi                   | string  | ???, comma-separated start and stop (ex. "81,142")                                                                  |
| force_bck_roi                 | boolean | ???                                                                                                                 |
| bck_roi                       | string  | ???, comma-separated start and stop (ex. "11,67")                                                                   |
| --                            | --      | --                                                                                                                  |
| subtract_background           | boolean | ???                                                                                                                 |
| cut_first_n_points            | int     | ???                                                                                                                 |
| cut_last_n_points             | int     | ???                                                                                                                 |
| --                            | --      | --                                                                                                                  |
| normalize_to_unity            | boolean | Normalize to unity when stitching                                                                                   |
| total_reflectivity_q_cutoff   | float   | ???                                                                                                                 |
| global_stitching              | boolean | ???                                                                                                                 |
| polynomial_stitching          | boolean | ???                                                                                                                 |
| polynomial_stitching_degree   | int     | ???                                                                                                                 |
| polynomial_stitching_points   | int     | ???                                                                                                                 |
| --                            | --      | --                                                                                                                  |
| normalize_x_tof               | boolean | ???                                                                                                                 |
| x_wl_map                      | boolean | ???                                                                                                                 |
| angle_map                     | boolean | ???                                                                                                                 |
| log_1d                        | boolean | ???                                                                                                                 |
| log_2d                        | boolean | ???                                                                                                                 |
| --                            | --      | --                                                                                                                  |
| use_constant_q                | boolean | ???                                                                                                                 |
| use_dangle                    | boolean | ???                                                                                                                 |
| set_direct_pixel              | boolean | ???                                                                                                                 |
| direct_pixel_overwrite        | float   | ???                                                                                                                 |
| set_direct_angle_offset       | boolean | ???                                                                                                                 |
| direct_angle_offset_overwrite | float   | ???                                                                                                                 |
| sample_size                   | int     | ???                                                                                                                 |
| do_final_rebin                | boolean | ???                                                                                                                 |
| final_rebin_step              | float   | ???                                                                                                                 |
| do_final_rebin_run            | boolean | ???                                                                                                                 |
| final_rebin_step_run          | float   | ???                                                                                                                 |
| lock_direct_beam_y            | boolean | ???                                                                                                                 |
| Dead time options             | --      | --                                                                                                                  |
| apply_deadtime                | boolean | ???                                                                                                                 |
| paralyzable_deadtime          | boolean | ???                                                                                                                 |
| deadtime_value                | float   | ???                                                                                                                 |
| deadtime_tof_step             | int     | ???                                                                                                                 |
| --                            | --      | --                                                                                                                  |
| nbr_events_min                | int     | Minimum number of events required to keep a workspace                                                               |
| Off-specular options          | --      | --                                                                                                                  |
| off_spec_x_axis               | int     | ???                                                                                                                 |
| off_spec_slice                | boolean | ???                                                                                                                 |
| off_spec_qz_list              | string  | ???, comma-separated list of floats                                                                                 |
| off_spec_err_weight           | boolean | ???                                                                                                                 |
| off_spec_nxbins               | int     | ???                                                                                                                 |
| off_spec_nybins               | int     | ???                                                                                                                 |
| off_spec_slice_qz_min         | float   | ???                                                                                                                 |
| off_spec_slice_qz_max         | float   | ???                                                                                                                 |
| Off-specular smoothing        | --      | --                                                                                                                  |
| apply_smoothing               | boolean | ???                                                                                                                 |
| off_spec_sigmas               | int ??? | ???                                                                                                                 |
| off_spec_sigmax               | float   | ???                                                                                                                 |
| off_spec_sigmay               | float   | ???                                                                                                                 |
| off_spec_x_min                | float   | ???                                                                                                                 |
| off_spec_x_max                | float   | ???                                                                                                                 |
| off_spec_y_min                | float   | ???                                                                                                                 |
| off_spec_y_max                | float   | ???                                                                                                                 |
| GISANS options                | --      | --                                                                                                                  |
| gisans_wl_min                 | float   | ???                                                                                                                 |
| gisans_wl_max                 | float   | ???                                                                                                                 |
| gisans_wl_npts                | int     | ???                                                                                                                 |
| gisans_qy_npts                | int     | ???                                                                                                                 |
| gisans_qz_npts                | int     | ???                                                                                                                 |
| gisans_use_pf                 | boolean | ???                                                                                                                 |
| gisans_slice                  | boolean | ???                                                                                                                 |
| gisans_slice_qz_min           | float   | ???                                                                                                                 |
| gisans_slice_qz_max           | float   | ???                                                                                                                 |

### Reduction Settings:

| Name                  | Type    | Description                                    |
| --------------------- | ------- | ---------------------------------------------- |
| email_send            | boolean | Send email with results of reduction           |
| email_to              | string  | Email address(es) to send to (comma separated) |
| email_subject         | string  | Email subject                                  |
| email_cc              | string  | Email CC                                       |
| email_send_data       | boolean | Include data in email                          |
| email_send_plots      | boolean | Include plots in email                         |
| email_zip_data        | boolean | Zip data files                                 |
| export_asym           | boolean | Export spin-asymmetry                          |
| export_gisans         | boolean | Export GISANS data                             |
| export_offspec        | boolean | Export raw off-specular data                   |
| export_offspec_smooth | boolean | Export binned off-specular data                |
| export_specular       | boolean | Export specular reflectivity                   |
| format_5cols          | boolean | Include theta column in output file(s)         |
| format_mantid         | boolean | Export Mantid script                           |
| format_matlab         | boolean | Export Matlab file                             |
| format_numpy          | boolean | Export Numpy (.npz) file                       |
| output_file_template  | string  | Output file naming template                    |
