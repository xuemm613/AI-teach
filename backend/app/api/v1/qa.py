"""智能问答接口（RAG 多轮对话）。"""
import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import async_session_factory, get_db
from app.core.llm import llm_client
from app.models.models import (
    ChatMessage,
    ChatSession,
    Exercise,
    Student,
    User,
    WrongBook,
)
from app.schemas.common import fail, ok
from app.schemas.qa import AskRequest, CollectRequest
from app.services.rag_service import rag_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/qa", tags=["智能问答"])


def exercise_brief(ex: Exercise) -> dict:
    return {
        "id": ex.id,
        "type": ex.type,
        "chapter": ex.chapter,
        "content": ex.content,
        "options": ex.options or [],
        "answer": ex.answer,
        "analysis": ex.analysis,
        "difficulty": ex.difficulty,
        "knowledge_points": ex.knowledge_points or [],
    }


@router.post("/ask")
async def ask(
    payload: AskRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await rag_service.ask(
        db=db,
        user_id=user.id,
        question=payload.question,
        session_id=payload.session_id,
        history=[h.model_dump() for h in payload.history],
    )
    return ok(result)


QA_SYSTEM_PROMPT = """你是一个严谨耐心的教育智能问答助手，请使用中文回答。
要求：
1. 使用 Markdown 格式组织答案，可用标题、列表、表格等，保证结构清晰。
2. 表格列数不要太多，确保列对齐、不串位、不乱码。
3. 数学公式请用普通文字清晰表达（如“x 的平方”“根号2”“a 除以 b”），不要使用 LaTeX 语法。
"""


@router.post("/ask-stream")
async def ask_stream(
    payload: AskRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """流式问答：SSE 逐字返回模型回答（Markdown 格式）。"""
    # 创建或复用会话（在返回前完成，确保 session_id 持久化）
    session_id = payload.session_id
    if not session_id:
        session = ChatSession(user_id=user.id, title=payload.question[:30])
        db.add(session)
        await db.commit()
        await db.refresh(session)
        session_id = session.id
    else:
        session = await db.get(ChatSession, session_id)
        if session is None or session.user_id != user.id:
            raise HTTPException(status_code=404, detail="会话不存在")

    messages = [{"role": "system", "content": QA_SYSTEM_PROMPT}]
    for item in payload.history:
        role = "user" if item.role == "user" else "assistant"
        messages.append({"role": role, "content": item.content})
    messages.append({"role": "user", "content": payload.question})

    async def event_stream():
        full = ""
        async with async_session_factory() as sdb:
            try:
                async for token in llm_client.chat_stream(messages, temperature=0.4, max_tokens=2048):
                    full += token
                    yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"
            except Exception as exc:  # noqa: BLE001
                logger.warning("流式问答失败: %s", exc)
            finally:
                if not full:
                    full = "（未获取到回答，请重试）"
                sdb.add(ChatMessage(session_id=session_id, role="user", content=payload.question))
                sdb.add(ChatMessage(session_id=session_id, role="assistant", content=full, sources=[]))
                await sdb.commit()
                yield f"data: {json.dumps({'session_id': session_id, 'done': True}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/collect")
async def collect(
    payload: CollectRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """把当前问答中的题目一键加入错题本（保存为问答题并收藏）。"""
    student = (
        await db.execute(select(Student).where(Student.user_id == user.id))
    ).scalar_one_or_none()
    if student is None:
        return fail("仅学生账号可收藏到错题本")

    exercise = Exercise(
        type="qa",
        content=payload.question,
        answer=payload.answer,
        analysis=payload.answer,
        knowledge_points=payload.knowledge_points or [],
    )
    db.add(exercise)
    await db.flush()

    exists = await db.execute(
        select(WrongBook).where(
            WrongBook.student_id == student.id,
            WrongBook.exercise_id == exercise.id,
        )
    )
    if exists.scalar_one_or_none() is None:
        db.add(
            WrongBook(
                student_id=student.id,
                exercise_id=exercise.id,
                reason="来自智能问答",
            )
        )
    await db.commit()
    return ok({"exercise_id": exercise.id}, message="已加入错题本")


@router.get("/sessions")
async def list_sessions(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.user_id == user.id)
        .order_by(desc(ChatSession.created_at))
    )
    sessions = result.scalars().all()
    return ok(
        [
            {
                "id": s.id,
                "title": s.title,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in sessions
        ]
    )


@router.get("/sessions/{session_id}")
async def session_messages(
    session_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await db.get(ChatSession, session_id)
    if session is None or session.user_id != user.id:
        raise HTTPException(status_code=404, detail="会话不存在")
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at)
    )
    messages = result.scalars().all()
    return ok(
        [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "sources": m.sources or [],
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in messages
        ]
    )


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await db.get(ChatSession, session_id)
    if session is None or session.user_id != user.id:
        raise HTTPException(status_code=404, detail="会话不存在")
    await db.delete(session)
    await db.commit()
    return ok(None, message="会话已删除")