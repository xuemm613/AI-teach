"""管理后台接口：数据看板、系统日志/配置、班级/课程/题库 CRUD、学习记录。"""
import logging
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import case, delete, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.api.subject_utils import ALL_SUBJECTS, is_valid_subject
from app.core.config import settings
from app.core.database import get_db
from app.models.models import (
    Class,
    ClassSchedule,
    ClassScheduleTeacher,
    ClassStudent,
    Course,
    Exercise,
    KnowledgeFile,
    LearningRecord,
    LessonPlan,
    Student,
    SystemLog,
    Teacher,
    User,
)
from app.schemas.admin import (
    ClassCreate,
    ClassUpdate,
    CourseCreate,
    CourseUpdate,
    ExerciseCreate,
    ExerciseUpdate,
    TimetableUpdate,
    TransferRequest,
)
from app.schemas.common import fail, ok

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["管理后台"])


async def _course_id_for_subject(db: AsyncSession, subject: str) -> Optional[int]:
    """按科目查找或自动创建一门课程，返回课程 id。"""
    course = (
        await db.execute(select(Course).where(Course.subject == subject).limit(1))
    ).scalar_one_or_none()
    if course is None:
        course = Course(name=f"{subject}课程", subject=subject, description="按科目自动生成的课程")
        db.add(course)
        await db.flush()
    return course.id


def _grade_order_expr(col):
    """年级顺序：一年级~九年级（含初一/初二/初三、高一/高二/高三），未知年级排最后。"""
    return case(
        (col == "一年级", 1), (col == "二年级", 2), (col == "三年级", 3),
        (col == "四年级", 4), (col == "五年级", 5), (col == "六年级", 6),
        (col == "七年级", 7), (col == "八年级", 8), (col == "九年级", 9),
        (col == "初一", 7), (col == "初二", 8), (col == "初三", 9),
        (col == "高一", 10), (col == "高二", 11), (col == "高三", 12),
        else_=99,
    )

ADMIN = require_roles("admin")
SUBJ_MSG = "学科必须为系统规定科目：语文、数学、英语、物理、化学、生物、政治、地理、历史、体育、音乐、美术、劳动"
# 题目管理仅管理员负责（教师不负责出题）


