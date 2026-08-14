from fastapi import APIRouter, Query
from app.services.live_intelligence import weather, news
router=APIRouter(prefix="/api/live",tags=["live intelligence"])
@router.get("/weather")
def get_weather(port:str=Query(...)): return weather(port)
@router.get("/news")
def get_news(query:str=Query(...)): return news(query)
