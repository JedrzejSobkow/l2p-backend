# app/example_service.py

from schemas.example_schema import ExampleDTO

async def check_dto(text: str) -> ExampleDTO:
    
    return ExampleDTO(text=text)