# ------------------------- 数据看板 -------------------------
@router.get("/dashboard/stats")
async def dashboard_stats(
    user: User = Depends(ADMIN),
    db: AsyncSession = Depends(get_db),
):
    user_count = (await db.execute(select(func.count(User.id)))).scalar() or 0
    teacher_count = (await db.execute(select(func.count(Teacher.id)))).scalar() or 0
    student_count = (await db.execute(select(func.count(Student.id)))).scalar() or 0
    admin_count = (
        await db.execute(select(func.count(User.id)).where(User.role == "admin"))
    ).scalar() or 0
    course_count = (await db.execute(select(func.count(Course.id)))).scalar() or 0
    exercise_count = (await db.execute(select(func.count(Exercise.id)))).scalar() or 0
    knowledge_file_count = (await db.execute(select(func.count(KnowledgeFile.id)))).scalar() or 0
    lesson_plan_count = (await db.execute(select(func.count(LessonPlan.id)))).scalar() or 0
    record_count = (await db.execute(select(func.count(LearningRecord.id)))).scalar() or 0
    correct_count = (
        await db.execute(
            select(func.count(LearningRecord.id)).where(LearningRecord.is_correct.is_(True))
        )
    ).scalar() or 0

    today = date.today()
    active_users_today = (
        await db.execute(
            select(func.count(func.distinct(SystemLog.user_id))).where(
                SystemLog.user_id.isnot(None),
                func.date(SystemLog.created_at) == today,
            )
        )
    ).scalar() or 0

    daily_rows = (
        await db.execute(
            select(func.date(LearningRecord.created_at), func.count(LearningRecord.id))
            .group_by(func.date(LearningRecord.created_at))
            .order_by(func.date(LearningRecord.created_at))
            .limit(30)
        )
    ).all()
    daily_answers = [{"date": str(d), "count": c} for d, c in daily_rows]

    week_ago = datetime.now() - timedelta(days=7)
    active_rows = (
        await db.execute(
            select(func.date(SystemLog.created_at), func.count(func.distinct(SystemLog.user_id)))
            .where(SystemLog.created_at >= week_ago)
            .group_by(func.date(SystemLog.created_at))
            .order_by(func.date(SystemLog.created_at))
        )
    ).all()
    daily_active_users = [{"date": str(d), "count": c} for d, c in active_rows]

    course_accuracy_rows = (
        await db.execute(
            select(
                Course.name,
                func.count(LearningRecord.id),
                func.sum(case((LearningRecord.is_correct.is_(True), 1), else_=0)),
            )
            .join(Exercise, Exercise.id == LearningRecord.exercise_id)
            .join(Course, Course.id == Exercise.course_id)
            .group_by(Course.id, Course.name)
        )
    ).all()
    course_accuracy = [
        {
            "course": name,
            "count": count,
            "correct": corr,
            "accuracy": round(corr / count, 4) if count else 0,
        }
        for name, count, corr in course_accuracy_rows
    ]

    recent = (
        await db.execute(
            select(LearningRecord, Exercise)
            .join(Exercise, Exercise.id == LearningRecord.exercise_id)
            .order_by(desc(LearningRecord.created_at))
            .limit(10)
        )
    ).all()
    recent_records = [
        {
            "id": rec.id,
            "exercise_id": rec.exercise_id,
            "content": ex.content[:60],
            "is_correct": rec.is_correct,
            "created_at": rec.created_at.isoformat() if rec.created_at else None,
        }
        for rec, ex in recent
    ]

    return ok(
        {
            "user_count": user_count,
            "teacher_count": teacher_count,
            "student_count": student_count,
            "admin_count": admin_count,
            "course_count": course_count,
            "exercise_count": exercise_count,
            "knowledge_file_count": knowledge_file_count,
            "lesson_plan_count": lesson_plan_count,
            "record_count": record_count,
            "accuracy": round(correct_count / record_count, 4) if record_count else 0,
            "active_users_today": active_users_today,
            "daily_answers": daily_answers,
            "daily_active_users": daily_active_users,
            "course_accuracy": course_accuracy,
            "recent_records": recent_records,
        }
    )


# ------------------------- 登录记录 -------------------------
@router.get("/login-logs")
async def login_logs(
    user: User = Depends(ADMIN),
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    size: int = Query(30, ge=1, le=200),
):
    """登录记录：何时（年-月-日 时:分）哪位用户（工号/学号 + 姓名）登录系统。"""
    stmt = select(SystemLog).where(SystemLog.action == "登录系统")
    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar() or 0
    result = await db.execute(
        stmt.order_by(desc(SystemLog.created_at)).offset((page - 1) * size).limit(size)
    )
    rows = result.scalars().all()
    return ok(
        {
            "total": total,
            "items": [
                {
                    "id": log.id,
                    "username": log.username,
                    "detail": log.detail,
                    "created_at": log.created_at.isoformat() if log.created_at else None,
                }
                for log in rows
            ],
        }
    )


# ------------------------- 班级 CRUD -------------------------
@router.get("/classes")
async def list_classes(
    user: User = Depends(ADMIN),
    db: AsyncSession = Depends(get_db),
    keyword: Optional[str] = Query(None),
):
    stmt = select(Class).order_by(_grade_order_expr(Class.grade), Class.class_no)
    if keyword:
        stmt = stmt.where(Class.name.ilike(f"%{keyword}%"))
    result = await db.execute(stmt)
    classes = result.scalars().all()
    items = []
    for cls in classes:
        count = (
            await db.execute(
                select(func.count(ClassStudent.id))
                .join(Student, Student.id == ClassStudent.student_id)
                .where(ClassStudent.class_id == cls.id)
            )
        ).scalar() or 0
        items.append(
            {
                "id": cls.id,
                "name": cls.name,
                "class_no": cls.class_no,
                "teacher_id": cls.teacher_id,
                "grade": cls.grade,
                "description": cls.description,
                "student_count": count,
            }
        )
    return ok(items)


