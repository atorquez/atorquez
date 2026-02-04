
def build_title(intent):
    """
    Build a human-readable chart title based on the intent.
    Handles missing fields gracefully.
    """

    chart_type = intent.get("chart_type")
    y_axis = intent.get("y_axis")
    filters = intent.get("filters", [])

    # Base title
    if y_axis:
        title = y_axis.replace("_", " ").title()
    else:
        title = "Value"

    # Add chart type context
    if chart_type:
        if chart_type == "line":
            title += " Over Time"
        elif chart_type == "bar":
            title += " by Category"
        elif chart_type == "boxplot":
            title += " Distribution"
        elif chart_type == "violin":
            title += " Distribution"
        # pie chart doesn't need modification

    # Add filters
    if filters:
        filter_parts = []
        for f in filters:
            col = f["column"].replace("_", " ").title()
            op = f["operator"]
            val = f["value"]
            filter_parts.append(f"{col} {op} {val}")
        title += " (" + ", ".join(filter_parts) + ")"

    return title

def intent_to_spec(intent, available_columns):

    chart_type = intent.get("chart_type")
    x_axis = intent.get("x_axis")
    y_axis = intent.get("y_axis")
    filters = intent.get("filters", [])
    statistics = intent.get("statistics", {})

    # ---------------------------
    # 1. Validate required fields
    # ---------------------------
    if chart_type is None:
        # caller must ask user for chart type
        return {
            "chart": {"type": None, "title": "Value "},
            "encoding": {},
            "data": {"filters": filters}
        }

    if x_axis is None or y_axis is None:
        # caller must ask user for axes
        return {
            "chart": {"type": chart_type, "title": "Value "},
            "encoding": {},
            "data": {"filters": filters}
        }

    # ---------------------------
    # 2. Build chart block
    # ---------------------------
    chart_block = {
        "type": chart_type,
        "title": build_title(intent)
    }

    # ---------------------------
    # 3. Build encoding block
    # ---------------------------
    encoding_block = {
        "x": {"column": x_axis, "type": available_columns[x_axis]},
        "y": {"column": y_axis, "type": available_columns[y_axis]},
        "tooltip": [x_axis, y_axis]
    }

    # ---------------------------
    # 4. Build final spec
    # ---------------------------
    spec = {
        "chart": chart_block,
        "encoding": encoding_block,
        "data": {"filters": filters}
    }

    if statistics:
        spec["statistics"] = statistics

    return spec