"""
CroSafe - Machine Learning Drought Prediction
Random Forest model for predicting SPEI-3.
"""

import pandas as pd

from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split


FEATURES = [
    "rainfall_mm",
    "temperature_c",
    "et0_mm",
    "soil_moisture",
]

TARGET = "spei_3"


def create_model():
    """Create the drought prediction model."""

    return Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("random_forest", RandomForestRegressor(
            n_estimators=200,
            max_depth=10,
            min_samples_split=4,
            random_state=42,
            n_jobs=-1
        ))
    ])


def train_model(data):
    """
    Train the model using historical climate data.

    Required columns:
    rainfall_mm, temperature_c, et0_mm,
    soil_moisture, spei_3
    """

    required = FEATURES + [TARGET]

    missing = [col for col in required if col not in data.columns]
    if missing:
        raise ValueError(f"Missing columns: {missing}")

    clean_data = data[required].dropna(subset=[TARGET])

    if len(clean_data) < 30:
        raise ValueError(
            "At least 30 historical records are required."
        )

    X = clean_data[FEATURES]
    y = clean_data[TARGET]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    model = create_model()
    model.fit(X_train, y_train)

    predictions = model.predict(X_test)

    results = {
        "mae": mean_absolute_error(y_test, predictions),
        "r2": r2_score(y_test, predictions),
        "training_records": len(X_train),
        "testing_records": len(X_test)
    }

    return model, results


def classify_drought(spei):
    """Convert SPEI-3 into drought severity."""

    if spei <= -2.0:
        return "Extreme drought"
    elif spei <= -1.5:
        return "Severe drought"
    elif spei <= -1.0:
        return "Moderate drought"
    elif spei <= -0.5:
        return "Mild drought"
    else:
        return "No significant drought"


def predict_drought(model, weather_data):
    """Predict SPEI-3 and drought category."""

    values = pd.DataFrame(
        [weather_data],
        columns=FEATURES
    )

    predicted_spei = float(model.predict(values)[0])

    return {
        "predicted_spei_3": round(predicted_spei, 3),
        "drought_status": classify_drought(predicted_spei)
    }
