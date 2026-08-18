"""SQLAlchemy ORM 模型（MySQL 8）。

核心关系：users / teachers / students / classes / courses / exercises /
learning_records / wrong_book / lesson_plans / knowledge_files /
chat_sessions / chat_messages / agent_tasks
"""
import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def gen_uuid() -> str:
    return str(uuid.uuid4())


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class User(Base, TimestampMixin):
    """统一用户表：admin / teacher / student 三种角色。"""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), index=True, nullable=False)  # 用户名允许重复
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(128), unique=True, nullable=True)
    full_name: Mapped[Optional[str]] = mapped_column(String(64))
    role: Mapped[str] = mapped_column(String(16), default="student", index=True)
    avatar: Mapped[Optional[str]] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    teacher: Mapped[Optional["Teacher"]] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    student: Mapped[Optional["Student"]] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    classes_teaching: Mapped[List["Class"]] = relationship(
        back_populates="teacher", foreign_keys="Class.teacher_id", passive_deletes=True
    )


class Teacher(Base, TimestampMixin):
    """教师扩展信息。"""

    __tablename__ = "teachers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    employee_no: Mapped[str] = mapped_column(String(32), index=True, unique=True, nullable=False)  # 工号唯一（教师主标识）
    subjects: Mapped[Optional[List]] = mapped_column(JSON, default=list)  # 负责的科目列表
    title: Mapped[Optional[str]] = mapped_column(String(64))       # 职称
    department: Mapped[Optional[str]] = mapped_column(String(128))  # 教研组/院系
    bio: Mapped[Optional[str]] = mapped_column(Text)

    user: Mapped["User"] = relationship(back_populates="teacher")


class Student(Base, TimestampMixin):
    """学生扩展信息。"""

    __tablename__ = "students"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    student_no: Mapped[Optional[str]] = mapped_column(String(32), unique=True, index=True)  # 学号唯一
    grade: Mapped[Optional[str]] = mapped_column(String(32))       # 年级

    user: Mapped["User"] = relationship(back_populates="student")
    records: Mapped[List["LearningRecord"]] = relationship(back_populates="student", passive_deletes=True)
    wrong_books: Mapped[List["WrongBook"]] = relationship(back_populates="student", passive_deletes=True)
    class_links: Mapped[List["ClassStudent"]] = relationship(back_populates="student", passive_deletes=True)


class Class(Base, TimestampMixin):
    """班级：关联教师（users.id）。"""

    __tablename__ = "classes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    teacher_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    grade: Mapped[Optional[str]] = mapped_column(String(32))
    class_no: Mapped[Optional[str]] = mapped_column(String(32), unique=True, index=True, nullable=True)  # 班级编号唯一
    description: Mapped[Optional[str]] = mapped_column(Text)

    teacher: Mapped["User"] = relationship(back_populates="classes_teaching", foreign_keys=[teacher_id])
    student_links: Mapped[List["ClassStudent"]] = relationship(back_populates="class_", passive_deletes=True)


