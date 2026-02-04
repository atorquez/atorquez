import altair as alt
import pandas as pd
import webbrowser

# ---------------------------------------------------------
# ENTRYPOINT
# ---------------------------------------------------------
def render_chart(spec: dict, df: pd.DataFrame):
    chart_type = spec["chart"]["type"]

    if chart_type == "line":
        chart = _render_line(spec, df)
    elif chart_type == "pie":
        chart = _render_pie(spec, df)
    elif chart_type == "bar":
        chart = _render_bar(spec, df)
    else:
        raise ValueError(f"Unsupported chart type: {chart_type}")

    chart.save("output_chart.html")
    webbrowser.open("output_chart.html")


# ---------------------------------------------------------
# PIE CHART
# ---------------------------------------------------------
def _render_pie(spec, df):
    encoding = spec["encoding"]

    theta_col = encoding["theta"]["column"]
    color_col = encoding["color"]["column"]

    chart = (
        alt.Chart(df)
        .mark_arc()
        .encode(
            theta=alt.Theta(field=theta_col, type="quantitative"),
            color=alt.Color(field=color_col, type="nominal")
        )
    )
    return chart


# ---------------------------------------------------------
# BAR CHART
# ---------------------------------------------------------
def _render_bar(spec, df):
    encoding = spec["encoding"]

    x_col = encoding["x"]["column"]
    y_col = encoding["y"]["column"]
    color_col = encoding["color"]["column"]

    chart = (
        alt.Chart(df)
        .mark_bar()
        .encode(
            x=alt.X(field=x_col, type="nominal"),
            y=alt.Y(field=y_col, type="quantitative"),
            color=alt.Color(field=color_col, type="nominal") if color_col else alt.value("steelblue")
        )
    )
    return chart


# ---------------------------------------------------------
# LINE CHART (Phase‑3 + Phase‑4 Dual Axis)
# ---------------------------------------------------------
def _render_line(spec, df):
    encoding = spec["encoding"]

    x_col = encoding["x"]["column"]

    # Detect mode
    y_single = encoding.get("y", None)
    y_left = encoding.get("y_left", None)
    y_right = encoding.get("y_right", None)

    # ---------------------------------------------------------
    # PHASE 3: SINGLE-AXIS MODE
    # ---------------------------------------------------------
    if y_single is not None:
        y_cols = y_single["column"]
        if isinstance(y_cols, str):
            y_cols = [y_cols]

        color_spec = encoding.get("color", None)
        layers = []

        for y in y_cols:
            if color_spec:
                color_encoding = alt.Color(field=color_spec["column"])
            else:
                color_encoding = alt.value(_color_for_metric(y))

            layer = (
                alt.Chart(df)
                .mark_line()
                .encode(
                    x=alt.X(field=x_col, type="temporal"),
                    y=alt.Y(field=y, type="quantitative"),
                    color=color_encoding
                )
            )
            layers.append(layer)

        chart = alt.layer(*layers)
        title = _auto_title(x_col, y_cols, color_spec["column"] if color_spec else None)
        return chart.properties(title=title, width=800, height=400)

    # ---------------------------------------------------------
    # PHASE 4: DUAL-AXIS MODE
    # ---------------------------------------------------------
    layers = []

    # Left-axis metrics
    if y_left is not None:
        left_cols = y_left["column"]
        if isinstance(left_cols, str):
            left_cols = [left_cols]

        for y in left_cols:
            layers.append(
                alt.Chart(df)
                .mark_line()
                .encode(
                    x=alt.X(field=x_col, type="temporal"),
                    y=alt.Y(
                        field=y,
                        type="quantitative",
                        axis=alt.Axis(title=y, titleColor=_color_for_metric(y))
                    ),
                    color=alt.value(_color_for_metric(y))
                )
            )

    # Right-axis metrics
    if y_right is not None:
        right_cols = y_right["column"]
        if isinstance(right_cols, str):
            right_cols = [right_cols]

        for y in right_cols:
            layers.append(
                alt.Chart(df)
                .mark_line()
                .encode(
                    x=alt.X(field=x_col, type="temporal"),
                    y=alt.Y(
                        field=y,
                        type="quantitative",
                        axis=alt.Axis(title=y, titleColor=_color_for_metric(y))
                    ),
                    color=alt.value(_color_for_metric(y))
                )
            )

    if not layers:
        raise ValueError("No y-axis columns provided for line chart.")

    chart = alt.layer(*layers).resolve_scale(y="independent")

    # Build title
    all_metrics = []
    if y_left: all_metrics += left_cols
    if y_right: all_metrics += right_cols

    title = _auto_title(x_col, all_metrics, None) + " (dual axis)"

    return chart.properties(title=title, width=800, height=400)


# ---------------------------------------------------------
# HELPERS
# ---------------------------------------------------------
def _color_for_metric(metric):
    palette = {
        "blood_pressure": "#d62728",
        "heart_rate": "#1f77b4",
        "temperature": "#ff7f0e",
        "oxygen_saturation": "#2ca02c",
        "glucose_level": "#9467bd",
    }
    return palette.get(metric, "#333333")


def _auto_title(x, ys, color):
    if isinstance(ys, list):
        y_part = ", ".join(ys)
    else:
        y_part = ys

    title = f"{y_part} over {x}"
    if color:
        title += f" by {color}"
    return title