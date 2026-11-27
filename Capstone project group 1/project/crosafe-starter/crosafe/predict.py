"""Public prediction interface for the CroSafe drought model."""

import pandas as pd
from models.drought_model import predict_drought


def predict(input_data):
    """
    Predict drought class using the trained CroSafe model.

    input_data must contain the exact 30 features used during training.
    It can be a pandas DataFrame or a dictionary containing one record.
    """

    if isinstance(input_data, dict):
        input_data = pd.DataFrame([input_data])

    if not isinstance(input_data, pd.DataFrame):
        raise TypeError(
            "Input must be a pandas DataFrame or a dictionary."
        )

    if input_data.empty:
        raise ValueError("Input data cannot be empty.")

    predictions = predict_drought(input_data)

    return {
        "drought_class": predictions[0],
        "forecast_horizon_months": 3
    }


if__name__== "main":
    print("CroSafe drought prediction interface is ready.")
    print("Provide a DataFrame with the 30 trained model features to predict.")
