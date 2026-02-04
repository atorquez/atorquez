import re
from datetime import timedelta
import pandas as pd

print(">>> USING nl_parser.py FROM:", __file__)

# ---------------------------
# 1. Normalization helper
# ---------------------------
def normalize(text):
    return (
        text.lower()
            .replace("_", " ")
            .replace("-", " ")
            .strip()
    )

# ---------------------------
# 2. Synonym dictionary
# ---------------------------
SYNONYMS = {
    "bp": "blood_pressure",
    "blood pressure": "blood_pressure",
    "pressure": "blood_pressure",

    "hr": "heart_rate",
    "heart rate": "heart_rate",

    "temp": "temperature",
    "temperature": "temperature",

    "o2": "oxygen_saturation",
    "oxygen": "oxygen_saturation",
    "oxygen saturation": "oxygen_saturation",

    "glucose": "glucose_level",
    "sugar": "glucose_level",

    "age group": "age_group",
    "gender": "gender",
}

ID_LIKE_COLUMNS = {"patient_id", "id", "record_id"}

# ---------------------------
# 3. Universal column matcher
# ---------------------------
def match_column(user_text, available_columns):
    text_norm = normalize(user_text)

    # 1. Synonym match
    for key, col in SYNONYMS.items():
        if key in text_norm and col in available_columns:
            return col

    # 2. Exact normalized match
    for col in available_columns:
        if normalize(col) in text_norm:
            return col

    # 3. Partial match
    for col in available_columns:
        col_norm = normalize(col)
        for word in text_norm.split():
            if word in col_norm:
                return col

    return None

def add_if_not_exists(lst, item):
    # If item is a list, add each element individually
    if isinstance(item, list):
        for i in item:
            if i not in lst:
                lst.append(i)
    else:
        if item and item not in lst:
            lst.append(item)
def is_conflicting(new_filter, filters):
    for f in filters:
        if f["column"] == new_filter["column"]:
            if f["value"] == new_filter["value"] and f["operator"] != new_filter["operator"]:
                return True
        if f["operator"] == "==" and new_filter["operator"] == "==":
            return True
    return False

