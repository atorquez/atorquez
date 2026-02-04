import altair as alt
import pandas as pd
import webbrowser

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

    # Save + open
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
# MULTI‑METRIC LINE CHART (Phase‑3)
# ---------------------------------------------------------
def _render_line(spec, df):
    encoding = spec["encoding"]

    x_col = encoding["x"]["column"]
    y_cols = encoding["y"]["column"]  # may be string or list
    color_spec = encoding.get("color", None)

    # Normalize to list
    if isinstance(y_cols, str):
        y_cols = [y_cols]

    layers = []

    for y in y_cols:
        # If user specified a color grouping
        if color_spec:
            color_encoding = alt.Color(field=color_spec["column"])
        else:
            # Use metric-based palette
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

    # Auto-title
    title = _auto_title(x_col, y_cols, color_spec["column"] if color_spec else None)
    chart = chart.properties(title=title, width=800, height=400)

    return chart

# ---------------------------------------------------------
# Helpers
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