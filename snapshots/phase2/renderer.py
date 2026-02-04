import altair as alt
import pandas as pd

# -----------------------------
# FILTER APPLICATION
# -----------------------------
def _apply_filters(spec, df):
    filters = spec.get("data", {}).get("filters", [])
    if not filters:
        return df

    df_filtered = df.copy()

    for f in filters:
        col = f["column"]
        op = f["operator"]
        val = f["value"]

        if op == "==":
            df_filtered = df_filtered[df_filtered[col] == val]
        elif op == "!=":
            df_filtered = df_filtered[df_filtered[col] != val]
        elif op == ">":
            df_filtered = df_filtered[df_filtered[col] > val]
        elif op == "<":
            df_filtered = df_filtered[df_filtered[col] < val]
        elif op == ">=":
            df_filtered = df_filtered[df_filtered[col] >= val]
        elif op == "<=":
            df_filtered = df_filtered[df_filtered[col] <= val]

    return df_filtered


# -----------------------------
# MAIN DISPATCHER
# -----------------------------
def render_chart(spec: dict, df: pd.DataFrame):
    df = _apply_filters(spec, df)

    chart_type = spec["chart"]["type"]

    if chart_type == "pie":
        return _render_pie(spec, df)

    if chart_type == "line":
        return _render_line(spec, df)

    if chart_type == "bar":
        return _render_bar(spec, df)

    if chart_type == "boxplot":
        return _render_boxplot(spec, df)

    if chart_type == "violin":
        return _render_violin(spec, df)

    raise ValueError(f"Unsupported chart type: {chart_type}")


# -----------------------------
# HELPERS
# -----------------------------
def _apply_title(chart, spec):
    title = spec.get("chart", {}).get("title")
    if title:
        chart = chart.properties(title=title)
    return chart


def _apply_tooltip(encoding, chart):
    tooltip_cols = encoding.get("tooltip")
    if tooltip_cols:
        chart = chart.encode(tooltip=tooltip_cols)
    return chart


# -----------------------------
# PIE CHART
# -----------------------------
def _render_pie(spec, df):
    encoding = spec["encoding"]

    theta_col = encoding["theta"]["column"]
    color_col = encoding["color"]["column"]

    chart = alt.Chart(df).mark_arc().encode(
        theta=alt.Theta(field=theta_col, type="quantitative"),
        color=alt.Color(field=color_col, type="nominal")
    )

    chart = _apply_tooltip(encoding, chart)
    chart = _apply_title(chart, spec)

    return chart


# -----------------------------
# LINE CHART (WITH OPTIONAL CI)
# -----------------------------
def _render_line(spec, df):
    encoding = spec["encoding"]
    x_col = encoding["x"]["column"]
    y_col = encoding["y"]["column"]

    stats = spec.get("statistics", {})
    ci = stats.get("confidence_interval")

    if ci is not None:
        base = alt.Chart(df).transform_aggregate(
            mean=f"mean({y_col})",
            ci_lower=f"ci0({y_col})",
            ci_upper=f"ci1({y_col})",
            groupby=[x_col]
        )

        band = base.mark_area(opacity=0.3).encode(
            x=alt.X(field=x_col, type="temporal"),
            y=alt.Y("ci_lower:Q", title=""),
            y2="ci_upper:Q"
        )

        line = base.mark_line().encode(
            x=alt.X(field=x_col, type="temporal"),
            y=alt.Y("mean:Q", title=y_col)
        )

        chart = band + line

    else:
        chart = alt.Chart(df).mark_line().encode(
            x=alt.X(field=x_col, type="temporal"),
            y=alt.Y(field=y_col, type="quantitative")
        )

    chart = _apply_tooltip(encoding, chart)
    chart = _apply_title(chart, spec)

    return chart


# -----------------------------
# BAR CHART
# -----------------------------
def _render_bar(spec, df):
    encoding = spec["encoding"]

    x_col = encoding["x"]["column"]
    y_col = encoding["y"]["column"]

    chart = alt.Chart(df).mark_bar().encode(
        x=alt.X(field=x_col, type="nominal"),
        y=alt.Y(field=y_col, type="quantitative")
    )

    if "color" in encoding:
        color_col = encoding["color"]["column"]
        chart = chart.encode(color=alt.Color(field=color_col, type="nominal"))

    if "column" in encoding:
        col_col = encoding["column"]["column"]
        chart = chart.encode(column=alt.Column(field=col_col, type="nominal"))

    chart = _apply_tooltip(encoding, chart)
    chart = _apply_title(chart, spec)

    return chart


# -----------------------------
# BOXPLOT
# -----------------------------
def _render_boxplot(spec, df):
    encoding = spec["encoding"]

    y_col = encoding["y"]["column"]
    y_type = encoding["y"]["type"]

    chart = alt.Chart(df).mark_boxplot().encode(
        y=alt.Y(field=y_col, type=y_type)
    )

    if "x" in encoding:
        x_col = encoding["x"]["column"]
        x_type = encoding["x"]["type"]
        chart = chart.encode(x=alt.X(field=x_col, type=x_type))

    chart = _apply_tooltip(encoding, chart)
    chart = _apply_title(chart, spec)

    return chart


# -----------------------------
# VIOLIN PLOT
# -----------------------------
def _render_violin(spec, df):
    encoding = spec["encoding"]

    y_col = encoding["y"]["column"]
    y_type = encoding["y"]["type"]

    if "x" in encoding:
        x_col = encoding["x"]["column"]
        x_type = encoding["x"]["type"]
    else:
        x_col = None

    base = alt.Chart(df)

    if x_col:
        violin = base.transform_density(
            y_col,
            as_=[y_col, "density"],
            groupby=[x_col]
        ).mark_area(orient="horizontal").encode(
            y=alt.Y(f"{y_col}:Q", type=y_type),
            x=alt.X("density:Q", stack="center", title=None),
            color=alt.Color(f"{x_col}:N")
        )
    else:
        violin = base.transform_density(
            y_col,
            as_=[y_col, "density"]
        ).mark_area(orient="horizontal").encode(
            y=alt.Y(f"{y_col}:Q", type=y_type),
            x=alt.X("density:Q", stack="center", title=None)
        )

    violin = _apply_tooltip(encoding, violin)
    violin = _apply_title(violin, spec)

    return violin