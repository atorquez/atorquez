import pandas as pd
import numpy as np

def normalize_categorical_fields(df):
    df["gender"] = (
        df["gender"].str.lower().map({
            "male": "male", "m": "male",
            "female": "female", "f": "female"
        }).fillna("unknown")
    )

    df["age_group"] = (
        df["age_group"].str.lower().map({
            "child": "child", "children": "child",
            "adult": "adult",
            "senior": "senior", "elderly": "senior"
        }).fillna("unknown")
    )

    df["ethnicity"] = (
        df["ethnicity"].str.lower().map({
            "white": "white", "caucasian": "white",
            "black": "black", "african american": "black",
            "asian": "asian",
            "hispanic": "hispanic", "latino": "hispanic"
        }).fillna("other")
    )

    df["smoker"] = (
        df["smoker"].str.lower().map({
            "yes": "true", "y": "true", "true": "true",
            "no": "false", "n": "false", "false": "false"
        }).fillna("false")
    )

    return df


def load_synthetic_medical_data(num_patients=50, hours=48):
    np.random.seed(42)

    # ---------------------------
    # 1. Patient IDs
    # ---------------------------
    patient_ids = np.arange(1, num_patients + 1)

    # ---------------------------
    # 2. Demographics (unique grain)
    # ---------------------------
    demographics = pd.DataFrame({
        "patient_id": patient_ids,
        "gender": np.random.choice(["male", "female"], size=num_patients),
        "age_group": np.random.choice(["child", "adult", "senior"], size=num_patients),
        "ethnicity": np.random.choice(["white", "black", "asian", "hispanic"], size=num_patients),
        "smoker": np.random.choice(["true", "false"], size=num_patients)
    })

    demographics = normalize_categorical_fields(demographics)

    # ---------------------------
    # 3. Labs (unique grain)
    # ---------------------------
    labs = pd.DataFrame({
        "patient_id": patient_ids,
        "date": pd.Timestamp("2024-02-15"),
        "glucose_level": np.random.normal(110, 15, size=num_patients).round(1),
        "cholesterol": np.random.normal(180, 25, size=num_patients).round(1),
        "hba1c": np.random.normal(5.5, 0.6, size=num_patients).round(2)
    })

    # Merge demographics → labs
    labs = labs.merge(demographics, on="patient_id", how="left")

    # ---------------------------
    # 4. Vitals (time-series grain)
    # ---------------------------
    base_time = pd.date_range(start="2024-01-01", periods=hours, freq="h")

    vitals_list = []
    for pid in patient_ids:
        df = pd.DataFrame({
            "patient_id": pid,
            "day": base_time,
            "blood_pressure": np.random.normal(120, 10, size=hours).round(1),
            "heart_rate": np.random.normal(75, 8, size=hours).round(1),
            "temperature": np.random.normal(98.6, 0.7, size=hours).round(1),
            "oxygen_saturation": np.random.normal(97, 1.5, size=hours).round(1)
        })
        vitals_list.append(df)

    vitals = pd.concat(vitals_list, ignore_index=True)

    # Merge demographics → vitals
    vitals = vitals.merge(demographics, on="patient_id", how="left")

    # Return only two files
    return labs, vitals

labs, vitals = load_synthetic_medical_data()
print("=== LABS ===")
print(labs)
print("\n=== VITALS ===")
print(vitals)

