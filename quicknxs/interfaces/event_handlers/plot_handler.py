# -*- coding: utf-8 -*-
# pylint: disable=invalid-name, too-many-instance-attributes, unused-argument, protected-access, line-too-long,
# pylint: disable=access-member-before-definition, too-many-locals, too-many-branches
"""
    Event handlers for the main application window.
    Most of those come straight from QuickNXS.
"""
import time
from PyQt5 import QtWidgets


def slow_down_events(fn):
    """
    Decorator to slow down UI events since PyQt5 seems to
    be overactive with the UI events.
    """

    def function_wrapper(self, *args, **kws):
        """
        Wrap a function to slow it down
        """
        if self.last_event is not None and time.time() - self.last_event < 0.3:
            return None
        self.last_event = time.time()
        return fn(self, *args, **kws)

    return function_wrapper


class PlotHandler(object):
    """
    Class to handle plotting events
    """

    _picked_line = None
    control_down = False
    last_event = None
    refl = None

    def __init__(self, main_window):
        self.main_window = main_window
        self.ui = main_window.ui
        self.plot_manager = main_window.plot_manager
        self.data_manager = main_window.data_manager
        self.connect_plot_events()

    def connect_plot_events(self):
        """
        Connect matplotlib mouse events.
        """
        for plot in [
            self.ui.xy_pp,
            self.ui.xy_mp,
            self.ui.xy_pm,
            self.ui.xy_mm,
            self.ui.xtof_pp,
            self.ui.xtof_mp,
            self.ui.xtof_pm,
            self.ui.xtof_mm,
            self.ui.xy_overview,
            self.ui.xtof_overview,
            self.ui.x_project,
            self.ui.y_project,
            self.ui.refl,
            self.ui.offspec_pp,
            self.ui.offspec_mm,
            self.ui.offspec_pm,
            self.ui.offspec_mp,
        ]:
            plot.canvas.mpl_connect("motion_notify_event", self.plot_mouse_event)
        for plot in [
            self.ui.xy_pp,
            self.ui.xy_mp,
            self.ui.xy_pm,
            self.ui.xy_mm,
            self.ui.xtof_pp,
            self.ui.xtof_mp,
            self.ui.xtof_pm,
            self.ui.xtof_mm,
            self.ui.xy_overview,
            self.ui.xtof_overview,
            self.ui.offspec_pp,
            self.ui.offspec_mm,
            self.ui.offspec_pm,
            self.ui.offspec_mp,
        ]:
            plot.canvas.mpl_connect("scroll_event", self.change_color_scale)
        # self.ui.x_project.canvas.mpl_connect('motion_notify_event', self.plot_pick_x)
        self.ui.x_project.canvas.mpl_connect("button_press_event", self.plot_pick_x)
        self.ui.x_project.canvas.mpl_connect("button_release_event", self.plot_release)
        # self.ui.y_project.canvas.mpl_connect('motion_notify_event', self.plot_pick_y)
        self.ui.y_project.canvas.mpl_connect("button_press_event", self.plot_pick_y)
        self.ui.y_project.canvas.mpl_connect("button_release_event", self.plot_release)
        # self.ui.refl.canvas.mpl_connect('scroll_event', self.scale_on_plot)
        self.ui.xy_overview.canvas.mpl_connect("button_press_event", self.plot_pick_xy)
        # self.ui.xy_overview.canvas.mpl_connect('motion_notify_event', self.plot_pick_xy)
        self.ui.xy_overview.canvas.mpl_connect("button_release_event", self.plot_release)
        self.ui.xtof_overview.canvas.mpl_connect("button_press_event", self.plot_pick_xtof)
        # self.ui.xtof_overview.canvas.mpl_connect('motion_notify_event', self.plot_pick_xtof)
        self.ui.xtof_overview.canvas.mpl_connect("button_release_event", self.plot_release)

        # Status bar indicator
        self.x_position_indicator = QtWidgets.QLabel(" x=%g" % 0.0)
        self.x_position_indicator.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Preferred)
        self.x_position_indicator.setMaximumWidth(100)
        self.x_position_indicator.setMinimumWidth(100)
        self.ui.statusbar.addPermanentWidget(self.x_position_indicator)
        self.y_position_indicator = QtWidgets.QLabel(" y=%g" % 0.0)
        self.y_position_indicator.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Preferred)
        self.y_position_indicator.setMaximumWidth(100)
        self.y_position_indicator.setMinimumWidth(100)
        self.ui.statusbar.addPermanentWidget(self.y_position_indicator)

    def plot_mouse_event(self, event):
        """
        Show the mouse position of any plot in the main window
        status bar, as the single plot status indicator is only
        visible for larger plot toolbars.
        :param event: event object
        """
        if event.inaxes is None:
            return
        self.x_position_indicator.setText(" x=%g" % event.xdata)
        self.y_position_indicator.setText(" y=%g" % event.ydata)

    @slow_down_events
    def change_color_scale(self, event):
        """
        Change the intensity limits of a map plot with the mouse wheel.
        :param event: event object
        """
        # Scaling parameters
        _scale = 1.5
        _step = 0.42

        canvas = None
        for plot in [self.ui.xy_overview, self.ui.xtof_overview]:
            if plot.canvas is event.canvas:
                canvas = [plot]
        if event.canvas in [self.ui.xy_pp.canvas, self.ui.xy_mp.canvas, self.ui.xy_pm.canvas, self.ui.xy_mm.canvas]:
            canvas = [self.ui.xy_pp, self.ui.xy_mp, self.ui.xy_pm, self.ui.xy_mm]
        if event.canvas in [
            self.ui.xtof_pp.canvas,
            self.ui.xtof_mp.canvas,
            self.ui.xtof_pm.canvas,
            self.ui.xtof_mm.canvas,
        ]:
            canvas = [self.ui.xtof_pp, self.ui.xtof_mp, self.ui.xtof_pm, self.ui.xtof_mm]
        if not (canvas and canvas[0].cplot):
            return
        clim = canvas[0].cplot.get_clim()
        for canv in canvas:
            if canv.cplot is None:
                continue
            if self.control_down:
                canv.cplot.set_clim(min(clim[1] / _scale, clim[0] * 10 ** (_step * event.step)), clim[1])
            else:
                canv.cplot.set_clim(clim[0], max(clim[0] * _scale, clim[1] * 10 ** (_step * event.step)))
            canv.draw()

    def plot_release(self, event):
        """
        :param event: event object
        """
        self._picked_line = None
        self.main_window.changeRegionValues()

    @slow_down_events
    def plot_pick_x(self, event):
        """
        Plot for x-projection has been clicked.
        :param event: event object
        """
        if event.button is not None and event.xdata is not None:
            self.main_window.auto_change_active = True
            if event.button == 1:
                xcen = self.ui.refXPos.value()
                bgc = self.ui.bgCenter.value()
                bgw = self.ui.bgWidth.value()
                bgl = bgc - bgw / 2.0
                bgr = bgc + bgw / 2.0
                dists = [abs(event.xdata - item) for item in [xcen, bgl, bgr]]
                min_dist = dists.index(min(dists))
                pl = self._picked_line
                if pl == "bgl" or (pl is None and min_dist == 1):
                    # left of right background bar and closer to left one
                    bgl = event.xdata
                    bgc = (bgr + bgl) / 2.0
                    bgw = bgr - bgl
                    self.ui.bgCenter.setValue(bgc)
                    self.ui.bgWidth.setValue(bgw)
                    self._picked_line = "bgl"
                elif pl == "bgr" or (pl is None and min_dist == 2):
                    # left of right background bar or closer to right background than peak
                    bgr = event.xdata
                    bgc = (bgr + bgl) / 2.0
                    bgw = bgr - bgl
                    self.ui.bgCenter.setValue(bgc)
                    self.ui.bgWidth.setValue(bgw)
                    self._picked_line = "bgr"
                else:
                    self.ui.refXPos.setValue(event.xdata)
                    self._picked_line = "xpos"
            elif event.button == 3:
                self.ui.refXWidth.setValue(abs(self.ui.refXPos.value() - event.xdata) * 2.0)
            self.main_window.auto_change_active = False
            self.change_region_values()

    def plot_pick_y(self, event):
        """
        Plot for y-projection has been clicked.
        :param self QMainWindow: main window object
        :param event: event object
        """
        self.main_window.auto_change_active = True
        if event.button == 1 and event.xdata is not None:
            ypos = self.ui.refYPos.value()
            yw = self.ui.refYWidth.value()
            yl = ypos - yw / 2.0
            yr = ypos + yw / 2.0
            pl = self._picked_line
            if pl == "yl" or (pl is None and abs(event.xdata - yl) < abs(event.xdata - yr)):
                yl = event.xdata
                self._picked_line = "yl"
            else:
                yr = event.xdata
                self._picked_line = "yr"
            ypos = (yr + yl) / 2.0
            yw = yr - yl
            self.ui.refYPos.setValue(ypos)
            self.ui.refYWidth.setValue(yw)
        self.main_window.auto_change_active = False
        self.change_region_values()

    def plot_pick_xy(self, event):
        """
        Plot for xy-map has been clicked.
        :param self QMainWindow: main window object
        :param event: event object
        """
        self.main_window.auto_change_active = True
        if event.button == 1 and event.xdata is not None:
            self.ui.refXPos.setValue(event.xdata)
        elif event.button == 3 and event.ydata is not None:
            ypos = self.ui.refYPos.value()
            yw = self.ui.refYWidth.value()
            yl = ypos - yw / 2.0
            yr = ypos + yw / 2.0
            pl = self._picked_line
            if pl == "yl" or (pl is None and abs(event.ydata - yl) < abs(event.ydata - yr)):
                yl = event.ydata
                self._picked_line = "yl"
            else:
                yr = event.ydata
                self._picked_line = "yr"
            ypos = (yr + yl) / 2.0
            yw = yr - yl
            self.ui.refYPos.setValue(ypos)
            self.ui.refYWidth.setValue(yw)
        self.main_window.auto_change_active = False
        self.change_region_values()

    def plot_pick_xtof(self, event):
        """
        :param event: event object
        """
        self.main_window.auto_change_active = True
        if event.button == 1 and event.ydata is not None:
            xcen = self.ui.refXPos.value()
            bgc = self.ui.bgCenter.value()
            bgw = self.ui.bgWidth.value()
            bgl = bgc - bgw / 2.0
            bgr = bgc + bgw / 2.0
            dists = [abs(event.ydata - item) for item in [xcen, bgl, bgr]]
            min_dist = dists.index(min(dists))
            pl = self._picked_line
            if pl == "bgl" or (pl is None and min_dist == 1):
                # left of right background bar and closer to left one
                bgl = event.ydata
                bgc = (bgr + bgl) / 2.0
                bgw = bgr - bgl
                self.ui.bgCenter.setValue(bgc)
                self.ui.bgWidth.setValue(bgw)
                self._picked_line = "bgl"
            elif pl == "bgr" or (pl is None and min_dist == 2):
                # left of right background bar or closer to right background than peak
                bgr = event.ydata
                bgc = (bgr + bgl) / 2.0
                bgw = bgr - bgl
                self.ui.bgCenter.setValue(bgc)
                self.ui.bgWidth.setValue(bgw)
                self._picked_line = "bgr"
            else:
                self.ui.refXPos.setValue(event.ydata)
                self._picked_line = "xpos"
        elif event.button == 3 and event.ydata is not None:
            xpos = self.ui.refXPos.value()
            self.ui.refXWidth.setValue(abs(xpos - event.ydata) * 2.0)
        self.main_window.auto_change_active = False
        self.change_region_values()

    @slow_down_events
    def scale_on_plot(self, event):
        """
        :param event: event object
        """
        steps = event.step
        xpos = event.xdata
        if xpos is None:
            return
        for i, refl in enumerate(self.data_manager.reduction_list):
            _, q_max = refl.get_q_range()
            if q_max > xpos:
                Ival = refl.configuration.scaling_factor
                if self.control_down:
                    Inew = Ival * 10 ** (0.05 * steps)
                else:
                    Inew = Ival * 10 ** (0.01 * steps)
                self.ui.reductionTable.setItem(i, 1, QtWidgets.QTableWidgetItem("%.4f" % (Inew)))

    def change_region_values(self):
        """
        Called when the reflectivity extraction region has been changed.
        Sets up a trigger to replot the reflectivity with a delay so
        a subsequent change can occur without several replots.
        """
        if self.plot_manager.proj_lines is None:
            return
        lines = self.plot_manager.proj_lines

        x_peak = self.ui.refXPos.value()
        x_width = self.ui.refXWidth.value()
        y_pos = self.ui.refYPos.value()
        y_width = self.ui.refYWidth.value()
        bg_pos = self.ui.bgCenter.value()
        bg_width = self.ui.bgWidth.value()

        lines[0].set_xdata([x_peak - x_width / 2.0, x_peak - x_width / 2.0])
        lines[1].set_xdata([x_peak, x_peak])
        lines[2].set_xdata([x_peak + x_width / 2.0, x_peak + x_width / 2.0])
        lines[3].set_xdata([bg_pos - bg_width / 2.0, bg_pos - bg_width / 2.0])
        lines[4].set_xdata([bg_pos + bg_width / 2.0, bg_pos + bg_width / 2.0])
        lines[5].set_xdata([y_pos - y_width / 2.0, y_pos - y_width / 2.0])
        lines[6].set_xdata([y_pos + y_width / 2.0, y_pos + y_width / 2.0])
        self.ui.x_project.draw()
        self.ui.y_project.draw()

        if not self.ui.tthPhi.isChecked():
            self.plot_manager.xy_x1.set_xdata([x_peak - x_width / 2.0, x_peak - x_width / 2.0])
            self.plot_manager.xy_x2.set_xdata([x_peak + x_width / 2.0, x_peak + x_width / 2.0])
            self.plot_manager.xy_y1.set_ydata([y_pos - y_width / 2.0, y_pos - y_width / 2.0])
            self.plot_manager.xy_y2.set_ydata([y_pos + y_width / 2.0, y_pos + y_width / 2.0])
            self.ui.xy_overview.draw()

        self.plot_manager.xtof_x1.set_ydata([x_peak - x_width / 2.0, x_peak - x_width / 2.0])
        self.plot_manager.xtof_x2.set_ydata([x_peak + x_width / 2.0, x_peak + x_width / 2.0])
        self.plot_manager.xtof_bck1.set_ydata([bg_pos - bg_width / 2.0, bg_pos - bg_width / 2.0])
        self.plot_manager.xtof_bck2.set_ydata([bg_pos + bg_width / 2.0, bg_pos + bg_width / 2.0])
        self.ui.xtof_overview.draw()

        # TODO: refactor this
        # if self.ui.fanReflectivity.isChecked() and self.refl and not self.refl.options['extract_fan']:
        #    old_aca = self.main_window.auto_change_active
        #    self.main_window.auto_change_active = False
        #    self.ui.rangeStart.setValue(self.cut_areas['fan'][0])
        #    self.ui.rangeEnd.setValue(self.cut_areas['fan'][1])
        #    self.main_window.auto_change_active = old_aca
        # elif not self.ui.fanReflectivity.isChecked() and self.refl and self.refl.options['extract_fan']:
        #    norm = self.getNorm()
        #    if norm in self.cut_areas:
        #        old_aca = self.main_window.auto_change_active
        #        self.main_window.auto_change_active = False
        #        self.ui.rangeStart.setValue(self.cut_areas[norm][0])
        #        self.ui.rangeEnd.setValue(self.cut_areas[norm][1])
        #        self.main_window.auto_change_active = old_aca

    def change_offspec_colorscale(self):
        """Modify color scale"""
        plots = [self.ui.offspec_pp, self.ui.offspec_mm, self.ui.offspec_pm, self.ui.offspec_mp]
        Imin = 10 ** self.ui.offspecImin.value()
        Imax = 10 ** self.ui.offspecImax.value()
        if Imin >= Imax:
            return
        data_set_keys = list(self.main_window.data_manager.data_sets.keys())
        for i in range(len(data_set_keys)):
            plot = plots[i]
            if plot.cplot is not None:
                for item in plot.canvas.ax.collections:
                    item.set_clim(Imin, Imax)
        self.plot_manager.plot_offspec(recalc=False)

    def clip_offspec_colorscale(self):
        """Modify color scale"""
        plots = [self.ui.offspec_pp, self.ui.offspec_mm, self.ui.offspec_pm, self.ui.offspec_mp]
        Imin = 1e10
        data_set_keys = list(self.main_window.data_manager.data_sets.keys())
        for i in range(len(data_set_keys)):
            plot = plots[i]
            if plot.cplot is not None:
                for item in plot.canvas.ax.collections:
                    I = item.get_array()
                    Imin = min(Imin, I[I > 0].min())
        for i in range(len(data_set_keys)):
            plot = plots[i]
            if plot.cplot is not None:
                for item in plot.canvas.ax.collections:
                    I = item.get_array()
                    I[I <= 0] = Imin
                    item.set_array(I)
            plot.draw()
