"""用户 / 学生 / 教师相关模型。"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class UserUpdate(BaseModel):
    full_name: Optional[str] = Field(default=None, max_length=64)
    email: Optional[str] = Field(default=None, max_length=128)
    avatar: Optional[str] = Field(default=None, max_length=255)
    password: Optional[str] = Field(default=None, min_length=6, max_length=64)


class UserOut(BaseModel):
    id: int
    username: str
    full_name: Optional[str] = None
    email: Optional[str] = None
    role: str
    avatar: Optional[str] = None
    is_active: bool
    created_at: Optional[datetime] = None
    student_no: Optional[str] = None
    grade: Optional[str] = None
    title: Optional[str] = None
    department: Optional[str] = None
    employee_no: Optional[str] = None


class AdminUserUpdate(BaseModel):
    role: Optional[str] = Field(default=None, pattern="^(admin|teacher|student)$")
    is_active: Optional[bool] = None
    full_name: Optional[str] = None
    email: Optional[str] = None
    employee_no: Optional[str] = Field(default=None, max_length=32)   # 教师工号
    subjects: Optional[List[str]] = None                                   # 负责科目
    title: Optional[str] = None                                           # 教师职称
    department: Optional[str] = None                                      # 教师教研组
    grade: Optional[str] = None                                           # 学生年级
    new_password: Optional[str] = Field(default=None, min_length=6, max_length=64)


class AdminUserCreate(BaseModel):
    username: str = Field(min_length=2, max_length=64)
    password: str = Field(min_length=6, max_length=64)
    role: str = Field(default="student", pattern="^(admin|teacher|student)$")
    full_name: Optional[str] = Field(default=None, max_length=64)
    email: Optional[str] = Field(default=None, max_length=128)
    employee_no: Optional[str] = Field(default=None, max_length=32)   # 教师工号
    subjects: Optional[List[str]] = None                                   # 负责科目
    student_no: Optional[str] = Field(default=None, max_length=32)   # 学生学号
    grade: Optional[str] = None
    title: Optional[str] = None
    department: Optional[str] = None


class SubmitRecordRequest(BaseModel):
    exercise_id: int
    user_answer: str
    is_correct: bool
    duration_seconds: Optional[int] = Field(default=None, ge=0)




class WrongBookAddRequest(BaseModel):
    exercise_id: int
    reason: Optional[str] = None


class StudentMessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=2000)


class ExerciseOut(BaseModel):
    id: int
    course_id: Optional[int] = None
    chapter: Optional[str] = None
    type: str
    content: str
    options: Optional[List[Dict[str, Any]]] = None
    answer: Optional[str] = None
    analysis: Optional[str] = None
    difficulty: str
    knowledge_points: Optional[List[str]] = None


class LearningRecordOut(BaseModel):
    id: int
    exercise_id: int
    user_answer: Optional[str] = None
    is_correct: bool
    duration_seconds: Optional[int] = None
    created_at: Optional[datetime] = None
    exercise: Optional[ExerciseOut] = None


class WrongBookOut(BaseModel):
    id: int
    exercise_id: int
    reason: Optional[str] = None
    created_at: Optional[datetime] = None
    exercise: Optional[ExerciseOut] = None


class CourseOut(BaseModel):
    id: int
    name: str
    grade: Optional[str] = None
    subject: Optional[str] = None
    teacher_id: Optional[int] = None
    chapter_tree: Optional[List[Any]] = None
    description: Optional[str] = None


class ClassOut(BaseModel):
    id: int
    name: str
    teacher_id: int
    grade: Optional[str] = None
    subject: Optional[str] = None
    description: Optional[str] = None
    student_count: Optional[int] = 0


class StatsOut(BaseModel):
    total_answered: int = 0
    correct_count: int = 0
    accuracy: float = 0.0
    by_course: List[Dict[str, Any]] = []
    daily: List[Dict[str, Any]] = []