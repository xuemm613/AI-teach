"""全局配置：从环境变量 / .env 读取。"""
from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # 应用
    APP_NAME: str = "AI教育智能备课与个性化学习辅导智能体"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"

    # JWT
    SECRET_KEY: str = "change-me-in-production-please"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24      # 24 小时
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # MySQL（aiomysql 异步驱动）
    DATABASE_URL: str = "mysql+aiomysql://root:password@localhost:3306/ai_edu?charset=utf8mb4"

    # Milvus Lite：本地 .db 文件即向量数据库，无需 Docker
    MILVUS_URI: str = "./milvus_data.db"
    MILVUS_COLLECTION: str = "knowledge_chunks"

    # 本地嵌入模型（HuggingFace sentence-transformers）
    EMBEDDING_MODEL_NAME: str = "BAAI/bge-m3"
    EMBEDDING_DIM: int = 1024          # 仅在降级哈希向量时使用，真实模型维度加载后自动探测
    EMBEDDING_DEVICE: str = "cpu"

    # 大模型 API（兼容 OpenAI 接口，如 DeepSeek / 通义千问 / 智谱 GLM）
    LLM_API_BASE: str = "https://api.deepseek.com/v1"
    LLM_API_KEY: str = "sk-xxxx"
    LLM_MODEL_NAME: str = "deepseek-chat"
    LLM_TEMPERATURE: float = 0.3
    LLM_TIMEOUT: int = 120

    # RAG
    RAG_TOP_K: int = 5
    RAG_SCORE_THRESHOLD: float = 0.35   # 检索最高分低于该值则拒答
    RAG_RE_RANK: bool = False           # 重排序开关（可选，默认关闭）

    # 文本切分
    CHUNK_SIZE: int = 800               # 块大小（字符数，约 500~1000 tokens）
    CHUNK_OVERLAP: int = 100            # 块重叠

    # 文件存储
    UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_SIZE_MB: int = 50

    # 跨域
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    @property
    def upload_dir(self) -> Path:
        return Path(self.UPLOAD_DIR)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()