from functools import reduce

import plotly.graph_objs as go
import plotly.offline as py

py.init_notebook_mode(connected=True)


def plot1d(data_list, data_names=None, x_title="", y_title="", x_log=False, y_log=False, show_dx=True):
    """
    Produce a 1D plot
    @param data_list: list of traces [ [x1, y1], [x2, y2], ...]
    @param data_names: name for each trace, for the legend
    """

    # Create traces
    if not isinstance(data_list, list):
        raise RuntimeError("plot1d: data_list parameter is expected to be a list")

    # Catch the case where the list is in the format [x y]
    data = []
    show_legend = False
    if len(data_list) == 2 and not isinstance(data_list[0], list):
        label = ""
        if isinstance(data_names, list) and len(data_names) == 1:
            label = data_names[0]
            show_legend = True
        data = [go.Scatter(name=label, x=data_list[0], y=data_list[1])]
    else:
        for i in range(len(data_list)):
            label = ""
            if isinstance(data_names, list) and len(data_names) == len(data_list):
                label = data_names[i]
                show_legend = True
            err_x = {}
            err_y = {}
            if len(data_list[i]) >= 3:
                err_y = dict(type="data", array=data_list[i][2], visible=True)
            if len(data_list[i]) >= 4:
                err_x = dict(type="data", array=data_list[i][3], visible=True)
                if show_dx is False:
                    err_x["thickness"] = 0
            data.append(go.Scatter(name=label, x=data_list[i][0], y=data_list[i][1], error_x=err_x, error_y=err_y))

    x_layout = dict(
        title=x_title,
        zeroline=False,
        exponentformat="power",
        showexponent="all",
        showgrid=True,
        showline=True,
        mirror="all",
        ticks="inside",
    )
    if x_log:
        x_layout["type"] = "log"
    y_layout = dict(
        title=y_title,
        zeroline=False,
        exponentformat="power",
        showexponent="all",
        showgrid=True,
        showline=True,
        mirror="all",
        ticks="inside",
    )
    if y_log:
        y_layout["type"] = "log"

    layout = go.Layout(
        showlegend=show_legend,
        autosize=True,
        width=600,
        height=400,
        margin=dict(t=40, b=40, l=80, r=40),
        hovermode="closest",
        bargap=0,
        xaxis=x_layout,
        yaxis=y_layout,
    )

    fig = go.Figure(data=data, layout=layout)
    py.iplot(fig, show_link=False)


def plot_heatmap(x, y, z, x_title="", y_title="", surface=False, x_log=False, y_log=False):
    """
    Produce a 2D plot
    """

    x_layout = dict(
        title=x_title,
        zeroline=False,
        exponentformat="power",
        showexponent="all",
        showgrid=True,
        showline=True,
        mirror="all",
        ticks="inside",
    )
    if x_log:
        x_layout["type"] = "log"

    y_layout = dict(
        title=y_title,
        zeroline=False,
        exponentformat="power",
        showexponent="all",
        showgrid=True,
        showline=True,
        mirror="all",
        ticks="inside",
    )
    if y_log:
        y_layout["type"] = "log"

    layout = go.Layout(
        showlegend=False,
        autosize=True,
        width=600,
        height=500,
        margin=dict(t=40, b=40, l=80, r=40),
        hovermode="closest",
        bargap=0,
        xaxis=x_layout,
        yaxis=y_layout,
    )

    colorscale = [
        [0, "rgb(0,0,131)"],
        [0.125, "rgb(0,60,170)"],
        [0.375, "rgb(5,255,255)"],
        [0.625, "rgb(255,255,0)"],
        [0.875, "rgb(250,0,0)"],
        [1, "rgb(128,0,0)"],
    ]
    plot_type = "surface" if surface else "heatmap"
    trace = go.Heatmap(
        z=z,
        x=x,
        y=y,
        autocolorscale=False,
        hoverinfo="x+y+z",
        colorscale=colorscale,  # type=plot_type,
    )
    fig = go.Figure(data=[trace], layout=layout)
    py.iplot(fig, show_link=False)


def fill_dict(accum_dict, value):
    if value[0] in ["#", "File"]:
        accum_dict[value[0]] = value[1]
    elif value[0] in ["#", "DB_ID", "P0", "PN", "dpix", "number"]:
        accum_dict[value[0]] = int(value[1])
    elif value[0] == "extract_fan":
        accum_dict[value[0]] = value[1] == "True"
    else:
        accum_dict[value[0]] = float(value[1])
    return accum_dict


