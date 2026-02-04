import pandas as pd
from load_test_data import load_synthetic_medical_data
from nl_parser import parse_natural_language
from router import build_merge_plan
from merger import merge_files
from intent_to_spec import intent_to_spec
from renderer import render_chart

print(">>> USING main.py FROM:", __file__)

# ---------------------------------------------------------
# 1. Load synthetic Phase‑3 datasets
# ---------------------------------------------------------
demographics_df, labs_df, vitals_df = load_synthetic_medical_data()

file_dfs = {
    "demographics.csv": demographics_df,
    "labs_february.csv": labs_df,
    "vitals_january.csv": vitals_df
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

print("\nDetected schemas per file:\n")
for file, schema in schemas.items():
    print(f"{file}:")
    for col, typ in schema.items():
        print(f"  {col}: {typ}")
    print()

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

print(">>> REAL DF COLUMNS:", list(available_columns.keys()))

# ---------------------------------------------------------
# 4. Ask user for natural language query
# ---------------------------------------------------------
user_text = input("Describe the chart you want:\n> ")

# ---------------------------------------------------------
# 5. Parse natural language into intent
# ---------------------------------------------------------
intent, mentioned_columns = parse_natural_language(
    user_text,
    available_columns,
    file_schemas
)

print("\nParsed intent:", intent)
print("Mentioned columns:", mentioned_columns)

# ---------------------------------------------------------
# 6. Build merge plan
# ---------------------------------------------------------
merge_plan = build_merge_plan(intent, schemas, mentioned_columns)
print("\nMerge plan:", merge_plan)

# ---------------------------------------------------------
# 7. Merge files safely
# ---------------------------------------------------------
merged_df = merge_files(merge_plan, file_dfs)

print("\nMerged dataframe preview:")
print(merged_df.head())

# ---------------------------------------------------------
# 8. Convert intent → chart spec
# ---------------------------------------------------------
spec = intent_to_spec(intent, merged_df)

# ---------------------------------------------------------
# 9. Render chart
# ---------------------------------------------------------
render_chart(spec, merged_df)