class ClassStudent(Base):
    """班级-学生 关联表（多对多）。"""

    __tablename__ = "class_students"
    __table_args__ = (UniqueConstraint("class_id", "student_id", name="uq_class_student"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    class_id: Mapped[int] = mapped_column(
        ForeignKey("classes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True
    )

    class_: Mapped["Class"] = relationship(back_populates="student_links")
    student: Mapped["Student"] = relationship(back_populates="class_links")


class Course(Base, TimestampMixin):
    """课程：含年级、学科、章节树（JSON）。"""

    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    grade: Mapped[Optional[str]] = mapped_column(String(32))
    subject: Mapped[Optional[str]] = mapped_column(String(32))  # 学科（系统固定13门）
    teacher_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    chapter_tree: Mapped[Optional[List]] = mapped_column(JSON, default=list)  # 章节树
    description: Mapped[Optional[str]] = mapped_column(Text)

    exercises: Mapped[List["Exercise"]] = relationship(back_populates="course", passive_deletes=True)


class Exercise(Base, TimestampMixin):
    """题库：题目、选项、答案、解析、难度、知识点标签。"""

    __tablename__ = "exercises"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    course_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("courses.id", ondelete="SET NULL"), nullable=True, index=True
    )
    chapter: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)  # 章节
    type: Mapped[str] = mapped_column(String(16), default="single")  # single/multiple/judge/fill/qa
    content: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[Optional[List]] = mapped_column(JSON, default=list)  # [{key,text}]
    answer: Mapped[Optional[str]] = mapped_column(Text)
    analysis: Mapped[Optional[str]] = mapped_column(Text)
    difficulty: Mapped[str] = mapped_column(String(16), default="medium")  # easy/medium/hard
    knowledge_points: Mapped[Optional[List]] = mapped_column(JSON, default=list)

    course: Mapped[Optional["Course"]] = relationship(back_populates="exercises")
    records: Mapped[List["LearningRecord"]] = relationship(back_populates="exercise", passive_deletes=True)


class LearningRecord(Base):
    """学生答题历史：正确与否、用时。"""

    __tablename__ = "learning_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True
    )
    exercise_id: Mapped[int] = mapped_column(
        ForeignKey("exercises.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_answer: Mapped[Optional[str]] = mapped_column(Text)
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False)
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    student: Mapped["Student"] = relationship(back_populates="records")
    exercise: Mapped["Exercise"] = relationship(back_populates="records")


class WrongBook(Base):
    """错题本：学生收藏错题与错因。"""

    __tablename__ = "wrong_book"
    __table_args__ = (UniqueConstraint("student_id", "exercise_id", name="uq_wrong_book"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True
    )
    exercise_id: Mapped[int] = mapped_column(
        ForeignKey("exercises.id", ondelete="CASCADE"), nullable=False, index=True
    )
    reason: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    student: Mapped["Student"] = relationship(back_populates="wrong_books")
    exercise: Mapped["Exercise"] = relationship()


class LessonPlan(Base, TimestampMixin):
    """生成的教案记录：结构化 JSON 存于 content。"""

    __tablename__ = "lesson_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    teacher_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    grade: Mapped[str] = mapped_column(String(32))
    subject: Mapped[str] = mapped_column(String(32))
    chapter: Mapped[str] = mapped_column(String(128))
    teaching_objectives: Mapped[Optional[str]] = mapped_column(Text)
    content: Mapped[Optional[dict]] = mapped_column(JSON)  # 结构化教案 JSON
    status: Mapped[str] = mapped_column(String(16), default="generated")

    teacher: Mapped["User"] = relationship()


class KnowledgeFile(Base, TimestampMixin):
    """知识库文件记录。"""

    __tablename__ = "knowledge_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_key: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    file_type: Mapped[str] = mapped_column(String(16))          # pdf/docx/txt/md
    subject: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True)  # 所属科目
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending/indexed/failed
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[Optional[str]] = mapped_column(Text)
    uploaded_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )


class ChatSession(Base, TimestampMixin):
    """问答会话（支持多轮追问）。"""

    __tablename__ = "chat_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(128), default="新对话")
    messages: Mapped[List["ChatMessage"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class ChatMessage(Base):
    """问答消息，sources 为引用来源 JSON。"""

    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(16))  # user / assistant
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sources: Mapped[Optional[List]] = mapped_column(JSON, default=list)  # 引用来源
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    session: Mapped["ChatSession"] = relationship(back_populates="messages")


class AgentTask(Base, TimestampMixin):
    """个性化学习 Agent 任务记录，支持状态跟踪与失败重试。"""

    __tablename__ = "agent_tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    student_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), nullable=True, index=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    task_type: Mapped[str] = mapped_column(String(32), default="personalized_plan")
    input_data: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)
    output: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)
    steps: Mapped[Optional[List]] = mapped_column(JSON, default=list)  # 工具调用记录
    status: Mapped[str] = mapped_column(String(16), default="running")  # running/completed/failed
    error: Mapped[Optional[str]] = mapped_column(Text)


class StudentMessage(Base):
    """教师给学生留言。"""

    __tablename__ = "student_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True
    )
    teacher_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class SystemLog(Base):
    """系统操作日志。"""

    __tablename__ = "system_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    username: Mapped[Optional[str]] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(128), index=True)
    detail: Mapped[Optional[str]] = mapped_column(Text)
    ip: Mapped[Optional[str]] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class ClassSchedule(Base):
    """班级课表：weekday(1-7) × period(1-N)，单元格 = 科目 + 上课老师（class_schedule_teachers）。"""

    __tablename__ = "class_schedules"
    __table_args__ = (
        UniqueConstraint("class_id", "weekday", "period", name="uq_schedule_cell"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    class_id: Mapped[int] = mapped_column(
        ForeignKey("classes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    weekday: Mapped[int] = mapped_column(Integer, nullable=False)   # 1-7 周一~周日
    period: Mapped[int] = mapped_column(Integer, nullable=False)    # 第几节
    subject: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)  # 固定科目或空


class ClassScheduleTeacher(Base):
    """班级课表单元格的可代课教师：一节课可有多个可代课老师。"""

    __tablename__ = "class_schedule_teachers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    schedule_id: Mapped[int] = mapped_column(
        ForeignKey("class_schedules.id", ondelete="CASCADE"), nullable=False, index=True
    )
    teacher_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )


