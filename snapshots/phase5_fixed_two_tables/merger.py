import pandas as pd

# ============================================================
# SAFE INNER JOIN (Phase‑3 safety)
# ============================================================

def safe_inner_join(left_df, right_df, on="patient_id"):
    """
    Phase‑3 safe join:
    - Left side (primary) may have duplicate patient_id (time-series)
    - Right side must NOT have duplicate patient_id (patient-level or lab-level)
    - Prevents row explosion by ensuring right_df is unique on join key
    """

    if on not in left_df.columns:
        raise ValueError(f"Left dataframe missing join column '{on}'")

    if on not in right_df.columns:
        raise ValueError(f"Right dataframe missing join column '{on}'")

    # Right side must be unique
    if right_df[on].duplicated().any():
        raise ValueError(
            f"Right dataframe '{on}' has duplicate values — unsafe to merge"
        )

    merged = pd.merge(left_df, right_df, on=on, how="inner")

    if len(merged) > len(left_df):
        raise ValueError(
            f"Join caused row explosion: {len(merged)} rows vs {len(left_df)} in primary"
        )

    return merged


# ============================================================
# HELPER: Dual-axis time-series alignment (Phase‑5)
# ============================================================

def align_dual_axis_timeseries(
    left_df,
    right_df,
    left_time_col,
    right_time_col,
    group_key,
    left_metric,
    right_metric,
):
    left_df = left_df.copy()
    right_df = right_df.copy()

    left_df[left_time_col] = pd.to_datetime(left_df[left_time_col])
    right_df[right_time_col] = pd.to_datetime(right_df[right_time_col])

    left_df = left_df.sort_values([group_key, left_time_col]).reset_index(drop=True)
    right_df = right_df.sort_values([group_key, right_time_col]).reset_index(drop=True)

    left_df = left_df.sort_values(left_time_col).reset_index(drop=True)
    right_df = right_df.sort_values(right_time_col).reset_index(drop=True)

    left_sub = left_df[[group_key, left_time_col, left_metric]]
    right_sub = right_df[[group_key, right_time_col, right_metric]]

    aligned = pd.merge_asof(
        left_sub,
        right_sub,
        left_on=left_time_col,
        right_on=right_time_col,
        by=group_key,
        direction="nearest",
        suffixes=("_left", "_right"),
    )

    # Preserve grouping columns
    group_cols = ["age_group", "gender", "ethnicity", "smoker"]
    cols_to_keep = [group_key, left_time_col, left_metric, right_metric]

    for col in group_cols:
        if col in left_df.columns:
            aligned[col] = left_df[col]
        elif col in right_df.columns:
            aligned[col] = right_df[col]

        if col in aligned.columns:
            cols_to_keep.append(col)

    aligned = aligned[cols_to_keep]
    return aligned


# ============================================================
# MERGE PLANNER (Phase‑5 ready)
# ============================================================

print(">>> USING NEW BUILD_MERGE_PLAN")

def build_merge_plan(mentioned_columns, file_dfs):
    """
    Build a safe merge plan:
    - Identify which file owns each mentioned column
    - Detect cross‑file filtering (FILTER‑THEN‑PLOT)
    - Detect dual‑axis cross‑file time-series (Phase‑5)
    - Choose primary file deterministically when simple merge is safe
    """

    # 1. Build column → file ownership map
    column_owner = {}
    for file_name, df in file_dfs.items():
        if file_name.startswith("_"):
            continue
        for col in df.columns:
            column_owner.setdefault(col, set()).add(file_name)

    intent = file_dfs.get("_intent", {}) or {}
    intent_filters = file_dfs.get("_intent_filters", [])

    # 2. Detect FILTER‑THEN‑PLOT
    filter_files = set()
    metric_files = set()

    for f in intent_filters:
        col = f["column"]
        if col in column_owner:
            filter_files.update(column_owner[col])

    for col in mentioned_columns:
        if col in column_owner:
            metric_files.update(column_owner[col])

    if filter_files and metric_files and filter_files != metric_files:
        return {
            "mode": "filter_then_plot",
            "filter_file": list(filter_files)[0],
            "metric_file": list(metric_files)[0],
            "filters": intent_filters,
        }

    # 3. Detect DUAL‑AXIS
    y_left = intent.get("y_axis_left")
    y_right = intent.get("y_axis_right")

    if y_left and y_right:
        left_metric = y_left[0] if isinstance(y_left, list) else y_left
        right_metric = y_right[0] if isinstance(y_right, list) else y_right

        left_files = column_owner.get(left_metric, set())
        right_files = column_owner.get(right_metric, set())

        left_file = list(left_files)[0]
        right_file = list(right_files)[0]

        if left_file != right_file:
            left_df = file_dfs[left_file]
            right_df = file_dfs[right_file]

            def pick_time_col(df):
                if "date" in df.columns:
                    return "date"
                if "day" in df.columns:
                    return "day"
                raise ValueError("No temporal column found")

            return {
                "mode": "dual_axis_align",
                "left_file": left_file,
                "right_file": right_file,
                "left_metric": left_metric,
                "right_metric": right_metric,
                "left_time_col": pick_time_col(left_df),
                "right_time_col": pick_time_col(right_df),
                "group_key": "patient_id",
                "filters": intent_filters,
            }

    # 4. Determine primary file
    file_hits = {file: 0 for file in file_dfs if not file.startswith("_")}

    for col in mentioned_columns:
        for file, df in file_dfs.items():
            if file.startswith("_"):
                continue
            if col in df.columns:
                file_hits[file] += 1

    primary_file = None
    for file, hits in file_hits.items():
        if hits == len(mentioned_columns):
            primary_file = file
            break

    if primary_file is None:
        first_col = mentioned_columns[0]
        primary_file = list(column_owner[first_col])[0]

    # 5. Determine joins
    joins = []
    primary_cols = set(file_dfs[primary_file].columns)

    for col in mentioned_columns:
        owners = column_owner.get(col, set())
        for file in owners:
            if file != primary_file and col not in primary_cols:
                joins.append({"file": file, "on": "patient_id"})

    # Deduplicate joins
    unique_joins = []
    seen = set()
    for j in joins:
        if j["file"] not in seen:
            unique_joins.append(j)
            seen.add(j["file"])

    return {
        "mode": "merge",
        "primary": primary_file,
        "joins": unique_joins,
        "filters": intent_filters,
    }