@router.post("/classes")
async def create_class(
    payload: ClassCreate,
    user: User = Depends(ADMIN),
    db: AsyncSession = Depends(get_db),
):
    if await db.get(User, payload.teacher_id) is None:
        return fail("教师不存在")
    # 班级编号唯一
    if payload.class_no:
        dup = await db.execute(select(Class).where(Class.class_no == payload.class_no))
        if dup.scalar_one_or_none() is not None:
            return fail("该班级编号已被其他班级使用")
    # 班级名称唯一（一个学校只有一个同名班级）
    dup_name = await db.execute(select(Class).where(Class.name == payload.name))
    if dup_name.scalar_one_or_none() is not None:
        return fail(f"班级名称「{payload.name}」已存在，请使用其他名称")
    # 一位老师只能担任一个班级的班主任
    dup_teacher = await db.execute(select(Class).where(Class.teacher_id == payload.teacher_id))
    if dup_teacher.scalar_one_or_none() is not None:
        t_user = await db.get(User, payload.teacher_id)
        tname = t_user.full_name or t_user.username if t_user else payload.teacher_id
        return fail(f"教师「{tname}」已是其他班级的班主任，一位老师只能担任一个班级的班主任")
    cls = Class(
        name=payload.name,
        teacher_id=payload.teacher_id,
        grade=payload.grade,
        class_no=payload.class_no,
        description=payload.description,
    )
    db.add(cls)
    await db.commit()
    await db.refresh(cls)
    return ok({"id": cls.id, **payload.model_dump()}, message="班级创建成功")


@router.put("/classes/{class_id}")
async def update_class(
    class_id: int,
    payload: ClassUpdate,
    user: User = Depends(ADMIN),
    db: AsyncSession = Depends(get_db),
):
    cls = await db.get(Class, class_id)
    if cls is None:
        raise HTTPException(status_code=404, detail="班级不存在")
    # 班级编号唯一（排除当前班级）
    if payload.class_no is not None:
        dup = await db.execute(
            select(Class).where(
                Class.class_no == payload.class_no,
                Class.id != class_id,
            )
        )
        if dup.scalar_one_or_none() is not None:
            return fail("该班级编号已被其他班级使用")
    # 班级名称唯一（排除当前班级）
    if payload.name is not None:
        dup_name = await db.execute(
            select(Class).where(
                Class.name == payload.name,
                Class.id != class_id,
            )
        )
        if dup_name.scalar_one_or_none() is not None:
            return fail(f"班级名称「{payload.name}」已存在，请使用其他名称")
    # 一位老师只能担任一个班级的班主任（排除当前班级）
    if payload.teacher_id is not None:
        dup_teacher = await db.execute(
            select(Class).where(
                Class.teacher_id == payload.teacher_id,
                Class.id != class_id,
            )
        )
        if dup_teacher.scalar_one_or_none() is not None:
            t_user = await db.get(User, payload.teacher_id)
            tname = t_user.full_name or t_user.username if t_user else payload.teacher_id
            return fail(f"教师「{tname}」已是其他班级的班主任，一位老师只能担任一个班级的班主任")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(cls, field, value)
    await db.commit()
    return ok(None, message="更新成功")


