# app/api/exception_handlers.py

from typing import TYPE_CHECKING
from fastapi import Request
from fastapi.responses import JSONResponse
from exceptions.domain_exceptions import DomainException

if TYPE_CHECKING:
    from fastapi import FastAPI


async def domain_exception_handler(request: Request, exc: DomainException) -> JSONResponse:
    """
    Global exception handler for domain exceptions in FastAPI
    
    Returns a consistent JSON response format for all domain exceptions
    """
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.__class__.__name__, 
            "message": exc.message,
            "details": exc.details,
            "path": request.url.path
        }
    )


def register_exception_handlers(app: "FastAPI") -> None:
    """
    Register all domain exception handlers with FastAPI app
    
    Usage:
        from api.exception_handlers import register_exception_handlers
        
        app = FastAPI()
        register_exception_handlers(app)
    """
    from exceptions.domain_exceptions import (
        DomainException,
        NotFoundException,
        BadRequestException,
        ConflictException,
        UnauthorizedException,
        ForbiddenException,
        ValidationException,
        InternalServerException
    )
    
    app.add_exception_handler(DomainException, domain_exception_handler)
    app.add_exception_handler(NotFoundException, domain_exception_handler)
    app.add_exception_handler(BadRequestException, domain_exception_handler)
    app.add_exception_handler(ConflictException, domain_exception_handler)
    app.add_exception_handler(UnauthorizedException, domain_exception_handler)
    app.add_exception_handler(ForbiddenException, domain_exception_handler)
    app.add_exception_handler(ValidationException, domain_exception_handler)
    app.add_exception_handler(InternalServerException, domain_exception_handler)
