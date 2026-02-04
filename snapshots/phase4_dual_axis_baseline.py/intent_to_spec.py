def build_title(intent):
    chart_type = intent.get("chart_type")
    y_axis = intent.get("y_axis")
    filters = intent.get("filters", [])

    if isinstance(y_axis, list):
        title = ", ".join([y.replace("_", " ").title() for y in y_axis])
    elif y_axis:
        title = y_axis.replace("_", " ").title()
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
    y_axis_raw = intent.get("y_axis")  # Phase‑3 single-axis
    y_left = intent.get("y_axis_left")  # Phase‑4 dual-axis
    y_right = intent.get("y_axis_right")
    color = intent.get("color")
    filters = intent.get("filters", [])
    statistics = intent.get("statistics", {})

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
    # PHASE 4: Dual-axis mode
    # ---------------------------------------------------
    if y_left or y_right:
        encoding_block = {
            "x": {"column": x_axis, "type": "temporal"},
            "y_left": {"column": y_left} if y_left else None,
            "y_right": {"column": y_right} if y_right else None,
            "color": {"column": color} if color else None,
            "tooltip": [x_axis] +
                       (y_left if isinstance(y_left, list) else ([y_left] if y_left else [])) +
                       (y_right if isinstance(y_right, list) else ([y_right] if y_right else []))
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

    encoding_block = {
        "x": {"column": x_axis, "type": "temporal"},
        "y": {"column": y_cols},
        "color": {"column": color} if color else None,
        "tooltip": [x_axis] + y_cols
    }

    spec = {
        "chart": chart_block,
        "encoding": encoding_block,
        "data": {"filters": filters}
    }

    if statistics:
        spec["statistics"] = statistics

    return spec