@router.delete("/classes/{class_id}")
async def delete_class(
    class_id: int,
    user: User = Depends(ADMIN),
    db: AsyncSession = Depends(get_db),
):
    cls = await db.get(Class, class_id)
    if cls is None:
        raise HTTPException(status_code=404, detail="班级不存在")
    # 先删除班级-学生关联（兼容未配置外键级联的情况）
    await db.execute(delete(ClassStudent).where(ClassStudent.class_id == class_id))
    await db.delete(cls)
    await db.commit()
    return ok(None, message="删除成功")


@router.get("/classes/{class_id}/timetable")
async def class_timetable(
    class_id: int,
    user: User = Depends(ADMIN),
    db: AsyncSession = Depends(get_db),
):
    """获取班级课表：cells[节次][星期] = {科目, 上课老师}。"""
    cls = await db.get(Class, class_id)
    if cls is None:
        raise HTTPException(status_code=404, detail="班级不存在")
    rows = (
        await db.execute(select(ClassSchedule).where(ClassSchedule.class_id == class_id))
    ).scalars().all()
    periods = max([r.period for r in rows] + [8])
    weekdays = 5
    # 读取每个课表单元格的上课老师（单值）
    schedule_ids = [r.id for r in rows]
    teacher_map: dict = {}
    if schedule_ids:
        links = (
            await db.execute(
                select(ClassScheduleTeacher).where(
                    ClassScheduleTeacher.schedule_id.in_(schedule_ids)
                )
            )
        ).scalars().all()
        for link in links:
            teacher_map[link.schedule_id] = link.teacher_user_id
    grid = []
    by_pos = {(r.weekday, r.period): r for r in rows}
    for p in range(1, periods + 1):
        row_cells = []
        for w in range(1, weekdays + 1):
            r = by_pos.get((w, p))
            if r:
                row_cells.append(
                    {
                        "subject": r.subject or "",
                        "teacher_user_id": teacher_map.get(r.id),
                    }
                )
            else:
                row_cells.append({"subject": "", "teacher_user_id": None})
        grid.append(row_cells)
    return ok({"class_id": class_id, "periods": periods, "weekdays": weekdays, "cells": grid})


