import pandas as pd
import numpy as np

def load_synthetic_medical_data(hours=48):
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
    # 3. Fixed labs (one row per patient, with full timestamp)
    # -----------------------------------------
    labs = pd.DataFrame({
        "patient_id": patient_ids,
        "date": pd.Timestamp("2024-02-15 14:00:00"),  # 2 PM timestamp
        "glucose_level": [100, 120, 95, 110, 130],
        "cholesterol": [180, 190, 170, 160, 200],
        "hba1c": [5.2, 6.1, 5.5, 5.8, 6.3]
    })

    # Merge demographics → labs
    labs = labs.merge(demographics, on="patient_id", how="left")

    # -----------------------------------------
    # 4. Vitals (4 readings per day, realistic variation)
    # -----------------------------------------
    num_days = hours // 24
    reading_times = ["08:00", "12:00", "16:00", "20:00"]

    vitals_list = []

    for pid in patient_ids:
        for day_offset in range(num_days):
            base_date = pd.Timestamp("2024-01-01") + pd.Timedelta(days=day_offset)  
        for t in reading_times:
            timestamp = pd.Timestamp(f"{base_date.date()} {t}")

            df = pd.DataFrame({
                "patient_id": [pid],
                "day": [timestamp],
                "blood_pressure": [120 + np.random.normal(0, 5)],
                "heart_rate": [75 + np.random.normal(0, 3)],
                "temperature": [98.6 + np.random.normal(0, 0.3)],
                "oxygen_saturation": [97 + np.random.normal(0, 1)]
            })

            vitals_list.append(df)

    vitals = pd.concat(vitals_list, ignore_index=True)

    # -----------------------------------------
    # 5. Return only two tables
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

