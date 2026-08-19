"""RAG 检索增强生成服务：入库 -> 检索 -> 拒答判断 -> 生成带引用答案。"""
import logging
from typing import Dict, List, Optional

from fastapi import HTTPException
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.embedding_service import embedding_service
from app.core.llm import llm_client
from app.core.milvus_client import milvus_client
from app.models.models import ChatMessage, ChatSession
from app.utils.document_parser import parse_document
from app.utils.prompt_templates import RAG_PROMPT, build_history_text
from app.utils.text_splitter import RecursiveCharacterTextSplitter, split_document

logger = logging.getLogger(__name__)


class RAGService:
    def __init__(self):
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.CHUNK_SIZE, chunk_overlap=settings.CHUNK_OVERLAP
        )

    # ---------- 入库 ----------
    async def index_file(
        self,
        file_path: str,
        filename: str,
        file_key: Optional[str] = None,
        subject: Optional[str] = None,
        uploader_user_id: Optional[int] = None,
    ) -> int:
        """解析 -> 切分 -> 向量化 -> 存入 Milvus，返回分块数。

        file_key 为该文件在存储中的唯一标识（如 uuid 文件名），
        写入 metadata 后可按其精确删除该文件全部分块。
        """
        pages = await run_in_threadpool(parse_document, file_path, filename)
        chunks = split_document(pages, self.splitter, filename)
        if not chunks:
            raise ValueError("文档解析后为空：扫描件/图片型文档或旧版 .doc 无法提取文本，请上传文本版 .docx / .txt / .md 文件")
        for chunk in chunks:
            chunk["metadata"]["file_key"] = file_key or filename
            if subject:
                chunk["metadata"]["subject"] = subject
            if uploader_user_id is not None:
                chunk["metadata"]["uploader_user_id"] = uploader_user_id
        texts = [c["content"] for c in chunks]
        embeddings = await embedding_service.aencode(texts)
        ids = await run_in_threadpool(
            milvus_client.insert,
            texts,
            embeddings,
            [c["metadata"] for c in chunks],
        )
        logger.info("文件 %s 已入库，共 %s 个分块", filename, len(ids))
        return len(ids)

    # ---------- 检索 ----------
    async def retrieve(
        self,
        query: str,
        top_k: Optional[int] = None,
        subject: Optional[str] = None,
    ) -> List[Dict]:
        top_k = top_k or settings.RAG_TOP_K
        vector = (await embedding_service.aencode([query]))[0]
        expr = f'metadata["subject"] == "{subject}"' if subject else None
        hits = await run_in_threadpool(milvus_client.search, vector, top_k, expr)
        return hits

    # ---------- 问答 ----------
    async def ask(
        self,
        db: AsyncSession,
        user_id: int,
        question: str,
        session_id: Optional[str] = None,
        history: Optional[List[dict]] = None,
        subject: Optional[str] = None,
    ) -> Dict:
        history = history or []
        # 直接调用大模型问答（不使用知识库检索）
        messages = []
        for item in history:
            role = "user" if item.get("role") == "user" else "assistant"
            messages.append({"role": role, "content": item.get("content", "")})
        messages.append({"role": "user", "content": question})
        answer = await llm_client.chat(messages, temperature=0.4, max_tokens=2048)
        sources: List[Dict] = []
        accepted = True
        top_score = None

        # 持久化会话与消息（支持多轮追问）
        if not session_id:
            session = ChatSession(user_id=user_id, title=question[:30])
            db.add(session)
            await db.flush()
            session_id = session.id
        else:
            session = await db.get(ChatSession, session_id)
            if session is None or session.user_id != user_id:
                raise HTTPException(status_code=404, detail="会话不存在")

        db.add(ChatMessage(session_id=session_id, role="user", content=question))
        db.add(
            ChatMessage(
                session_id=session_id,
                role="assistant",
                content=answer,
                sources=sources,
            )
        )
        await db.commit()

        return {
            "answer": answer,
            "sources": sources,
            "session_id": session_id,
            "accepted": accepted,
            "score": None,
        }


rag_service = RAGService()