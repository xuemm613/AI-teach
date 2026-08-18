"""智能备课相关模型。"""
from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class LessonGenerateRequest(BaseModel):
    grade: str = Field(min_length=1, max_length=32)
    subject: str = Field(min_length=1, max_length=32)
    chapter: str = Field(min_length=1, max_length=128)
    teaching_objectives: Optional[str] = Field(default=None, max_length=2000)


class LessonPlanUpdate(BaseModel):
    content: Dict[str, Any]


class LessonPlanOut(BaseModel):
    id: int
    teacher_id: int
    grade: str
    subject: str
    chapter: str
    teaching_objectives: Optional[str] = None
    content: Optional[Dict[str, Any]] = None
    status: str
    created_at: Optional[datetime] = None