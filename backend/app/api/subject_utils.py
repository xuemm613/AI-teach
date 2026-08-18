"""科目权限工具：固定学科列表与教师科目校验。"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Course, Teacher, User

# 系统规定学科（下拉选择，不允许自定义）
ALL_SUBJECTS = [
    "语文", "数学", "英语", "物理", "化学",
    "生物", "政治", "地理", "历史",
    "体育", "音乐", "美术", "劳动",
]


def is_valid_subject(subject: str) -> bool:
    """校验学科是否属于系统规定列表。"""
    return subject in ALL_SUBJECTS


async def teacher_subjects(db: AsyncSession, user: User) -> set:
    """返回教师负责的科目集合；非教师返回空集。"""
    if user.role != "teacher":
        return set()
    teacher = (
        await db.execute(select(Teacher).where(Teacher.user_id == user.id))
    ).scalar_one_or_none()
    subs = set(teacher.subjects or []) if teacher else set()
    if not subs:
        # 兜底：从该教师负责的课程学科推导
        rows = await db.execute(select(Course.subject).where(Course.teacher_id == user.id))
        subs = {s for s in rows.scalars().all() if s}
    return subs
