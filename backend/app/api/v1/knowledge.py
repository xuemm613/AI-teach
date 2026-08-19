"""知识库接口：按科目隔离。教师只能建设/管理自己负责科目的知识库，管理员管理全部。"""
import logging
import uuid
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.api.subject_utils import is_valid_subject, teacher_subjects
from app.core.config import settings
from app.core.llm import llm_client
from app.core.database import async_session_factory, get_db
from app.core.milvus_client import milvus_client
from app.models.models import KnowledgeFile, User
from app.schemas.common import fail, ok
from app.schemas.knowledge import KnowledgeAskRequest, SearchRequest
from app.services.rag_service import rag_service
from app.utils.document_parser import SUPPORTED_EXTS, parse_document
from app.utils.prompt_templates import RAG_PROMPT

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/knowledge", tags=["知识库"])

async def _process_upload(file_id: int) -> None:
    """后台任务：解析 -> 切分 -> 向量化 -> 入库。"""
    async with async_session_factory() as db:
        record = await db.get(KnowledgeFile, file_id)
        if record is None:
            return
        try:
            record.status = "processing"
            await db.commit()
            count = await rag_service.index_file(
                record.file_path,
                record.filename,
                file_key=record.file_key,
                subject=record.subject,
                uploader_user_id=record.uploaded_by,
            )
            record.status = "indexed"
            record.chunk_count = count
            record.error = None
        except Exception as exc:  # noqa: BLE001
            logger.error("文件入库失败 %s: %s", record.filename, exc)
            record.status = "failed"
            record.error = str(exc)
        await db.commit()


def _file_to_dict(record: KnowledgeFile) -> dict:
    return {
        "id": record.id,
        "filename": record.filename,
        "file_type": record.file_type,
        "subject": record.subject,
        "file_size": record.file_size,
        "status": record.status,  # pending/processing/indexed/failed
        "chunk_count": record.chunk_count,
        "error": record.error,
        "uploaded_by": record.uploaded_by,
        "created_at": record.created_at.isoformat() if record.created_at else None,
    }


async def _teacher_subject_cond(db: AsyncSession, user: User) -> List:
    """返回教师可见科目的筛选条件；教师无科目时返回恒假条件（看不到任何文件）。"""
    if user.role == "teacher":
        subs = await teacher_subjects(db, user)
        if not subs:
            return [KnowledgeFile.id < 0]
        return [KnowledgeFile.subject.in_(list(subs)), KnowledgeFile.uploaded_by == user.id]
    return []


async def _teacher_file_keys(db: AsyncSession, user: User) -> set:
    """返回该教师自己上传的所有文件 key（以数据库为准，兼容历史上传的旧向量）"""
    result = await db.execute(
        select(KnowledgeFile.file_key).where(KnowledgeFile.uploaded_by == user.id)
    )
    return set(result.scalars().all())


async def _repair_knowledge_files(db: AsyncSession, user: User) -> None:
    """一致性修复：把数据库中标记为“已入库”但物理文件已丢失的记录标记为失败，
    避免出现“状态显示已完成却无法检索”的误导情况。"""
    cond = await _teacher_subject_cond(db, user)
    stmt = select(KnowledgeFile).where(KnowledgeFile.status == "indexed", *cond)
    records = (await db.execute(stmt)).scalars().all()
    changed = False
    for rec in records:
        if not Path(rec.file_path).exists():
            rec.status = "failed"
            rec.error = "原始文件已丢失，请重新上传"
            changed = True
    if changed:
        await db.commit()


async def _reindex_missing_vectors(user_id: Optional[int]) -> None:
    """后台任务：物理文件仍在、但向量分块缺失的文件重新向量化入库。"""
    async with async_session_factory() as db:
        stmt = select(KnowledgeFile).where(KnowledgeFile.status == "indexed")
        if user_id is not None:
            stmt = stmt.where(KnowledgeFile.uploaded_by == user_id)
        records = (await db.execute(stmt)).scalars().all()
        for rec in records:
            if not Path(rec.file_path).exists():
                continue
            if await run_in_threadpool(milvus_client.has_file_key, rec.file_key):
                continue
            try:
                count = await rag_service.index_file(
                    rec.file_path,
                    rec.filename,
                    file_key=rec.file_key,
                    subject=rec.subject,
                    uploader_user_id=rec.uploaded_by,
                )
                rec.chunk_count = count
                rec.error = None
            except Exception as exc:  # noqa: BLE001
                rec.status = "failed"
                rec.error = str(exc)
            await db.commit()


