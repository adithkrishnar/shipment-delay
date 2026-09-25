from fastapi import APIRouter, Query, Depends
from app.services.live_intelligence import weather, news
from app.auth.deps import get_current_user
from app.models.user import User
router=APIRouter(prefix="/api/live",tags=["live intelligence"])
@router.get("/weather")
def get_weather(port:str=Query(...), current_user: User=Depends(get_current_user)): return weather(port)
@router.get("/news")
def get_news(query:str=Query(...), current_user: User=Depends(get_current_user)): return news(query)
