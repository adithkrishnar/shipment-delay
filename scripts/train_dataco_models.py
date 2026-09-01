import pandas as pd
import numpy as np
import os
import joblib
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score, f1_score, precision_score, recall_score
from sklearn.metrics import mean_absolute_error, mean_squared_error
from lightgbm import LGBMClassifier, LGBMRegressor
from category_encoders import TargetEncoder
import warnings
warnings.filterwarnings('ignore')

def load_and_preprocess(filepath):
    print("Loading data...")
    df = pd.read_csv(filepath, encoding='latin1')
    
    print("Preprocessing data...")
    # Convert dates
    df['order date (DateOrders)'] = pd.to_datetime(df['order date (DateOrders)'])
    df['shipping date (DateOrders)'] = pd.to_datetime(df['shipping date (DateOrders)'])
    
    # Sort chronologically by order date for time-based split
    df = df.sort_values(by='order date (DateOrders)').reset_index(drop=True)
    
    # Drop irrelevant, highly cardinal text, or PII columns to clean up
    cols_to_drop = [
        'Customer Email', 'Customer Fname', 'Customer Lname', 'Customer Password', 
        'Customer Street', 'Product Description', 'Product Image', 'Order Zipcode'
    ]
    df.drop(columns=[c for c in cols_to_drop if c in df.columns], inplace=True)
    
    return df

def feature_engineering(df):
    print("Engineering features...")
    # Temporal features
    df['order_year'] = df['order date (DateOrders)'].dt.year
    df['order_month'] = df['order date (DateOrders)'].dt.month
    df['order_day'] = df['order date (DateOrders)'].dt.day
    df['order_dayofweek'] = df['order date (DateOrders)'].dt.dayofweek
    
    # Define categorical and numerical features
    cat_features = [
        'Type', 'Category Name', 'Customer City', 'Customer Country', 
        'Customer Segment', 'Customer State', 'Department Name', 
        'Market', 'Order City', 'Order Country', 'Order Region', 
        'Order State', 'Order Status', 'Product Name', 'Shipping Mode'
    ]
    
    # Exclude leakage features (Delivery Status, real shipping days)
    num_features = [
        'Benefit per order', 'Sales per customer', 'Latitude', 'Longitude',
        'Order Item Discount', 'Order Item Discount Rate', 'Order Item Product Price',
        'Order Item Profit Ratio', 'Order Item Quantity', 'Sales', 'Order Item Total',
        'Order Profit Per Order', 'Product Price'
    ]
    
    return df, cat_features, num_features

def time_based_split(df, target_col, features, test_size=0.2):
    split_idx = int(len(df) * (1 - test_size))
    X_train = df.loc[:split_idx, features]
    y_train = df.loc[:split_idx, target_col]
    X_test = df.loc[split_idx+1:, features]
    y_test = df.loc[split_idx+1:, target_col]
    return X_train, X_test, y_train, y_test

def train_classifier(df, cat_features, num_features, output_dir):
    print("\n--- Training Shipment Delay Classifier ---")
    features = cat_features + num_features
    target = 'Late_delivery_risk'
    
    # Target encoding
    encoder = TargetEncoder(cols=cat_features)
    X_encoded = encoder.fit_transform(df[features], df[target])
    df_encoded = pd.concat([X_encoded, df[[target]]], axis=1)
    
    X_train, X_test, y_train, y_test = time_based_split(df_encoded, target, features)
    
    clf = LGBMClassifier(class_weight='balanced', random_state=42)
    clf.fit(X_train, y_train)
    
    preds = clf.predict(X_test)
    probs = clf.predict_proba(X_test)[:, 1]
    
    print("Classifier Evaluation:")
    print(f"ROC-AUC: {roc_auc_score(y_test, probs):.4f}")
    print(f"F1-Score: {f1_score(y_test, preds):.4f}")
    print(f"Precision: {precision_score(y_test, preds):.4f}")
    print(f"Recall: {recall_score(y_test, preds):.4f}")
    
    os.makedirs(output_dir, exist_ok=True)
    joblib.dump(encoder, os.path.join(output_dir, 'classifier_encoder.pkl'))
    joblib.dump(clf, os.path.join(output_dir, 'shipment_delay_classifier.pkl'))
    return roc_auc_score(y_test, probs), f1_score(y_test, preds)

