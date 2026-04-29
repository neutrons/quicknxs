from functools import reduce

import plotly.graph_objs as go
import plotly.offline as py

py.init_notebook_mode(connected=True)


def plot1d(
    data_list, data_names=None, x_title="", y_title="", x_log=False, y_log=False, show_dx=True, width=600, height=400
):
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
        width=width,
        height=height,
        margin=dict(t=40, b=40, l=80, r=40),
        hovermode="closest",
        bargap=0,
        xaxis=x_layout,
        yaxis=y_layout,
    )

    fig = go.Figure(data=data, layout=layout)
    py.iplot(fig, show_link=False)


def plot_heatmap(x, y, z, x_title="", y_title="", surface=False, x_log=False, y_log=False, z_min=None, z_max=None):
    """
    Produce a 2D plot
    """
    import plotly.graph_objs as go

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
        autocolorscale=False,  # type=plot_type,
        hoverinfo="x+y+z",
        colorscale=colorscale,
        zauto=z_min is None,
        zmin=z_min,
        zmax=z_max,
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
