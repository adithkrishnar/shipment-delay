from typing import List, Dict, Any

CAPABILITIES = [
    {
        "id": "demand",
        "name": "Demand Intelligence",
        "required_fields": ["quantity", "date", "product_id"],
        "missing_reason": "Demand Intelligence is unavailable because the dataset is missing historical sales quantity, dates, or product identification."
    },
    {
        "id": "inventory",
        "name": "Inventory Intelligence",
        "required_fields": ["inventory_level", "date", "product_id"],
        "missing_reason": "Inventory Intelligence is unavailable because the dataset does not contain inventory levels, dates, or product identification."
    },
    {
        "id": "supplier",
        "name": "Supplier Intelligence",
        "required_fields": ["supplier_name"],
        "missing_reason": "Supplier Intelligence is unavailable because the dataset does not contain supplier names."
    },
    {
        "id": "shipment",
        "name": "Shipment Routing / Volume",
        "required_fields": ["origin", "destination", "product_id"],
        "missing_reason": "Shipment volume analysis is unavailable because origin, destination, or product_id were not detected."
    },
    {
        "id": "delivery",
        "name": "Delivery Delay Analysis",
        "required_fields": ["planned_delivery", "actual_delivery"],
        "missing_reason": "Delivery performance and delay risk analysis is unavailable because planned vs actual delivery dates were not detected."
    },
    {
        "id": "weather",
        "name": "Historical Weather ML",
        "required_fields": ["__never__"],
        "missing_reason": "Historical weather-based ML is unavailable because historical weather observations are not aligned with the shipment records."
    },
    {
        "id": "gps",
        "name": "GPS Tracking",
        "required_fields": ["__never__"],
        "missing_reason": "GPS tracking is unavailable because the dataset does not contain live GPS/telemetry data."
    }
]

def detect_capabilities(mapped_fields: List[str]) -> List[Dict[str, Any]]:
    mapped_set = set(mapped_fields)
    results = []
    
    for cap in CAPABILITIES:
        req_set = set(cap["required_fields"])
        if "__never__" in req_set:
            status = "NOT AVAILABLE"
            reason = cap["missing_reason"]
        elif req_set.issubset(mapped_set):
            status = "AVAILABLE"
            reason = ""
        else:
            status = "NOT AVAILABLE"
            reason = cap["missing_reason"]
            
        results.append({
            "id": cap["id"],
            "name": cap["name"],
            "status": status,
            "reason": reason
        })
        
    return results
