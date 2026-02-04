import pandas as pd
import numpy as np

def load_synthetic_medical_data():
    # -----------------------------------------
    # 1. Fixed patient list
    # -----------------------------------------
    patient_ids = [1, 2, 3, 4, 5]

    # -----------------------------------------
    # 2. Fixed demographics (fully controlled)
    # -----------------------------------------
    demographics = pd.DataFrame({
        "patient_id": patient_ids,
        "gender": ["male", "female", "female", "male", "male"],
        "age_group": ["adult", "senior", "adult", "child", "adult"],
        "ethnicity": ["white", "black", "asian", "hispanic", "white"],
        "smoker": ["false", "true", "false", "false", "true"]
    })

    # -----------------------------------------
    # 3. LABS — 3 times in 2025, staggered by 1 hour per patient
    # -----------------------------------------
    lab_dates = [
        "2025-03-13",
        "2025-06-12",
        "2025-09-15"
    ]

    labs_list = []

    for d in lab_dates:
        base_time = pd.Timestamp(f"{d} 15:00:00")  # starting time for first patient

        for i, pid in enumerate(patient_ids):
            timestamp = base_time + pd.Timedelta(hours=i)  # 1-hour stagger

            df = pd.DataFrame({
                "patient_id": [pid],
                "date": [timestamp],
                "glucose_level": [100 + np.random.normal(0, 10)],
                "cholesterol": [180 + np.random.normal(0, 15)],
                "hba1c": [5.5 + np.random.normal(0, 0.3)]
            })

            labs_list.append(df)

    labs = pd.concat(labs_list, ignore_index=True)
    labs = labs.merge(demographics, on="patient_id", how="left")

    # -----------------------------------------
    # 4. VITALS — 4 times in 2025, staggered by 1 hour per patient
    # -----------------------------------------
    vital_dates = [
        "2025-01-10",
        "2025-04-11",
        "2025-07-12",
        "2025-10-09"
    ]

    vitals_list = []

    for d in vital_dates:
        base_time = pd.Timestamp(f"{d} 08:00:00")  # first patient at 8 AM

        for i, pid in enumerate(patient_ids):
            # Each patient gets 4 readings, 1 hour apart
            for reading_offset in range(4):
                timestamp = base_time + pd.Timedelta(hours=i + reading_offset)

                df = pd.DataFrame({
                    "patient_id": [pid],
                    "date": [timestamp],   # <-- UNIFIED TIMESTAMP
                    "blood_pressure": [120 + np.random.normal(0, 5)],
                    "heart_rate": [75 + np.random.normal(0, 3)],
                    "temperature": [98.6 + np.random.normal(0, 0.3)],
                    "oxygen_saturation": [97 + np.random.normal(0, 1)]
                })

                vitals_list.append(df)

    vitals = pd.concat(vitals_list, ignore_index=True)
    vitals = vitals.merge(demographics, on="patient_id", how="left")

    # -----------------------------------------
    # 5. Sort both tables by patient + date
    # -----------------------------------------
    labs = labs.sort_values(["patient_id", "date"]).reset_index(drop=True)
    vitals = vitals.sort_values(["patient_id", "date"]).reset_index(drop=True)

    # -----------------------------------------
    # 6. Return unified tables
    # -----------------------------------------
    return labs, vitals

# -----------------------------------------
# Example usage
# -----------------------------------------
labs, vitals = load_synthetic_medical_data()

print("=== LABS ===")
print(labs)

print("\n=== VITALS ===")
print(vitals)