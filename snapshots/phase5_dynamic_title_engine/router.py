# router.py (Phase‑3 merge planner)

def build_merge_plan(intent, file_schemas, mentioned_columns):
    """
    Phase‑3 merge planner:
    - Primary file = file containing the X‑axis column
    - Join all other files that contain any mentioned columns
    - Always join on patient_id
    """

    x_axis = intent.get("x_axis")
    if not x_axis:
        raise ValueError("Cannot build merge plan without an x-axis")

    # ---------------------------
    # 1. Select primary file
    # ---------------------------
    primary = None
    for file, schema in file_schemas.items():
        if x_axis in schema:
            primary = file
            break

    if primary is None:
        raise ValueError(f"No file contains the x-axis column '{x_axis}'")

    # ---------------------------
    # 2. Build join list
    # ---------------------------
    joins = []

    for file, schema in file_schemas.items():
        if file == primary:
            continue

        # Join if file contains ANY mentioned column
        if any(col in schema for col in mentioned_columns):
            joins.append({
                "file": file,
                "on": "patient_id",
                "type": "inner"
            })

    # ---------------------------
    # 3. Return merge plan
    # ---------------------------
    return {
        "primary": primary,
        "joins": joins
    }