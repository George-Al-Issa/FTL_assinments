"""Public prediction interface for the CroSafe drought model."""

import pandas as pd

from model.drought_model import (
    load_drought_model,
    predict_drought,
    prepare_nasa_features,
)


def predict(input_data):
    """
    Predict drought class using the trained CroSafe model.

    input_data can be a pandas DataFrame or a dictionary.

    It can contain either:
    - The 30 ready model features.
    - Raw monthly NASA data with the required climate columns.

    Returns:
        A dictionary containing the latest drought class
        and all predictions.
    """

    if isinstance(input_data, dict):
        input_data = pd.DataFrame([input_data])

    if not isinstance(input_data, pd.DataFrame):
        raise TypeError(
            "Input must be a pandas DataFrame or a dictionary."
        )

    if input_data.empty:
        raise ValueError("Input data cannot be empty.")

    # Load the model bundle once.
    bundle = load_drought_model()

    features = bundle["features"]

    # Check whether all trained features are already available.
    has_ready_features = all(
        feature in input_data.columns
        for feature in features
    )

    if has_ready_features:
        prepared_data = input_data.copy()
    else:
        # Prepare raw NASA monthly data.
        prepared_data = prepare_nasa_features(
            input_data,
            bundle=bundle
        )

    if prepared_data.empty:
        raise ValueError(
            "No valid data available for prediction."
        )

    # Run model prediction.
    predictions = predict_drought(
        prepared_data,
        bundle=bundle
    )

    return {
        "drought_class": predictions[-1],
        "all_predictions": predictions,
    }


    if __name__ == "__main__":
         print("CroSafe drought prediction interface is ready.")

         print(
              "Provide a DataFrame with the 30 trained model features, "
              "or raw monthly NASA data."
    )
