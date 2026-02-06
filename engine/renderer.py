import altair as alt
import pandas as pd
import webbrowser

# ---------------------------------------------------------
# TABLE RENDERING (Option 2)
# ---------------------------------------------------------
def render_table(df: pd.DataFrame):
    """
    Renders the dataframe as a clean HTML table and opens it in the browser.
    """
    html = df.to_html(index=False)

    with open("output_table.html", "w") as f:
        f.write(html)

    webbrowser.open("output_table.html")

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
    elif chart_type == "boxplot":
        chart = _render_boxplot(spec, df)
    elif chart_type == "violin":
        chart = _render_violin(spec, df)
    else:
        raise ValueError(f"Unsupported chart type: {chart_type}")

    chart.save("output_chart.html")
    webbrowser.open("output_chart.html")

    return chart

# ---------------------------------------------------------
# PIE CHART
# ---------------------------------------------------------
def _render_pie(spec, df):
    encoding = spec["encoding"]
    group_col = encoding["color"]["column"]

    chart = (
        alt.Chart(df)
        .mark_arc()
        .encode(
            theta=alt.Theta(field=group_col, type="nominal", aggregate="count"),
            color=alt.Color(field=group_col, type="nominal")
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

    color_spec = encoding.get("color")
    color_col = color_spec["column"] if isinstance(color_spec, dict) else None

    # ---------------------------------------------------------
    # IMPORTANT: df is already aggregated when statistics are used
    # Do NOT aggregate again. Just plot the table as-is.
    # ---------------------------------------------------------

    chart = (
        alt.Chart(df)
        .mark_bar()
        .encode(
            x=alt.X(field=x_col, type="nominal"),
            y=alt.Y(field=y_col, type="quantitative"),
            color=alt.Color(field=color_col, type="nominal") if color_col else alt.value("steelblue")
        )
    )

    print("AGGREGATED DF:\n", df)

    return chart.properties(
        title=spec["chart"].get("title", f"{y_col} by {x_col}"),
        width=600,
        height=400
    )
# ---------------------------------------------------------
# BOX PLOT
# ---------------------------------------------------------
def _render_boxplot(spec, df):
    encoding = spec["encoding"]

    x_col = encoding["x"]["column"]
    y_col = encoding["y"]["column"]

    chart = (
        alt.Chart(df)
        .mark_boxplot()
        .encode(
            x=alt.X(field=x_col, type="nominal"),
            y=alt.Y(field=y_col, type="quantitative")
        )
    )

    return chart.properties(
        title=spec["chart"]["title"],
        width=600,
        height=400
    )


# ---------------------------------------------------------
# LINE CHART (with grouped dual-axis support)
# ---------------------------------------------------------
def _render_line(spec, df):
    encoding = spec["encoding"]
    x_col = encoding["x"]["column"]

    # Determine which y-column to use
    y_enc = encoding.get("y", None)
    if isinstance(y_enc, dict):
        y_cols = y_enc["column"]
        if isinstance(y_cols, str):
            y_cols = [y_cols]
    else:
        y_cols = []

    # If df is already aggregated (one row), line charts cannot render.
    # Switch to a point chart. If x_col is missing, create a dummy one.
    if len(df) == 1:
        y_col = y_cols[0]

        # If the aggregated df doesn't have the x_col, create a synthetic one
        if x_col not in df.columns:
            df = df.copy()
            df["stat"] = "summary"
            x_field = "stat"
            x_type = "nominal"
        else:
            x_field = x_col
            x_type = "temporal"

        chart = (
            alt.Chart(df)
            .mark_point(size=120)
            .encode(
                x=alt.X(field=x_field, type=x_type),
                y=alt.Y(field=y_col, type="quantitative")
            )
        )
        print("LINE DF (POINT MODE):\n", df)
        return chart.properties(
            title=spec["chart"].get("title", f"{y_col}"),
            width=600,
            height=400
        )

    # ---------------------------------------------------------
    # NORMAL MULTI-METRIC LINE CHART (AUTO‑ZOOM Y‑AXIS)
    # ---------------------------------------------------------
    layers = []
    for y_col in y_cols:

        # Auto‑zoom y-axis domain
        y_min = df[y_col].min()
        y_max = df[y_col].max()
        padding = (y_max - y_min) * 0.1 if y_max != y_min else 1  # avoid zero-range

        y_scale = alt.Scale(domain=[y_min - padding, y_max + padding])

        layer = (
            alt.Chart(df)
            .mark_line()
            .encode(
                x=alt.X(field=x_col, type="temporal"),
                y=alt.Y(field=y_col, type="quantitative", scale=y_scale),
                color=alt.value("steelblue")
            )
        )
        layers.append(layer)
 

# ---------------------------------------------------------
# VIOLIN CHART
# ---------------------------------------------------------
def _render_violin(spec, df):
    encoding = spec["encoding"]
    x_col = encoding["x"]["column"]
    y_col = encoding["y"]["column"]

    chart = (
        alt.Chart(df)
        .transform_density(
            y_col,
            as_=[y_col, "density"],
            groupby=[x_col]
        )
        .mark_area(orient="horizontal")
        .encode(
            y=alt.Y(f"{y_col}:Q", title=y_col),
            x=alt.X("density:Q", stack="center", title="Density"),
            color=alt.Color(f"{x_col}:N"),
            facet=alt.Facet(f"{x_col}:N", columns=1)
        )
    )
    return chart


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