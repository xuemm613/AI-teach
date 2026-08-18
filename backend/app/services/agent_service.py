"""个性化学习 Agent：任务分解 -> 循环调用工具 -> 汇总生成个性化方案。

工具（Python 函数封装）：
- search_knowledge     知识检索
- generate_exercise    生成练习题
- analyze_error        错因分析
- query_sql            教学数据只读 SQL 查询
- plan_path            学习路径规划
"""
import json
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import engine
from app.core.llm import extract_sql, llm_client, parse_json
from app.models.models import AgentTask, LearningRecord, Student, User
from app.services.rag_service import rag_service
from app.utils.prompt_templates import (
    AGENT_FINAL_PROMPT,
    ERROR_ANALYSIS_PROMPT,
    EXERCISE_GENERATION_PROMPT,
    PLAN_PATH_PROMPT,
    SQL_AGENT_PROMPT,
    TUTOR_AGENT_SYSTEM_PROMPT,
)

logger = logging.getLogger(__name__)

FORBIDDEN_SQL_KEYWORDS = [
    "insert", "update", "delete", "drop", "alter", "create",
    "truncate", "grant", "revoke", "replace", "merge", "vacuum",
]


def _validate_readonly_sql(sql: str) -> str:
    """严格限制 SQL 只读：仅允许单条 SELECT（或 WITH...SELECT）。"""
    stripped = sql.strip().rstrip(";")
    if ";" in stripped:
        raise ValueError("仅允许单条 SQL 查询")
    lowered = stripped.lower()
    for kw in FORBIDDEN_SQL_KEYWORDS:
        if kw in lowered:
            raise ValueError(f"检测到禁止关键字: {kw}")
    if not (lowered.startswith("select") or lowered.startswith("with")):
        raise ValueError("仅允许 SELECT 查询")
    return stripped


