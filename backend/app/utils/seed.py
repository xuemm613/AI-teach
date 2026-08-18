"""启动种子数据：确保存在默认管理员账号。"""
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_factory
from app.core.security import hash_password
from app.models.models import User

logger = logging.getLogger(__name__)

DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "admin123"


async def ensure_default_admin() -> None:
    """若系统中不存在任何管理员，则创建默认管理员 admin/admin123。"""
    async with async_session_factory() as db:
        result = await db.execute(select(User).where(User.role == "admin").limit(1))
        admin = result.scalar_one_or_none()
        if admin is not None:
            return
        user = User(
            username=DEFAULT_ADMIN_USERNAME,
            password_hash=hash_password(DEFAULT_ADMIN_PASSWORD),
            full_name="系统管理员",
            role="admin",
            is_active=True,
        )
        db.add(user)
        await db.commit()
        logger.info("已创建默认管理员账号: %s / %s", DEFAULT_ADMIN_USERNAME, DEFAULT_ADMIN_PASSWORD)