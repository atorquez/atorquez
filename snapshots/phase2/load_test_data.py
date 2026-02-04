import pandas as pd
import numpy as np

def load_synthetic_medical_data():
    np.random.seed(42)

    # 48 time points (2 days, every hour)
    num_points = 48
    base_time = pd.date_range(start="2024-01-01", periods=num_points, freq="H")

    df = pd.DataFrame({
        "day": base_time,
        "blood_pressure": np.random.normal(120, 10, num_points).round(1),
        "heart_rate": np.random.normal(75, 8, num_points).round(1),
        "temperature": np.random.normal(98.6, 0.4, num_points).round(1),
        "oxygen_saturation": np.random.normal(97, 1, num_points).round(1),
        "glucose_level": np.random.normal(110, 15, num_points).round(1),
        "gender": np.random.choice(["male", "female"], num_points),
        "age_group": np.random.choice(["child", "adult", "senior"], num_points)
    })

    return df