@router.post("/upload")
async def upload_knowledge(
    background: BackgroundTasks,
    file: UploadFile = File(...),
    subject: str = Form(...),
    user: User = Depends(require_roles("admin", "teacher")),
    db: AsyncSession = Depends(get_db),
):
    """上传资料。教师必须选择自己负责的科目。"""
    if not is_valid_subject(subject):
        return fail("学科必须为系统规定科目：语文、数学、英语、物理、化学、生物、政治、历史、地理、体育、音乐、美术、劳动")
    if user.role == "teacher":
        subs = await teacher_subjects(db, user)
        if subject not in subs:
            return fail(f"只能建设您负责科目的知识库：{', '.join(sorted(subs)) or '未分配科目'}")

    filename = file.filename or "unnamed"
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_EXTS:
        return fail(f"不支持的文件类型: {suffix or '未知'}，仅支持 pdf/docx/txt/md")

    content = await file.read()
    if len(content) > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        return fail(f"文件超过大小限制（{settings.MAX_UPLOAD_SIZE_MB}MB）")

    upload_dir = settings.upload_dir
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_key = f"{uuid.uuid4().hex}{suffix}"
    file_path = upload_dir / file_key
    file_path.write_bytes(content)


    record = KnowledgeFile(
        filename=filename,
        file_key=file_key,
        file_type=suffix[1:],
        subject=subject,
        file_path=str(file_path),
        file_size=len(content),
        status="pending",
        uploaded_by=user.id,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)

    background.add_task(_process_upload, record.id)
    return ok(_file_to_dict(record), message="上传成功，正在后台解析入库")


@router.get("/stats")
async def knowledge_stats(
    user: User = Depends(require_roles("admin", "teacher")),
    db: AsyncSession = Depends(get_db),
):
    cond = await _teacher_subject_cond(db, user)
    total = (await db.execute(select(func.count(KnowledgeFile.id)).where(*cond))).scalar() or 0
    indexed = (
        await db.execute(
            select(func.count(KnowledgeFile.id)).where(KnowledgeFile.status == "indexed", *cond)
        )
    ).scalar() or 0
    failed = (
        await db.execute(
            select(func.count(KnowledgeFile.id)).where(KnowledgeFile.status == "failed", *cond)
        )
    ).scalar() or 0
    pending = total - indexed - failed
    total_chunks = await run_in_threadpool(milvus_client.count)
    return ok(
        {
            "total_documents": total,
            "indexed": indexed,
            "pending": pending,
            "failed": failed,
            "total_chunks": total_chunks,
        }
    )


@router.get("/files")
async def list_files(
    background: BackgroundTasks,
    user: User = Depends(require_roles("admin", "teacher", "student")),
    db: AsyncSession = Depends(get_db),
    status: Optional[str] = Query(None),
    subject: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
):
    await _repair_knowledge_files(db, user)
    if user.role in ("admin", "teacher"):
        background.add_task(
            _reindex_missing_vectors, user.id if user.role == "teacher" else None
        )
    cond = await _teacher_subject_cond(db, user)
    stmt = select(KnowledgeFile).where(*cond)
    if subject:
        stmt = stmt.where(KnowledgeFile.subject == subject)
    if status:
        stmt = stmt.where(KnowledgeFile.status == status)
    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar() or 0
    result = await db.execute(stmt.order_by(KnowledgeFile.id.desc()).offset((page - 1) * size).limit(size))
    records = result.scalars().all()
    return ok({"total": total, "items": [_file_to_dict(r) for r in records]})


@router.get("/files/{file_id}")
async def file_detail(
    file_id: int,
    user: User = Depends(require_roles("admin", "teacher", "student")),
    db: AsyncSession = Depends(get_db),
):
    record = await db.get(KnowledgeFile, file_id)
    if record is None:
        raise HTTPException(status_code=404, detail="文件记录不存在")
    if user.role == "teacher" and record.uploaded_by != user.id:
        raise HTTPException(status_code=403, detail="无权查看其他教师的文件")
    return ok(_file_to_dict(record))


