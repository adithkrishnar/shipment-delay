import os
import zipfile
import pandas as pd
import numpy as np
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data"
RAW_DIR = BASE_DIR / "raw"
GEN_DIR = BASE_DIR / "generated"

def process_maritime_data():
    print("Processing Maritime (AIS) data...")
    ais_zip = RAW_DIR / "noaa_maritime" / "AIS_2023_01_01.zip"
    if not ais_zip.exists():
        print(f"Skipping: {ais_zip} not found.")
        return

    with zipfile.ZipFile(ais_zip) as z:
        csv_name = [n for n in z.namelist() if n.endswith('.csv')][0]
        # Read in chunks to save memory
        chunks = []
        for chunk in pd.read_csv(z.open(csv_name), chunksize=100000, usecols=['BaseDateTime', 'LAT', 'LON', 'SOG']):
            chunk['date'] = pd.to_datetime(chunk['BaseDateTime']).dt.date
            # SOG = Speed Over Ground. If SOG < 0.5, vessel is likely waiting/anchored (congested)
            chunk['is_waiting'] = (chunk['SOG'] < 0.5).astype(int)
            daily_stats = chunk.groupby('date').agg(
                total_vessels=('LAT', 'count'),
                waiting_vessels=('is_waiting', 'sum')
            ).reset_index()
            chunks.append(daily_stats)
            
    df = pd.concat(chunks)
    final = df.groupby('date').sum().reset_index()
    final['port_congestion_index'] = (final['waiting_vessels'] / final['total_vessels']).fillna(0)
    
    os.makedirs(GEN_DIR, exist_ok=True)
    out_path = GEN_DIR / "maritime_congestion.csv"
    final[['date', 'port_congestion_index']].to_csv(out_path, index=False)
    print(f"Saved maritime congestion index to {out_path}")

def process_rail_data():
    print("Processing Rail data...")
    rail_zip = RAW_DIR / "rail" / "23100062-eng.zip"
    if not rail_zip.exists():
        print(f"Skipping: {rail_zip} not found.")
        return

    with zipfile.ZipFile(rail_zip) as z:
        csv_name = [n for n in z.namelist() if n.endswith('.csv') and 'MetaData' not in n][0]
        df = pd.read_csv(z.open(csv_name), usecols=['REF_DATE', 'VALUE'])
        
    df['date'] = pd.to_datetime(df['REF_DATE'] + '-01').dt.date
    # Normalize VALUE to create a mock congestion index
    df['VALUE'] = pd.to_numeric(df['VALUE'], errors='coerce').fillna(0)
    daily = df.groupby('date')['VALUE'].sum().reset_index()
    max_val = daily['VALUE'].max()
    # High tonnage = higher congestion risk
    daily['rail_congestion_index'] = (daily['VALUE'] / max_val) if max_val > 0 else 0
    
    os.makedirs(GEN_DIR, exist_ok=True)
    out_path = GEN_DIR / "rail_congestion.csv"
    daily[['date', 'rail_congestion_index']].to_csv(out_path, index=False)
    print(f"Saved rail congestion index to {out_path}")

if __name__ == "__main__":
    process_maritime_data()
    process_rail_data()
