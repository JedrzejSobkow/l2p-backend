# app/api/routes/avatars.py

from fastapi import APIRouter
from typing import List

avatar_router = APIRouter(prefix="/avatars", tags=["Avatars"])


@avatar_router.get("/", response_model=List[str])
async def get_available_avatars():
    """
    Get list of all available avatar paths.
    
    Returns a list of avatar paths in format /images/avatar/x.png where x is 1-16.
    """
    avatars = [f"/images/avatar/{i}.png" for i in range(1, 17)]
    return avatars