@router.put("/classes/{class_id}/timetable")
async def save_timetable(
    class_id: int,
    payload: TimetableUpdate,
    user: User = Depends(ADMIN),
    db: AsyncSession = Depends(get_db),
):
    """保存班级课表（整体替换）：每节课设置科目 + 上课老师（单值）。"""
    cls = await db.get(Class, class_id)
    if cls is None:
        raise HTTPException(status_code=404, detail="班级不存在")
    week_names = ["", "周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    # 校验科目与上课老师
    for p_idx, row in enumerate(payload.cells[: payload.periods], start=1):
        for w_idx, cell in enumerate(row[: payload.weekdays], start=1):
            if cell.subject:
                if not is_valid_subject(cell.subject):
                    return fail(SUBJ_MSG)
                if not cell.teacher_user_id:
                    return fail(f"{week_names[w_idx]}第{p_idx}节：请为该课选择上课老师")
                teacher_user = await db.get(User, cell.teacher_user_id)
                if teacher_user is None or teacher_user.role != "teacher":
                    return fail(f"{week_names[w_idx]}第{p_idx}节：上课老师不存在或不是教师")
                teacher_ext = (
                    await db.execute(select(Teacher).where(Teacher.user_id == cell.teacher_user_id))
                ).scalar_one_or_none()
                if teacher_ext is None or cell.subject not in (teacher_ext.subjects or []):
                    tname = teacher_user.full_name or teacher_user.username
                    return fail(f"{week_names[w_idx]}第{p_idx}节：老师「{tname}」不负责「{cell.subject}」学科，不能安排其上课")
    # 跨班同时段冲突校验：同一老师不能在多个班级同一时段上课
    for p_idx, row in enumerate(payload.cells[: payload.periods], start=1):
        for w_idx, cell in enumerate(row[: payload.weekdays], start=1):
            tid = cell.teacher_user_id
            if not tid:
                continue
            conflict = (
                await db.execute(
                    select(ClassSchedule, Class)
                    .join(ClassScheduleTeacher, ClassScheduleTeacher.schedule_id == ClassSchedule.id)
                    .join(Class, Class.id == ClassSchedule.class_id)
                    .where(
                        ClassSchedule.class_id != class_id,
                        ClassSchedule.weekday == w_idx,
                        ClassSchedule.period == p_idx,
                        ClassScheduleTeacher.teacher_user_id == tid,
                        ClassSchedule.subject.isnot(None),
                        ClassSchedule.subject != "",
                    )
                )
            ).one_or_none()
            if conflict is not None:
                teacher_user = await db.get(User, tid)
                tname = teacher_user.full_name or teacher_user.username if teacher_user else tid
                return fail(
                    f"{week_names[w_idx]}第{p_idx}节：老师「{tname}」已在班级「{conflict[1].name}」上课，"
                    f"同一时间不能上两个班的课，请更换上课老师"
                )
    # 删除旧课表（含上课老师关联）
    olds = (
        await db.execute(select(ClassSchedule).where(ClassSchedule.class_id == class_id))
    ).scalars().all()
    old_ids = [o.id for o in olds]
    if old_ids:
        await db.execute(
            delete(ClassScheduleTeacher).where(
                ClassScheduleTeacher.schedule_id.in_(old_ids)
            )
        )
    for o in olds:
        await db.delete(o)
    await db.flush()
    # 写入新课表
    for p_idx, row in enumerate(payload.cells[: payload.periods], start=1):
        for w_idx, cell in enumerate(row[: payload.weekdays], start=1):
            if cell.subject:
                schedule = ClassSchedule(
                    class_id=class_id,
                    weekday=w_idx,
                    period=p_idx,
                    subject=cell.subject,
                )
                db.add(schedule)
                await db.flush()
                if cell.teacher_user_id:
                    db.add(
                        ClassScheduleTeacher(
                            schedule_id=schedule.id, teacher_user_id=cell.teacher_user_id
                        )
                    )
    await db.commit()
    return ok(None, message="课表已保存")


@router.get("/timetable/overview")
async def timetable_overview(
    user: User = Depends(ADMIN),
    db: AsyncSession = Depends(get_db),
):
    """返回全部班级的课表总览，供前端选课时实时检测同一老师同一时段冲突。"""
    rows = (
        await db.execute(
            select(ClassSchedule, Class)
            .join(Class, Class.id == ClassSchedule.class_id)
            .order_by(ClassSchedule.class_id, ClassSchedule.weekday, ClassSchedule.period)
        )
    ).all()
    schedule_ids = [cs.id for cs, _ in rows]
    teacher_map: dict = {}
    if schedule_ids:
        links = (
            await db.execute(
                select(ClassScheduleTeacher).where(
                    ClassScheduleTeacher.schedule_id.in_(schedule_ids)
                )
            )
        ).scalars().all()
        for link in links:
            teacher_map[link.schedule_id] = link.teacher_user_id
    return ok(
        [
            {
                "class_id": cls.id,
                "class_name": cls.name,
                "weekday": cs.weekday,
                "period": cs.period,
                "subject": cs.subject,
                "teacher_user_id": teacher_map.get(cs.id),
            }
            for cs, cls in rows
        ]
    )


@router.get("/classes/{class_id}/students")
async def class_students(
    class_id: int,
    user: User = Depends(ADMIN),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Student, User)
        .join(ClassStudent, ClassStudent.student_id == Student.id)
        .join(User, User.id == Student.user_id)
        .where(ClassStudent.class_id == class_id)
    )
    rows = result.all()
    return ok(
        [
            {
                "student_id": s.id,
                "user_id": u.id,
                "username": u.username,
                "full_name": u.full_name,
                "student_no": s.student_no,
                "grade": s.grade,
            }
            for s, u in rows
        ]
    )


