"""CroSafe drought prediction model and NASA POWER utilities."""

from pathlib import Path

import joblib
import pandas as pd


# Directory containing this Python file and the trained model
MODEL_DIR = Path(__file__).resolve().parent

# Trained XGBoost model bundle
MODEL_PATH = MODEL_DIR / "CroSafe_Final_Model.pkl"


MONTHS = [
    "JAN", "FEB", "MAR", "APR", "MAY", "JUN",
    "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"
]

MONTH_NUMBERS = {
    month: index
    for index, month in enumerate(MONTHS, start=1)
}


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
    the exact 30 features used during model training.
    """

    if bundle is None:
        bundle = load_drought_model()

    model = bundle["model"]
    label_encoder = bundle["label_encoder"]
    features = bundle["features"]

    if not isinstance(input_data, pd.DataFrame):
        raise TypeError("Input must be a pandas DataFrame.")

    if input_data.empty:
        raise ValueError("Input data cannot be empty.")

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

    if X.isnull().any().any():
        raise ValueError(
            "Input contains missing values. "
            "Prepare valid rows before prediction."
        )

    predictions = model.predict(X)

    return label_encoder.inverse_transform(
        predictions.astype(int)
    ).tolist()


def load_nasa_power_data(data_dir):
    """
    Load NASA POWER monthly CSV files.

    Convert the original wide format into long format,
    combine climate parameters, and create DATE and
    MONTH_NUM columns.

    The ANN column is excluded because it represents
    the annual average, not an additional month.
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

    monthly_data = []

    for file in csv_files:

        # Skip the 9 NASA metadata lines.
        df = pd.read_csv(file, skiprows=9)

        df.columns = (
            df.columns
            .str.strip()
            .str.upper()
        )

        required_columns = [
            "PARAMETER",
            "YEAR",
            "LAT",
            "LON"
        ] + MONTHS

        missing = [
            col for col in required_columns
            if col not in df.columns
        ]

        if missing:
            raise ValueError(
                f"Missing columns in {file.name}: {missing}"
            )

        # Exclude ANN and keep the 12 monthly values.
        df = df[required_columns].copy()

        # Convert monthly values to numeric.
        for month in MONTHS:
            df[month] = pd.to_numeric(
                df[month],
                errors="coerce"
            )

        # Convert wide format to long format.
        long_df = df.melt(
            id_vars=[
                "PARAMETER",
                "YEAR",
                "LAT",
                "LON"
            ],
            value_vars=MONTHS,
            var_name="MONTH",
            value_name="VALUE"
        )

        monthly_data.append(long_df)

    # Combine all parameter files.
    combined = pd.concat(
        monthly_data,
        ignore_index=True
    )

    # Replace NASA missing-value indicator.
    combined["VALUE"] = combined["VALUE"].replace(
        -999, float("nan")
    )
    # Convert parameter names into separate columns.
    data = combined.pivot_table(
        index=[
            "YEAR",
            "LAT",
            "LON",
            "MONTH"
        ],
        columns="PARAMETER",
        values="VALUE",
        aggfunc="first"
    ).reset_index()

    data.columns.name = None

    # Add numeric month.
    data["MONTH_NUM"] = data["MONTH"].map(
        MONTH_NUMBERS
    )

    # Create monthly date.
    data["DATE"] = pd.to_datetime(
        data["YEAR"].astype(int).astype(str)
        + "-"
        + data["MONTH_NUM"].astype(str)
        + "-01"
    )

    # Sort chronologically for each location.
    data = data.sort_values(
        ["LAT", "LON", "DATE"]
    ).reset_index(drop=True)

    return data


def get_model_features(bundle=None):
    """Return the exact feature names expected by the model."""

    if bundle is None:
        bundle = load_drought_model()

    return bundle["features"]


if__name__== "main":

    bundle = load_drought_model()

    print("Model loaded successfully!")

    print("\nModel features:")

    for index, feature in enumerate(
        get_model_features(bundle),
        start=1
    ):
        print(f"{index}. {feature}")
    
