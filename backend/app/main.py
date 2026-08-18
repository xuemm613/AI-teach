"""FastAPI 应用入口。"""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.v1 import admin, auth, knowledge, lesson, qa, tutor, users
from app.core.config import settings
from sqlalchemy import text

from app.core.database import async_session_factory, engine, init_db
from app.core.embedding_service import embedding_service
from app.core.milvus_client import milvus_client
from app.core.security import decode_token
from app.models.models import SystemLog, User
from app.schemas.common import fail
from app.utils.seed import ensure_default_admin

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

_SKIP_AUDIT_PREFIXES = (
    "/docs", "/redoc", "/openapi.json", "/uploads", "/favicon",
    "/api/v1/health",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. 初始化 MySQL 数据表（幂等；失败不阻塞启动，请求会给出明确提示）
    try:
        await init_db()
        logger.info("MySQL 数据表初始化完成")
    except Exception as exc:  # noqa: BLE001
        logger.error("数据表初始化失败（服务继续启动）: %s", exc)

    # 2. 加载本地嵌入模型至内存（失败自动降级哈希向量，保证离线可运行）
    embedding_service.load()

    # 3. 自动检测并创建 Milvus 集合（不存在则创建）
    milvus_client.ensure_collection(embedding_service.dimension)
    logger.info("Milvus 初始化完成，集合: %s", settings.MILVUS_COLLECTION)

    # 4. 确保默认管理员账号存在
    await ensure_default_admin()

    # 5. 确保上传目录存在
    settings.upload_dir.mkdir(parents=True, exist_ok=True)

    yield

    await engine.dispose()


app = FastAPI(
    title=settings.APP_NAME,
    description="AI 教育智能备课与个性化学习辅导智能体（FastAPI + MySQL + Milvus Lite + 本地向量化）",
    version="1.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def audit_middleware(request: Request, call_next):
    """系统操作日志：记录谁在什么时间做了什么操作（写入 system_logs）。"""
    response = await call_next(request)
    path = request.url.path
    if path.startswith(_SKIP_AUDIT_PREFIXES) or not path.startswith("/api/"):
        return response

    user_id = None
    username = None
    auth = request.headers.get("Authorization")
    if auth and auth.lower().startswith("bearer "):
        try:
            payload = decode_token(auth[7:], expected_type="access")
            user_id = int(payload["sub"])
        except Exception:  # noqa: BLE001
            user_id = None

    action = f"{request.method} {path}"
    try:
        async with async_session_factory() as db:
            if user_id is not None:
                u = await db.get(User, user_id)
                username = u.username if u else None
            db.add(
                SystemLog(
                    user_id=user_id,
                    username=username,
                    action=action,
                    detail=f"status={response.status_code}",
                    ip=request.client.host if request.client else None,
                )
            )
            await db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning("审计日志写入失败: %s", exc)
    return response


# 统一异常响应格式 { code, message, data }
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content=fail(str(exc.detail), code=exc.status_code),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content=fail("参数校验失败", code=422, data=exc.errors()),
    )


@app.exception_handler(Exception)
async def integrity_error_handler(request: Request, exc: Exception):
    name = exc.__class__.__name__
    msg = str(exc)
    low = msg.lower()
    # 数据库结构/连接类错误给出明确提示
    if name in ("ProgrammingError", "OperationalError", "InterfaceError", "DBAPIError"):
        if "unknown column" in low or "doesn't exist" in low or "unknown table" in low:
            logger.warning("数据库结构不完整: %s", exc)
            return JSONResponse(
                status_code=500,
                content=fail("数据库结构不完整：请执行 scripts/init_mysql.sql（建表）与 scripts/seed_data.sql（示例数据）后重启后端", code=500),
            )
        if any(k in low for k in ("can't connect", "refused", "server has gone away", "lost connection", "timed out", "access denied", "unknown database", "authentication")):
            logger.warning("数据库连接失败: %s", exc)
            return JSONResponse(
                status_code=500,
                content=fail(f"数据库连接失败（{name}）：请确认 MySQL 服务已启动，且 .env 中 DATABASE_URL 的账号/密码/库名正确", code=500),
            )
    if name == "IntegrityError":
        logger.warning("数据完整性错误: %s", exc)
        return JSONResponse(
            status_code=409,
            content=fail("操作失败：存在关联数据或唯一约束冲突，请先清理相关数据", code=409),
        )
    logger.exception("未处理异常: %s", exc)
    return JSONResponse(
        status_code=500,
        content=fail(f"服务器内部错误：{name}: {msg[:300]}", code=500),
    )


# 路由注册
for module in (auth, users, knowledge, qa, lesson, tutor, admin):
    app.include_router(module.router, prefix=settings.API_V1_PREFIX)


@app.get("/api/v1/health", tags=["系统"])
async def health():
    db_status = "ok"
    try:
        async with async_session_factory() as db:
            await db.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        db_status = f"error: {exc.__class__.__name__}: {str(exc)[:120]}"
    return {"code": 0, "message": "ok", "data": {"app": settings.APP_NAME, "db": db_status}}


@app.get("/", tags=["系统"])
async def root():
    return {"code": 0, "message": "AI 教育智能体后端服务运行中", "data": {"docs": "/docs"}}


# 静态文件（上传文件/头像访问）
uploads_dir = Path(settings.UPLOAD_DIR)
uploads_dir.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=uploads_dir), name="uploads")
