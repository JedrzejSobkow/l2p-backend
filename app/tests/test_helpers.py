# tests/test_helpers.py
"""
Helper functions for tests after migration to identifier pattern
"""

def user_id_to_identifier(user_id: int) -> str:
    """Convert user_id to identifier format for tests"""
    return f"user:{user_id}"

def identifier_to_user_id(identifier: str) -> int:
    """Extract user_id from identifier (for backward compatibility checks)"""
    if identifier.startswith("user:"):
        return int(identifier.split(":", 1)[1])
    raise ValueError(f"Invalid user identifier format: {identifier}")