@router.delete("/classes/{class_id}/students/{student_id}")
async def remove_class_student(
    class_id: int,
    student_id: int,
    user: User = Depends(ADMIN),
    db: AsyncSession = Depends(get_db),
):
    """将学生移出班级（仅删除班级-学生关联，不影响学生账号）。"""
    cls = await db.get(Class, class_id)
    if cls is None:
        raise HTTPException(status_code=404, detail="班级不存在")
    if await db.get(Student, student_id) is None:
        raise HTTPException(status_code=404, detail="学生不存在")
    link = await db.execute(
        select(ClassStudent).where(
            ClassStudent.class_id == class_id,
            ClassStudent.student_id == student_id,
        )
    )
    row = link.scalar_one_or_none()
    if row is None:
        return fail("该学生不在该班级中")
    await db.delete(row)
    await db.commit()
    return ok(None, message="已将该学生移出班级")


@router.post("/classes/{class_id}/students")
async def add_class_students(
    class_id: int,
    student_ids: List[int],
    user: User = Depends(ADMIN),
    db: AsyncSession = Depends(get_db),
):
    cls = await db.get(Class, class_id)
    if cls is None:
        raise HTTPException(status_code=404, detail="班级不存在")
    added = 0
    for sid in student_ids:
        student = await db.get(Student, sid)
        if student is None:
            continue
        # 一名学生只能在一个班级
        other = (
            await db.execute(
                select(Class)
                .join(ClassStudent, ClassStudent.class_id == Class.id)
                .where(
                    ClassStudent.student_id == sid,
                    ClassStudent.class_id != class_id,
                )
            )
        ).scalar_one_or_none()
        if other is not None:
            s_user = await db.get(User, student.user_id)
            sname = s_user.full_name or s_user.username if s_user else sid
            return fail(f"学生「{sname}」已在班级「{other.name}」中，请先移出或使用转班后再加入")
        # 学生年级需与班级年级一致
        if student.grade and cls.grade and student.grade != cls.grade:
            s_user = await db.get(User, student.user_id)
            sname = s_user.full_name or s_user.username if s_user else sid
            return fail(
                f"学生「{sname}」的年级（{student.grade}）与班级「{cls.name}」的年级（{cls.grade}）不一致，不能加入"
            )
        exists = await db.execute(
            select(ClassStudent).where(
                ClassStudent.class_id == class_id, ClassStudent.student_id == sid
            )
        )
        if exists.scalar_one_or_none() is None:
            db.add(ClassStudent(class_id=class_id, student_id=sid))
            added += 1
    await db.commit()
    return ok({"added": added}, message=f"已添加 {added} 名学生")


@router.post("/students/{student_id}/transfer")
async def transfer_student(
    student_id: int,
    payload: TransferRequest,
    user: User = Depends(ADMIN),
    db: AsyncSession = Depends(get_db),
):
    """将学生从当前班级转移到目标班级（仅限同年级）。"""
    student = await db.get(Student, student_id)
    if student is None:
        return fail("学生不存在")
    target_cls = await db.get(Class, payload.to_class_id)
    if target_cls is None:
        return fail("目标班级不存在")
    # 转班只能在同年级之间进行，保持学生年级与班级年级一致
    if student.grade and target_cls.grade and student.grade != target_cls.grade:
        return fail(
            f"学生当前年级（{student.grade}）与目标班级「{target_cls.name}」的年级（{target_cls.grade}）不一致，"
            f"只能在同年级班级之间转班"
        )
    links = (
        await db.execute(select(ClassStudent).where(ClassStudent.student_id == student_id))
    ).scalars().all()
    for link in links:
        if link.class_id != payload.to_class_id:
            await db.delete(link)
    exists = await db.execute(
        select(ClassStudent).where(
            ClassStudent.student_id == student_id,
            ClassStudent.class_id == payload.to_class_id,
        )
    )
    if exists.scalar_one_or_none() is None:
        db.add(ClassStudent(class_id=payload.to_class_id, student_id=student_id))
    await db.commit()
    return ok(None, message="学生已转移班级")

