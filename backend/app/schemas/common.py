"""统一响应格式：{ code, message, data }"""
from typing import Any, Dict, Optional


def ok(data: Any = None, message: str = "success") -> Dict[str, Any]:
    return {"code": 0, "message": message, "data": data}


def fail(message: str, code: int = 1, data: Any = None) -> Dict[str, Any]:
    return {"code": code, "message": message, "data": data}