# ============================================================
# EXECUTE MERGE PLAN
# ============================================================

def merge_files(merge_plan, file_dfs):
    mode = merge_plan.get("mode", "merge")

    # ---------------------------------------------------------
    # FILTER‑THEN‑PLOT
    # ---------------------------------------------------------
    if mode == "filter_then_plot":
        filter_file = merge_plan["filter_file"]
        metric_file = merge_plan["metric_file"]
        filters = merge_plan.get("filters", [])

        df_filter = file_dfs[filter_file].copy()

        # Normalize smoker
        if "smoker" in df_filter.columns:
            df_filter["smoker"] = df_filter["smoker"].astype(str).str.lower().map({
                "true": True,
                "false": False
            })

        for f in filters:
            col, op, val = f["column"], f["operator"], f["value"]
            df_filter = df_filter.query(f"{col} {op} @val")

        allowed_ids = set(df_filter["patient_id"].unique())

        df_metric = file_dfs[metric_file].copy()

        if "smoker" in df_metric.columns:
            df_metric["smoker"] = df_metric["smoker"].astype(str).str.lower().map({
                "true": True,
                "false": False
            })

        return df_metric[df_metric["patient_id"].isin(allowed_ids)]

    # ---------------------------------------------------------
    # DUAL‑AXIS ALIGN
    # ---------------------------------------------------------
    if mode == "dual_axis_align":
        left_file = merge_plan["left_file"]
        right_file = merge_plan["right_file"]
        left_metric = merge_plan["left_metric"]
        right_metric = merge_plan["right_metric"]
        left_time_col = merge_plan["left_time_col"]
        right_time_col = merge_plan["right_time_col"]
        group_key = merge_plan["group_key"]
        filters = merge_plan.get("filters", [])

        left_df = file_dfs[left_file].copy()
        right_df = file_dfs[right_file].copy()

        for df_side in (left_df, right_df):
            if "smoker" in df_side.columns:
                df_side["smoker"] = df_side["smoker"].astype(str).str.lower().map({
                    "true": True,
                    "false": False
                })

        for f in filters:
            col, op, val = f["column"], f["operator"], f["value"]
            if col in left_df.columns:
                left_df = left_df.query(f"{col} {op} @val")
            if col in right_df.columns:
                right_df = right_df.query(f"{col} {op} @val")

        return align_dual_axis_timeseries(
            left_df,
            right_df,
            left_time_col,
            right_time_col,
            group_key,
            left_metric,
            right_metric,
        )

    # ---------------------------------------------------------
    # NORMAL MERGE
    # ---------------------------------------------------------
    primary = merge_plan["primary"]
    df = file_dfs[primary].copy()

    # Normalize smoker
    if "smoker" in df.columns:
        df["smoker"] = df["smoker"].astype(str).str.lower().map({
            "true": True,
            "false": False
        })

    for join in merge_plan.get("joins", []):
        right_file = join["file"]
        df = pd.merge(df, file_dfs[right_file], on=join["on"], how="inner")

    # Apply filters
    for f in merge_plan.get("filters", []):
        col, op, val = f["column"], f["operator"], f["value"]
        if op == "==":
            df = df[df[col] == val]
        elif op == "!=":
            df = df[df[col] != val]
        elif op == ">":
            df = df[df[col] > val]
        elif op == "<":
            df = df[df[col] < val]
        elif op == ">=":
            df = df[df[col] >= val]
        elif op == "<=":
            df = df[df[col] <= val]

    return df