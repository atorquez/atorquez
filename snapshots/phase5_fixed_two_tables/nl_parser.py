import re
from typing import Dict, Any, List, Tuple

# ---------------------------------------------------------
# Helper: simple keyword search
# ---------------------------------------------------------
def contains_any(text: str, keywords: List[str]) -> bool:
    t = text.lower()
    return any(k in t for k in keywords)


# ---------------------------------------------------------
# Main entry point
# ---------------------------------------------------------
def parse_natural_language(
    text: str,
    available_columns: Dict[str, str],
    file_schemas: Dict[str, Dict[str, str]],
) -> Dict[str, Any]:
    print(">>> PARSER RECEIVED TEXT:", text)
    print(">>> AVAILABLE COLUMNS:", available_columns)

    text_lower = text.lower()

    # -----------------------------------------------------
    # 0. Initialize intent skeleton
    # -----------------------------------------------------
    intent: Dict[str, Any] = {
        "chart_type": None,
        "x_axis": None,
        "y_axis": None,
        "color": None,
        "filters": [],
        "statistics": {},
        "mentioned_columns": [],
    }

    quantitative_cols = [
        c for c, t in available_columns.items() if t == "quantitative"
    ]
    temporal_cols = [
        c for c, t in available_columns.items() if t == "temporal"
    ]
    nominal_cols = [
        c for c, t in available_columns.items() if t == "nominal"
    ]

    # -----------------------------------------------------
    # 1. Metric detection (multi‑metric y-axis)
    # -----------------------------------------------------
    metric_candidates = [
        "glucose_level",
        "cholesterol",
        "hba1c",
        "blood_pressure",
        "heart_rate",
        "temperature",
        "oxygen_saturation",
    ]

    metric_aliases = {
        "glucose": "glucose_level",
        "sugar": "glucose_level",
        "cholesterol": "cholesterol",
        "hba1c": "hba1c",
        "blood pressure": "blood_pressure",
        "bp": "blood_pressure",
        "heart rate": "heart_rate",
        "pulse": "heart_rate",
        "temperature": "temperature",
        "temp": "temperature",
        "oxygen": "oxygen_saturation",
        "o2": "oxygen_saturation",
        "oxygen saturation": "oxygen_saturation",
    }

    detected_metrics = []

    # direct column name match
    for col in metric_candidates:
        if col in available_columns and col.replace("_", " ") in text_lower:
            detected_metrics.append(col)

    # alias match
    for alias, col in metric_aliases.items():
        if alias in text_lower and col in available_columns:
            if col not in detected_metrics:
                detected_metrics.append(col)

    # fallback
    if not detected_metrics and quantitative_cols:
        detected_metrics = [quantitative_cols[0]]

    intent["y_axis"] = detected_metrics
    intent["mentioned_columns"].extend(detected_metrics)
    print(">>> FINAL Y_AXIS:", intent["y_axis"])

    # -----------------------------------------------------
    # 2. Basic chart type inference
    # -----------------------------------------------------
    chart_type = None
    if contains_any(text_lower, ["trend", "over time", "time series"]):
        chart_type = "line"
    elif contains_any(text_lower, ["distribution", "histogram"]):
        chart_type = "histogram"
    elif contains_any(text_lower, ["violin", "spread", "shape"]):
        chart_type = "violin"
    elif contains_any(text_lower, ["bar", "count", "by "]) and detected_metrics:
        chart_type = "bar"
    else:
        chart_type = "line" if temporal_cols else "bar"

    intent["chart_type"] = chart_type

    # -----------------------------------------------------
    # 3. X-axis inference
    # -----------------------------------------------------
    print(">>> X-AXIS BLOCK IS RUNNING")

    x_axis = None
    if "date" in available_columns:
        x_axis = "date"

    intent["x_axis"] = x_axis
    if x_axis:
        intent["mentioned_columns"].append(x_axis)

    # -----------------------------------------------------
    # 4. Statistics / aggregation detection (multi‑stat)
    # -----------------------------------------------------
    stats = {"aggregation": []}

    if contains_any(text_lower, ["average", "mean"]):
        stats["aggregation"].append("mean")
    if "median" in text_lower:
        stats["aggregation"].append("median")
    if contains_any(text_lower, ["std", "standard deviation", "stdev"]):
        stats["aggregation"].append("std")
    if "variance" in text_lower:
        stats["aggregation"].append("var")
    if contains_any(text_lower, ["sum", "total"]):
        stats["aggregation"].append("sum")
    if contains_any(text_lower, ["count", "number of"]):
        stats["aggregation"].append("count")

    if "statistics" in text_lower and not stats["aggregation"]:
        stats["aggregation"] = ["mean"]

    intent["statistics"] = stats

    # -----------------------------------------------------
    # 5. Stage 1.7: Age-group normalization helpers
    # -----------------------------------------------------
    print(">>> STAGE 1.7 TRIGGERED")

    AGE_SYNONYMS = {
        "kid": "child",
        "kids": "child",
        "child": "child",
        "children": "child",
        "pediatric": "child",
        "paediatric": "child",
        "youth": "child",
        "adult": "adult",
        "adults": "adult",
        "senior": "senior",
        "seniors": "senior",
        "elderly": "senior",
        "older": "senior",
    }

    def normalize_age_token(token: str):
        token = token.lower().strip()
        if token in AGE_SYNONYMS:
            return AGE_SYNONYMS[token]
        # Only match exact tokens, not substrings or fuzzy matches
        if token in AGE_SYNONYMS:
            return AGE_SYNONYMS[token]
        return None

    # -----------------------------------------------------
    # 6. Grouping detection (MOVED BEFORE FILTERS)
    # -----------------------------------------------------
    group_col = None

    for col in nominal_cols:
        col_phrase = col.replace("_", " ")
        if f"by {col_phrase}" in text_lower:
            group_col = col
            break

    if group_col is None and ("by age" in text_lower or "by age group" in text_lower):
        if "age_group" in available_columns:
            group_col = "age_group"

    if group_col:
        intent["x_axis"] = group_col
        if group_col not in intent["mentioned_columns"]:
            intent["mentioned_columns"].append(group_col)
        print(f">>> GROUPING DETECTED: x_axis = {group_col}")
    else:
        print(">>> GROUPING DETECTED: none")

    # -----------------------------------------------------
    # 7. FILTER EXTRACTION BLOCK (PATCHED)
    # -----------------------------------------------------
    print(">>> FILTER BLOCK EXECUTED")

    filters: List[Dict[str, Any]] = []
    tokens = text_lower.replace(",", " ").split()

    for tok in tokens:

        # AGE GROUP FILTER ONLY IF NO GROUPING
        if group_col is None:
            age_value = normalize_age_token(tok)
            if age_value:
                filters.append(
                    {"column": "age_group", "operator": "==", "value": age_value}
                )
                continue

        # GENDER
        if tok in ["male", "man", "men"]:
            filters.append({"column": "gender", "operator": "==", "value": "male"})
            continue

        if tok in ["female", "woman", "women"]:
            filters.append({"column": "gender", "operator": "==", "value": "female"})
            continue

        # SMOKER
        if tok in ["smoker", "smokers"]:
            filters.append({"column": "smoker", "operator": "==", "value": True})
            continue

        if tok in ["nonsmoker", "non-smoker", "nonsmokers"]:
            filters.append({"column": "smoker", "operator": "!=", "value": True})
            continue

    # dedupe
    unique = []
    seen = set()
    for f in filters:
        key = (f["column"], f["operator"], f["value"])
        if key not in seen:
            seen.add(key)
            unique.append(f)
    intent["filters"] = unique

    if unique:
        print(">>> FILTERS APPLIED:")
        for f in unique:
            print(f"    {f['column']} {f['operator']} {f['value']}")
    else:
        print(">>> FILTERS APPLIED:")

    # -----------------------------------------------------
    # 8. Chart type refinement
    # -----------------------------------------------------
    if intent["chart_type"] is None:
        if group_col and detected_metrics:
            intent["chart_type"] = "bar"
        else:
            intent["chart_type"] = "line"

    if contains_any(text_lower, ["spread", "shape", "violin"]):
        intent["chart_type"] = "violin"

    print(">>> AFTER STAGE 8 CHART TYPE:", intent["chart_type"])

    # -----------------------------------------------------
    # 9. Final bookkeeping
    # -----------------------------------------------------
    intent["mentioned_columns"] = list(dict.fromkeys(intent["mentioned_columns"]))

    print(">>> FINAL INTENT:", intent)
    return intent

   
  