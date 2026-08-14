from __future__ import annotations

import os
import requests

PORTS={
    "Mumbai":(18.9388,72.8354),"Chennai":(13.0827,80.2707),"Bengaluru":(12.9716,77.5946),
    "Delhi":(28.6139,77.2090),"Pune":(18.5204,73.8567),"Hyderabad":(17.3850,78.4867),
    "Kolkata":(22.5726,88.3639),"Ahmedabad":(23.0225,72.5714)
}

def weather(port: str) -> dict:
    if port not in PORTS: return {"status":"unavailable","port":port}
    lat,lon=PORTS[port]
    try:
        r=requests.get("https://api.open-meteo.com/v1/forecast",params={"latitude":lat,"longitude":lon,"current":"temperature_2m,weather_code,wind_speed_10m,precipitation","hourly":"temperature_2m,precipitation_probability,wind_speed_10m","forecast_days":2},timeout=5)
        r.raise_for_status(); d=r.json(); c=d.get("current",{})
        return {"status":"live","port":port,"temperature_c":c.get("temperature_2m"),"weather_code":c.get("weather_code"),"wind_kmh":c.get("wind_speed_10m"),"precipitation":c.get("precipitation"),"source":"Open-Meteo"}
    except Exception as e:
        return {"status":"offline","port":port,"message":str(e)}

def news(query: str) -> dict:
    # Optional provider; the core app never depends on it.
    api_key=os.getenv("NEWS_API_KEY")
    if not api_key:
        return {"status":"offline","query":query,"articles":[],"message":"NEWS_API_KEY not configured; demo/offline mode active."}
    return {"status":"offline","query":query,"articles":[],"message":"News provider is optional and not configured."}
