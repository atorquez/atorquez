import altair as alt
alt.themes.enable('none')
import streamlit as st
import pandas as pd

from engine.nl_parser import parse_natural_language
from engine.merger import build_merge_plan, merge_files
from engine.intent_to_spec import intent_to_spec
from engine.renderer import render_chart
from engine.load_test_data import load_synthetic_medical_data

CSS_VERSION = "v2025_02_05_05"   # increment this anytime you change CSS

st.markdown(f"<!-- cache-bust: {CSS_VERSION} -->")
st.markdown(f"**Civio Build: {CSS_VERSION}**")

st.markdown(
    f"""
    <style id="{CSS_VERSION}">

    /* -------------------------------------------------- */
    /* GLOBAL BACKGROUND                                  */
    /* -------------------------------------------------- */
    .stApp {{
        background-color: #d5dbe1; /* Civio soft steel gray */
    }}

    /* -------------------------------------------------- */
    /* INPUT LABELS                                       */
    /* -------------------------------------------------- */
    label[data-testid="stWidgetLabel"] {{
        font-size: 20px !important;
        font-weight: 600 !important;
        color: #1a1a1a !important;
    }}

    /* -------------------------------------------------- */
    /* TEXT INPUT BOX                                     */
    /* -------------------------------------------------- */
    .stTextInput input {{
        font-size: 20px !important;
        padding: 10px !important;
    }}

    /* -------------------------------------------------- */
    /* EXAMPLE QUERIES                                    */
    /* -------------------------------------------------- */
    .example-queries {{
        font-size: 18px !important;
        line-height: 1.5 !important;
        color: #2b2b2b !important;
        margin-bottom: 12px !important;
    }}

    /* -------------------------------------------------- */
    /* CHART DESCRIPTION                                  */
    /* -------------------------------------------------- */
    .chart-description-title {{
        font-size: 22px !important;
        font-weight: 700 !important;
        margin-top: 20px !important;
        margin-bottom: 6px !important;
        color: #1a1a1a !important;
    }}

    .chart-description-text {{
        font-size: 18px !important;
        line-height: 1.5 !important;
        color: #2b2b2b !important;
    }}

    /* -------------------------------------------------- */
    /* FORCE BOLD TEXT FOR st.dataframe()                 */
    /* -------------------------------------------------- */

    /* Body cells */
    div[data-testid="stDataFrame"] div[data-testid="cell"] span span {{
        font-size: 18px !important;
        font-weight: 900 !important;
    }}

    /* Header cells */
    div[data-testid="stDataFrame"] div[data-testid="column"] span span {{
        font-size: 18px !important;
        font-weight: 900 !important;
    }}

    /* -------------------------------------------------- */
    /* WIDEN FILE UPLOADER                                */
    /* -------------------------------------------------- */

    /* Increase height of file uploader drop zone */
    div[data-testid="stFileUploader"] section {
        padding: 40px !important;        /* was 20px — doubling height */
        min-height: 180px !important;    /* enforce a taller drop zone */
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
    }

    div[data-testid="stFileUploader"] section > div {
        font-size: 18px !important;
    }

    </style>
    """,
    unsafe_allow_html=True
)

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
# Aggregated table computation (patched to preserve demographics)
# ---------------------------------------------------------
def compute_table(intent, merged_df: pd.DataFrame, available_columns):
    stats = intent.get("statistics", {})
    aggs = stats.get("aggregation", [])
    metrics = intent.get("y_axis", [])
    x = intent.get("x_axis")

    # Columns we always want to preserve (demographics + smoker)
    preserve_cols = ["gender", "age_group", "ethnicity", "smoker"]

    # No statistics → return raw merged table (already contains all columns)
    if not aggs or not metrics:
        return merged_df.copy()

    # ---------------------------------------------------------
    # GROUPED CASE (nominal x-axis)
    # ---------------------------------------------------------
    if x in merged_df.columns and available_columns.get(x) == "nominal":
        groups = merged_df.groupby(x)
        rows = []

        for group_value, group_df in groups:
            row = {x: group_value}

            # Compute aggregated metrics
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

            # Preserve demographic columns (take first value in group)
            for col in preserve_cols:
                if col in group_df.columns:
                    row[col] = group_df[col].iloc[0]

            rows.append(row)

        table_df = pd.DataFrame(rows)

        # If single row + line intent, flip to bar
        if len(table_df) == 1 and intent["chart_type"] == "line":
            intent["chart_type"] = "bar"

        return table_df

    # ---------------------------------------------------------
    # UNGROUPED CASE
    # ---------------------------------------------------------
    values = {}

    # Compute aggregated metrics
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

    # Preserve demographic columns (take first row)
    for col in preserve_cols:
        if col in merged_df.columns:
            values[col] = merged_df[col].iloc[0]

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


    # 🔍 Debug prints BEFORE rendering
    print(">>> SPEC:", spec)
    print(">>> DF COLUMNS BEFORE RENDER:", table_df.columns.tolist())

    
    # Render chart using the same table_df
    chart = render_chart(spec, table_df)

    # ---------------------------------------------------------
    # Chart Description (simple auto-summary)
    # ---------------------------------------------------------
    with st.expander("Chart Description"):
        st.markdown(
            f"""
            This chart shows <strong>{spec['chart'].get('title', 'clinical data')}</strong> based on your query. 
            It visualizes <strong>{', '.join(intent.get('y_axis', []))}</strong> across 
            <strong>{intent.get('x_axis', 'time')}</strong>, using a <strong>{intent.get('chart_type', 'chart')}</strong> format.
         """,
        unsafe_allow_html=True
        )

    # ---------------------------------------------------------
    # Polished chart title + subtitle
    # ---------------------------------------------------------
    pretty_title = spec["chart"].get("title", "Chart")
    subtitle = f"Query: {query}"
    st.markdown(f"### {pretty_title}")
    st.markdown(
        f"<span style='color: gray; font-size: 14px;'>{subtitle}</span>",
        unsafe_allow_html=True
    )
    # ---------------------------------------------------------
    # Render chart
    # ---------------------------------------------------------
    # ---------------------------------------------------------
    # Configure chart FIRST
    # ---------------------------------------------------------
    chart = chart.configure_axis(
        labelFontSize=18,
        labelFontWeight="bold",
        titleFontSize=20,
        titleFontWeight="bold"
    ).configure_legend(
        labelFontSize=16,
        titleFontSize=18
    ).configure_title(
        fontSize=24,
        fontWeight="bold"
    )
    # ---------------------------------------------------------
    # Render chart AFTER configuration
    # ---------------------------------------------------------
    st.altair_chart(chart, use_container_width=True, theme=None)

