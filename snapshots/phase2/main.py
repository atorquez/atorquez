print(">>> USING main.py FROM:", __file__)

import os
import json
import webbrowser
import pandas as pd

from nl_parser import parse_natural_language, match_column
from intent_to_spec import intent_to_spec
from validator import validate_chart_spec
from renderer import render_chart
from load_test_data import load_synthetic_medical_data
from file_router import build_schemas_for_files, pick_file_for_columns

# ---------------------------------------------------
# 1. Load synthetic dataset (for reference/debug)
# ---------------------------------------------------
df_demo = load_synthetic_medical_data()
print(df_demo.dtypes)
print(">>> REAL DF COLUMNS:", list(df_demo.columns))

# ---------------------------------------------------
# 2. Load all user data files (multi-file environment)
# ---------------------------------------------------
DATA_FOLDER = "data_files"

files = {}
for fname in os.listdir(DATA_FOLDER):
    path = os.path.join(DATA_FOLDER, fname)
    if fname.lower().endswith(".csv"):
        files[fname] = pd.read_csv(path)
    elif fname.lower().endswith((".xlsx", ".xls")):
        files[fname] = pd.read_excel(path)

if not files:
    print("No data files found in the data_files folder.")
    exit()

# ---------------------------------------------------
# 3. Detect schemas for ALL files
# ---------------------------------------------------
def detect_column_types(df: pd.DataFrame) -> dict:
    column_types = {}
    for col in df.columns:
        dtype = df[col].dtype

        if "datetime" in str(dtype).lower():
            column_types[col] = "temporal"
        elif "float" in str(dtype).lower() or "int" in str(dtype).lower():
            column_types[col] = "quantitative"
        else:
            column_types[col] = "nominal"

    return column_types

schemas = build_schemas_for_files(files, detect_column_types)

print("\nDetected schemas per file:")
for fname, schema in schemas.items():
    print(f"\n{fname}:")
    for col, ctype in schema.items():
        print(f"  {col}: {ctype}")

# ---------------------------------------------------
# 4. Merge all columns across all files for the parser
# ---------------------------------------------------
all_columns = {}
for schema in schemas.values():
    all_columns.update(schema)

# ---------------------------------------------------
# 5. Ask user for chart description
# ---------------------------------------------------
user_text = input("\nDescribe the chart you want:\n> ")

# ---------------------------------------------------
# 6. Parse user input (Phase 2 parser)
# ---------------------------------------------------
intent, mentioned_columns = parse_natural_language(user_text, all_columns)

print("\nParsed intent:", intent)
print("Mentioned columns:", mentioned_columns)

# ---------------------------------------------------
# 7. Route to the correct file based on mentioned columns
# ---------------------------------------------------
selected_file, candidates = pick_file_for_columns(mentioned_columns, schemas)

if selected_file is None:
    print("\nCould not uniquely determine a file for this request.")
    if not candidates:
        print("No file contains all of the mentioned columns.")
    else:
        print("Multiple files could satisfy this request:")
        for i, fname in enumerate(candidates, start=1):
            print(f"{i}. {fname}")

    print("\nAvailable files:")
    for i, name in enumerate(files.keys(), start=1):
        print(f"{i}. {name}")
    choice = int(input("\nSelect a file to analyze: "))
    selected_file = list(files.keys())[choice - 1]

print(f"\n>>> USING FILE: {selected_file}")
df = files[selected_file]
available_columns = schemas[selected_file]

# ---------------------------------------------------
# 8. Convert intent → chart spec
# ---------------------------------------------------
spec = intent_to_spec(intent, available_columns)
print("\nGenerated spec:", json.dumps(spec, indent=2))

# If chart type is still None, ask user
if spec["chart"]["type"] is None:
    print("I can create this chart, but I need to know the chart type.")
    print("Options: line, bar, pie, boxplot, violin")
    chart_type = input("Which chart type would you like? > ").strip().lower()
    spec["chart"]["type"] = chart_type

# ---------------------------------------------------
# 9. If encoding is empty (ambiguous), ask user for axes
# ---------------------------------------------------
if spec["encoding"] == {}:
    print("\nI need to know which variable should be on the x-axis.")
    x_raw = input("Choose x-axis column: ").strip().lower()

    print("And which variable should be on the y-axis.")
    y_raw = input("Choose y-axis column: ").strip().lower()

    x_axis = match_column(x_raw, available_columns)
    y_axis = match_column(y_raw, available_columns)

    if x_axis is None or y_axis is None:
        raise ValueError("Could not match your axis selections to dataset columns.")

    spec["encoding"] = {
        "x": {"column": x_axis, "type": available_columns[x_axis]},
        "y": {"column": y_axis, "type": available_columns[y_axis]},
        "tooltip": [x_axis, y_axis],
    }

# ---------------------------------------------------
# 10. Validate the chart specification
# ---------------------------------------------------
validate_chart_spec(spec, available_columns)
print("\nValidator passed!")

# ---------------------------------------------------
# 11. Render the chart
# ---------------------------------------------------
chart = render_chart(spec, df)
chart.save("output_chart.html")

print("\nChart rendered successfully!")

# ---------------------------------------------------
# 12. Open automatically in browser
# ---------------------------------------------------
webbrowser.open("output_chart.html")

