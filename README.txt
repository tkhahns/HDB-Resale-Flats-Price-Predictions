# Real Estate Price Analytics & Prediction

## Overview
Forecast Singapore HDB resale flat prices using transaction history and geospatial features.

## Data Sources
- **Data.gov.sg**: 174,893 transactions (160,858 train / 14,035 test; 28 columns)  
- **OneMap API**: Coordinates for flats, MRT stations, elite schools  
- **Kaggle**: Supplementary amenity and demographic data  

## Data Processing & EDA
- Notebooks:  
  1. `1_feature_engineering+EDA.ipynb` – ingestion, cleaning, Geopy distance calculations, and exploratory analysis (mean floor area 107.23 sqm; mean price SGD 493 000).  
  2. `2_model_building.ipynb` – feature encoding (197 total), model training and evaluation.  

## Modeling
- **Train/test split**: 160,858 / 14,035 records  
- **Models & Test Performance**:  
  - Linear Regression: R² = 0.864, MAE = SGD 48 455  
  - Decision Tree: R² = 0.808, MAE = SGD 54 335  
  - Random Forest: R² = 0.913, MAE = SGD 35 874  
  - **XGBoost**: R² = 0.9537, MAE = SGD 27 568, RMSE = SGD 38 274, MAPE = 4.66% 
