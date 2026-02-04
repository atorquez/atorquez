import stat
import statistics


def build_title(intent):
    chart_type = intent.get("chart_type")
    y_axis = intent.get("y_axis")
    y_left = intent.get("y_axis_left")
    y_right = intent.get("y_axis_right")
    filters = intent.get("filters", [])

    # -------------------------
    # Collect all metric fields
    # -------------------------
    metrics = []

    # Primary y_axis
    if isinstance(y_axis, list):
        metrics.extend(y_axis)
    elif y_axis:
        metrics.append(y_axis)

    # Dual-axis left
    if isinstance(y_left, list):
        metrics.extend(y_left)
    elif y_left:
        metrics.append(y_left)

    # Dual-axis right
    if isinstance(y_right, list):
        metrics.extend(y_right)
    elif y_right:
        metrics.append(y_right)

    # Deduplicate while preserving order
    seen = set()
    unique_metrics = []
    for m in metrics:
        if m and m not in seen:
            seen.add(m)
            unique_metrics.append(m)

    # -------------------------
    # Base title from metrics
    # -------------------------
    if unique_metrics:
        title = ", ".join([m.replace("_", " ").title() for m in unique_metrics])
    else:
        title = "Value"

    # -------------------------
    # Chart-type suffix
    # -------------------------
    if chart_type == "line":
        title += " Over Time"
    elif chart_type == "bar":
        title += " by Category"
    elif chart_type in ("boxplot", "violin"):
        title += " Distribution"

    # -------------------------
    # Filters in title
    # -------------------------
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
    # Normalize x-axis to match merged dataframe columns
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
    # Chart block
    # ---------------------------------------------------
    chart_block = {
        "type": chart_type,
        "title": build_title(intent)
    }

    # ---------------------------------------------------
    # PHASE 5: Dual-axis mode
    # ---------------------------------------------------
    if y_left or y_right:
        # Normalize left/right to lists for tooltip construction
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
    # PHASE 3: Single-axis mode (fallback)
    # ---------------------------------------------------
    if isinstance(y_axis_raw, list):
        y_cols = y_axis_raw
    else:
        y_cols = [y_axis_raw]

    # ---------------------------------------------------
    # Determine x-axis type
    # ---------------------------------------------------
    if chart_type in ("line", "area"):
        x_type = "temporal"
    elif chart_type in ("bar", "boxplot", "violin", "pie"):
        x_type = "nominal"
    else:
        x_type = "temporal"  # fallback

    # ---------------------------------------------------
    # Determine y-axis column (supports statistics)
    # ---------------------------------------------------
    stat_list = statistics.get("aggregation", [])
    stat = stat_list[0] if stat_list else None

    metric = y_cols[0]  # always single metric for now

    if stat:
        # aggregated column name
        y_column = f"{stat}_{metric}"
    else:
        # raw metric
        y_column = metric
    tooltip_cols = [x_axis, y_column]

    
    # If statistics collapse the dataset to a single row,
    # a line chart cannot render. Switch to bar.
    if statistics.get("aggregation") and len(merged_columns) == 1:
        chart_type = "bar"
        intent["chart_type"] = "bar"
    
    # ---------------------------------------------------
    # Build encoding block
    # ---------------------------------------------------
    encoding_block = {
        "x": {"column": x_axis, "type": x_type},
        "y": {"column": y_column},
        "color": {"column": color} if color else None,
        "tooltip": tooltip_cols
    }

    # ---------------------------------------------------
    # Final spec
    # ---------------------------------------------------
    spec = {
        "chart": chart_block,
        "encoding": encoding_block,
        "data": {"filters": filters}
    }

    if statistics:
        spec["statistics"] = statistics

    return spec