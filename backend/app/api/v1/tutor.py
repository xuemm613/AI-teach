"""个性化学习 Agent 接口。"""
import json

from fastapi import APIRouter, Depends
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
from app.services.agent_service import TutorTools, agent_service
from app.utils.prompt_templates import EXERCISE_GENERATION_PROMPT

router = APIRouter(prefix="/tutor", tags=["个性化辅导"])


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
):
    """学生个人学情分析：由个性化学习 Agent 根据答题/错题/学习记录生成辅导方案。"""
    if user.role != "student":
        return fail("仅学生可生成个人学情分析")
    student = (
        await db.execute(select(Student).where(Student.user_id == user.id))
    ).scalar_one_or_none()
    if student is None:
        return fail("学生资料不存在")

    # 最近错题
    wrong_ids = (
        await db.execute(
            select(WrongBook.exercise_id)
            .where(WrongBook.student_id == student.id)
            .order_by(WrongBook.created_at.desc())
            .limit(10)
        )
    ).scalars().all()

    # 薄弱知识点：从最近答错的题目中统计
    kp_counter = {}
    rows = (
        await db.execute(
            select(Exercise.knowledge_points)
            .join(LearningRecord, LearningRecord.exercise_id == Exercise.id)
            .where(
                LearningRecord.student_id == student.id,
                LearningRecord.is_correct.is_(False),
            )
            .order_by(LearningRecord.created_at.desc())
            .limit(30)
        )
    ).all()
    for (kps,) in rows:
        for kp in kps or []:
            kp_counter[kp] = kp_counter.get(kp, 0) + 1
    weak_kps = sorted(kp_counter, key=lambda k: kp_counter[k], reverse=True)[:6]

    problems = "请根据我的答题情况、错题与学习记录，分析我的薄弱点并生成个性化学习辅导方案。"
    task = await agent_service.run_agent(
        db=db,
        user=user,
        problems=problems,
        wrong_exercise_ids=list(wrong_ids),
        knowledge_points=weak_kps,
    )
    return ok(task_to_dict(task), message="学情分析完成")


@router.post("/generate-exercise")
async def generate_exercise(
    payload: ExerciseGenRequest,
    user: User = Depends(require_roles("admin", "teacher", "student")),
    db: AsyncSession = Depends(get_db),
):
    """按知识点 + 难度生成练习题。"""
    prompt = EXERCISE_GENERATION_PROMPT.format(
        knowledge_point=payload.knowledge_point, difficulty=payload.difficulty
    )
    data = await llm_client.chat_json(
        [{"role": "system", "content": prompt}], temperature=0.6, max_tokens=1024
    )
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