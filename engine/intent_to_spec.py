import stat
import statistics


def build_title(intent):
    chart_type = intent.get("chart_type")
    y_axis = intent.get("y_axis")
    y_left = intent.get("y_axis_left")
    y_right = intent.get("y_axis_right")
    filters = intent.get("filters", [])

    metrics = []
    if isinstance(y_axis, list):
        metrics.extend(y_axis)
    elif y_axis:
        metrics.append(y_axis)

    if isinstance(y_left, list):
        metrics.extend(y_left)
    elif y_left:
        metrics.append(y_left)

    if isinstance(y_right, list):
        metrics.extend(y_right)
    elif y_right:
        metrics.append(y_right)

    seen = set()
    unique_metrics = []
    for m in metrics:
        if m and m not in seen:
            seen.add(m)
            unique_metrics.append(m)

    if unique_metrics:
        title = ", ".join([m.replace("_", " ").title() for m in unique_metrics])
    else:
        title = "Value"

    if chart_type == "line":
        title += " Over Time"
    elif chart_type == "bar":
        title += " by Category"
    elif chart_type in ("boxplot", "violin"):
        title += " Distribution"

    if filters:
        parts = []
        for f in filters:
            col = f["column"].replace("_", " ").title()
            op = f["operator"]
            val = f["value"]
            parts.append(f"{col} {op} {val}")
        title += " (" + ", ".join(parts) + ")"

    return title


def intent_to_spec(intent, merged_columns):
    chart_type = intent.get("chart_type")
    x_axis = intent.get("x_axis")
    y_axis_raw = intent.get("y_axis")
    y_left = intent.get("y_axis_left")
    y_right = intent.get("y_axis_right")
    color = intent.get("color")
    filters = intent.get("filters", [])
    statistics = intent.get("statistics", {})

    # ---------------------------------------------------
    # Auto-detect aggregated column names
    # ---------------------------------------------------
    if y_axis_raw and isinstance(y_axis_raw, str) and "_" in y_axis_raw:
        parts = y_axis_raw.split("_", 1)
        possible_stat = parts[0]
        possible_metric = parts[1]

        if possible_stat in ("mean", "median", "std", "min", "max", "var", "sum", "count"):
            statistics = {"aggregation": [possible_stat]}
            intent["statistics"] = statistics
            intent["y_axis"] = possible_metric
            y_axis_raw = possible_metric

            if not chart_type:
                chart_type = "line"
                intent["chart_type"] = "line"

            if not x_axis and "date" in merged_columns:
                x_axis = "date"
                intent["x_axis"] = "date"

    # ---------------------------------------------------
    # Normalize x-axis
    # ---------------------------------------------------
    if x_axis == "day" and "day" not in merged_columns and "date" in merged_columns:
        x_axis = "date"

    print(">>> FINAL X_AXIS USED IN SPEC:", x_axis)

    # ---------------------------------------------------
    # Validate required fields
    # ---------------------------------------------------
    if chart_type is None or x_axis is None:
        return {
            "chart": {"type": chart_type, "title": "Value"},
            "encoding": {},
            "data": {"filters": filters}
        }

    # ---------------------------------------------------
    # Safety: drop invalid color columns
    # ---------------------------------------------------
    if color not in merged_columns:
        color = None

    # ---------------------------------------------------
    # Chart block
    # ---------------------------------------------------
    chart_block = {
        "type": chart_type,
        "title": build_title(intent)
    }

    # ---------------------------------------------------
    # Dual-axis mode
    # ---------------------------------------------------
    if y_left or y_right:
        def to_list(v):
            if v is None:
                return []
            if isinstance(v, list):
                return v
            return [v]

        y_left_list = to_list(y_left)
        y_right_list = to_list(y_right)

        tooltip_cols = [x_axis] + y_left_list + y_right_list

        encoding_block = {
            "x": {"column": x_axis, "type": "temporal"},
            "y_left": {"column": y_left} if y_left else None,
            "y_right": {"column": y_right} if y_right else None,
            "color": {"column": color} if color else None,
            "tooltip": tooltip_cols
        }

        spec = {
            "chart": chart_block,
            "encoding": encoding_block,
            "data": {"filters": filters}
        }

        if statistics:
            spec["statistics"] = statistics

        return spec

    # ---------------------------------------------------
    # Grouped aggregation bar charts (Option A: single metric)
    # ---------------------------------------------------
    if chart_type == "bar" and statistics and x_axis and y_axis_raw:
        stat_list = statistics.get("aggregation", [])
        stat = stat_list[0] if stat_list else None

        metric = y_axis_raw if isinstance(y_axis_raw, str) else y_axis_raw[0]
        y_column = f"{stat}_{metric}" if stat else metric

        encoding_block = {
            "x": {"column": x_axis, "type": "nominal"},
            "y": {"column": y_column},
            "tooltip": [x_axis, y_column]
        }

        spec = {
            "chart": chart_block,
            "encoding": encoding_block,
            "data": {"filters": filters},
            "statistics": statistics
        }

        return spec

    # ---------------------------------------------------
    # Single-axis fallback
    # ---------------------------------------------------
    if isinstance(y_axis_raw, list):
        y_cols = y_axis_raw
    else:
        y_cols = [y_axis_raw]

    if chart_type in ("line", "area"):
        x_type = "temporal"
    elif chart_type in ("bar", "boxplot", "violin", "pie"):
        x_type = "nominal"
    else:
        x_type = "temporal"

    stat_list = statistics.get("aggregation", [])
    stat = stat_list[0] if stat_list else None

    metric = y_cols[0]
    y_column = f"{stat}_{metric}" if stat else metric

    tooltip_cols = [x_axis, y_column]

    if statistics.get("aggregation") and len(merged_columns) == 1:
        chart_type = "bar"
        intent["chart_type"] = "bar"

    encoding_block = {
        "x": {"column": x_axis, "type": x_type},
        "y": {"column": y_column},
        "color": {"column": color} if color else None,
        "tooltip": tooltip_cols
    }

    spec = {
        "chart": chart_block,
        "encoding": encoding_block,
        "data": {"filters": filters}
    }

    if statistics:
        spec["statistics"] = statistics

    return spec