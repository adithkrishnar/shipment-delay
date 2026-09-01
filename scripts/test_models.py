import pandas as pd
import joblib

def test_models():
    print("Loading dataset for testing...")
    df = pd.read_csv('data/raw/dataco/DataCoSupplyChainDataset.csv', encoding='latin1')
    
    # Preprocess a couple of rows
    df['order date (DateOrders)'] = pd.to_datetime(df['order date (DateOrders)'])
    df['shipping date (DateOrders)'] = pd.to_datetime(df['shipping date (DateOrders)'])
    
    # Grab a sample that actually suffered a delay for demonstration
    sample_delayed = df[df['Late_delivery_risk'] == 1].iloc[0:1].copy()
    # Grab a sample that was on time
    sample_ontime = df[df['Late_delivery_risk'] == 0].iloc[0:1].copy()
    
    samples = pd.concat([sample_delayed, sample_ontime])
    
    # Re-apply the feature engineering for these rows
    samples['order_year'] = samples['order date (DateOrders)'].dt.year
    samples['order_month'] = samples['order date (DateOrders)'].dt.month
    samples['order_day'] = samples['order date (DateOrders)'].dt.day
    samples['order_dayofweek'] = samples['order date (DateOrders)'].dt.dayofweek
    
    cat_features = [
        'Type', 'Category Name', 'Customer City', 'Customer Country', 
        'Customer Segment', 'Customer State', 'Department Name', 
        'Market', 'Order City', 'Order Country', 'Order Region', 
        'Order State', 'Order Status', 'Product Name', 'Shipping Mode'
    ]
    num_features = [
        'Benefit per order', 'Sales per customer', 'Latitude', 'Longitude',
        'Order Item Discount', 'Order Item Discount Rate', 'Order Item Product Price',
        'Order Item Profit Ratio', 'Order Item Quantity', 'Sales', 'Order Item Total',
        'Order Profit Per Order', 'Product Price'
    ]
    
    features = cat_features + num_features
    
    print("\n--- Testing Shipment Delay Classifier ---")
    clf = joblib.load('trained_models/shipment_delay_classifier.pkl')
    clf_encoder = joblib.load('trained_models/classifier_encoder.pkl')
    
    X_encoded_clf = clf_encoder.transform(samples[features])
    
    preds_clf = clf.predict(X_encoded_clf)
    probs_clf = clf.predict_proba(X_encoded_clf)[:, 1]
    
    for i, (_, row) in enumerate(samples.iterrows()):
        print(f"Sample {i+1}:")
        print(f"  Actual Delay Risk: {row['Late_delivery_risk']}")
        print(f"  Predicted Delay Risk: {preds_clf[i]} (Probability: {probs_clf[i]:.2f})")
        
    print("\n--- Testing Delay Duration Regressor ---")
    reg = joblib.load('trained_models/delay_duration_regressor.pkl')
    reg_encoder = joblib.load('trained_models/regressor_encoder.pkl')
    
    X_encoded_reg = reg_encoder.transform(samples[features])
    preds_reg = reg.predict(X_encoded_reg)
    
    for i, (_, row) in enumerate(samples.iterrows()):
        actual_delay = row['Days for shipping (real)'] - row['Days for shipment (scheduled)']
        print(f"Sample {i+1}:")
        print(f"  Actual Delay Duration: {actual_delay} days")
        print(f"  Predicted Delay Duration: {preds_reg[i]:.2f} days")

if __name__ == "__main__":
    test_models()
