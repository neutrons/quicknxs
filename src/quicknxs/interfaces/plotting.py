# -*- coding: utf-8 -*-
# pylint: bare-except

# local imports
# standard imports
import logging
import sys

# third-party imports
import numpy as np

from quicknxs.interfaces.data_handling.data_set import CrossSectionData


class PlotManager(object):
    _refl_color_list = ["blue", "red", "green", "purple", "#aaaa00", "cyan"]

    def __init__(self, main_window):
        self.main_window = main_window
        self.overview_lines = None
        self._x_projection = None
        self._y_projection = None
        self.proj_lines = None
        self.y_bg = 0.0
        self.color = None

        # Selection lines
        self.xy_x1 = None
        self.xy_x2 = None
        self.xy_y1 = None
        self.xy_y2 = None

        self.xtof_x1 = None
        self.xtof_x2 = None
        self.xtof_bck1 = None
        self.xtof_bck2 = None

    def plot_overview(self):
        """
        X vs. Y and X vs. Tof for main channel.
        """
        self.xy_x1 = None
        self.xy_x2 = None
        self.xy_y1 = None
        self.xy_y2 = None
        self.xtof_x1 = None
        self.xtof_x2 = None
        self.xtof_bck1 = None
        self.xtof_bck2 = None
        main_window = self.main_window
        main_window.ui.xy_overview.clear()
        main_window.ui.xtof_overview.clear()

        data: CrossSectionData = main_window.data_manager.active_channel
        # Initialize data as needed
        data.prepare_plot_data()

        if data.total_counts == 0:
            main_window.ui.xy_overview.draw()
            main_window.ui.xtof_overview.draw()
            return

        xy = data.xydata
        if data.proton_charge > 0.0:
            xtof = data.xtofdata / data.proton_charge
        else:
            logging.error("Empty reflectivity curve has no proton charge")
            xtof = data.xtofdata

        if len(xtof[xtof > 0]) == 0:
            logging.error("No positive data found")
            return

        ref_norm = main_window.getNorm()
        if main_window.ui.normalizeXTof.isChecked() and ref_norm is not None:
            ref_norm = ref_norm.get_counts_vs_TOF()
            # normalize ToF dataset for wavelength distribution
            ref_norm = np.where(ref_norm > 0.0, ref_norm, 1.0)
            xtof = xtof.astype(float) / ref_norm[np.newaxis, :]
        xy_imin = xy[xy > 0].min()
        xy_imax = xy.max()
        tof_imin = xtof[xtof > 0].min()
        tof_imax = xtof.max()

        # for lines of the current extraction area
        x_peak = main_window.ui.refXPos.value()
        x_width = main_window.ui.refXWidth.value()
        y_pos = main_window.ui.refYPos.value()
        y_width = main_window.ui.refYWidth.value()
        bg_pos = main_window.ui.bgCenter.value()
        bg_width = main_window.ui.bgWidth.value()

        # XY plot
        if main_window.ui.tthPhi.isChecked():
            rad_per_pixel = data.det_size_x / data.dist_sam_det / data.xydata.shape[1]
            phi_range = xy.shape[0] * rad_per_pixel * 180.0 / np.pi
            tth_range = xy.shape[1] * rad_per_pixel * 180.0 / np.pi
            phi0 = main_window.ui.refYPos.value() * rad_per_pixel * 180.0 / np.pi
            tth0 = (data.dangle - data.angle_offset) - (xy.shape[1] - data.dpix) * rad_per_pixel * 180.0 / np.pi
            main_window.ui.xy_overview.imshow(
                xy,
                log=main_window.ui.logarithmic_colorscale.isChecked(),
                aspect="auto",
                cmap=self.color,
                origin="lower",
                extent=[tth_range + tth0, tth0, phi0, phi0 - phi_range],
            )
            main_window.ui.xy_overview.set_xlabel("2$\\Theta{}$ [°]")
            main_window.ui.xy_overview.set_ylabel("$\\phi{}$ [°]")
            main_window.ui.xy_overview.cplot.set_clim([xy_imin, xy_imax])
        else:
            main_window.ui.xy_overview.imshow(
                xy,
                log=main_window.ui.logarithmic_colorscale.isChecked(),
                aspect="auto",
                cmap=self.color,
                origin="lower",
            )
            main_window.ui.xy_overview.set_xlabel("x [pix]")
            main_window.ui.xy_overview.set_ylabel("y [pix]")
            main_window.ui.xy_overview.cplot.set_clim([xy_imin, xy_imax])

            if self.xy_x1 is None:
                self.xy_x1 = main_window.ui.xy_overview.canvas.ax.axvline(x_peak - (x_width / 2.0), color="#aa0000")
                self.xy_x2 = main_window.ui.xy_overview.canvas.ax.axvline(x_peak + (x_width / 2.0), color="#aa0000")
                self.xy_y1 = main_window.ui.xy_overview.canvas.ax.axhline(y_pos - (y_width / 2.0), color="#00aa00")
                self.xy_y2 = main_window.ui.xy_overview.canvas.ax.axhline(y_pos + (y_width / 2.0), color="#00aa00")
            else:
                self.xy_x1.set_xdata([x_peak - (x_width / 2.0), x_peak - (x_width / 2.0)])
                self.xy_x2.set_xdata([x_peak + (x_width / 2.0), x_peak + (x_width / 2.0)])
                self.xy_y1.set_ydata([y_pos - (y_width / 2.0), y_pos - (y_width / 2.0)])
                self.xy_y2.set_ydata([y_pos + (y_width / 2.0), y_pos + (y_width / 2.0)])

        # XToF plot
        if main_window.ui.xLamda.isChecked():
            main_window.ui.xtof_overview.imshow(
                xtof[::-1],
                log=main_window.ui.logarithmic_colorscale.isChecked(),
                aspect="auto",
                cmap=self.color,
                extent=[data.wavelength[0], data.wavelength[-1], 0, data.x.shape[0] - 1],
            )
            main_window.ui.xtof_overview.set_xlabel("$\\lambda{}$ [Å]")
        else:
            main_window.ui.xtof_overview.imshow(
                xtof[::-1],
                log=main_window.ui.logarithmic_colorscale.isChecked(),
                aspect="auto",
                cmap=self.color,
                extent=[data.tof[0] * 1e-3, data.tof[-1] * 1e-3, 0, data.x.shape[0] - 1],
            )
            main_window.ui.xtof_overview.set_xlabel("ToF [ms]")
        main_window.ui.xtof_overview.set_ylabel("x [pix]")

        if self.xtof_x1 is None:
            self.xtof_x1 = main_window.ui.xtof_overview.canvas.ax.axhline(x_peak - (x_width / 2.0), color="#aa0000")
            self.xtof_x2 = main_window.ui.xtof_overview.canvas.ax.axhline(x_peak + (x_width / 2.0), color="#aa0000")
            self.xtof_bck1 = main_window.ui.xtof_overview.canvas.ax.axhline(bg_pos - (bg_width / 2.0), color="black")
            self.xtof_bck2 = main_window.ui.xtof_overview.canvas.ax.axhline(bg_pos + (bg_width / 2.0), color="black")
        else:
            self.xtof_x1.set_ydata([x_peak - (x_width / 2.0), x_peak - (x_width / 2.0)])
            self.xtof_x2.set_ydata([x_peak + (x_width / 2.0), x_peak + (x_width / 2.0)])
            self.xtof_bck1.set_ydata([bg_pos - (bg_width / 2.0), bg_pos - (bg_width / 2.0)])
            self.xtof_bck2.set_ydata([bg_pos + (bg_width / 2.0), bg_pos + (bg_width / 2.0)])

        main_window.ui.xtof_overview.cplot.set_clim([tof_imin, tof_imax])

        if main_window.ui.show_colorbars.isChecked() and main_window.ui.xy_overview.cbar is None:
            main_window.ui.xy_overview.cbar = main_window.ui.xy_overview.canvas.fig.colorbar(
                main_window.ui.xy_overview.cplot
            )
            main_window.ui.xtof_overview.cbar = main_window.ui.xtof_overview.canvas.fig.colorbar(
                main_window.ui.xtof_overview.cplot
            )
        main_window.ui.xy_overview.draw()
        main_window.ui.xtof_overview.draw()

    def plot_xy(self):
        """
        X vs. Y plots for all channels.
        """
        main_window = self.main_window
        data_set_keys = list(main_window.data_manager.data_sets.keys())
        plots = [main_window.ui.xy_pp, main_window.ui.xy_mm, main_window.ui.xy_pm, main_window.ui.xy_mp]
        for i in range(len(data_set_keys), 4):
            if plots[i].cplot is not None:
                plots[i].clear()
                plots[i].draw()
        imin = 1e20
        imax = 1e-20
        xynormed = []

        progress = self.main_window.file_handler.new_progress_reporter()
        n_total = len(data_set_keys)
        progress(0.1, message="Compiling plots", out_of=n_total + 1)
        for i, key in enumerate(data_set_keys[:4]):
            dataset = main_window.data_manager.data_sets[key]
            dataset.prepare_plot_data()
            d = dataset.xydata / dataset.proton_charge
            xynormed.append(d)
            if dataset.total_counts == 0:
                continue
            imin = min(imin, d[d > 0].min())
            imax = max(imax, d.max())
            progress(i, message="Prepared %s plot" % key, out_of=n_total + 1)

        if len(xynormed) > 1:
            main_window.ui.frame_xy_mm.show()
            if len(xynormed) == 4:
                main_window.ui.frame_xy_sf.show()
            else:
                main_window.ui.frame_xy_sf.hide()
        else:
            main_window.ui.frame_xy_mm.hide()
            main_window.ui.frame_xy_sf.hide()

        progress(n_total, message="Plotting...", out_of=n_total + 1)
        for i, datai in enumerate(xynormed):
            if main_window.data_manager.data_sets[data_set_keys[i]].total_counts == 0:
                continue
            if main_window.ui.tthPhi.isChecked():
                plots[i].clear()
                rad_per_pixel = dataset.det_size_x / dataset.dist_sam_det / dataset.xydata.shape[1]
                phi_range = datai.shape[0] * rad_per_pixel * 180.0 / np.pi
                tth_range = datai.shape[1] * rad_per_pixel * 180.0 / np.pi
                phi0 = main_window.ui.refYPos.value() * rad_per_pixel * 180.0 / np.pi
                tth0 = (dataset.dangle - dataset.angle_offset) - (
                    datai.shape[1] - dataset.dpix
                ) * rad_per_pixel * 180.0 / np.pi
                plots[i].imshow(
                    datai,
                    log=main_window.ui.logarithmic_colorscale.isChecked(),
                    imin=imin,
                    imax=imax,
                    aspect="auto",
                    cmap=self.color,
                    origin="lower",
                    extent=[tth_range + tth0, tth0, phi0, phi0 - phi_range],
                )
                plots[i].set_xlabel("2$\\Theta{}$ [°]")
                plots[i].set_ylabel("$\\phi{}$ [°]")
            else:
                plots[i].imshow(
                    datai,
                    log=main_window.ui.logarithmic_colorscale.isChecked(),
                    imin=imin,
                    imax=imax,
                    aspect="auto",
                    cmap=self.color,
                    origin="lower",
                )
                plots[i].set_xlabel("x [pix]")
                plots[i].set_ylabel("y [pix]")
            plots[i].set_title(data_set_keys[i])
            if plots[i].cplot is not None:
                plots[i].cplot.set_clim([imin, imax])
            if plots[i].cplot is not None and main_window.ui.show_colorbars.isChecked() and plots[i].cbar is None:
                plots[i].cbar = plots[i].canvas.fig.colorbar(plots[i].cplot)
            plots[i].draw()
        progress(100, message="Ready", out_of=100)

    def plot_xtof(self):
        """
        X vs. ToF plots for all channels.
        """
        main_window = self.main_window
        data_set_keys = list(main_window.data_manager.data_sets.keys())
        imin = 1e20
        imax = 1e-20
        xtofnormed = []
        ref_norm = main_window.getNorm()
        if ref_norm is not None:
            ref_norm = ref_norm.get_counts_vs_TOF()
            ref_norm = np.where(ref_norm > 0, ref_norm, 1.0)

        progress = self.main_window.file_handler.new_progress_reporter()
        n_total = len(data_set_keys)
        progress(0.1, message="Compiling plots", out_of=n_total + 1)
        for i, key in enumerate(data_set_keys[:4]):
            dataset = main_window.data_manager.data_sets[key]
            dataset.prepare_plot_data()
            d = dataset.xtofdata / dataset.proton_charge
            if main_window.ui.normalizeXTof.isChecked() and ref_norm is not None:
                # normalize all datasets for wavelength distribution
                d = d / ref_norm[np.newaxis, :]
            xtofnormed.append(d)
            if dataset.total_counts == 0:
                continue
            imin = min(imin, d[d > 0].min())
            imax = max(imax, d.max())
            progress(i, message="Prepared %s plot" % key, out_of=n_total + 1)

        progress(n_total, message="Plotting...", out_of=n_total + 1)

        wavelength = main_window.data_manager.active_channel.wavelength
        tof = main_window.data_manager.active_channel.tof

        plots = [main_window.ui.xtof_pp, main_window.ui.xtof_mm, main_window.ui.xtof_pm, main_window.ui.xtof_mp]
        for i in range(len(data_set_keys), 4):
            if plots[i].cplot is not None:
                plots[i].clear()
                plots[i].draw()

        if len(xtofnormed) > 1:
            main_window.ui.frame_xtof_mm.show()
            if len(xtofnormed) == 4:
                main_window.ui.frame_xtof_sf.show()
            else:
                main_window.ui.frame_xtof_sf.hide()
        else:
            main_window.ui.frame_xtof_mm.hide()
            main_window.ui.frame_xtof_sf.hide()
        for i, datai in enumerate(xtofnormed):
            if main_window.data_manager.data_sets[data_set_keys[i]].total_counts == 0:
                continue
            if main_window.ui.xLamda.isChecked():
                plots[i].imshow(
                    datai[::-1],
                    log=main_window.ui.logarithmic_colorscale.isChecked(),
                    imin=imin,
                    imax=imax,
                    aspect="auto",
                    cmap=self.color,
                    extent=[wavelength[0], wavelength[-1], 0, datai.shape[0] - 1],
                )
                plots[i].set_xlabel("$\\lambda{}$ [Å]")
            else:
                plots[i].imshow(
                    datai[::-1],
                    log=main_window.ui.logarithmic_colorscale.isChecked(),
                    imin=imin,
                    imax=imax,
                    aspect="auto",
                    cmap=self.color,
                    extent=[tof[0] * 1e-3, tof[-1] * 1e-3, 0, datai.shape[0] - 1],
                )
                plots[i].set_xlabel("ToF [ms]")
            plots[i].set_title(data_set_keys[i])
            plots[i].set_ylabel("x [pix]")
            if plots[i].cplot is not None:
                plots[i].cplot.set_clim([imin, imax])
            if plots[i].cplot is not None and main_window.ui.show_colorbars.isChecked() and plots[i].cbar is None:
                plots[i].cbar = plots[i].canvas.fig.colorbar(plots[i].cplot)
            plots[i].draw()
        progress(100, message="Ready", out_of=100)

    def plot_projections(self, preserve_lim=False):
        """
        Create projections of the data on the x and y axes.
        The x-projection can also be done be means of quantile calculation,
        which means that the ToF intensities are calculation which are
        exceeded by a certain number of points. This can be helpful to better
        separate the specular reflection from bragg-sheets
        """
        main_window = self.main_window
        if main_window.data_manager.active_channel is None:
            return
        data = main_window.data_manager.active_channel
        data.prepare_plot_data()

        if data.total_counts == 0:
            main_window.ui.x_project.clear()
            main_window.ui.x_project.draw()
            main_window.ui.y_project.clear()
            main_window.ui.y_project.draw()
            return

        xproj = data.xdata
        yproj = data.ydata

        x_peak = main_window.ui.refXPos.value()
        x_width = main_window.ui.refXWidth.value()
        y_pos = main_window.ui.refYPos.value()
        y_width = main_window.ui.refYWidth.value()
        bg_pos = main_window.ui.bgCenter.value()
        bg_width = main_window.ui.bgWidth.value()

        if preserve_lim:
            xview = main_window.ui.x_project.canvas.ax.axis()
            yview = main_window.ui.y_project.canvas.ax.axis()
        xxlim = (0, len(xproj) - 1)
        xylim = (xproj[xproj > 0].min(), xproj.max() * 2)
        yxlim = (0, len(yproj) - 1)
        yylim = (yproj[yproj > 0].min(), yproj.max() * 2)

        if self._x_projection is None or len(self._x_projection.get_xdata()) != xproj.shape[0]:
            main_window.ui.x_project.clear_fig()
            main_window.ui.y_project.clear_fig()
            x_projection = main_window.ui.x_project.plot(xproj, color="blue")[0]
            # main_window.ui.x_project.set_xlabel(u'x [pix]')
            # main_window.ui.x_project.set_ylabel(u'I$_{max}$')
            xpos = main_window.ui.x_project.canvas.ax.axvline(x_peak, color="black")
            xleft = main_window.ui.x_project.canvas.ax.axvline(x_peak - x_width / 2.0, color="red")
            xright = main_window.ui.x_project.canvas.ax.axvline(x_peak + x_width / 2.0, color="red")
            xleft_bg = main_window.ui.x_project.canvas.ax.axvline(bg_pos - bg_width / 2.0, color="black")
            xright_bg = main_window.ui.x_project.canvas.ax.axvline(bg_pos + bg_width / 2.0, color="black")

            self._y_projection = main_window.ui.y_project.plot(yproj, color="blue")[0]
            # main_window.ui.y_project.set_xlabel(u'y [pix]')
            # main_window.ui.y_project.set_ylabel(u'I$_{max}$')
            yreg_left = main_window.ui.y_project.canvas.ax.axvline(y_pos - y_width / 2.0, color="green")
            yreg_right = main_window.ui.y_project.canvas.ax.axvline(y_pos + y_width / 2.0, color="green")
            ybg = main_window.ui.y_project.canvas.ax.axhline(self.y_bg, color="black")
            self.proj_lines = (xleft, xpos, xright, xleft_bg, xright_bg, yreg_left, yreg_right, ybg)
            self._x_projection = x_projection
        else:
            self._x_projection.set_ydata(xproj)
            self._y_projection.set_ydata(yproj)
            lines = self.proj_lines
            lines[0].set_xdata([x_peak - x_width / 2.0, x_peak - x_width / 2.0])
            lines[1].set_xdata([x_peak, x_peak])
            lines[2].set_xdata([x_peak + x_width / 2.0, x_peak + x_width / 2.0])
            lines[3].set_xdata([bg_pos - bg_width / 2.0, bg_pos - bg_width / 2.0])
            lines[4].set_xdata([bg_pos + bg_width / 2.0, bg_pos + bg_width / 2.0])
            lines[5].set_xdata([y_pos - y_width / 2.0, y_pos - y_width / 2.0])
            lines[6].set_xdata([y_pos + y_width / 2.0, y_pos + y_width / 2.0])
            lines[7].set_ydata([self.y_bg, self.y_bg])

        if preserve_lim:
            main_window.ui.x_project.canvas.ax.axis(xview)
            main_window.ui.y_project.canvas.ax.axis(yview)
        if main_window.ui.logarithmic_y.isChecked():
            main_window.ui.x_project.set_yscale("log")
            main_window.ui.y_project.set_yscale("log")
        else:
            main_window.ui.x_project.set_yscale("linear")
            main_window.ui.y_project.set_yscale("linear")
        main_window.ui.x_project.canvas.ax.set_xlim(*xxlim)
        main_window.ui.x_project.canvas.ax.set_ylim(*xylim)
        main_window.ui.y_project.canvas.ax.set_xlim(*yxlim)
        main_window.ui.y_project.canvas.ax.set_ylim(*yylim)

        main_window.ui.x_project.draw()
        main_window.ui.y_project.draw()

    def plot_offspec(self, recalc=True, crop=False):
        """
        Create an offspecular plot for all channels of the datasets in the
        reduction list. The user can define upper and lower bounds for the
        plotted intensity and select the coordinates to be ither kiz-kfz vs. Qz,
        Qx vs. Qz or kiz vs. kfz.
        """
        if self.main_window.data_manager.active_channel is None:
            return

        xlim = None
        ylim = None
        if crop and self.main_window.ui.offspec_pp.cplot is not None:
            xlim = self.main_window.ui.offspec_pp.canvas.ax.get_xlim()
            ylim = self.main_window.ui.offspec_pp.canvas.ax.get_ylim()

        plots = [
            self.main_window.ui.offspec_pp,
            self.main_window.ui.offspec_mm,
            self.main_window.ui.offspec_pm,
            self.main_window.ui.offspec_mp,
        ]
        for plot in plots:
            plot.clear()
        data_set_keys = list(self.main_window.data_manager.data_sets.keys())
        for i in range(len(data_set_keys), 4):
            if plots[i].cplot is not None:
                plots[i].draw()
            plots[i].hide()

        i_min = 10 ** self.main_window.ui.offspecImin.value()
        i_max = 10 ** self.main_window.ui.offspecImax.value()
        qz_min = 0.5
        qz_max = -0.1
        qx_min = -0.001
        qx_max = 0.001
        ki_z_min = 0.1
        ki_z_max = -0.1
        kf_z_min = 0.1
        kf_z_max = -0.1
        k_diff_min = 0.01
        k_diff_max = -0.01

        progress = self.main_window.file_handler.new_progress_reporter()
        n_total = len(self.main_window.data_manager.reduction_list)
        if n_total == 0:
            progress(100, message="No data to reduce: add data to the reduction list", out_of=100)
            return
        progress(0.1, message="Computing off-specular", out_of=n_total)
        final_msg = "Off-specular calculation complete"
        for i_run, nexus_data in enumerate(self.main_window.data_manager.reduction_list):
            for i, channel in enumerate(data_set_keys):
                plot = plots[i]
                plot.show()
                selected_data = nexus_data.cross_sections[channel]
                progress(
                    i_run + i / 4.0, message="Processed run %s %s" % (selected_data.number, channel), out_of=n_total
                )

                PN = len(selected_data.tof) - selected_data.configuration.cut_first_n_points
                P0 = selected_data.configuration.cut_last_n_points
                ki_z, kf_z = selected_data.off_spec.ki_z, selected_data.off_spec.kf_z
                Qx, Qz, S = selected_data.off_spec.Qx, selected_data.off_spec.Qz, selected_data.off_spec.S
                try:
                    qz_max = max(Qz[S > 0].max(), qz_max)
                    qz_min = min(Qz[S > 0].min(), qz_min)
                    qx_min = min(qx_min, Qx[S > 0].min())
                    qx_max = max(qx_max, Qx[S > 0].max())
                    ki_z_min = min(ki_z_min, ki_z[S > 0].min())
                    ki_z_max = max(ki_z_max, ki_z[S > 0].max())
                    kf_z_min = min(kf_z_min, kf_z[S > 0].min())
                    kf_z_max = max(kf_z_max, kf_z[S > 0].max())
                    k_diff_min = min(k_diff_min, (ki_z - kf_z)[S > 0].min())
                    k_diff_max = max(k_diff_max, (ki_z - kf_z)[S > 0].max())
                except:
                    logging.error("Error computing ranges: %s", sys.exc_info()[1])
                if self.main_window.ui.kizmkfzVSqz.isChecked():
                    plot.pcolormesh(
                        (ki_z - kf_z)[:, P0:PN],
                        Qz[:, P0:PN],
                        S[:, P0:PN],
                        log=True,
                        imin=i_min,
                        imax=i_max,
                        cmap=self.color,
                        shading="gouraud",
                    )
                elif self.main_window.ui.qxVSqz.isChecked():
                    plot.pcolormesh(
                        Qx[:, P0:PN],
                        Qz[:, P0:PN],
                        S[:, P0:PN],
                        log=True,
                        imin=i_min,
                        imax=i_max,
                        cmap=self.color,
                        shading="gouraud",
                    )
                else:
                    plot.pcolormesh(
                        ki_z[:, P0:PN],
                        kf_z[:, P0:PN],
                        S[:, P0:PN],
                        log=True,
                        imin=i_min,
                        imax=i_max,
                        cmap=self.color,
                        shading="gouraud",
                    )
        for i, channel in enumerate(data_set_keys):
            plot = plots[i]
            if self.main_window.ui.kizmkfzVSqz.isChecked():
                plot.canvas.ax.set_xlim([k_diff_min, k_diff_max])
                plot.canvas.ax.set_ylim([qz_min, qz_max])
                plot.set_xlabel("k$_{i,z}$-k$_{f,z}$ [Å$^{-1}$]")
                plot.set_ylabel("Q$_z$ [Å$^{-1}$]")
            elif self.main_window.ui.qxVSqz.isChecked():
                plot.canvas.ax.set_xlim([qx_min, qx_max])
                plot.canvas.ax.set_ylim([qz_min, qz_max])
                plot.set_xlabel("Q$_x$ [Å$^{-1}$]")
                plot.set_ylabel("Q$_z$ [Å$^{-1}$]")
            else:
                plot.canvas.ax.set_xlim([ki_z_min, ki_z_max])
                plot.canvas.ax.set_ylim([kf_z_min, kf_z_max])
                plot.set_xlabel("k$_{i,z}$ [Å$^{-1}$]")
                plot.set_ylabel("k$_{f,z}$ [Å$^{-1}$]")
            plot.set_title(channel)
            if plot.cplot is not None:
                plot.cplot.set_clim([i_min, i_max])
                if self.main_window.ui.show_colorbars.isChecked() and plots[i].cbar is None:
                    plots[i].cbar = plots[i].canvas.fig.colorbar(plots[i].cplot)
                if xlim is not None and ylim is not None:
                    plot.canvas.ax.set_xlim(*xlim)
                    plot.canvas.ax.set_ylim(*ylim)
            plot.draw()
        progress(100, message=final_msg, out_of=100)

    def plot_refl(self, preserve_lim=False):
        """
        Calculate and display the reflectivity from the current dataset
        and any dataset stored. Intensities from direct beam
        measurements can be used for normalization.
        """

        def _plot_message(message):
            self.main_window.ui.refl.canvas.ax.text(
                0.5,
                0.5,
                message,
                horizontalalignment="center",
                verticalalignment="center",
                fontsize=14,
                transform=self.main_window.ui.refl.canvas.ax.transAxes,
            )
            self.main_window.ui.refl.draw()

        self.main_window.ui.refl.clear()

        if (
            self.main_window.data_manager.active_channel is None
            or self.main_window.data_manager.active_channel.r is None
            or self.main_window.data_manager.active_channel.q is None
            or self.main_window.data_manager.active_channel.dr is None
        ):
            _plot_message("No data")
            return False

        if (
            self.main_window.data_manager.active_channel.is_direct_beam
            and not self.main_window.data_manager.reduction_list
        ):
            _plot_message("No reflectivity for the\nselected direct-beam data!")
            return False

        data = self.main_window.data_manager.active_channel
        if data.total_counts == 0:
            _plot_message("No points to show\nin active dataset!")
            return False

        def _set_ymax(ymax, ynormed):
            _ymax = max(ymax, ynormed.max())
            if _ymax == np.inf:
                _ymax = np.ma.array(ynormed, mask=~np.isfinite(ynormed)).max()
                _ymax = max(ymax, _ymax)
            return _ymax

        ymin = 1.5
        ymax = 1e-7
        P0 = self.main_window.ui.rangeStart.value()
        PN = len(self.main_window.data_manager.active_channel.q) - self.main_window.ui.rangeEnd.value()
        ynormed = self.main_window.data_manager.active_channel.r[P0:PN]
        if len(ynormed[ynormed > 0]) < 2:
            _plot_message("No points to show\nin active dataset!")
            return False

        if not self.main_window.data_manager.active_channel.is_direct_beam:
            ymin = min(ymin, ynormed[ynormed > 0].min())
            ymax = _set_ymax(ymax, ynormed)
            self.main_window.ui.refl.errorbar(
                self.main_window.data_manager.active_channel.q[P0:PN],
                ynormed,
                yerr=self.main_window.data_manager.active_channel.dr[P0:PN],
                label="Active",
                lw=2,
                capsize=1,
                color="black",
            )

        channel_name = self.main_window.data_manager.active_channel.name
        for i, refli in enumerate(self.main_window.data_manager.reduction_list):
            if refli.cross_sections[channel_name].q is None:
                continue
            P0i = refli.cross_sections[channel_name].configuration.cut_first_n_points
            PNi = (
                len(refli.cross_sections[channel_name].q)
                - refli.cross_sections[channel_name].configuration.cut_last_n_points
            )
            ynormed = refli.cross_sections[channel_name].r[P0i:PNi]
            try:
                ymin = min(ymin, ynormed[ynormed > 0].min())
            except ValueError:
                pass
            try:
                ymax = _set_ymax(ymax, ynormed)
            except ValueError:
                pass
            self.main_window.ui.refl.errorbar(
                refli.cross_sections[channel_name].q[P0i:PNi],
                ynormed,
                yerr=refli.cross_sections[channel_name].dr[P0i:PNi],
                label=str(refli.number),
                capsize=1,
                color=self._refl_color_list[i % len(self._refl_color_list)],
            )
        self.main_window.ui.refl.canvas.ax.set_ylim((ymin * 0.9, ymax * 1.1))
        self.main_window.ui.refl.set_xlabel("Q$_z$ [Å$^{-1}$]")

        if self.main_window.ui.logarithmic_y.isChecked():
            self.main_window.ui.refl.set_yscale("log")
        else:
            self.main_window.ui.refl.set_yscale("linear")
        self.main_window.ui.refl.legend()
        self.main_window.ui.refl.toolbar.set_history_buttons()
        self.main_window.ui.refl.draw()

        self.main_window.ui.compare_widget.update_preview()

    def plot_gisans(self):
        """
        Create GISANS plots of the current dataset with Qy-Qz maps.
        """
        if self.main_window.data_manager.active_channel is None:
            return

        plots = [
            self.main_window.ui.gisans_pp,
            self.main_window.ui.gisans_mm,
            self.main_window.ui.gisans_pm,
            self.main_window.ui.gisans_mp,
        ]

        for plot in plots:
            plot.clear()
        data_set_keys = list(self.main_window.data_manager.data_sets.keys())
        for i in range(len(data_set_keys), 4):
            if plots[i].cplot is not None:
                plots[i].draw()
            plots[i].hide()

        Imin = 10 ** self.main_window.ui.gisansImin.value()
        Imax = 10 ** self.main_window.ui.gisansImax.value()

        for i, channel in enumerate(data_set_keys):
            plot = plots[i]
            plot.show()
            selected_data = self.main_window.data_manager.data_sets[channel]
            plots[i].clear_fig()
            plots[i].pcolormesh(
                selected_data.gisans_data.QyGrid,
                selected_data.gisans_data.QzGrid,
                selected_data.gisans_data.SGrid,
                log=self.main_window.ui.logarithmic_colorscale.isChecked(),
                imin=Imin,
                imax=Imax,
                cmap=self.color,
            )
            plots[i].set_xlabel("Q$_y$ [Å$^{-1}$]")
            plots[i].set_ylabel("Q$_z$ [Å$^{-1}$]")
            plots[i].set_title(channel)
            if plots[i].cplot is not None:
                plots[i].cplot.set_clim([Imin, Imax])
            if plots[i].cplot is not None and self.main_window.ui.show_colorbars.isChecked() and plots[i].cbar is None:
                plots[i].cbar = plots[i].canvas.fig.colorbar(plots[i].cplot)
            plots[i].draw()
