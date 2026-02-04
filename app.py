import streamlit as st
import pandas as pd

# -----------------------------
# File upload with persistence
# -----------------------------
uploaded_labs = st.file_uploader("Upload Labs File", type=["csv", "xlsx"])
uploaded_vitals = st.file_uploader("Upload Vitals File", type=["csv", "xlsx"])

# Save files to session_state so they persist across reruns
if uploaded_labs is not None:
    st.session_state["labs_file"] = uploaded_labs

if uploaded_vitals is not None:
    st.session_state["vitals_file"] = uploaded_vitals

# Retrieve persisted files
labs_file = st.session_state.get("labs_file", None)
vitals_file = st.session_state.get("vitals_file", None)


from engine.nl_parser import parse_natural_language
from engine.merger import build_merge_plan, merge_files
from engine.intent_to_spec import intent_to_spec
from engine.renderer import render_chart
from engine.load_test_data import load_synthetic_medical_data





# ---------------------------------------------------------
# Schema detection helper
# ---------------------------------------------------------
def detect_schema(df: pd.DataFrame):
    schema = {}
    for col in df.columns:
        if pd.api.types.is_numeric_dtype(df[col]):
            schema[col] = "quantitative"
        elif pd.api.types.is_datetime64_any_dtype(df[col]):
            schema[col] = "temporal"
        else:
            schema[col] = "nominal"
    return schema


# ---------------------------------------------------------
# Aggregated table computation (extracted from main.py)
# ---------------------------------------------------------
def compute_table(intent, merged_df: pd.DataFrame, available_columns):
    stats = intent.get("statistics", {})
    aggs = stats.get("aggregation", [])
    metrics = intent.get("y_axis", [])
    x = intent.get("x_axis")

    # No statistics → return raw merged table
    if not aggs or not metrics:
        return merged_df.copy()

    # GROUPED CASE (nominal x-axis)
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

        # Optional: if single row + line intent, you could flip to bar here
        if len(table_df) == 1 and intent["chart_type"] == "line":
            intent["chart_type"] = "bar"

        return table_df

    # UNGROUPED CASE
    values = {}

    for metric in metrics:
        if metric in merged_df.columns:
            for agg in aggs:
                col_name = f"{agg}_{metric}"
                try:
                    values[col_name] = getattr(merged_df[metric], agg)()
                except AttributeError:
                    if agg == "var":
                        values[col_name] = merged_df[metric].var()
                    elif agg == "std":
                        values[col_name] = merged_df[metric].std()
                    else:
                        values[col_name] = None

    return pd.DataFrame([values])


# ---------------------------------------------------------
# Engine wrapper
# ---------------------------------------------------------
def run_engine(query: str, labs_df: pd.DataFrame, vitals_df: pd.DataFrame):
    # 1. Build file dictionary
    file_dfs = {
        "labs.csv": labs_df,
        "vitals.csv": vitals_df,
    }

    # 2. Detect schemas
    schemas = {file: detect_schema(df) for file, df in file_dfs.items()}
    available_columns = {
        col: typ
        for schema in schemas.values()
        for col, typ in schema.items()
    }

    # 3. Parse NL query
    intent = parse_natural_language(query, available_columns, schemas)

    # 4. Build merge plan
    file_dfs["_intent_filters"] = intent.get("filters", [])
    file_dfs["_intent"] = intent

    merge_plan = build_merge_plan(intent["mentioned_columns"], file_dfs)
    merge_plan["filters"] = intent.get("filters", [])

    # 5. Merge files
    merged_df = merge_files(merge_plan, file_dfs)

    # 6. Compute aggregated table
    table_df = compute_table(intent, merged_df, available_columns)

    # 7. Convert intent → spec
    spec = intent_to_spec(intent, merged_df.columns)
    if intent.get("statistics"):
        spec["chart"]["statistics"] = intent["statistics"]

    # 8. Render results in Streamlit
    st.subheader("Aggregated / Result Table")
    st.dataframe(table_df)

    st.subheader("Chart")
    chart = render_chart(spec, table_df)
    st.altair_chart(chart, use_container_width=True)


# ---------------------------------------------------------
# Streamlit UI
# ---------------------------------------------------------
def main():
    st.set_page_config(page_title="Clinical Chart Explorer — Phase I", layout="wide")

    st.title("Clinical Chart Explorer — Phase I")
    st.write(
        "Upload your labs and vitals files, or use demo data, then ask a question in natural language."
    )

    # Demo toggle
    use_demo = st.checkbox("Use synthetic demo data (ignore file uploads)")

    labs_df = None
    vitals_df = None

    col1, col2 = st.columns(2)

    with col1:
        labs_file = st.file_uploader("Upload Labs File (labs.csv)", type=["csv"])
    with col2:
        vitals_file = st.file_uploader("Upload Vitals File (vitals.csv)", type=["csv"])

    if use_demo:
        labs_df, vitals_df = load_synthetic_medical_data()
        st.success("Using synthetic demo data.")
    else:
        if labs_file is not None and vitals_file is not None:
            try:
                labs_df = pd.read_csv(labs_file)
                vitals_df = pd.read_csv(vitals_file)
                st.success("Files uploaded successfully.")
            except Exception as e:
                st.error(f"Error reading files: {e}")

    if labs_df is not None and vitals_df is not None:
        with st.expander("Preview data"):
            st.write("**Labs preview:**")
            st.dataframe(labs_df.head())
            st.write("**Vitals preview:**")
            st.dataframe(vitals_df.head())

        st.markdown("---")

        query = st.text_input("Describe the chart you want:")

        with st.expander("Example queries"):
            st.write(
                """
- mean glucose by age group  
- glucose over time  
- average sugar for kids  
- mean cholesterol and glucose  
- mean and std glucose  
- mean glucose and cholesterol for adults  
"""
            )

        if st.button("Generate Chart"):
            if not query.strip():
                st.error("Please enter a question.")
            else:
                try:
                    run_engine(query, labs_df, vitals_df)
                except Exception as e:
                    st.error(f"Something went wrong while generating the chart: {e}")
    else:
        st.info("Upload both labs and vitals files, or enable demo mode to continue.")


if __name__ == "__main__":
    main()