"""认证接口：注册 / 登录 / 刷新 Token。"""
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.api.subject_utils import is_valid_subject
from app.core.database import get_db
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.models import Student, SystemLog, Teacher, User
from app.schemas.auth import LoginRequest, RefreshRequest, RegisterRequest
from app.schemas.common import fail, ok

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["认证"])


async def _user_brief(db: AsyncSession, user: User) -> dict:
    brief = {
        "id": user.id,
        "username": user.username,
        "full_name": user.full_name,
        "email": user.email,
        "role": user.role,
        "avatar": user.avatar,
    }
    # 教师附带工号/负责科目、学生附带学号（登录后用于展示/确认登录标识）
    if user.role == "teacher":
        teacher = (
            await db.execute(select(Teacher).where(Teacher.user_id == user.id))
        ).scalar_one_or_none()
        brief["employee_no"] = teacher.employee_no if teacher else None
        brief["subjects"] = list(teacher.subjects or []) if teacher else []
        brief["title"] = teacher.title if teacher else None
        brief["department"] = teacher.department if teacher else None
    elif user.role == "student":
        student = (
            await db.execute(select(Student).where(Student.user_id == user.id))
        ).scalar_one_or_none()
        brief["student_no"] = student.student_no if student else None
    return brief


@router.post("/register")
async def register(payload: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """注册学生 / 教师账号（管理员账号由系统初始化或管理员创建）。"""
    if payload.email:
        result = await db.execute(select(User).where(User.email == payload.email))
        if result.scalar_one_or_none() is not None:
            return fail("邮箱已被注册", code=1)

    user = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
        email=payload.email or None,
        role=payload.role,
        is_active=True,
    )
    db.add(user)
    await db.flush()

    if payload.role == "teacher":
        if payload.subject and not is_valid_subject(payload.subject):
            return fail("学科必须为系统规定科目")
        # 自动生成工号（t26xxxx）；教研组根据学科自动识别；职称由管理员后续分配
        teacher_nos = (
            await db.execute(select(Teacher.employee_no).where(Teacher.employee_no.isnot(None)))
        ).scalars().all()
        nums = [int("".join(ch for ch in (no or "") if ch.isdigit())[-4:] or 0) for no in teacher_nos]
        employee_no = f"t26{max(nums) + 1 if nums else 1:04d}"
        db.add(
            Teacher(
                user_id=user.id,
                employee_no=employee_no,
                title=None,
                department=f"{payload.subject}教研组" if payload.subject else None,
                subjects=[payload.subject] if payload.subject else [],
            )
        )
    elif payload.role == "student":
        db.add(
            Student(
                user_id=user.id,
                student_no=f"S{user.id:06d}",
                grade=payload.grade,
            )
        )
    await db.commit()
    await db.refresh(user)

    access_token = create_access_token(user.id, user.role)
    refresh_token = create_refresh_token(user.id)
    return ok(
        {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user": await _user_brief(db, user),
        },
        message="注册成功",
    )


@router.post("/login")
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    user = None
    # 学生：仅按学号登录
    student_row = (
        await db.execute(
            select(Student, User)
            .join(User, User.id == Student.user_id)
            .where(func.lower(Student.student_no) == payload.username.strip().lower())
        )
    ).one_or_none()
    if student_row is not None and verify_password(payload.password, student_row[1].password_hash):
        user = student_row[1]
    # 教师：仅按工号登录
    if user is None:
        teacher_row = (
            await db.execute(
                select(Teacher, User)
                .join(User, User.id == Teacher.user_id)
                .where(func.lower(Teacher.employee_no) == payload.username.strip().lower())
            )
        ).one_or_none()
        if teacher_row is not None and verify_password(payload.password, teacher_row[1].password_hash):
            user = teacher_row[1]
    # 管理员：按用户名登录
    if user is None:
        admin = (
            await db.execute(
                select(User).where(
                    User.username == payload.username,
                    User.role == "admin",
                )
            )
        ).scalar_one_or_none()
        if admin is not None and verify_password(payload.password, admin.password_hash):
            user = admin
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="学号/工号或密码错误")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号已被禁用")

    # 记录登录日志（工号/学号 + 姓名），供管理员端查看
    identifier = user.username
    if user.role == "teacher":
        teacher = (
            await db.execute(select(Teacher).where(Teacher.user_id == user.id))
        ).scalar_one_or_none()
        if teacher and teacher.employee_no:
            identifier = teacher.employee_no
    elif user.role == "student":
        student = (
            await db.execute(select(Student).where(Student.user_id == user.id))
        ).scalar_one_or_none()
        if student and student.student_no:
            identifier = student.student_no
    db.add(
        SystemLog(
            user_id=user.id,
            username=user.username,
            action="登录系统",
            detail=f"{identifier} {user.full_name or user.username}",
        )
    )
    await db.commit()

    access_token = create_access_token(user.id, user.role)
    refresh_token = create_refresh_token(user.id)
    return ok(
        {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user": await _user_brief(db, user),
        },
        message="登录成功",
    )


@router.post("/refresh")
async def refresh(payload: RefreshRequest, db: AsyncSession = Depends(get_db)):
    try:
        token_payload = decode_token(payload.refresh_token, expected_type="refresh")
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="刷新 Token 无效或已过期"
        ) from exc
    user = await db.get(User, int(token_payload["sub"]))
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在或已被禁用")
    return ok(
        {
            "access_token": create_access_token(user.id, user.role),
            "refresh_token": create_refresh_token(user.id),
            "token_type": "bearer",
            "user": await _user_brief(db, user),
        }
    )


@router.get("/me")
async def me(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return ok(await _user_brief(db, user))