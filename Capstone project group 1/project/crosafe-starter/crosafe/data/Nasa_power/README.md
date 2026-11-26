NASA POWER datasets used for drought prediction.

CroSafe – Drought Prediction Model Integration

1. Project Overview

This branch contains the trained XGBoost drought prediction model developed for the CroSafe project.

The model uses climate data collected from NASA POWER to predict drought conditions in Syria, with a forecast horizon of three months.

The goal is to provide a drought prediction component that can be integrated into the CroSafe application.

2. Model Information

- Model: XGBoost Classifier
- Project: CroSafe – Syria Drought Prediction
- Data Source: NASA POWER
- Forecast Horizon: 3 Months
- Number of Features: 30
- Macro F1-Score: 0.2609
- Status: Preliminary Research Model

3. Predicted Classes

The model predicts one of the following four drought classes:

- Extreme Drought
- Severe Drought
- Moderate Drought
- No Drought

4. Repository Structure

crosafe
models
 CroSafe_Final_Model.pkl
 CroSafe_Final_Model_Info.json


5. Model Files

- CroSafe_Final_Model.pkl: Contains the trained XGBoost model bundle.
- CroSafe_Final_Model_Info.json: Contains model metadata, performance information, and prediction classes.
- drought_model.py: Provides functions to load the trained model, retrieve the required feature names, predict drought classes, and load NASA POWER CSV files.

6. Input Requirements

The model expects a Pandas DataFrame containing the exact 30 features used during training.

Input column names, order, data types, units, and preprocessing must match the original training pipeline.

The original NASA POWER datasets are included as source data. They must be processed using the same methodology applied during model training before prediction.

7. Prediction Output

The model returns a predicted drought class:

- Extreme Drought
- Severe Drought
- Moderate Drought
- No Drought

The prediction represents the model's three-month forecast horizon.

8. Integration with CroSafe

The model is prepared as a separate component for integration into CroSafe.

The intended integration workflow is:

1. Obtain the relevant climate data for the selected field.
2. Prepare the input features using the original preprocessing methodology.
3. Load the trained XGBoost model.
4. Generate the drought prediction.
5. Return the predicted drought class to the CroSafe assessment module.
6. Integration Contact

Branch: "sami/drought-model-integration"

Component: XGBoost-based Syria Drought Prediction Model
