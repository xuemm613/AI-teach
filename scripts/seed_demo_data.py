"""示例/测试数据填充脚本（幂等，可重复执行）。

运行方式（需后端虚拟环境 + 已配置 backend/.env，MySQL 已启动）：
    cd backend
    python ../scripts/seed_demo_data.py

写入内容：
  1. 补「初中数学（七年级）」课程，并把无课程的数学题关联上
  2. 学习记录（错落分布在近 30 天，用于统计/学情分析展示）
  3. 错题本
  4. 教案（teacher1 两条，用于「智能备课-生成历史」展示）
  5. 知识库文件（teacher1 两条，用于「知识库-文件列表」展示；仅占位，无真实向量分块）
  6. 5 个班级的课表（每个班的数学课分散在不同节次，避免教师「今日安排」全在同一节）
"""
import asyncio
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# 定位 backend 目录，确保 app 包与 .env 能被加载（无论从哪个目录运行）
_BACKEND = Path(__file__).resolve().parent.parent / "backend"
os.chdir(_BACKEND)
sys.path.insert(0, str(_BACKEND))

from sqlalchemy import delete, func, select  # noqa: E402

from app.core.database import async_session_factory, init_db  # noqa: E402
from app.models.models import (  # noqa: E402
    Class,
    ClassSchedule,
    ClassScheduleTeacher,
    Course,
    Exercise,
    KnowledgeFile,
    LearningRecord,
    LessonPlan,
    Student,
    User,
    WrongBook,
)

OTHERS = ["语文", "英语", "物理"]
TEACHER_BY_SUBJECT = {"数学": "teacher1", "语文": "wang", "英语": "li", "物理": "zhao"}


def subject_for(class_index: int, period: int) -> str:
    """第 class_index 个班的数学课排在第 class_index+1 节，其余节次轮换填语文/英语/物理。"""
    if period == class_index + 1:
        return "数学"
    non_math = [p for p in range(1, 6) if p != class_index + 1]
    return OTHERS[non_math.index(period) % 3]


async def seed() -> None:
    await init_db()
    async with async_session_factory() as db:
        # 1. 补数学课程 + 关联孤儿题目
        math = (await db.execute(select(Course).where(Course.subject == "数学"))).scalars().all()
        if not math:
            math = Course(
                name="初中数学（七年级）",
                grade="七年级",
                subject="数学",
                chapter_tree=[
                    {"chapter": "第一章 有理数", "sections": ["1.1 正数和负数", "1.2 有理数"]},
                    {"chapter": "第二章 整式的加减", "sections": ["2.1 整式", "2.2 整式的加减"]},
                ],
                description="七年级上册数学示例课程",
            )
            db.add(math)
            await db.flush()
        else:
            math = math[0]
        for ex in (await db.execute(select(Exercise).where(Exercise.course_id.is_(None)))).scalars().all():
            ex.course_id = math.id

        students = (await db.execute(select(Student))).scalars().all()
        exercises = (await db.execute(select(Exercise))).scalars().all()

        # 2. 学习记录（幂等）
        if ((await db.execute(select(func.count(LearningRecord.id)))).scalar() or 0) == 0 and students and exercises:
            now = datetime.now()
            for s in students:
                for e in exercises:
                    if (s.id + e.id) % 5 == 0:
                        continue
                    correct = (s.id + e.id) % 3 != 0
                    db.add(
                        LearningRecord(
                            student_id=s.id,
                            exercise_id=e.id,
                            user_answer=e.answer if correct else "X",
                            is_correct=correct,
                            duration_seconds=15 + (s.id * 7 + e.id * 11) % 75,
                            created_at=now - timedelta(days=(s.id * 3 + e.id * 5) % 30),
                        )
                    )

        # 3. 错题本（幂等）
        if ((await db.execute(select(func.count(WrongBook.id)))).scalar() or 0) == 0 and students and exercises:
            for s in students[:6]:
                for e in exercises:
                    if (s.id + e.id) % 3 == 0:
                        db.add(WrongBook(student_id=s.id, exercise_id=e.id, reason="知识点掌握不牢固"))
                        break

        # 4. 教案（幂等）
        if ((await db.execute(select(func.count(LessonPlan.id)))).scalar() or 0) == 0:
            t1 = (await db.execute(select(User).where(User.username == "teacher1"))).scalar_one()
            for ch in ["第一章 有理数", "第二章 整式的加减"]:
                db.add(
                    LessonPlan(
                        teacher_id=t1.id,
                        grade="七年级",
                        subject="数学",
                        chapter=ch,
                        teaching_objectives="掌握本章基本概念与解题方法",
                        content={
                            "teaching_objectives": ["理解基本概念", "掌握核心公式", "能独立解题"],
                            "introduction": "通过生活实例引入本章内容",
                            "outline": ["知识点讲解", "例题演示", "课堂练习"],
                            "interactive_questions": [{"question": "你能举一个生活中的例子吗？", "answer": "略"}],
                            "board_design": "板书：核心公式与例题",
                            "layered_exercises": {"basic": ["基础练习一"], "medium": ["提高练习一"], "advanced": ["拓展练习一"]},
                        },
                        status="generated",
                    )
                )

        # 5. 知识库文件（幂等；仅占位记录，无真实向量分块，RAG 问答不可用）
        if ((await db.execute(select(func.count(KnowledgeFile.id)))).scalar() or 0) == 0:
            t1 = (await db.execute(select(User).where(User.username == "teacher1"))).scalar_one()
            for i, (fn, ft) in enumerate([("有理数知识点.md", "md"), ("一元一次方程讲义.txt", "txt")]):
                db.add(
                    KnowledgeFile(
                        filename=fn,
                        file_key=f"demo_seed_{i}",
                        file_type=ft,
                        subject="数学",
                        file_path=f"./uploads/{fn}",
                        file_size=2048,
                        status="indexed",
                        chunk_count=3,
                        uploaded_by=t1.id,
                    )
                )

        # 6. 课表（清空重建，幂等）
        teacher_map = {
            uname: (await db.execute(select(User).where(User.username == uname))).scalar_one().id
            for uname in ["teacher1", "wang", "li", "zhao"]
        }
        await db.execute(delete(ClassScheduleTeacher))
        await db.execute(delete(ClassSchedule))
        classes = (await db.execute(select(Class).order_by(Class.id))).scalars().all()
        for i, c in enumerate(classes):
            for wd in range(1, 6):  # 周一~周五
                for p in range(1, 6):  # 每天 5 节
                    subj = subject_for(i, p)
                    sch = ClassSchedule(class_id=c.id, weekday=wd, period=p, subject=subj)
                    db.add(sch)
                    await db.flush()
                    db.add(ClassScheduleTeacher(schedule_id=sch.id, teacher_user_id=teacher_map[TEACHER_BY_SUBJECT[subj]]))

        await db.commit()
        print("SEED_DEMO_DATA_DONE")


if __name__ == "__main__":
    asyncio.run(seed())
