import requests
import json
from pathlib import Path
import time

API_URL = "http://127.0.0.1:8000/api"

def run_test():
    # 1. Login
    print("Logging in...")
    login_resp = requests.post(f"{API_URL}/v1/auth/login", data={"username": "test@example.com", "password": "password"})
    if login_resp.status_code != 200:
        # Create user if doesn't exist
        print("User not found, registering...")
        reg_resp = requests.post(f"{API_URL}/v1/auth/register", json={"email": "test@example.com", "password": "password", "company_name": "Test Company"})
        login_resp = requests.post(f"{API_URL}/v1/auth/login", data={"username": "test@example.com", "password": "password"})
    
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    me_resp = requests.get(f"{API_URL}/v1/auth/me", headers=headers).json()
    company_id = me_resp["company_id"]
    print(f"Company ID: {company_id}")

    # 2. Upload
    print("Uploading file...")
    csv_path = r"c:\Users\adith\Downloads\Telegram Desktop\supply-chain-intelligence\supply-chain-intelligence\backend\uploads\company_5\upload_4.csv"
    with open(csv_path, 'rb') as f:
        files = {'file': ('upload_4.csv', f, 'text/csv')}
        data = {'company_id': company_id, 'dataset_type': 'unified'}
        up_resp = requests.post(f"{API_URL}/upload", files=files, data=data, headers=headers)
    
    print(up_resp.status_code, up_resp.text)
    upload_id = up_resp.json()["upload_id"]
    mapping = up_resp.json()["suggested_mapping"]
    print(f"Suggested mapping: {mapping}")

    # 3. Map
    print("Mapping...")
    map_resp = requests.post(f"{API_URL}/data/map", json={"upload_id": upload_id, "column_mapping": mapping}, headers=headers)
    print(map_resp.status_code, map_resp.text)

    # 4. Validate & Get Capabilities
    print("Validating...")
    val_resp = requests.post(f"{API_URL}/data/validate", json={"upload_id": upload_id, "column_mapping": mapping}, headers=headers)
    print("Validation:", val_resp.status_code, val_resp.text)

    cap_resp = requests.get(f"{API_URL}/data/uploads/{upload_id}/capabilities", headers=headers)
    print("Capabilities:", cap_resp.status_code, cap_resp.text)

    # 5. Process
    print("Processing...")
    imp_resp = requests.post(f"{API_URL}/data/import?company_id={company_id}&upload_id={upload_id}", headers=headers)
    print("Import:", imp_resp.status_code, imp_resp.text)

if __name__ == "__main__":
    run_test()
