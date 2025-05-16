# coding: utf-8
"""
Dialog to let the user select smoothing options
This code was taken as-is from QuickNXS v1
"""
# pylint: disable=bare-except

# third-party imports
from mantid.simpleapi import logger
from matplotlib.lines import Line2D
from matplotlib.patches import Ellipse
from qtpy import QtWidgets

# quicknxs imports
from quicknxs.interfaces import load_ui
from quicknxs.interfaces.configuration import Configuration
from quicknxs.ui.mplwidget import MPLWidget


class SmoothDialog(QtWidgets.QDialog):
    """
    Dialog to define smoothing parameters.
    """

    INTENSITY_MIN = 1e-6  # starting value for the color scale
    INTENSITY_MAX = 1.0  # ending value for the color scale
    GRID_OFFSET = 0.05  # Starting percentage offset of the grid area inside the whole plot area

    drawing = False

    def __init__(self, parent, data_manager):
        QtWidgets.QDialog.__init__(self, parent)
        self.ui = load_ui("ui_smooth_dialog.ui", baseinstance=self)
        self.data_manager = data_manager
        self.ui.plot.canvas.mpl_connect("motion_notify_event", self.plotSelect)
        self.ui.plot.canvas.mpl_connect("button_press_event", self.plotSelect)
        self.drawPlot()

    def _grid_region_coordinates(self, x_min, x_max, y_min, y_max):
        """
        Calculate the coordinates of box inside the plot area representing the grid region

        :param x_min: Either k_diff_min, qx_min or ki_z_min
        :param x_max: Either k_diff_max, qx_max or ki_z_max
        :param y_min: Either qz_min or kf_z_min
        :param y_max: Either qz_max or kf_z_max
        :return: Tuple of coordinates (x1, x2, y1, y2)
        """
        x_offset = (x_max - x_min) * self.GRID_OFFSET
        y_offset = (y_max - y_min) * self.GRID_OFFSET
        return x_min + x_offset, x_max - x_offset, y_min + y_offset, y_max - y_offset

    def _paint_intensities(self, ki_z, kf_z, Qx, Qz, I, plot: MPLWidget):
        """
         Color-paint the intensities versus appropriate X and Y coordinates.

        X and Y coordinates are selected based on the checked option:
        - (ki_z - kf_z), Qz
        - Qx, Qz
        - ki_z, kf_z

        :param ki_z: Array of k$_{i,z}$ values
        :param kf_z: Array of k$_{f,z}$ values
        :param Qx: Array of Q$_x$ values
        :param Qz: Array of Q$_z$ values
        :param I: Intensity array
        :param plot: The plot object to draw on
        """
        common_args = {
            "log": True,
            "imin": self.INTENSITY_MIN,
            "imax": self.INTENSITY_MAX,
            "cmap": "jet",
            "shading": "gouraud",
        }

        if self.ui.kizmkfzVSqz.isChecked():
            x, y = (ki_z - kf_z), Qz
        elif self.ui.qxVSqz.isChecked():
            x, y = Qx, Qz
        elif self.ui.kizVSkfz.isChecked():
            x, y = ki_z, kf_z
        else:
            raise ValueError("No valid plot option selected")
        plot.pcolormesh(x, y, I, **common_args)

    def drawPlot(self):
        """
        Plot the unsmoothed data.
        """
        self.drawing = True

        # initialize the plot widget
        plot: MPLWidget = self.ui.plot
        plot.clear()
        plot.set_xticks_fontsize(8)
        plot.set_yticks_fontsize(8)

        #
        # Block to paint the intensities on the canvas
        #
        Qzmax = 0.001
        k_diff_min = 0.01
        k_diff_max = -0.01
        qz_min = 0.5
        qz_max = -0.1
        qx_min = -0.001
        qx_max = 0.001
        ki_z_min = 0.1
        ki_z_max = -0.1
        kf_z_min = 0.1
        kf_z_max = -0.1
        first_state = self.data_manager.reduction_states[0]  # Get data from first cross-section
        for item in self.data_manager.reduction_list:  # type: NexusData
            offspec = item.cross_sections[first_state].off_spec
            Qx, Qz, ki_z, kf_z, I, _ = (offspec.Qx, offspec.Qz, offspec.ki_z, offspec.kf_z, offspec.S, offspec.dS)

            n_total = len(I[0])
            # P_0 and P_N are the number of points to cut in TOF on each side
            p_0 = item.cross_sections[first_state].configuration.cut_first_n_points
            p_n = n_total - item.cross_sections[first_state].configuration.cut_last_n_points

            Qx = Qx[:, p_0:p_n]
            Qz = Qz[:, p_0:p_n]
            ki_z = ki_z[:, p_0:p_n]
            kf_z = kf_z[:, p_0:p_n]
            I = I[:, p_0:p_n]

            # Extend the X and Y limits of the plotting area so that intensities for all runs are visible
            try:
                Qzmax = max(ki_z.max() * 2.0, Qzmax)
                qz_max = max(Qz[I > 0].max(), qz_max)
                qz_min = min(Qz[I > 0].min(), qz_min)
                qx_min = min(qx_min, Qx[I > 0].min())
                qx_max = max(qx_max, Qx[I > 0].max())
                ki_z_min = min(ki_z_min, ki_z[I > 0].min())
                ki_z_max = max(ki_z_max, ki_z[I > 0].max())
                kf_z_min = min(kf_z_min, kf_z[I > 0].min())
                kf_z_max = max(kf_z_max, kf_z[I > 0].max())
                k_diff_min = min(k_diff_min, (ki_z - kf_z)[I > 0].min())
                k_diff_max = max(k_diff_max, (ki_z - kf_z)[I > 0].max())
            except Exception as exception:
                logger.error(f"Error extending plotting limits: {exception}")

            self._paint_intensities(ki_z, kf_z, Qx, Qz, I, plot)  # color-paint intensities on the canvas

        #
        # Block to set the plot's X and Y limits, the X and Y labels, and the grid region
        #
        sigma_percentage = 0.005  # percentage of the sigma spot from the whole plot area
        min_sigma_size = 0.0001  # default-minimum sigma x,y size
        if self.ui.kizmkfzVSqz.isChecked():
            plot.canvas.ax.set_xlim([k_diff_min, k_diff_max])
            plot.canvas.ax.set_ylim([qz_min, qz_max])
            plot.set_xlabel("k$_{i,z}$-k$_{f,z}$ [Å$^{-1}$]", fontsize=14)
            plot.set_ylabel("Q$_z$ [Å$^{-1}$]", fontsize=14)
            x1, x2, y1, y2 = self._grid_region_coordinates(k_diff_min, k_diff_max, qz_min, qz_max)
        elif self.ui.qxVSqz.isChecked():
            plot.canvas.ax.set_xlim([qx_min, qx_max])
            plot.canvas.ax.set_ylim([qz_min, qz_max])
            plot.set_xlabel("Q$_x$ [Å$^{-1}$]", fontsize=14)
            plot.set_ylabel("Q$_z$ [Å$^{-1}$]", fontsize=14)
            x1, x2, y1, y2 = self._grid_region_coordinates(qx_min, qx_max, qz_min, qz_max)
        elif self.ui.kizVSkfz.isChecked():
            plot.canvas.ax.set_xlim([ki_z_min, ki_z_max])
            plot.canvas.ax.set_ylim([kf_z_min, kf_z_max])
            plot.set_xlabel("k$_{i,z}$ [Å$^{-1}$]", fontsize=14)
            plot.set_ylabel("k$_{f,z}$ [Å$^{-1}$]", fontsize=14)
            x1, x2, y1, y2 = self._grid_region_coordinates(ki_z_min, ki_z_max, kf_z_min, kf_z_max)
        else:
            raise ValueError("No valid plot option selected")
        self.rect_region = Line2D([x1, x1, x2, x2, x1], [y1, y2, y2, y1, y1])
        plot.canvas.ax.add_line(self.rect_region)
        self.ui.gridXmin.setValue(x1)
        self.ui.gridXmax.setValue(x2)
        self.ui.gridYmin.setValue(y1)
        self.ui.gridYmax.setValue(y2)

        #
        # Block to set the sigma spot and determine sigma properties
        #
        sigma_x = max((x2 - x1) * sigma_percentage, min_sigma_size)
        sigma_y = max((y2 - y1) * sigma_percentage, min_sigma_size)
        self.ui.sigmaX.setValue(sigma_x)
        self.ui.sigmaY.setValue(sigma_y)
        self.ui.sigmasCoupled.setChecked(True)
        self.ui.sigmaY.setEnabled(True)
        sigma_ang = 0.0
        if self.ui.kizmkfzVSqz.isChecked():
            sigma_pos = (0.0, Qzmax / 3.0)
            self.ui.sigmaY.setEnabled(False)
        elif self.ui.qxVSqz.isChecked():
            sigma_pos = (0.0, Qzmax / 3.0)
            self.ui.sigmasCoupled.setChecked(False)
        else:
            sigma_pos = (Qzmax / 6.0, Qzmax / 6.0)
        self.sigma_1 = Ellipse(
            sigma_pos, self.ui.sigmaX.value() * 2, self.ui.sigmaY.value() * 2, angle=sigma_ang, fill=False
        )
        self.sigma_2 = Ellipse(
            sigma_pos, self.ui.sigmaX.value() * 4, self.ui.sigmaY.value() * 4, angle=sigma_ang, fill=False
        )
        self.sigma_3 = Ellipse(
            sigma_pos, self.ui.sigmaX.value() * 6, self.ui.sigmaY.value() * 6, angle=sigma_ang, fill=False
        )
        plot.canvas.ax.add_artist(self.sigma_1)
        plot.canvas.ax.add_artist(self.sigma_2)
        plot.canvas.ax.add_artist(self.sigma_3)

        # Show the plot
        if plot.cplot is not None:
            plot.cplot.set_clim([self.INTENSITY_MIN, self.INTENSITY_MAX])
        plot.draw()
        self.updateGrid()
        self.drawing = False

    def updateSettings(self):
        if self.drawing:
            return
        self.drawing = True
        if self.ui.sigmasCoupled.isChecked():
            self.ui.sigmaY.setValue(self.ui.sigmaX.value())
        self.updateGrid()
        # redraw indicators
        x1 = self.ui.gridXmin.value()
        x2 = self.ui.gridXmax.value()
        y1 = self.ui.gridYmin.value()
        y2 = self.ui.gridYmax.value()
        self.rect_region.set_data([x1, x1, x2, x2, x1], [y1, y2, y2, y1, y1])
        self.sigma_1.width = 2 * self.ui.sigmaX.value()
        self.sigma_1.height = 2 * self.ui.sigmaY.value()
        self.sigma_2.width = 4 * self.ui.sigmaX.value()
        self.sigma_2.height = 4 * self.ui.sigmaY.value()
        self.sigma_3.width = 6 * self.ui.sigmaX.value()
        self.sigma_3.height = 6 * self.ui.sigmaY.value()
        self.ui.plot.draw()
        self.drawing = False

    def updateGrid(self):
        if self.ui.gridSizeCoupled.isChecked():
            sx = self.ui.sigmaX.value()
            sy = self.ui.sigmaY.value()
            x1 = self.ui.gridXmin.value()
            x2 = self.ui.gridXmax.value()
            y1 = self.ui.gridYmin.value()
            y2 = self.ui.gridYmax.value()
            self.ui.gridSizeX.setValue(int((x2 - x1) / sx * 1.41))
            self.ui.gridSizeY.setValue(int((y2 - y1) / sy * 1.41))

    def plotSelect(self, event):
        """
        Plot for y-projection has been clicked.
        """
        # if event.button == 1 and self.ui.plot.toolbar._active is None and event.xdata is not None:
        if event.button == 1 and event.xdata is not None:
            x = event.xdata
            y = event.ydata
            x1 = self.ui.gridXmin.value()
            x2 = self.ui.gridXmax.value()
            y1 = self.ui.gridYmin.value()
            y2 = self.ui.gridYmax.value()
            if x < x1 or abs(x - x1) < abs(x - x2):
                x1 = x
            else:
                x2 = x
            if y < y1 or abs(y - y1) < abs(y - y2):
                y1 = y
            else:
                y2 = y
            self.drawing = True
            self.ui.gridXmin.setValue(x1)
            self.ui.gridXmax.setValue(x2)
            self.ui.gridYmin.setValue(y1)
            self.ui.gridYmax.setValue(y2)
            self.drawing = False
            self.updateSettings()

    def update_output_options(self, output_options):
        """
        Update a dict with smoothing options
        :param dict: dictionary object
        """
        if self.ui.kizVSkfz.isChecked():
            output_options["off_spec_x_axis"] = Configuration.KZI_VS_KZF
        elif self.ui.qxVSqz.isChecked():
            output_options["off_spec_x_axis"] = Configuration.QX_VS_QZ
        else:
            output_options["off_spec_x_axis"] = Configuration.DELTA_KZ_VS_QZ

        output_options["off_spec_nxbins"] = self.ui.gridSizeX.value()
        output_options["off_spec_nybins"] = self.ui.gridSizeY.value()

        output_options["off_spec_sigmas"] = self.ui.rSigmas.value()
        output_options["off_spec_sigmax"] = self.ui.sigmaX.value()
        output_options["off_spec_sigmay"] = self.ui.sigmaY.value()
        output_options["off_spec_x_min"] = self.ui.gridXmin.value()
        output_options["off_spec_x_max"] = self.ui.gridXmax.value()
        output_options["off_spec_y_min"] = self.ui.gridYmin.value()
        output_options["off_spec_y_max"] = self.ui.gridYmax.value()

        return output_options
