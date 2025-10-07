# app/example_schema.py

from pydantic import BaseModel

class ExampleDTO(BaseModel):
    text: str

    model_config = {
        'from_attributes': True
    }
