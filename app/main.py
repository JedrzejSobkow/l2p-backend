# app/main.py

from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI
from api.routes import default

app = FastAPI()

app.add_middleware(
    middleware_class=CORSMiddleware,
    allow_origins=["*"],  #TODO adres frontendu zamiast '*'
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(default.router, prefix="")