# ------------------------- 课程 CRUD -------------------------
@router.get("/courses")
async def list_courses(
    user: User = Depends(ADMIN),
    db: AsyncSession = Depends(get_db),
    grade: Optional[str] = Query(None),
    subject: Optional[str] = Query(None),
):
    stmt = select(Course).order_by(Course.id)
    if grade:
        stmt = stmt.where(Course.grade == grade)
    if subject:
        stmt = stmt.where(Course.subject == subject)
    result = await db.execute(stmt)
    courses = result.scalars().all()
    return ok(
        [
            {
                "id": c.id,
                "name": c.name,
                "grade": c.grade,
                "subject": c.subject,
                "teacher_id": c.teacher_id,
                "chapter_tree": c.chapter_tree or [],
                "description": c.description,
            }
            for c in courses
        ]
    )


@router.post("/courses")
async def create_course(
    payload: CourseCreate,
    user: User = Depends(ADMIN),
    db: AsyncSession = Depends(get_db),
):
    if payload.subject and not is_valid_subject(payload.subject):
        return fail(SUBJ_MSG)
    course = Course(**payload.model_dump())
    db.add(course)
    await db.commit()
    await db.refresh(course)
    return ok({"id": course.id, **payload.model_dump()}, message="课程创建成功")


@router.put("/courses/{course_id}")
async def update_course(
    course_id: int,
    payload: CourseUpdate,
    user: User = Depends(ADMIN),
    db: AsyncSession = Depends(get_db),
):
    course = await db.get(Course, course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="课程不存在")
    if payload.subject and not is_valid_subject(payload.subject):
        return fail(SUBJ_MSG)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(course, field, value)
    await db.commit()
    return ok(None, message="更新成功")


@router.delete("/courses/{course_id}")
async def delete_course(
    course_id: int,
    user: User = Depends(ADMIN),
    db: AsyncSession = Depends(get_db),
):
    course = await db.get(Course, course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="课程不存在")
    await db.delete(course)
    await db.commit()
    return ok(None, message="删除成功")


# ------------------------- 题库 CRUD（管理员 + 教师） -------------------------
@router.get("/exercises")
async def list_exercises(
    user: User = Depends(ADMIN),
    db: AsyncSession = Depends(get_db),
    course_id: Optional[int] = Query(None),
    chapter: Optional[str] = Query(None),
    difficulty: Optional[str] = Query(None),
    knowledge_point: Optional[str] = Query(None),
    subject: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
):
    stmt = select(Exercise)
    if course_id:
        stmt = stmt.where(Exercise.course_id == course_id)
    if chapter:
        stmt = stmt.where(Exercise.chapter == chapter)
    if difficulty:
        stmt = stmt.where(Exercise.difficulty == difficulty)
    if knowledge_point:
        stmt = stmt.where(Exercise.knowledge_points.contains([knowledge_point]))
    if subject:
        subj_course_ids = (
            await db.execute(select(Course.id).where(Course.subject == subject))
        ).scalars().all()
        stmt = stmt.where(Exercise.course_id.in_(list(subj_course_ids)))
    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar() or 0
    # 题库列表只展示最近 100 条；其余内容仍保存在数据库，可通过筛选查询
    total = min(total, 100)
    result = await db.execute(stmt.order_by(Exercise.id.desc()).offset((page - 1) * size).limit(size))
    exercises = result.scalars().all()
    # 科目信息从关联课程获取（课程未关联时为 None）
    course_ids = {e.course_id for e in exercises if e.course_id}
    course_subjects = {}
    if course_ids:
        courses = (
            await db.execute(select(Course).where(Course.id.in_(list(course_ids))))
        ).scalars().all()
        course_subjects = {c.id: c.subject for c in courses}
    return ok(
        {
            "total": total,
            "items": [
                {
                    "id": e.id,
                    "course_id": e.course_id,
                    "subject": course_subjects.get(e.course_id),
                    "chapter": e.chapter,
                    "type": e.type,
                    "content": e.content,
                    "options": e.options or [],
                    "answer": e.answer,
                    "analysis": e.analysis,
                    "difficulty": e.difficulty,
                    "knowledge_points": e.knowledge_points or [],
                }
                for e in exercises
            ],
        }
    )