def train_regressor(df, cat_features, num_features, output_dir):
    print("\n--- Training Delay Duration Regressor ---")
    
    # Target: Delay in days = real shipping days - scheduled shipping days
    df['Delay_Duration'] = df['Days for shipping (real)'] - df['Days for shipment (scheduled)']
    
    features = cat_features + num_features
    target = 'Delay_Duration'
    
    encoder = TargetEncoder(cols=cat_features)
    X_encoded = encoder.fit_transform(df[features], df[target])
    df_encoded = pd.concat([X_encoded, df[[target]]], axis=1)
    
    X_train, X_test, y_train, y_test = time_based_split(df_encoded, target, features)
    
    reg = LGBMRegressor(random_state=42)
    reg.fit(X_train, y_train)
    
    preds = reg.predict(X_test)
    
    print("Regressor Evaluation:")
    mae = mean_absolute_error(y_test, preds)
    rmse = np.sqrt(mean_squared_error(y_test, preds))
    print(f"MAE: {mae:.4f}")
    print(f"RMSE: {rmse:.4f}")
    
    joblib.dump(encoder, os.path.join(output_dir, 'regressor_encoder.pkl'))
    joblib.dump(reg, os.path.join(output_dir, 'delay_duration_regressor.pkl'))
    return mae, rmse

def train_demand_forecasting(df, output_dir):
    print("\n--- Training Demand Forecasting Model ---")
    
    # Demand forecasting: Aggregate Demand (Order Item Quantity) by Date
    daily_demand = df.groupby(df['order date (DateOrders)'].dt.date)['Order Item Quantity'].sum().reset_index()
    daily_demand.columns = ['date', 'demand']
    daily_demand['date'] = pd.to_datetime(daily_demand['date'])
    daily_demand.set_index('date', inplace=True)
    daily_demand = daily_demand.resample('D').sum().reset_index()
    daily_demand['demand'] = daily_demand['demand'].fillna(0)
    
    # Feature engineering for time series
    daily_demand['year'] = daily_demand['date'].dt.year
    daily_demand['month'] = daily_demand['date'].dt.month
    daily_demand['day'] = daily_demand['date'].dt.day
    daily_demand['dayofweek'] = daily_demand['date'].dt.dayofweek
    
    # Lag features
    for lag in [1, 7, 14]:
        daily_demand[f'demand_lag_{lag}'] = daily_demand['demand'].shift(lag)
        
    # Rolling features
    daily_demand['demand_roll_mean_7'] = daily_demand['demand'].shift(1).rolling(7).mean()
    
    daily_demand = daily_demand.dropna().reset_index(drop=True)
    
    features = ['year', 'month', 'day', 'dayofweek', 'demand_lag_1', 'demand_lag_7', 'demand_lag_14', 'demand_roll_mean_7']
    target = 'demand'
    
    X_train, X_test, y_train, y_test = time_based_split(daily_demand, target, features)
    
    reg = LGBMRegressor(random_state=42)
    reg.fit(X_train, y_train)
    
    preds = reg.predict(X_test)
    
    print("Demand Forecasting Evaluation:")
    mae = mean_absolute_error(y_test, preds)
    rmse = np.sqrt(mean_squared_error(y_test, preds))
    print(f"MAE: {mae:.4f}")
    print(f"RMSE: {rmse:.4f}")
    
    joblib.dump(reg, os.path.join(output_dir, 'demand_forecasting_model.pkl'))
    return mae, rmse

if __name__ == "__main__":
    filepath = 'data/raw/dataco/DataCoSupplyChainDataset.csv'
    output_dir = 'trained_models'
    
    df = load_and_preprocess(filepath)
    df, cat_features, num_features = feature_engineering(df)
    
    train_classifier(df.copy(), cat_features, num_features, output_dir)
    train_regressor(df.copy(), cat_features, num_features, output_dir)
    train_demand_forecasting(df.copy(), output_dir)
    
    print("\nTraining completed. Models saved to:", output_dir)
