"""个性化学习 Agent 接口。"""
import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.core.llm import llm_client
from app.models.models import (
    AgentTask,
    Course,
    Exercise,
    LearningRecord,
    Student,
    User,
    WrongBook,
)
from app.schemas.common import fail, ok
from app.schemas.tutor import (
    AnalyzeErrorRequest,
    ExerciseGenRequest,
    SqlQueryRequest,
)
from app.services.agent_service import TutorTools
from app.utils.prompt_templates import EXERCISE_GENERATION_PROMPT, STUDENT_ANALYSIS_PROMPT

router = APIRouter(prefix="/tutor", tags=["个性化辅导"])


def _gen_norm(text: str) -> str:
    """内容归一化哈希（去空白/转小写），用于判重。"""
    from app.services.text import norm_text
    return norm_text(text)


def task_to_dict(task: AgentTask) -> dict:
    return {
        "id": task.id,
        "task_type": task.task_type,
        "input_data": task.input_data,
        "output": task.output,
        "steps": task.steps or [],
        "status": task.status,
        "error": task.error,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "updated_at": task.updated_at.isoformat() if task.updated_at else None,
    }


@router.post("/analyze-error")
async def analyze_error(
    payload: AnalyzeErrorRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """错因分析：题目 + 学生答案 + 正确答案 -> 错因与建议（练习答错时自动弹出）。"""
    tools = TutorTools(db)
    result = await tools.analyze_error(
        payload.question, payload.user_answer, payload.correct_answer
    )
    return ok(json.loads(result), message="错因分析完成")


@router.get("/my-analysis/latest")
async def my_analysis_latest(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """返回最近一次已完成的个性化辅导方案（不重新生成，进入页面直接展示）。"""
    if user.role != "student":
        return fail("仅学生可查看")
    student = (
        await db.execute(select(Student).where(Student.user_id == user.id))
    ).scalar_one_or_none()
    if student is None:
        return fail("学生资料不存在")
    task = (
        await db.execute(
            select(AgentTask)
            .where(
                AgentTask.student_id == student.id,
                AgentTask.task_type == "personalized_plan",
                AgentTask.status == "completed",
            )
            .order_by(AgentTask.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    return ok(task_to_dict(task) if task else None)


@router.post("/my-analysis")
async def my_analysis(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    subject: Optional[str] = Query(None, description="仅基于该科目生成方案"),
):
    """学生个人学情分析：仅拉取学生自身的学习记录、错题本、薄弱知识点生成方案；
    若没有任何学习记录，则直接提示学习活动太少，不检索其他数据。
    subject 非空时，只使用该科目的错题与作答记录，方案更具针对性。"""
    if user.role != "student":
        return fail("仅学生可生成个人学情分析")
    student = (
        await db.execute(select(Student).where(Student.user_id == user.id))
    ).scalar_one_or_none()
    if student is None:
        return fail("学生资料不存在")

    # 最近错题（仅学生自己的错题本，带题目内容；可按科目过滤）
    wrong_stmt = (
        select(WrongBook, Exercise)
        .join(Exercise, Exercise.id == WrongBook.exercise_id)
        .where(WrongBook.student_id == student.id)
    )
    if subject:
        wrong_stmt = wrong_stmt.join(Course, Course.id == Exercise.course_id).where(Course.subject == subject)
    wrong_rows = (
        await db.execute(wrong_stmt.order_by(WrongBook.created_at.desc()).limit(10))
    ).all()
    wrong_exercises = [
        {
            "content": (ex.content or "")[:200],
            "answer": (ex.answer or "")[:200],
            "knowledge_points": ex.knowledge_points or [],
            "reason": wb.reason or "",
        }
        for wb, ex in wrong_rows
    ]

    # 学习记录统计（仅学生自己的作答记录；可按科目过滤）
    rec_stmt = (
        select(LearningRecord, Exercise)
        .join(Exercise, Exercise.id == LearningRecord.exercise_id)
        .where(LearningRecord.student_id == student.id)
    )
    if subject:
        rec_stmt = rec_stmt.join(Course, Course.id == Exercise.course_id).where(Course.subject == subject)
    record_rows = (
        await db.execute(rec_stmt.order_by(LearningRecord.created_at.desc()).limit(50))
    ).all()
    total = len(record_rows)
    correct = sum(1 for rec, _ in record_rows if rec.is_correct)

    # 薄弱知识点：从该学生最近答错的题目中统计
    kp_counter = {}
    for rec, ex in record_rows:
        if not rec.is_correct:
            for kp in ex.knowledge_points or []:
                kp_counter[kp] = kp_counter.get(kp, 0) + 1
    weak_kps = sorted(kp_counter, key=lambda k: kp_counter[k], reverse=True)[:6]

    # 没有任何学习记录：直接返回提示，不调用大模型/检索，避免拉到无关数据
    if total == 0 and not wrong_exercises:
        task = AgentTask(
            user_id=user.id,
            student_id=student.id,
            task_type="personalized_plan",
            input_data={"message": "无学习记录"},
            output={"message": "您的学习活动太少，请开始学习吧"},
            status="completed",
        )
        db.add(task)
        await db.commit()
        await db.refresh(task)
        return ok(task_to_dict(task), message="学情分析完成")

    # 有学习数据：仅使用学生自身数据直接调用大模型生成 JSON 方案
    accuracy = correct / total if total else 0.0
    wrong_detail = "\n".join(
        "- 题目：%s 知识点：%s" % (
            w["content"],
            "、".join(w["knowledge_points"]) if w["knowledge_points"] else "（无）",
        )
        for w in wrong_exercises
    ) or "（无）"
    prompt = STUDENT_ANALYSIS_PROMPT.format(
        student_name=user.full_name or user.username,
        student_no=student.student_no or "-",
        grade=student.grade or "-",
        total=total,
        correct=correct,
        accuracy="%.1f%%" % (accuracy * 100),
        wrong_count=len(wrong_exercises),
        weak_kps="、".join(weak_kps) if weak_kps else "（暂无明显薄弱知识点）",
        wrong_detail=wrong_detail,
    )
    try:
        output = await llm_client.chat_json(
            [{"role": "system", "content": prompt}], temperature=0.4, max_tokens=2048
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail="方案生成失败：%s" % exc)
    if not isinstance(output, dict):
        output = {"weakness_diagnosis": str(output)}

    task = AgentTask(
        user_id=user.id,
        student_id=student.id,
        task_type="personalized_plan",
        input_data={
            "wrong_exercise_ids": [wb.id for wb, _ in wrong_rows],
            "knowledge_points": weak_kps,
        },
        output=output,
        status="completed",
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return ok(task_to_dict(task), message="学情分析完成")


@router.post("/generate-exercise")
async def generate_exercise(
    payload: ExerciseGenRequest,
    user: User = Depends(require_roles("admin", "teacher", "student")),
    db: AsyncSession = Depends(get_db),
):
    """按知识点 + 难度生成练习题。

    多样性/去重控制：
    - exclude_contents：提示 LLM 避开已生成题目，杜绝"再出一题"生成同一道题；
    - 若生成结果仍与历史归一化后雷同，则强制换表述重新生成一次（仅采纳不重复项）。
    """
    prompt = EXERCISE_GENERATION_PROMPT.format(
        knowledge_point=payload.knowledge_point, difficulty=payload.difficulty
    )
    exclude = [c for c in (payload.exclude_contents or []) if c]
    vary_hint = ""
    if exclude:
        vary_hint = (
            "\n请务必不要生成与下列已生成题目重复或雷同的内容：\n"
            + "\n".join("- %s" % (str(c)[:80]) for c in exclude)
        )
    elif payload.force_vary:
        vary_hint = "\n请换一种全新的场景/数据/表述，尽量与前一道题不同。"

    data = await llm_client.chat_json(
        [{"role": "system", "content": prompt + vary_hint}], temperature=0.7, max_tokens=1024
    )
    # 与学习/学科无关的知识点：发出禁答提示
    if data.get("refused"):
        return fail(data.get("message") or "该内容与学习/学科无关，无法生成练习题")
    # 仍与历史雷同：强制换表述再生成一次（仅采纳不重复项）
    excluded_set = {_gen_norm(c) for c in exclude}
    if exclude and _gen_norm(data.get("content")) in excluded_set:
        try:
            data = await llm_client.chat_json(
                [{
                    "role": "system",
                    "content": prompt + vary_hint
                    + "\n必须换一种完全不同的数据/场景/表述，绝不能与上述题目重复。",
                }],
                temperature=0.9,
                max_tokens=1024,
            )
        except Exception:  # noqa: BLE001 重新生成失败则沿用首次结果
            pass
    if data.get("refused"):
        return fail(data.get("message") or "该内容与学习/学科无关，无法生成练习题")
    # 确定题目所属课程：优先用传入的 course_id；否则按科目查找/创建课程，
    # 保证题库管理里“科目”与“知识点”正确对应
    course_id = payload.course_id
    if course_id and await db.get(Course, course_id) is None:
        course_id = None
    if not course_id and payload.subject:
        course = (
            await db.execute(select(Course).where(Course.subject == payload.subject).limit(1))
        ).scalar_one_or_none()
        if course is None:
            course = Course(
                name=f"AI出题（{payload.subject}）",
                subject=payload.subject,
                description="AI 自动出题生成的课程",
            )
            db.add(course)
            await db.flush()
        course_id = course.id
    if course_id:
        exercise = Exercise(
            course_id=course_id,
            type="single" if data.get("options") else "qa",
            content=data.get("content", ""),
            options=data.get("options") or [],
            answer=data.get("answer", ""),
            analysis=data.get("analysis", ""),
            difficulty=data.get("difficulty") or payload.difficulty,
            knowledge_points=[data.get("knowledge_point", payload.knowledge_point)],
        )
        db.add(exercise)
        await db.commit()
        await db.refresh(exercise)
        data["exercise_id"] = exercise.id
    return ok(data, message="题目生成成功")


@router.post("/sql-query")
async def sql_query(
    payload: SqlQueryRequest,
    user: User = Depends(require_roles("admin", "teacher")),
    db: AsyncSession = Depends(get_db),
):
    """SQL Agent：自然语言 -> 只读 SQL 查询教学统计数据。"""
    tools = TutorTools(db)
    result = await tools.query_sql(payload.natural_language)
    return ok(result, message="查询成功")