@router.get("/files/{file_id}/content")
async def file_content(
    file_id: int,
    user: User = Depends(require_roles("admin", "teacher")),
    db: AsyncSession = Depends(get_db),
):
    """查看文件内容：解析物理文件并返回纯文本（教师仅能查看自己上传的文件）"""
    record = await db.get(KnowledgeFile, file_id)
    if record is None:
        raise HTTPException(status_code=404, detail="文件记录不存在")
    if user.role == "teacher" and record.uploaded_by != user.id:
        raise HTTPException(status_code=403, detail="无权查看其他教师的文件")
    try:
        pages = await run_in_threadpool(parse_document, record.file_path, record.filename)
        text = "\n\n".join(pg.text for pg in pages)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail="文件内容解析失败：%s" % exc)
    return ok({"filename": record.filename, "content": text})


@router.delete("/files/{file_id}")
async def delete_file(
    file_id: int,
    user: User = Depends(require_roles("admin", "teacher")),
    db: AsyncSession = Depends(get_db),
):
    record = await db.get(KnowledgeFile, file_id)
    if record is None:
        raise HTTPException(status_code=404, detail="文件记录不存在")
    if user.role == "teacher" and record.uploaded_by != user.id:
        raise HTTPException(status_code=403, detail="无权删除其他教师的文件")

    await run_in_threadpool(milvus_client.delete_by_metadata, "file_key", record.file_key)
    try:
        Path(record.file_path).unlink(missing_ok=True)
    except OSError as exc:  # noqa: BLE001
        logger.warning("物理文件删除失败: %s", exc)

    await db.delete(record)
    await db.commit()
    return ok(None, message="删除成功")


@router.post("/search")
async def search_knowledge(
    payload: SearchRequest,
    user: User = Depends(require_roles("admin", "teacher", "student")),
    db: AsyncSession = Depends(get_db),
):
    """检索调试接口：返回 Top-K 命中文档（可按科目过滤）。"""
    await _repair_knowledge_files(db, user)
    hits = await rag_service.retrieve(
        payload.query,
        top_k=payload.top_k,
        subject=payload.subject,
    )
    if user.role == "teacher":
        own_keys = await _teacher_file_keys(db, user)
        hits = [h for h in hits if h["metadata"].get("file_key") in own_keys]
    return ok(
        {
            "query": payload.query,
            "subject": payload.subject,
            "hits": [
                {
                    "id": h["id"],
                    "score": round(h["score"], 4),
                    "content": h["content"],
                    "metadata": h["metadata"],
                }
                for h in hits
            ],
        }
    )


@router.post("/ask")
async def ask_knowledge(
    payload: KnowledgeAskRequest,
    user: User = Depends(require_roles("admin", "teacher")),
    db: AsyncSession = Depends(get_db),
):
    """RAG 问答：检索知识库并生成带引用来源的回答。教师只能提问自己负责科目的知识库。"""
    await _repair_knowledge_files(db, user)
    if user.role == "teacher":
        subs = await teacher_subjects(db, user)
        if payload.subject and payload.subject not in subs:
            return fail(f"只能提问您负责科目的知识库：{', '.join(sorted(subs)) or '未分配科目'}")

    hits = await rag_service.retrieve(
        payload.question,
        top_k=settings.RAG_TOP_K,
        subject=payload.subject or None,
    )
    if user.role == "teacher":
        own_keys = await _teacher_file_keys(db, user)
        hits = [h for h in hits if h["metadata"].get("file_key") in own_keys]
    if not hits:
        return ok({"answer": "知识库中暂无相关信息，请先上传相关文件后再提问。", "sources": []})
    # 有命中时即结合资料回答；若资料不足以回答，提示词会要求模型明确说明“知识库中暂无相关信息”

    context = "\n\n".join(
        f"[{i + 1}] (来源：{h['metadata'].get('filename', '未知')}-第{h['metadata'].get('page', '?')}页)\n{h['content']}"
        for i, h in enumerate(hits)
    )
    prompt = RAG_PROMPT.format(context=context, history="（无）", question=payload.question)
    answer = await llm_client.chat(
        [{"role": "system", "content": prompt}], temperature=0.3, max_tokens=2048
    )
    sources = [
        {
            "filename": h["metadata"].get("filename", ""),
            "page": h["metadata"].get("page"),
            "score": round(h["score"], 4),
            "content": h["content"],
        }
        for h in hits
    ]
    return ok({"answer": answer, "sources": sources})