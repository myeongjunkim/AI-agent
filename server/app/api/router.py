from fastapi import APIRouter
from app.api.v1 import chat
from app.api.v1 import search


api_router = APIRouter()
api_router.include_router(chat.router)
api_router.include_router(search.router)