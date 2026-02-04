# merger.py — Phase‑3 Safe Clinical Merging

import pandas as pd

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

    # Perform join
    merged = pd.merge(left_df, right_df, on=on, how="inner")

    # Ensure no row explosion beyond left_df
    if len(merged) > len(left_df):
        raise ValueError(
            f"Join caused row explosion: {len(merged)} rows vs {len(left_df)} in primary"
        )

    return merged


def merge_files(merge_plan, file_dfs):
    """
    Execute a Phase‑3 merge plan:
    - Primary file defines the grain
    - All other files join onto it using safe_inner_join
    """

    primary_file = merge_plan["primary"]
    joins = merge_plan["joins"]

    if primary_file not in file_dfs:
        raise ValueError(f"Primary file '{primary_file}' not found in loaded data")

    # Start with primary dataframe
    df = file_dfs[primary_file].copy()

    # Apply joins in order
    for join in joins:
        file = join["file"]
        on = join.get("on", "patient_id")

        if file not in file_dfs:
            raise ValueError(f"Join file '{file}' not found in loaded data")

        right_df = file_dfs[file]

        df = safe_inner_join(df, right_df, on=on)

    return df