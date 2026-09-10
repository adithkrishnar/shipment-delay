import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.live_intelligence import live_risk_fusion

def test_risk_fusion():
    print("Testing Case A: ML = 0.60, Weather = 0, News = 0 (All live)")
    w_data = {"status": "live", "weather_risk_score": 0.0}
    n_data = {"status": "live", "news_risk_score": 0.0}
    ml = 0.60
    res = live_risk_fusion(ml, w_data, n_data)
    print(f"Result: {res['live_risk_score']}, Expected: 0.42")
    assert abs(res["live_risk_score"] - 0.42) < 0.001
    
    print("\nTesting Case B: ML = 0.60, Weather = 0.80, News = 0.70")
    w_data = {"status": "live", "weather_risk_score": 0.80}
    n_data = {"status": "live", "news_risk_score": 0.70}
    ml = 0.60
    res = live_risk_fusion(ml, w_data, n_data)
    print(f"Result: {res['live_risk_score']}, Expected: 0.65")
    assert abs(res["live_risk_score"] - 0.65) < 0.001
    
    print("\nTesting Case C: ML = 0.60, Weather unavailable, News unavailable")
    w_data = {"status": "offline"}
    n_data = {"status": "offline"}
    ml = 0.60
    res = live_risk_fusion(ml, w_data, n_data)
    print(f"Result: {res['live_risk_score']}, Expected: 0.60")
    assert abs(res["live_risk_score"] - 0.60) < 0.001
    
    print("\nAll risk fusion tests passed.")

if __name__ == "__main__":
    test_risk_fusion()
