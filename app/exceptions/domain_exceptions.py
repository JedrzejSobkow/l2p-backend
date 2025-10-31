# app/domain/exceptions.py

from typing import Any, Dict, Optional


class DomainException(Exception):
    """Base class for all domain exceptions"""
    
    def __init__(
        self,
        message: str,
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


class NotFoundException(DomainException):
    """Exception raised when a resource is not found"""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=404,
            details=details
        )


class BadRequestException(DomainException):
    """Exception raised for invalid client requests"""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=400,
            details=details
        )


class ConflictException(DomainException):
    """Exception raised when there's a conflict with current state"""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=409,
            details=details
        )


class UnauthorizedException(DomainException):
    """Exception raised for unauthorized access"""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=401,
            details=details
        )


class ForbiddenException(DomainException):
    """Exception raised for forbidden access"""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=403,
            details=details
        )


class ValidationException(DomainException):
    """Exception raised for validation errors"""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=422,
            details=details
        )


class InternalServerException(DomainException):
    """Exception raised for internal server errors"""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=500,
            details=details
        )
