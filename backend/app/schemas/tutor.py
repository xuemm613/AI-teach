"""个性化学习 Agent 相关模型。"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field




class ExerciseGenRequest(BaseModel):
    knowledge_point: str = Field(min_length=1, max_length=200)
    difficulty: str = Field(default="medium", pattern="^(easy|medium|hard)$")
    course_id: Optional[int] = None
    subject: Optional[str] = None   # 题目所属科目（用于保证题库科目正确对应）


class AnalyzeErrorRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    user_answer: str = Field(default="", max_length=2000)
    correct_answer: str = Field(default="", max_length=2000)


class SqlQueryRequest(BaseModel):
    natural_language: str = Field(min_length=1, max_length=1000)


class TaskOut(BaseModel):
    id: str
    task_type: str
    input_data: Optional[Dict[str, Any]] = None
    output: Optional[Dict[str, Any]] = None
    steps: Optional[List[Dict[str, Any]]] = None
    status: str
    error: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None