# ---------------------------------------------------------
# Streamlit UI
# ---------------------------------------------------------
def main():
    # ---------------------------------------------------------
    # Page config + chrome cleanup
    # ---------------------------------------------------------
    st.set_page_config(
        page_title="Chartix",
        layout="wide",
        initial_sidebar_state="collapsed"
    )

    st.markdown("""
        <style>
            #MainMenu {visibility: hidden;}
            header {visibility: hidden;}
            footer {visibility: hidden;}
        </style>
    """, unsafe_allow_html=True)

   # ---------------------------------------------------------
    # Header
    # ---------------------------------------------------------
    st.title("Civio")

    st.markdown(
        """
        <div style='
            font-size:20px;
            font-weight:600;
            padding:12px 14px;
            background-color:#eef6ff;
            border-left:4px solid #1f77b4;
            border-radius:4px;
            margin-bottom:10px;
        '>
            Upload your labs and vitals files or use synthetic demo data.<br>
            Then describe the chart you want in natural language.
        </div>
        """,
        unsafe_allow_html=True
    )

    st.markdown("---")

    # ---------------------------------------------------------
    # Data Source Section
    # ---------------------------------------------------------
    st.markdown(
        """
        <h3 style='margin-bottom:4px;'>1. Data Source</h3>
        <div style='
            font-size:18px;
            font-weight:600;
            padding:8px 10px;
            background-color:#eef6ff;
            border-left:4px solid #1f77b4;
            border-radius:4px;
            margin-bottom:10px;
        '>
            Upload your Labs and Vitals CSV files below
        </div>
        """,
        unsafe_allow_html=True
    )

    # use_demo = st.checkbox("Use synthetic demo data (ignore file uploads)")
    use_demo = False

    # show_debug = st.checkbox("Show debug info")
    show_debug = False

    # ---------------------------------------------------------
    # Debug Banner (hidden for end‑user test)
    # ---------------------------------------------------------
    # st.markdown(
    #     f"""
    #     <div style="
    #         padding: 10px;
    #         background-color: #eef6ff;
    #         border-left: 4px solid #1f77b4;
    #         margin-bottom: 20px;
    #         font-size: 14px;
    #     ">
    #         <strong>Debug Info</strong><br>
    #         Running file: <code>{__file__}</code><br>
    #         Demo mode: <strong>{'ON' if use_demo else 'OFF'}</strong><br>
    #         Port: <strong>8502</strong>
    #     </div>
    #     """,
    #     unsafe_allow_html=True
    # )
    # ---------------------------------------------------------
    # Reset App Button (optional to hide)
    # ---------------------------------------------------------
    # if st.button("🔄 Reset App"):
    #     st.session_state.clear()
    #     st.rerun()

    # ---------------------------------------------------------
    # File Upload or Demo Data
    # ---------------------------------------------------------
    labs_df = None
    vitals_df = None

    if not use_demo:

        # Styled instruction above the uploader
        st.markdown(
            """
            <div style='
                font-size:18px;
                font-weight:600;
                padding:8px 10px;
                background-color:#eef6ff;
                border-left:4px solid #1f77b4;
                border-radius:4px;
                margin-bottom:6px;
            '>
                Upload your Labs and Vitals CSV files below
            </div>
            """,
            unsafe_allow_html=True
        )

        # Minimal uploader label (keeps UI clean)
        uploaded_files = st.file_uploader(
            "Select CSV files",
            type=["csv"],
            accept_multiple_files=True
        )
        if uploaded_files:
            try:
                for file in uploaded_files:
                    df = pd.read_csv(file)
                    cols = set(df.columns)
                    # Detect labs file
                    if {"glucose_level", "cholesterol", "hba1c"}.issubset(cols):
                        labs_df = df

                    # Detect vitals file
                    elif {"blood_pressure", "heart_rate", "temperature"}.issubset(cols):
                        vitals_df = df
                if labs_df is not None and vitals_df is not None:
                    st.success("Files uploaded and detected successfully.")
                else:
                    st.warning("Please upload both labs and vitals CSV files.")

            except Exception as e:
                st.error(f"Error reading files: {e}")

        else:
            # Show instruction ONLY when no files uploaded
            st.markdown(
                """
                <div style='
                    font-size:18px;
                    font-weight:600;
                    padding:10px;
                    background-color:#eef6ff;
                    border-left:4px solid #1f77b4;
                    border-radius:4px;
                '>
                    Upload your labs and vitals files, or enable demo mode.
                </div>
                """,
                unsafe_allow_html=True
            )

    else:
        labs_df, vitals_df = load_synthetic_medical_data()
        st.success("Using synthetic demo data.")
    # ---------------------------------------------------------
    # Data Preview
    # ---------------------------------------------------------
    if labs_df is not None and vitals_df is not None:
        with st.expander("Preview Uploaded Data"):
            st.write("**Labs Preview**")
            st.dataframe(labs_df.head())

            st.write("**Vitals Preview**")
            st.dataframe(vitals_df.head())

        st.markdown("---")

        # ---------------------------------------------------------
        # Query Section
        # ---------------------------------------------------------
        st.subheader("2. Describe the Chart")

        query = st.text_input("What would you like to visualize?")

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

        # ---------------------------------------------------------
        # Generate Chart
        # ---------------------------------------------------------
        if st.button("Generate Chart"):
            if not query.strip():
                st.error("Please enter a question.")
            else:
                try:
                    run_engine(query, labs_df, vitals_df)
                except Exception as e:
                    st.error(f"Something went wrong while generating the chart: {e}")

if __name__ == "__main__":
    main()