@router.post("/exercises")
async def create_exercise(
    payload: ExerciseCreate,
    user: User = Depends(ADMIN),
    db: AsyncSession = Depends(get_db),
):
    data = payload.model_dump()
    # 按科目自动关联课程，保证题库表格中“科目”正确显示
    if data.get("subject"):
        if not is_valid_subject(data["subject"]):
            return fail(SUBJ_MSG)
        data["course_id"] = await _course_id_for_subject(db, data["subject"])
    data.pop("subject", None)
    exercise = Exercise(**data)
    db.add(exercise)
    await db.commit()
    await db.refresh(exercise)
    return ok({"id": exercise.id, **data}, message="题目创建成功")


@router.put("/exercises/{exercise_id}")
async def update_exercise(
    exercise_id: int,
    payload: ExerciseUpdate,
    user: User = Depends(ADMIN),
    db: AsyncSession = Depends(get_db),
):
    exercise = await db.get(Exercise, exercise_id)
    if exercise is None:
        raise HTTPException(status_code=404, detail="题目不存在")
    data = payload.model_dump(exclude_unset=True)
    # 编辑科目时自动重新关联该科目的课程，保证表格中“科目”更新
    if "subject" in data:
        if data["subject"] and not is_valid_subject(data["subject"]):
            return fail(SUBJ_MSG)
        data["course_id"] = await _course_id_for_subject(db, data["subject"]) if data["subject"] else None
        data.pop("subject", None)
    for field, value in data.items():
        setattr(exercise, field, value)
    await db.commit()
    return ok(None, message="更新成功")


@router.delete("/exercises/{exercise_id}")
async def delete_exercise(
    exercise_id: int,
    user: User = Depends(ADMIN),
    db: AsyncSession = Depends(get_db),
):
    exercise = await db.get(Exercise, exercise_id)
    if exercise is None:
        raise HTTPException(status_code=404, detail="题目不存在")
    await db.delete(exercise)
    await db.commit()
    return ok(None, message="删除成功")


# ------------------------- 学习记录 -------------------------
@router.get("/teachers")
async def list_teachers(user: User = Depends(ADMIN), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Teacher, User).join(User, User.id == Teacher.user_id).order_by(Teacher.employee_no)
    )
    return ok(
        [
            {
                "id": t.id,
                "user_id": u.id,
                "username": u.username,
                "full_name": u.full_name,
                "email": u.email,
                "employee_no": t.employee_no,
                "subjects": list(t.subjects or []),
                "title": t.title,
                "department": t.department,
                "is_active": u.is_active,
            }
            for t, u in result.all()
        ]
    )


@router.get("/students")
async def list_students(user: User = Depends(ADMIN), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Student, User).join(User, User.id == Student.user_id).order_by(_grade_order_expr(Student.grade), Student.student_no)
    )
    items = []
    for s, u in result.all():
        class_links = (
            await db.execute(
                select(Class)
                .join(ClassStudent, ClassStudent.class_id == Class.id)
                .where(ClassStudent.student_id == s.id)
            )
        ).scalars().all()
        items.append(
            {
                "id": s.id,
                "user_id": u.id,
                "username": u.username,
                "full_name": u.full_name,
                "student_no": s.student_no,
                "grade": s.grade,
                "is_active": u.is_active,
                "classes": [c.name for c in class_links],
                "class_ids": [c.id for c in class_links],
            }
        )
    return ok(items)