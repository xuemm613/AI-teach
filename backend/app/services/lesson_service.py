"""智能备课引擎：检索知识库 + 结构化提示词 -> 严格 JSON 教案 -> 入库。"""
import logging
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.llm import llm_client
from app.models.models import LessonPlan
from app.services.rag_service import rag_service
from app.utils.prompt_templates import LESSON_GENERATION_PROMPT

logger = logging.getLogger(__name__)


class LessonService:
    async def generate(
        self,
        db: AsyncSession,
        teacher_id: int,
        grade: str,
        subject: str,
        chapter: str,
        teaching_objectives: Optional[str] = None,
    ) -> LessonPlan:
        # 1. 检索知识库获取章节相关内容
        query = f"{grade} {subject} {chapter} 教案 教学 知识点"
        hits = await rag_service.retrieve(query, top_k=8)
        context = "\n\n".join(
            f"[{i + 1}] (来源：{h['metadata'].get('filename', '未知')}"
            f"-第{h['metadata'].get('page', '?')}页)\n{h['content']}"
            for i, h in enumerate(hits[:8])
        ) or "（知识库暂无相关章节内容，请基于通用教学经验生成）"

        # 2. 构建结构化提示词，要求输出严格 JSON
        prompt = LESSON_GENERATION_PROMPT.format(
            grade=grade,
            subject=subject,
            chapter=chapter,
            objectives=teaching_objectives or "（未提供，请自行设计合理目标）",
            context=context,
        )
        data = await llm_client.chat_json(
            [{"role": "system", "content": prompt}],
            temperature=0.4,
            max_tokens=4096,
        )
        data = self._normalize(data)

        # 3. 存入 lesson_plans
        plan = LessonPlan(
            teacher_id=teacher_id,
            grade=grade,
            subject=subject,
            chapter=chapter,
            teaching_objectives=teaching_objectives,
            content=data,
            status="generated",
        )
        db.add(plan)
        await db.commit()
        await db.refresh(plan)
        return plan

    def _normalize(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """保证教案 JSON 包含全部必需字段。"""
        layered = data.get("layered_exercises") or {}
        normalized = {
            "teaching_objectives": data.get("teaching_objectives") or [],
            "introduction": data.get("introduction") or "",
            "outline": data.get("outline") or [],
            "interactive_questions": data.get("interactive_questions") or [],
            "board_design": data.get("board_design") or "",
            "layered_exercises": {
                "basic": layered.get("basic") or [],
                "medium": layered.get("medium") or [],
                "advanced": layered.get("advanced") or [],
            },
        }
        # 保留模型额外输出
        for key in ("teaching_methods", "homework", "summary"):
            if key in data:
                normalized[key] = data[key]
        return normalized


lesson_service = LessonService()