def read_settings(file_path):
    DATA_BLOCK = 0
    DIRECT_BEAM_BLOCK = 1
    DATA_RUN_BLOCK = 2
    DIRECT_BEAM_HEADERS = [
        "#",
        "DB_ID",
        "P0",
        "PN",
        "x_pos",
        "x_width",
        "y_pos",
        "y_width",
        "bg_pos",
        "bg_width",
        "dpix",
        "tth",
        "number",
        "File",
    ]
    DATA_RUN_HEADERS = [
        "#",
        "scale",
        "P0",
        "PN",
        "x_pos",
        "x_width",
        "y_pos",
        "y_width",
        "bg_pos",
        "bg_width",
        "extract_fan",
        "dpix",
        "tth",
        "number",
        "DB_ID",
        "File",
    ]

    reduction_settings = {"direct_beam_runs": [], "data_runs": [], "process_type": "Specular"}

    fd = open(file_path, "r")
    current_block = DATA_BLOCK

    for line in fd.readlines():
        if "# Type:" in line:
            toks = line.strip().split()
            reduction_settings["process_type"] = toks[2]
            continue
        elif "[Direct Beam Runs]" in line:
            current_block = DIRECT_BEAM_BLOCK
            continue
        elif "[Data Runs]" in line:
            current_block = DATA_RUN_BLOCK
            continue
        elif "[Data]" in line:
            break

        if line.startswith("#") and current_block == DIRECT_BEAM_BLOCK:
            # Skip the column names
            if line.startswith("# DB_ID"):
                continue
            toks = line.strip().split()
            if len(toks) == len(DIRECT_BEAM_HEADERS):
                settings_dict = reduce(fill_dict, zip(DIRECT_BEAM_HEADERS, toks), {})
                reduction_settings["direct_beam_runs"].append(settings_dict)

        elif line.startswith("#") and current_block == DATA_RUN_BLOCK:
            # Skip the column names
            if line.startswith("# scale"):
                continue
            toks = line.strip().split()
            if len(toks) == len(DATA_RUN_HEADERS):
                settings_dict = reduce(fill_dict, zip(DATA_RUN_HEADERS, toks), {})
                reduction_settings["data_runs"].append(settings_dict)

    return reduction_settings


def find_peaks(workspace, x_min=50, x_max=250):
    """Find reflectivity peaks"""
    roi = RefRoi(
        InputWorkspace=workspace,
        NXPixel=304,
        NYPixel=256,
        XPixelMin=50,
        XPixelMax=303,
        YPixelMin=0,
        YPixelMax=255,
        IntegrateY=True,
        ConvertToQ=False,
    )
    peaks = Transpose(InputWorkspace=roi)
    peaks = CropWorkspace(InputWorkspace=peaks, XMin=x_min, XMax=x_max)
    output = LRPeakSelection(InputWorkspace=peaks)
    x_peak = (output[0][0] + x_min, output[0][1] + x_min)

    roi = RefRoi(
        InputWorkspace=workspace,
        NXPixel=304,
        NYPixel=256,
        XPixelMin=0,
        XPixelMax=303,
        YPixelMin=0,
        YPixelMax=255,
        IntegrateY=False,
        ConvertToQ=False,
    )
    peaks2 = Transpose(InputWorkspace=roi)
    peaks2 = CropWorkspace(InputWorkspace=peaks2, XMin=0, XMax=250)
    output = LRPeakSelection(InputWorkspace=peaks2)
    y_peak = output[1]
    return x_peak, y_peak


def process_run(run_number, settings, direct_beam=True):
    """Process a run"""
    ws = LoadEventNexus(
        Filename="REF_M%s" % run_number, NXentryName="entry-Off_Off", OutputWorkspace="%s_%s" % ("REF_M", run_number)
    )
    dirpix = ws.getRun()["DIRPIX"].value[0]
    x_max = 250 if direct_beam else dirpix - 30
    x_peak, y_peak = find_peaks(ws, x_max=x_max)
    r_max = settings["x_pos"] + settings["x_width"] / 2.0
    r_min = settings["x_pos"] - settings["x_width"] / 2.0
    low_max = settings["y_pos"] + settings["y_width"] / 2.0
    low_min = settings["y_pos"] - settings["y_width"] / 2.0

    print("r%s - PEAK: [%s %s]   Input: [%s %s]" % (run_number, x_peak[0], x_peak[1], r_min, r_max))
    print("r%s - LOW:  [%s %s]   Input: [%s %s]" % (run_number, y_peak[0], y_peak[1], low_min, low_max))