class TutorTools:
    """Agent 可调用工具集合。"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def search_knowledge(self, query: str) -> str:
        hits = await rag_service.retrieve(query, top_k=5)
        payload = [
            {
                "content": h["content"][:500],
                "score": round(h["score"], 4),
                "metadata": h["metadata"],
            }
            for h in hits
        ]
        return json.dumps(payload, ensure_ascii=False)

    async def generate_exercise(self, knowledge_point: str, difficulty: str = "medium") -> str:
        prompt = EXERCISE_GENERATION_PROMPT.format(
            knowledge_point=knowledge_point, difficulty=difficulty
        )
        data = await llm_client.chat_json(
            [{"role": "system", "content": prompt}], temperature=0.6, max_tokens=1024
        )
        return json.dumps(data, ensure_ascii=False)

    async def analyze_error(self, question: str, user_answer: str, correct_answer: str) -> str:
        prompt = ERROR_ANALYSIS_PROMPT.format(
            question=question,
            user_answer=user_answer or "（未作答）",
            correct_answer=correct_answer or "（未知）",
        )
        data = await llm_client.chat_json(
            [{"role": "system", "content": prompt}], temperature=0.3, max_tokens=1024
        )
        return json.dumps(data, ensure_ascii=False)

    async def query_sql(self, natural_language: str) -> str:
        """自然语言 -> 只读 SQL -> 执行并返回结果。"""
        sql = await self._nl_to_sql(natural_language)
        validated = _validate_readonly_sql(sql)
        rows, keys = await self._execute_readonly(validated)
        return json.dumps({"sql": validated, "columns": keys, "rows": rows}, ensure_ascii=False)

    async def plan_path(self, weak_points: str, student_id: Optional[int] = None) -> str:
        history_text = "（无历史记录）"
        if student_id:
            result = await self.db.execute(
                select(LearningRecord)
                .where(LearningRecord.student_id == student_id)
                .order_by(LearningRecord.created_at.desc())
                .limit(10)
            )
            records = result.scalars().all()
            if records:
                history_text = "\n".join(
                    f"题{rec.exercise_id}: {'对' if rec.is_correct else '错'}"
                    for rec in records
                )
        prompt = PLAN_PATH_PROMPT.format(
            weak_points=weak_points, history=history_text
        )
        data = await llm_client.chat_json(
            [{"role": "system", "content": prompt}], temperature=0.4, max_tokens=2048
        )
        return json.dumps(data, ensure_ascii=False)

    async def _nl_to_sql(self, natural_language: str) -> str:
        prompt = SQL_AGENT_PROMPT.format(question=natural_language)
        resp = await llm_client.chat(
            [{"role": "system", "content": prompt}],
            temperature=0.0,
            max_tokens=512,
        )
        return extract_sql(resp)

    async def _execute_readonly(self, sql: str):
        async with engine.connect() as conn:
            result = await conn.execute(text(sql))
            rows = result.fetchmany(100)
            keys = list(result.keys())
            return [dict(zip(keys, row)) for row in rows]

    async def call(self, name: str, args: Dict[str, Any]) -> str:
        if name == "search_knowledge":
            return await self.search_knowledge(args.get("query", ""))
        if name == "generate_exercise":
            return await self.generate_exercise(
                args.get("knowledge_point", ""), args.get("difficulty", "medium")
            )
        if name == "analyze_error":
            return await self.analyze_error(
                args.get("question", ""),
                args.get("user_answer", ""),
                args.get("correct_answer", ""),
            )
        if name == "query_sql":
            return await self.query_sql(args.get("natural_language", ""))
        if name == "plan_path":
            return await self.plan_path(
                args.get("weak_points", ""), args.get("student_id")
            )
        raise ValueError(f"未知工具: {name}")


class AgentService:
    def __init__(self, max_steps: int = 8):
        self.max_steps = max_steps

    async def run_agent(
        self,
        db: AsyncSession,
        user: User,
        problems: str,
        wrong_exercise_ids: Optional[List[int]] = None,
        knowledge_points: Optional[List[str]] = None,
    ) -> AgentTask:
        # 学生扩展信息（教师/管理员也可为学生创建方案）
        student = None
        if user.role == "student":
            result = await db.execute(
                select(Student).where(Student.user_id == user.id)
            )
            student = result.scalar_one_or_none()

        task = AgentTask(
            user_id=user.id,
            student_id=student.id if student else None,
            task_type="personalized_plan",
            input_data={
                "problems": problems,
                "wrong_exercise_ids": wrong_exercise_ids or [],
                "knowledge_points": knowledge_points or [],
            },
            status="running",
        )
        db.add(task)
        await db.commit()
        await db.refresh(task)

        try:
            steps: List[Dict[str, Any]] = []
            messages = [
                {
                    "role": "system",
                    "content": TUTOR_AGENT_SYSTEM_PROMPT.replace("{max_steps}", str(self.max_steps)),
                },
                {
                    "role": "user",
                    "content": self._build_user_message(
                        user, student, problems, wrong_exercise_ids, knowledge_points
                    ),
                },
            ]
            final_answer: Optional[Dict[str, Any]] = None

            for step in range(self.max_steps):
                try:
                    # 使用 json_mode 强制模型输出 JSON，避免偶发空内容
                    decision = await llm_client.chat_json(
                        messages, temperature=0.3, max_tokens=1024
                    )
                except Exception:
                    # 模型未输出严格 JSON：提示后重试，不直接报错
                    messages.append(
                        {"role": "user", "content": "请只输出一个 JSON 对象，不要输出任何其他文字。"}
                    )
                    continue
                resp = json.dumps(decision, ensure_ascii=False)
                messages.append({"role": "assistant", "content": resp})

                if decision.get("final"):
                    final_answer = decision.get("answer")
                    break

                tool = decision.get("tool")
                args = decision.get("args") or {}
                tools = TutorTools(db)
                try:
                    result = await tools.call(tool, args)
                    ok = True
                except Exception as exc:  # noqa: BLE001
                    logger.warning("工具 %s 执行失败: %s", tool, exc)
                    result = f"工具执行失败: {exc}"
                    ok = False

                messages.append(
                    {"role": "user", "content": f"[工具 {tool} 返回] {result}"}
                )
                steps.append(
                    {
                        "step": step + 1,
                        "tool": tool,
                        "args": args,
                        "ok": ok,
                        "result": str(result)[:800],
                    }
                )
                task.steps = list(steps)
                await db.commit()

            # 汇总生成最终方案
            if final_answer is None:
                final_answer = await llm_client.chat_json(
                    [
                        {
                            "role": "system",
                            "content": AGENT_FINAL_PROMPT.format(
                                problems=problems,
                                steps=json.dumps(steps, ensure_ascii=False),
                            ),
                        }
                    ],
                    temperature=0.3,
                    max_tokens=2048,
                )
            if not isinstance(final_answer, dict):
                final_answer = {"answer": final_answer}

            task.output = final_answer
            task.steps = steps
            task.status = "completed"
            task.error = None
            await db.commit()
            await db.refresh(task)
            return task
        except Exception as exc:  # noqa: BLE001
            logger.error("Agent 工作流失败: %s", exc)
            task.status = "failed"
            task.error = str(exc)
            await db.commit()
            raise

    def _build_user_message(
        self,
        user: User,
        student: Optional[Student],
        problems: str,
        wrong_exercise_ids: Optional[List[int]],
        knowledge_points: Optional[List[str]],
    ) -> str:
        lines = [
            f"学生姓名：{user.full_name or user.username}",
            f"学生ID：{user.id}",
            f"角色：{user.role}",
        ]
        if student:
            lines.append(f"学号：{student.student_no or '-'}  年级：{student.grade or '-'}")
        lines.append(f"学生描述的问题/错题：{problems}")
        if wrong_exercise_ids:
            lines.append(f"错题ID列表：{wrong_exercise_ids}")
        if knowledge_points:
            lines.append(f"薄弱知识点：{knowledge_points}")
        lines.append("请进行任务分解并调用工具，最终输出个性化辅导方案。")
        return "\n".join(lines)


agent_service = AgentService()