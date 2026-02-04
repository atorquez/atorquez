from datetime import datetime


# ---------------------------------------------------
# TITLE ENGINE (Phase 5.4)
# ---------------------------------------------------
def build_title(intent):
    chart_type = intent.get("chart_type")
    y_axis = intent.get("y_axis")
    filters = intent.get("filters", [])

    # -------------------------------
    # 1. Base metric title
    # -------------------------------
    if isinstance(y_axis, list):
        title = ", ".join([y.replace("_", " ").title() for y in y_axis])
    elif y_axis:
        title = y_axis.replace("_", " ").title()
    else:
        title = "Value"

    # -------------------------------
    # 2. Chart-type suffix
    # -------------------------------
    if chart_type == "line":
        title += " Over Time"
    elif chart_type == "bar":
        title += " by Category"
    elif chart_type in ("boxplot", "violin"):
        title += " Distribution"

    # -------------------------------
    # 3. Filter formatting
    # -------------------------------
    if filters:
        parts = []
        for f in filters:
            col = f["column"].replace("_", " ").title()
            op = f["operator"]
            val = f["value"]

            # Temporal ranges
            if op == "between" and isinstance(val, list) and len(val) == 2:
                v0 = str(val[0]).split("T")[0]
                v1 = str(val[1]).split("T")[0]

                # Convert to readable dates
                try:
                    d0 = datetime.fromisoformat(v0).strftime("%b %d, %Y")
                    d1 = datetime.fromisoformat(v1).strftime("%b %d, %Y")
                except:
                    d0, d1 = v0, v1

                parts.append(f"{col} Between {d0} and {d1}")

            # Simple comparisons
            elif op in (">", "<", ">=", "<=", "=="):
                pretty_op = {
                    ">=": "≥",
                    "<=": "≤",
                    "==": "="
                }.get(op, op)
                parts.append(f"{col} {pretty_op} {val}")

            # Fallback
            else:
                parts.append(f"{col} {op} {val}")

        title += " (" + ", ".join(parts) + ")"

    return title



# ---------------------------------------------------
# INTENT → SPEC ENGINE
# ---------------------------------------------------
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
    # PHASE 5.1B: Auto-default chart type
    # ---------------------------------------------------
    if chart_type is None:

        if x_axis in merged_columns.get("temporal", []):
            x_axis_type = "temporal"
        elif x_axis in merged_columns.get("categorical", []):
            x_axis_type = "categorical"
        else:
            x_axis_type = "unknown"

        if x_axis_type == "temporal":
            chart_type = "line"
        elif x_axis_type == "categorical":
            chart_type = "bar"
        elif isinstance(y_axis_raw, list) and len(y_axis_raw) >= 2:
            chart_type = "line"
        else:
            chart_type = "bar"

        intent["chart_type"] = chart_type
        print(">>> CHART TYPE (auto-default):", chart_type)



    # ---------------------------------------------------
    # PHASE 5.2: Auto-default axes
    # ---------------------------------------------------

    # 1. Auto-default X-axis
    if x_axis is None:
        temporal_cols = merged_columns.get("temporal", [])
        if temporal_cols:
            x_axis = temporal_cols[0]
            intent["x_axis"] = x_axis
            print(">>> X-AXIS (auto-default temporal):", x_axis)
        else:
            all_cols = merged_columns.get("all", [])
            if all_cols:
                x_axis = all_cols[0]
                intent["x_axis"] = x_axis
                print(">>> X-AXIS (fallback):", x_axis)

    # 2. Auto-default Y-axis
    if not y_axis_raw:
        quantitative_cols = merged_columns.get("quantitative", [])
        if quantitative_cols:
            y_axis_raw = quantitative_cols
            intent["y_axis"] = y_axis_raw
            print(">>> Y-AXIS (auto-default quantitative):", y_axis_raw)

    # 3. Auto-default dual-axis
    if not y_left and not y_right:
        if isinstance(y_axis_raw, list) and len(y_axis_raw) == 2:
            y_left = y_axis_raw[0]
            y_right = y_axis_raw[1]
            intent["y_axis_left"] = y_left
            intent["y_axis_right"] = y_right
            print(">>> DUAL-AXIS (auto-default):", y_left, y_right)



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
    # PHASE 5.3: Replace placeholder temporal filters
    # ---------------------------------------------------
    for f in intent["filters"]:
        if f["column"] == "__TEMPORAL__":
            f["column"] = x_axis
            print(">>> TEMPORAL FILTER REPLACED WITH:", x_axis)



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
            "tooltip": (
                [x_axis] +
                (y_left if isinstance(y_left, list) else ([y_left] if y_left else [])) +
                (y_right if isinstance(y_right, list) else ([y_right] if y_right else []))
            )
        }

        spec = {
            "chart": chart_block,
            "encoding": encoding_block,
            "data": {"filters": intent["filters"]}
        }

        if statistics:
            spec["statistics"] = statistics

        return spec



    # ---------------------------------------------------
    # PHASE 3: Single-axis mode
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
        "data": {"filters": intent["filters"]}
    }

    if statistics:
        spec["statistics"] = statistics

    return spec