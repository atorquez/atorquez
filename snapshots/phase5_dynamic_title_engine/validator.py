class ChartValidationError(Exception):
    def __init__(self, message: str):
        super().__init__(message)


def validate_chart_spec(chart_spec: dict, available_columns: dict):
    _validate_chart_block(chart_spec)
    _validate_title(chart_spec)
    _validate_encoding(chart_spec, available_columns)
    _validate_tooltip(chart_spec, available_columns)
    _validate_filters(chart_spec, available_columns)
    _validate_statistics(chart_spec)


def _validate_chart_block(spec):
    allowed_types = {"line", "bar", "boxplot", "scatter", "histogram", "pie", "table","violin"}

    chart = spec.get("chart", {})
    chart_type = chart.get("type")

    if chart_type not in allowed_types:
        raise ChartValidationError(f"Unsupported chart type: {chart_type}")


def _validate_title(spec):
    chart = spec.get("chart", {})
    title = chart.get("title")

    if title is not None and not isinstance(title, str):
        raise ChartValidationError("Chart title must be a string")


def _validate_encoding(spec, available_columns):
    encoding = spec.get("encoding", {})

    for axis, axis_spec in encoding.items():
        # Skip tooltip — validated separately
        if axis == "tooltip":
            continue

        # Skip non-dict encodings (e.g., size=40, order="ascending")
        if not isinstance(axis_spec, dict):
            continue

        _validate_axis(axis, axis_spec, available_columns)


def _validate_axis(axis_name, axis_spec, available_columns):
    column = axis_spec.get("column")
    dtype = axis_spec.get("type")

    if column not in available_columns:
        raise ChartValidationError(f"Column '{column}' does not exist in the dataset")

    if dtype not in {"temporal", "quantitative", "nominal"}:
        raise ChartValidationError(f"Invalid type '{dtype}' for axis '{axis_name}'")


def _validate_tooltip(spec, available_columns):
    encoding = spec.get("encoding", {})
    tooltip = encoding.get("tooltip")

    if tooltip is None:
        return

    if not isinstance(tooltip, list):
        raise ChartValidationError("Tooltip must be a list of column names")

    for col in tooltip:
        if col not in available_columns:
            raise ChartValidationError(f"Tooltip column '{col}' does not exist in the dataset")


def _validate_filters(spec, available_columns):
    filters = spec.get("data", {}).get("filters", [])

    # If no filters, nothing to validate
    if not filters:
        return

    VALID_OPERATORS = {">", ">=", "<", "<=", "==", "!=", "range"}

    for f in filters:
        col = f.get("column")
        op = f.get("operator")
        val = f.get("value")

        # Validate column
        if col not in available_columns:
            raise ValueError(f"Invalid filter column: {col}")

        # Validate operator
        if op not in VALID_OPERATORS:
            raise ValueError(f"Invalid operator: {op}")

        # Special validation for range filters
        if op == "range":
            if not isinstance(val, list) or len(val) != 2:
                raise ValueError("Range operator requires a list of two timestamps")
            continue

        # Validate numeric filters
        if available_columns[col] == "quantitative":
            if not isinstance(val, (int, float)):
                raise ValueError(f"Filter value for {col} must be numeric")


def _validate_statistics(spec):
    stats = spec.get("statistics", {})
    ci = stats.get("confidence_interval")

    if ci is not None:
        if not (0 < ci < 1):
            raise ChartValidationError("Confidence interval must be between 0 and 1")
        

        




        
