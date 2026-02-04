# file_router.py

def build_schemas_for_files(files, detect_column_types_fn):
    """
    files: dict[str, DataFrame]
    detect_column_types_fn: function(df) -> dict[column -> type]
    """
    schemas = {}
    for name, df in files.items():
        schemas[name] = detect_column_types_fn(df)
    return schemas


def pick_file_for_columns(mentioned_columns, schemas):
    """
    mentioned_columns: list[str]
    schemas: dict[file_name -> {column: type}]
    Returns: (selected_file_name or None, candidate_files)
    """
    if not mentioned_columns:
        return None, []

    candidate_files = []

    for fname, schema in schemas.items():
        cols = set(schema.keys())
        if all(col in cols for col in mentioned_columns):
            candidate_files.append(fname)

    if len(candidate_files) == 1:
        return candidate_files[0], candidate_files

    # None if zero or multiple matches → caller decides what to do
    return None, candidate_files