"""CroSafe drought prediction model loader and NASA POWER data utilities."""

from pathlib import Path

import joblib
import pandas as pd


# Directory containing this Python file and the trained model
MODEL_DIR = Path__file__).resolve().parent

# Trained XGBoost model bundle
MODEL_PATH = MODEL_DIR / "CroSafe_Final_Model.pkl"


def load_drought_model():
    """Load the trained XGBoost model bundle."""
    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"CroSafe model file not found: {MODEL_PATH}"
        )

    return joblib.load(MODEL_PATH)


def predict_drought(input_data, bundle=None):
    """
    Predict drought class from a DataFrame containing
    the exact features used during model training.
    """
    if bundle is None:
        bundle = load_drought_model()

    model = bundle["model"]
    label_encoder = bundle["label_encoder"]
    features = bundle["features"]

    missing = [
        feature
        for feature in features
        if feature not in input_data.columns
    ]

    if missing:
        raise ValueError(
            f"Missing model features: {missing}"
        )

    X = input_data[features]
    predictions = model.predict(X)

    return label_encoder.inverse_transform(
        predictions.astype(int)
    ).tolist()


def load_nasa_power_data(data_dir):
    """
    Load and combine NASA POWER monthly CSV files.
    """
    data_dir = Path(data_dir)

    if not data_dir.exists():
        raise FileNotFoundError(
            f"NASA data directory not found: {data_dir}"
        )

    csv_files = sorted(data_dir.glob("*.csv"))

    if not csv_files:
        raise FileNotFoundError(
            f"No NASA CSV files found in: {data_dir}"
        )

    dataframes = []

    for file in csv_files:
        df = pd.read_csv(file)
        df.columns = df.columns.str.strip()
        dataframes.append(df)

    data = pd.concat(
        dataframes,
        ignore_index=True
    )

    data = data.drop_duplicates()

    return data


def get_model_features(bundle=None):
    """Return the exact feature names expected by the model."""
    if bundle is None:
        bundle = load_drought_model()

    return bundle["features"]


if __name__ == "main":
    bundle = load_drought_model()

    print("Model loaded successfully!")
    print("Model features:")

    for index, feature in enumerate(
        get_model_features(bundle),
        start=1
    ):
        print(f"{index}. {feature}")