# ---------------------------
# 4. Main parser
# ---------------------------
def parse_natural_language(text, available_columns):
    print(">>> PARSER RECEIVED TEXT:", text)
    print(">>> AVAILABLE COLUMNS:", available_columns)

    text = text.lower()
    mentioned_columns = []

    intent = {
        "chart_type": None,
        "x_axis": None,
        "y_axis": None,
        "color": None,
        "filters": [],
        "statistics": {}
    }

    # ---------------------------
    # Stage 1: Chart type + CI
    # ---------------------------
    if "line" in text:
        intent["chart_type"] = "line"
    elif "bar" in text:
        intent["chart_type"] = "bar"
    elif "pie" in text:
        intent["chart_type"] = "pie"
    elif "box" in text or "boxplot" in text:
        intent["chart_type"] = "boxplot"
    elif "violin" in text:
        intent["chart_type"] = "violin"

    ci_match = re.search(r"(\d+)%\s*ci", text)
    if ci_match:
        ci_value = int(ci_match.group(1)) / 100
        intent["statistics"]["confidence_interval"] = ci_value

    # ---------------------------
    # Stage 2: X-axis detection
    # ---------------------------
    # Rule 1: "over time" → day
    if "over time" in text and "day" in available_columns:
        intent["x_axis"] = "day"

    # Rule 2: "by X" (but not "color by" or "group by")
    if intent["x_axis"] is None:
        for col in available_columns:
            if (
                f"by {col}" in text
                and "color by" not in text
                and "group by" not in text
            ):
                intent["x_axis"] = col
                break

    # Rule 3: If user mentions a time-like column, prefer it
    if intent["x_axis"] is None:
        for time_col in ["day", "date", "time", "timestamp"]:
            if time_col in available_columns and time_col in text:
                intent["x_axis"] = time_col
                break

    # Rule 4: Fallback to match_column (excluding ID-like)
    if intent["x_axis"] is None:
        fallback_x = match_column(text, available_columns)
        if fallback_x in ID_LIKE_COLUMNS:
            fallback_x = None
        intent["x_axis"] = fallback_x

    add_if_not_exists(mentioned_columns, intent["x_axis"])

    # ---------------------------
    # Stage 3: Color / grouping
    # ---------------------------
    if "color by" in text:
        after = text.split("color by", 1)[1]
        intent["color"] = match_column(after, available_columns)
    elif "group by" in text:
        after = text.split("group by", 1)[1]
        intent["color"] = match_column(after, available_columns)
    else:
        intent["color"] = None

    add_if_not_exists(mentioned_columns, intent["color"])

    print(">>> FILTER BLOCK EXECUTED")

    # ---------------------------
    # Stage 4: Filters (numeric, categorical, negation, age, temporal)
    # ---------------------------

    # 4.1 Simple numeric filters: "<col> over|>|>= N"
    for col in available_columns:
        match = re.search(fr"{col} (over|>|>=) (\d+)", text)
        if not match:
            continue

        op_raw = match.group(1)
        val = int(match.group(2))
        op = ">" if op_raw == "over" else op_raw

        new_filter = {"column": col, "operator": op, "value": val}
        if not is_conflicting(new_filter, intent["filters"]):
            intent["filters"].append(new_filter)
            add_if_not_exists(mentioned_columns, col)

    # 4.2 Categorical filters
    CATEGORICAL_MAP = {
        "senior": "age_group",
        "adult": "age_group",
        "child": "age_group",
        "children": "age_group",
        "female": "gender",
        "male": "gender",
        "smoker": "smoker",
        "smokers": "smoker",
    }

    # Positive categorical
    for value, col in CATEGORICAL_MAP.items():
        if (
            f"not {value}" in text
            or f"excluding {value}" in text
            or f"non-{value}" in text
        ):
            continue

        if re.search(rf"\b{value}\b", text):
            normalized_value = value.rstrip("s")
            new_filter = {"column": col, "operator": "==", "value": normalized_value}
            if not is_conflicting(new_filter, intent["filters"]):
                intent["filters"].append(new_filter)
                add_if_not_exists(mentioned_columns, col)

    # Negation categorical
    for value, col in CATEGORICAL_MAP.items():
        plural_value = value + "s"
        if value not in text and plural_value not in text:
            continue

        normalized_value = value.rstrip("s")
        is_negated = (
            f"non-{value}" in text
            or f"non {value}" in text
            or f"non-{plural_value}" in text
            or f"non {plural_value}" in text
            or f"excluding {value}" in text
            or f"excluding {plural_value}" in text
        )

        if is_negated:
            new_filter = {"column": col, "operator": "!=", "value": "true"}
            if not is_conflicting(new_filter, intent["filters"]):
                intent["filters"].append(new_filter)
                add_if_not_exists(mentioned_columns, col)
            continue

        new_filter = {"column": col, "operator": "==", "value": normalized_value}
        if not is_conflicting(new_filter, intent["filters"]):
            intent["filters"].append(new_filter)
            add_if_not_exists(mentioned_columns, col)

    # 4.3 Age-based numeric → age_group
    if re.search(r"(over|above)\s+6[0-9]", text):
        new_filter = {"column": "age_group", "operator": "==", "value": "senior"}
        if not is_conflicting(new_filter, intent["filters"]):
            intent["filters"].append(new_filter)
            add_if_not_exists(mentioned_columns, "age_group")

    if re.search(r"(under|below)\s+(1[0-8]|[0-9])", text):
        new_filter = {"column": "age_group", "operator": "==", "value": "child"}
        if not is_conflicting(new_filter, intent["filters"]):
            intent["filters"].append(new_filter)
            add_if_not_exists(mentioned_columns, "age_group")

    if re.search(r"between\s+1[8-9]\s+and\s+6[0-4]", text):
        new_filter = {"column": "age_group", "operator": "==", "value": "adult"}
        if not is_conflicting(new_filter, intent["filters"]):
            intent["filters"].append(new_filter)
            add_if_not_exists(mentioned_columns, "age_group")

    # 4.4 Multi-condition numeric filters
    numeric_patterns = re.findall(
        r"(\w+)\s*(over|>|>=|<|<=|under|below)\s*(\d+)", text
    )
    for col_raw, op_raw, val_raw in numeric_patterns:
        col = match_column(col_raw, available_columns)
        if not col:
            continue

        if op_raw in ["over", ">"]:
            op = ">"
        elif op_raw == ">=":
            op = ">="
        elif op_raw in ["under", "below", "<"]:
            op = "<"
        elif op_raw == "<=":
            op = "<="
        else:
            continue

        new_filter = {"column": col, "operator": op, "value": int(val_raw)}
        if not is_conflicting(new_filter, intent["filters"]):
            intent["filters"].append(new_filter)
            add_if_not_exists(mentioned_columns, col)

    # 4.5 Multi-condition categorical filters
    for value, col in CATEGORICAL_MAP.items():
        if (
            f"not {value}" in text
            or f"excluding {value}" in text
            or f"non-{value}" in text
        ):
            continue

        if re.search(rf"\b{value}\b", text):
            normalized_value = value.rstrip("s")
            new_filter = {"column": col, "operator": "==", "value": normalized_value}
            if not is_conflicting(new_filter, intent["filters"]):
                intent["filters"].append(new_filter)
                add_if_not_exists(mentioned_columns, col)

    # 4.6 Temporal filters
    now = pd.Timestamp.now()

    if re.search(r"(last|past)\s+7\s+days|week", text):
        new_filter = {
            "column": "day",
            "operator": ">=",
            "value": (now - timedelta(days=7)).isoformat(),
        }
        intent["filters"].append(new_filter)
        add_if_not_exists(mentioned_columns, "day")

    if re.search(r"(last|past)\s+30\s+days|month", text):
        new_filter = {
            "column": "day",
            "operator": ">=",
            "value": (now - timedelta(days=30)).isoformat(),
        }
        intent["filters"].append(new_filter)
        add_if_not_exists(mentioned_columns, "day")

    if "january" in text:
        new_filter = {
            "column": "day",
            "operator": "range",
            "value": [
                pd.Timestamp("2024-01-01").isoformat(),
                pd.Timestamp("2024-01-31").isoformat(),
            ],
        }
        intent["filters"].append(new_filter)
        add_if_not_exists(mentioned_columns, "day")

    match = re.search(
        r"between\s+jan(?:uary)?\s+(\d+)\s+and\s+jan(?:uary)?\s+(\d+)", text
    )
    if match:
        start_day = int(match.group(1))
        end_day = int(match.group(2))
        new_filter = {
            "column": "day",
            "operator": "range",
            "value": [
                pd.Timestamp(f"2024-01-{start_day:02d}").isoformat(),
                pd.Timestamp(f"2024-01-{end_day:02d}").isoformat(),
            ],
        }
        intent["filters"].append(new_filter)
        add_if_not_exists(mentioned_columns, "day")

    # ---------------------------
    # Stage 5: Ambiguous multi-metric detection
    # ---------------------------
    MULTI_CONNECTORS = [
        r"\band\b", r"\badn\b", r"\ban\b", r"\bnad\b",
        r"\bvs\b", r"\bversus\b",
        r"\b&\b",
        r"\bplus\b",
        r",",
    ]

    has_multi_connector = any(re.search(conn, text) for conn in MULTI_CONNECTORS)

    # Collect mentioned columns (do NOT reset mentioned_columns)
    for col in available_columns:
        col_norm = normalize(col)

        if re.search(rf"\b{col}\b", text):
            add_if_not_exists(mentioned_columns, col)
            continue

        if re.search(rf"\b{col_norm}\b", text):
            add_if_not_exists(mentioned_columns, col)
            continue

        for key, val in SYNONYMS.items():
            if val == col and re.search(rf"\b{key}\b", text):
                add_if_not_exists(mentioned_columns, col)
                break

    quantitative_mentions = [
        col for col in mentioned_columns
        if available_columns[col] == "quantitative"
    ]

    if len(quantitative_mentions) >= 2 and has_multi_connector:
        print(">>> AMBIGUOUS MULTI-METRIC REQUEST DETECTED")
        intent["x_axis"] = intent["x_axis"]  # keep x if already good
        intent["y_axis"] = None
        intent["chart_type"] = intent["chart_type"]

    
    fallback_metrics = []
    # ---------------------------
    # Stage 6: Y-axis (multi-metric support)
    # ---------------------------
    filter_columns = [f["column"] for f in intent["filters"]]

    # All quantitative columns except ID-like
    quantitative_cols = [
        c for c, t in available_columns.items()
        if t == "quantitative" and c not in ID_LIKE_COLUMNS
    ]
    # Metrics explicitly mentioned in text
    explicit_metrics = [
        col for col in quantitative_cols
        if col in text and col not in filter_columns
    ]
    # Metrics mentioned anywhere (fallback)
    mentioned_metrics = [
        col for col in mentioned_columns
        if col in quantitative_cols and col not in filter_columns
    ]
    # Priority 1: explicit metrics in text
    if explicit_metrics:
        intent["y_axis"] = explicit_metrics if len(explicit_metrics) > 1 else explicit_metrics[0]

    # Priority 2: metrics mentioned elsewhere
    elif mentioned_metrics:
        intent["y_axis"] = mentioned_metrics if len(mentioned_metrics) > 1 else mentioned_metrics[0]
    # Priority 3: fallback to first quantitative metric
    elif quantitative_cols:
        intent["y_axis"] = quantitative_cols[0]

    else:
        intent["y_axis"] = None
    print(">>> FINAL Y_AXIS:", intent["y_axis"])
    
    # ---------------------------
    # Stage 7: Auto-defaults
    # ---------------------------
    if intent["x_axis"] is None and intent["y_axis"] is None:
        if "day" in available_columns:
            intent["x_axis"] = "day"

        for metric in [
            "blood_pressure", "heart_rate", "glucose_level",
            "oxygen_saturation", "temperature"
        ]:
            if metric in available_columns:
                intent["y_axis"] = metric
                break

        intent["chart_type"] = "line"

    if intent["x_axis"] == intent["y_axis"] and "day" in available_columns:
        intent["x_axis"] = "day"

    # ---------------------------
    # Stage 8: Default chart type inference
    # ---------------------------
    if intent["chart_type"] is None:
        if intent["x_axis"] == "day":
            intent["chart_type"] = "line"
        elif intent["x_axis"] and available_columns[intent["x_axis"]] == "nominal":
            intent["chart_type"] = "bar"
        elif intent["y_axis"]:
            if isinstance(intent["y_axis"], list):
                # if any y is quantitative → line
                if any(available_columns[y] == "quantitative" for y in intent["y_axis"]):
                    intent["chart_type"] = "line"
            elif available_columns[intent["y_axis"]] == "quantitative":
                intent["chart_type"] = "line"

    # ---------------------------
    # Stage 9: Deduplicate filters
    # ---------------------------
    unique_filters = []
    seen = set()
    for f in intent["filters"]:
        key = (f["column"], f["operator"], str(f["value"]))
        if key not in seen:
            seen.add(key)
            unique_filters.append(f)
    intent["filters"] = unique_filters

    print(">>> FINAL INTENT:", intent)
    print(">>> FILTERS APPLIED:")
    for f in intent["filters"]:
        print(f"    {f['column']} {f['operator']} {f['value']}")

    add_if_not_exists(mentioned_columns, intent["x_axis"])
    add_if_not_exists(mentioned_columns, intent["y_axis"])

    return intent, mentioned_columns
   
  