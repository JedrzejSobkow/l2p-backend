# app/api/routes/default.py

from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from schemas.example_schema import ExampleDTO
from services.example_service import check_dto
import time

router = APIRouter()

@router.get("/", response_class=HTMLResponse)
async def root():
    # Przykładowy tekst do sprawdzenia
    example ="SIEMA"
    return f"""
    <html>
        <head>
            <title>Available Endpoint</title>
            <style>
                body {{ font-family: Arial, sans-serif; padding: 20px; }}
                ul {{ list-style-type: none; padding: 0; }}
                li {{ margin-bottom: 10px; }}
                a {{ text-decoration: none; color: #007BFF; }}
                a:hover {{ text-decoration: underline; }}
            </style>
        </head>
        <body>
            <h1>Available Endpoint</h1>
            <ul>
                <li><a href="/check-dto/{example}" target="_blank">/check-dto/{example}</a></li>
            </ul>
        </body>
    </html>
    """


@router.get("/check-dto/{text}", response_model=ExampleDTO)
async def check_dto_endpoint(text: str):
    start = time.perf_counter()

    message = await check_dto(text=text)

    total = time.perf_counter() - start

    print(f"⏱ Request with text '{message}' took {total:.4f} seconds")

    return ExampleDTO.model_validate(message)
