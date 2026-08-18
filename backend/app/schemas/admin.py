"""管理后台相关模型。"""
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ClassCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    teacher_id: int
    class_no: Optional[str] = None
    grade: Optional[str] = None
    description: Optional[str] = None


class ClassUpdate(BaseModel):
    name: Optional[str] = None
    teacher_id: Optional[int] = None
    class_no: Optional[str] = None
    grade: Optional[str] = None
    description: Optional[str] = None


class TimetableCell(BaseModel):
    """课表单元格：科目 + 上课老师（单值，users.id）。"""
    subject: Optional[str] = None
    teacher_user_id: Optional[int] = None


class TimetableUpdate(BaseModel):
    # cells: periods 行 × weekdays 列，每个单元格为 TimetableCell
    cells: List[List[TimetableCell]]
    periods: int = Field(default=8, ge=1, le=12)
    weekdays: int = Field(default=5, ge=1, le=7)


class CourseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    grade: Optional[str] = None
    subject: Optional[str] = None
    teacher_id: Optional[int] = None
    chapter_tree: Optional[List[Any]] = None
    description: Optional[str] = None


class CourseUpdate(BaseModel):
    name: Optional[str] = None
    grade: Optional[str] = None
    subject: Optional[str] = None
    teacher_id: Optional[int] = None
    chapter_tree: Optional[List[Any]] = None
    description: Optional[str] = None


class ExerciseCreate(BaseModel):
    course_id: Optional[int] = None
    subject: Optional[str] = None   # 科目（保存时按科目自动关联课程）
    chapter: Optional[str] = None
    type: str = Field(default="single", pattern="^(single|multiple|judge|fill|qa)$")
    content: str = Field(min_length=1)
    options: Optional[List[Dict[str, Any]]] = None
    answer: Optional[str] = None
    analysis: Optional[str] = None
    difficulty: str = Field(default="medium", pattern="^(easy|medium|hard)$")
    knowledge_points: Optional[List[str]] = None


class ExerciseUpdate(BaseModel):
    course_id: Optional[int] = None
    subject: Optional[str] = None   # 科目（保存时按科目自动关联课程）
    chapter: Optional[str] = None
    type: Optional[str] = None
    content: Optional[str] = None
    options: Optional[List[Dict[str, Any]]] = None
    answer: Optional[str] = None
    analysis: Optional[str] = None
    difficulty: Optional[str] = None
    knowledge_points: Optional[List[str]] = None


class TransferRequest(BaseModel):
    to_class_id: int
