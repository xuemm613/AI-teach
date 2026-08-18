"""知识库相关模型。"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class KnowledgeFileOut(BaseModel):
    id: int
    filename: str
    file_type: str
    file_size: int
    status: str
    chunk_count: int
    error: Optional[str] = None
    uploaded_by: Optional[int] = None
    created_at: Optional[datetime] = None


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)
    subject: Optional[str] = None


class KnowledgeAskRequest(BaseModel):
    """知识库 RAG 问答请求。"""
    question: str = Field(min_length=1, max_length=2000)
    subject: Optional[str] = None


class SearchHit(BaseModel):
    id: int
    score: float
    content: str
    metadata: Dict[str, Any]


class SearchOut(BaseModel):
    query: str
    hits: List[SearchHit]
    threshold: float
    accepted: bool