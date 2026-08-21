"""智能问答相关模型。"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class HistoryItem(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    session_id: Optional[str] = None
    course_id: Optional[int] = None
    subject: Optional[str] = None
    chapter: Optional[str] = None
    history: List[HistoryItem] = Field(default_factory=list)
    # 学情分析结构化上下文
    context_from: Optional[str] = Field(default=None, description="来源标识，如 'analysis'")
    stage_name: Optional[str] = Field(default=None, description="学习阶段名称")
    stage_content: Optional[str] = Field(default=None, description="学习阶段内容")
    weak_points: Optional[str] = Field(default=None, description="薄弱点诊断")


class CollectRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    answer: str = Field(min_length=1, max_length=8000)
    session_id: Optional[str] = None
    knowledge_points: List[str] = Field(default_factory=list)


class SourceItem(BaseModel):
    filename: Optional[str] = None
    page: Optional[int] = None
    score: Optional[float] = None
    content: Optional[str] = None


class AskOut(BaseModel):
    answer: str
    sources: List[SourceItem]
    session_id: str
    accepted: bool
    score: Optional[float] = None


class SessionOut(BaseModel):
    id: str
    title: str
    created_at: Optional[datetime] = None


class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    sources: Optional[List[Dict[str, Any]]] = None
    created_at: Optional[datetime] = None