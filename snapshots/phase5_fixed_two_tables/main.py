import pandas as pd
from load_test_data import load_synthetic_medical_data
from nl_parser import parse_natural_language
from merger import build_merge_plan, merge_files
from intent_to_spec import intent_to_spec
from renderer import render_chart, render_table


print(">>> USING main.py FROM:", __file__)

# ---------------------------------------------------------
# 1. Load synthetic datasets
# ---------------------------------------------------------
labs_df, vitals_df = load_synthetic_medical_data()

file_dfs = {
    "labs.csv": labs_df,
    "vitals.csv": vitals_df
}

# ---------------------------------------------------------
# 2. Detect schemas (quantitative vs nominal)
# ---------------------------------------------------------
def detect_schema(df):
    schema = {}
    for col in df.columns:
        if pd.api.types.is_numeric_dtype(df[col]):
            schema[col] = "quantitative"
        elif pd.api.types.is_datetime64_any_dtype(df[col]):
            schema[col] = "temporal"
        else:
            schema[col] = "nominal"
    return schema

schemas = {
    file: detect_schema(df)
    for file, df in file_dfs.items()
}

print("\nDetected schemas per file:")
for file, schema in schemas.items():
    print(f"\n{file}:")
    for col, typ in schema.items():
        print(f"  {col}: {typ}")

# ---------------------------------------------------------
# 2.5 Build file_schemas for parser (file → column → type)
# ---------------------------------------------------------
file_schemas = schemas

# ---------------------------------------------------------
# 3. Build unified available_columns dictionary
# ---------------------------------------------------------
available_columns = {}
for schema in schemas.values():
    for col, typ in schema.items():
        available_columns[col] = typ

print("\n>>> AVAILABLE COLUMNS:", list(available_columns.keys()))

# ---------------------------------------------------------
# 4. Ask user for natural language query
# ---------------------------------------------------------
user_text = input("\nDescribe the chart you want:\n> ")


# ---------------------------------------------------------
# 5. Parse natural language into intent
# ---------------------------------------------------------
intent = parse_natural_language(
    user_text, available_columns, file_schemas
)
mentioned_columns = intent["mentioned_columns"]

print("\nParsed intent:", intent)
print("Mentioned columns:", mentioned_columns)

# ---------------------------------------------------------
# 6. Pass intent + filters into file_dfs for merge planner
# ---------------------------------------------------------
file_dfs["_intent_filters"] = intent.get("filters", [])
file_dfs["_intent"] = intent

# ---------------------------------------------------------
# 7. Build merge plan
# ---------------------------------------------------------
merge_plan = build_merge_plan(intent["mentioned_columns"], file_dfs)
merge_plan["filters"] = intent.get("filters", [])

print("\nMerge plan:", merge_plan)

# ---------------------------------------------------------
# 8. Execute merge (or filter-then-plot / dual-axis-align)
# ---------------------------------------------------------
merged_df = merge_files(merge_plan, file_dfs)

print("\nMerged dataframe preview:")
print(merged_df.head())

# ---------------------------------------------------------
# 8.5 Render HTML table (extended statistics engine)
# ---------------------------------------------------------
stats = intent.get("statistics", {})
aggs = stats.get("aggregation", [])
metrics = intent.get("y_axis", [])
x = intent.get("x_axis")

# If no statistics requested → show raw table
if not aggs or not metrics:
    table_df = merged_df.copy()
    render_table(table_df)
else:
    # GROUPED CASE (multi‑metric + multi‑stat)
    if x in merged_df.columns and available_columns.get(x) == "nominal":
        groups = merged_df.groupby(x)
        rows = []

        for group_value, group_df in groups:
            row = {x: group_value}

            for metric in metrics:
                if metric in group_df.columns:
                    for agg in aggs:
                        col_name = f"{agg}_{metric}"
                        try:
                            row[col_name] = getattr(group_df[metric], agg)()
                        except AttributeError:
                            if agg == "var":
                                row[col_name] = group_df[metric].var()
                            elif agg == "std":
                                row[col_name] = group_df[metric].std()
                            else:
                                row[col_name] = None

            rows.append(row)

        table_df = pd.DataFrame(rows)

        if len(table_df) == 1 and intent["chart_type"] == "line":
            intent["chart_type"] = "bar"
    
    else:
        # UNGROUPED CASE: compute each metric/stat explicitly into a flat dict
        values = {}

        for metric in metrics:
            if metric in merged_df.columns:
                for agg in aggs:
                    col_name = f"{agg}_{metric}"
                    try:
                        values[col_name] = getattr(merged_df[metric], agg)()
                    except AttributeError:
                        # fallback for 'var' vs 'variance' naming, etc.
                        if agg == "var":
                            values[col_name] = merged_df[metric].var()
                        elif agg == "std":
                            values[col_name] = merged_df[metric].std()
                        else:
                            values[col_name] = None

        table_df = pd.DataFrame([values])

    print("\nAggregated table preview:")
    print(table_df.head())
    render_table(table_df)

# ---------------------------------------------------------
# 9. Convert intent → chart spec
# ---------------------------------------------------------
spec = intent_to_spec(intent, merged_df.columns)
if intent.get("statistics"):
    spec["chart"]["statistics"] = intent["statistics"]
# ---------------------------------------------------------
# 10. Render chart
# ---------------------------------------------------------
render_chart(spec, table_df)

