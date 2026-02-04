import re

mentioned_columns = []
 
#  ---------------------------
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
    "gender": "gender"
}

print(">>> USING nl_parser.py FROM:", __file__)

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
    if item and item not in lst:
        lst.append(item)

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
    # 1. Detect chart type (explicit)
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

    # ---------------------------
    # 2. Detect confidence interval
    # ---------------------------
    ci_match = re.search(r"(\d+)%\s*ci", text)
    if ci_match:
        ci_value = int(ci_match.group(1)) / 100
        intent["statistics"]["confidence_interval"] = ci_value

   
   
   
    # ---------------------------
    # 3. Detect x-axis
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

    # Rule 4: Fallback to match_column
    if intent["x_axis"] is None:
        intent["x_axis"] = match_column(text, available_columns)

    # Track mentioned column
    add_if_not_exists(mentioned_columns, intent["x_axis"])  
   
   
    # ---------------------------
    # 4. Detect y-axis
    # ---------------------------

    # Columns already used in filters should NOT be considered for axes
    filter_columns = [f["column"] for f in intent["filters"]]

    # Try to match a clinical/quantitative column first
    y_candidate = match_column(text, available_columns)

    # If the candidate is actually a filter column, ignore it
    if y_candidate in filter_columns:
        y_candidate = None

    # If still none, try again but only with quantitative columns
    if y_candidate is None:
        quantitative_cols = [c for c, t in available_columns.items() if t == "quantitative"]
        y_candidate = match_column(text, quantitative_cols)

    # Final fallback: default to the first quantitative column
    if y_candidate is None:
        y_candidate = next((c for c, t in available_columns.items() if t == "quantitative"), None)

    intent["y_axis"] = y_candidate

    # Track mentioned column
    add_if_not_exists(mentioned_columns, intent["y_axis"])

        
    # ---------------------------
    # 5. Detect color/grouping (explicit only)
    # ---------------------------
    if "color by" in text:
        after = text.split("color by", 1)[1]
        intent["color"] = match_column(after, available_columns)

    elif "group by" in text:
        after = text.split("group by", 1)[1]
        intent["color"] = match_column(after, available_columns)

    else:
        intent["color"] = None  

    # Record color column if present
    add_if_not_exists(mentioned_columns, intent["color"]) 
    
    def is_conflicting(new_filter, filters):
        for f in filters:
            if f["column"] == new_filter["column"]:
                if f["value"] == new_filter["value"] and f["operator"] != new_filter["operator"]:
                    return True
            if f["operator"] == "==" and new_filter["operator"] == "==":
                return True  # multiple == filters on same column
        return False
        
    print(">>> FILTER BLOCK EXECUTED")
    
    # ---------------------------
    # 6. Detect numeric filters
    # ---------------------------
    for col in available_columns:
        match = re.search(fr"{col} (over|>|>=) (\d+)", text)
        if not match:
            continue

        op_raw = match.group(1)
        val = int(match.group(2))

        # Normalize operator
        op = ">" if op_raw == "over" else op_raw

        new_filter = {
            "column": col,
            "operator": op,
            "value": val
        }

        if not is_conflicting(new_filter, intent["filters"]):
            intent["filters"].append(new_filter)
            add_if_not_exists(mentioned_columns, col)
           
    # ---------------------------
    # 7. Detect categorical filters
    # ---------------------------
    CATEGORICAL_MAP = {
        "senior": "age_group",
        "adult": "age_group",
        "child": "age_group",
        "children": "age_group",
        "female": "gender",
        "male": "gender",

        # Smoker variants — ONLY the base word
        "smoker": "smoker",
        "smokers": "smoker"
    }

    for value, col in CATEGORICAL_MAP.items():

        # Skip if negated (handled in negation block)
        if (f"not {value}" in text or
            f"excluding {value}" in text or
            f"non-{value}" in text):
            continue

        # Whole-word match only
        if re.search(rf"\b{value}\b", text):
            normalized_value = value.rstrip("s")

            new_filter = {
                "column": col,
                "operator": "==",
                "value": normalized_value
            }

            if not is_conflicting(new_filter, intent["filters"]):
                intent["filters"].append(new_filter)
                add_if_not_exists(mentioned_columns, col)


    # ---------------------------
    # Negation + categorical filters
    # ---------------------------
    for value, col in CATEGORICAL_MAP.items():

        # Handle plural forms BEFORE regex whole-word match
        plural_value = value + "s"

        # If neither singular nor plural appears, skip
        if value not in text and plural_value not in text:
            continue

        normalized_value = value.rstrip("s")

        # NEGATION FIRST
        is_negated = (
            f"non-{value}" in text
            or f"non {value}" in text
            or f"non-{plural_value}" in text
            or f"non {plural_value}" in text
            or f"excluding {value}" in text
            or f"excluding {plural_value}" in text
        )

        if is_negated:
            new_filter = {
                "column": col,
                "operator": "!=",
                "value": "true"
            }
            if not is_conflicting(new_filter, intent["filters"]):
                intent["filters"].append(new_filter)
                add_if_not_exists(mentioned_columns, col)
            continue  # <-- CRITICAL: prevents positive match

        # POSITIVE MATCH (only if NOT negated)
        new_filter = {
            "column": col,
            "operator": "==",
            "value": normalized_value
        }
        if not is_conflicting(new_filter, intent["filters"]):
            intent["filters"].append(new_filter)
            add_if_not_exists(mentioned_columns, col)  
    
    # ---------------------------
    # 8. Age-based numeric filters (fallback for age_group)
    # ---------------------------

    if re.search(r"(over|above)\s+6[0-9]", text):
        new_filter = {
            "column": "age_group",
            "operator": "==",
            "value": "senior"
        }
        if not is_conflicting(new_filter, intent["filters"]):
            intent["filters"].append(new_filter)
            add_if_not_exists(mentioned_columns, "age_group")



    if re.search(r"(under|below)\s+(1[0-8]|[0-9])", text):
        new_filter = {
            "column": "age_group",
            "operator": "==",
            "value": "child"
        }
        if not is_conflicting(new_filter, intent["filters"]):
            intent["filters"].append(new_filter)
            add_if_not_exists(mentioned_columns, "age_group")

    if re.search(r"between\s+1[8-9]\s+and\s+6[0-4]", text):
        new_filter = {
            "column": "age_group",
            "operator": "==",
            "value": "adult"
        }
        if not is_conflicting(new_filter, intent["filters"]):
            intent["filters"].append(new_filter)
            add_if_not_exists(mentioned_columns, "age_group")
    
    # ---------------------------
    # Multi-condition numeric filters (AND logic)
    # ---------------------------
    numeric_patterns = re.findall(
    r"(\w+)\s*(over|>|>=|<|<=|under|below)\s*(\d+)",
    text
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

        new_filter = {
            "column": col,
            "operator": op,
            "value": int(val_raw)
        }

        if not is_conflicting(new_filter, intent["filters"]):
            intent["filters"].append(new_filter)
            add_if_not_exists(mentioned_columns, col)

    # ---------------------------
    # Multi-condition categorical filters (AND logic)
    # ---------------------------
    for value, col in CATEGORICAL_MAP.items():

        # Skip if negated (handled in negation block)
        if (f"not {value}" in text or
            f"excluding {value}" in text or
            f"non-{value}" in text):
            continue

        # Whole-word match only
        if re.search(rf"\b{value}\b", text):
            normalized_value = value.rstrip("s")

            new_filter = {
                "column": col,
                "operator": "==",
                "value": normalized_value
            }

            if not is_conflicting(new_filter, intent["filters"]):
                 intent["filters"].append(new_filter)
                 add_if_not_exists(mentioned_columns, col)
    
    # ---------------------------
    # 9. Temporal filters
    # ---------------------------
    from datetime import datetime, timedelta
    import pandas as pd

    now = pd.Timestamp.now()

    # last 7 days / past week

    if re.search(r"(last|past)\s+7\s+days|week", text):
        new_filter = {
            "column": "day",
            "operator": ">=",
            "value": (now - timedelta(days=7)).isoformat()
        }
        intent["filters"].append(new_filter)
        add_if_not_exists(mentioned_columns, "day")

    # last 30 days / past month
    if re.search(r"(last|past)\s+30\s+days|month", text):
        new_filter = {
            "column": "day",
            "operator": ">=",
            "value": (now - timedelta(days=30)).isoformat()
        }
        intent["filters"].append(new_filter)
        add_if_not_exists(mentioned_columns, "day")

    # January only
    if "january" in text:
        new_filter = {
            "column": "day",
            "operator": "range",
            "value": [
            pd.Timestamp("2024-01-01").isoformat(),
            pd.Timestamp("2024-01-31").isoformat()
           ]
        }
        intent["filters"].append(new_filter)
        add_if_not_exists(mentioned_columns, "day")

    # between Jan X and Jan Y
    match = re.search(r"between\s+jan(?:uary)?\s+(\d+)\s+and\s+jan(?:uary)?\s+(\d+)", text)
    if match:
        start_day = int(match.group(1))
        end_day = int(match.group(2))

        new_filter = {
            "column": "day",
            "operator": "range",
            "value": [
            pd.Timestamp(f"2024-01-{start_day:02d}").isoformat(),
            pd.Timestamp(f"2024-01-{end_day:02d}").isoformat()
            ]
        }
        intent["filters"].append(new_filter)
        add_if_not_exists(mentioned_columns, "day")

   
    # ---------------------------
    # 9. Ambiguous multi-metric detection
    # ---------------------------

    # Robust connectors for multi-metric requests (with typo tolerance)
    MULTI_CONNECTORS = [
    r"\band\b", r"\badn\b", r"\ban\b", r"\bnad\b",   # and + common typos
    r"\bvs\b", r"\bversus\b",
    r"\b&\b",
    r"\bplus\b",
    r",",  # comma-separated metrics
    ]

    # Check if the text contains any multi-metric connector
    has_multi_connector = any(re.search(conn, text) for conn in MULTI_CONNECTORS)

    # Collect mentioned columns using whole-word matching + synonyms
    mentioned_columns = []

    for col in available_columns:
        col_norm = normalize(col)

        # whole-word match for raw column name
        if re.search(rf"\b{col}\b", text):
            mentioned_columns.append(col)
            continue

        # whole-word match for normalized column name (blood pressure)
        if re.search(rf"\b{col_norm}\b", text):
            mentioned_columns.append(col)
            continue

        # whole-word match for synonyms
        for key, val in SYNONYMS.items():
            if val == col and re.search(rf"\b{key}\b", text):
                mentioned_columns.append(col)
                break

    # Keep only quantitative columns
    quantitative_mentions = [
        col for col in mentioned_columns
        if available_columns[col] == "quantitative"
    ]

    # Ambiguity rule:
    # If user mentions 2+ quantitative metrics AND uses a connector → ambiguous
    if len(quantitative_mentions) >= 2 and has_multi_connector:
        print(">>> AMBIGUOUS MULTI-METRIC REQUEST DETECTED")
        intent["x_axis"] = None
        intent["y_axis"] = None
        intent["chart_type"] = None
        #return intent

    # ---------------------------
    # 10. Auto-defaults for vague queries
    # ---------------------------
    if intent["x_axis"] is None and intent["y_axis"] is None:

        # Default x-axis: time
        if "day" in available_columns:
            intent["x_axis"] = "day"

        # Default y-axis: most clinically relevant metric
        for metric in ["blood_pressure", "heart_rate", "glucose_level",
                       "oxygen_saturation", "temperature"]:
            if metric in available_columns:
                intent["y_axis"] = metric
                break

        # Default chart type: line
        intent["chart_type"] = "line"

    # If x and y are the same → fallback to x = day
    if intent["x_axis"] == intent["y_axis"] and "day" in available_columns:
        intent["x_axis"] = "day"

    # ---------------------------
    # 11. Default chart type inference
    # ---------------------------
    if intent["chart_type"] is None:

        if intent["x_axis"] == "day":
            intent["chart_type"] = "line"

        elif intent["x_axis"] and available_columns[intent["x_axis"]] == "nominal":
            intent["chart_type"] = "bar"

        elif intent["y_axis"] and available_columns[intent["y_axis"]] == "quantitative":
            intent["chart_type"] = "line"

    # ---------------------------
    # Deduplicate filters
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
    
    # Add axes to mentioned columns
    add_if_not_exists(mentioned_columns, intent["x_axis"])
    add_if_not_exists(mentioned_columns, intent["y_axis"])

    return intent, mentioned_columns 
   
  