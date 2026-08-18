"""★ 本地向量化服务封装（核心）。

- 启动时把本地嵌入模型（HuggingFace，如 BAAI/bge-m3）加载进内存。
- 提供 encode(texts) / aencode(texts) 方法。
- 若模型未下载或无网络，自动降级为确定性哈希向量，保证断网环境下
  知识库入库与检索全流程仍然可运行（仅演示用，语义质量较低）。
- CPU 推理较慢：所有调用方必须使用 aencode()，内部通过
  fastapi.concurrency.run_in_threadpool 包裹，避免阻塞事件循环。
"""
import hashlib
import logging
import math
import threading
from typing import List, Optional

from fastapi.concurrency import run_in_threadpool

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    def __init__(
        self,
        model_name: Optional[str] = None,
        device: Optional[str] = None,
        dimension: Optional[int] = None,
    ):
        self.model_name = model_name or settings.EMBEDDING_MODEL_NAME
        self.device = device or settings.EMBEDDING_DEVICE
        self.dimension = dimension or settings.EMBEDDING_DIM
        self._model = None
        self._model_lock = threading.Lock()
        self._load_error: Optional[str] = None

    def load(self) -> bool:
        """加载本地嵌入模型至内存。失败时降级为哈希向量并返回 False。"""
        with self._model_lock:
            if self._model is not None:
                return True
            try:
                from sentence_transformers import SentenceTransformer

                logger.info(
                    "正在加载本地嵌入模型: %s (device=%s)", self.model_name, self.device
                )
                self._model = SentenceTransformer(self.model_name, device=self.device)
                probe = self._model.encode(["测试"])
                if probe is not None and len(probe) > 0:
                    self.dimension = len(probe[0])
                logger.info(
                    "嵌入模型加载成功，向量维度=%s", self.dimension
                )
                return True
            except Exception as exc:  # noqa: BLE001
                self._load_error = f"{type(exc).__name__}: {exc}"
                logger.warning(
                    "本地嵌入模型加载失败，降级为哈希向量（可离线运行）: %s",
                    self._load_error,
                )
                return False

    def is_model_loaded(self) -> bool:
        return self._model is not None

    def encode(self, texts: List[str]) -> List[List[float]]:
        """同步编码（CPU 密集）。请使用 aencode() 以避免阻塞事件循环。"""
        if not texts:
            return []
        if self._model is not None:
            vectors = self._model.encode(
                texts, normalize_embeddings=True, show_progress_bar=False
            )
            return [v.tolist() for v in vectors]
        return [self._hash_embed(t) for t in texts]

    async def aencode(self, texts: List[str]) -> List[List[float]]:
        """异步编码：内部使用 run_in_threadpool 包裹，不阻塞事件循环。"""
        if not texts:
            return []
        return await run_in_threadpool(self.encode, texts)

    def _hash_embed(self, text: str) -> List[float]:
        """确定性哈希向量：字符 n-gram + TF 加权 + L2 归一化（降级方案）。"""
        dim = self.dimension
        vec = [0.0] * dim
        lowered = text.lower()
        for n in (1, 2, 3):
            for i in range(len(lowered) - n + 1):
                gram = lowered[i : i + n]
                h = int(hashlib.md5(gram.encode("utf-8")).hexdigest()[:8], 16)
                vec[h % dim] += 1.0 if (h >> 8) & 1 else -1.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]


# 全局单例：FastAPI 启动时调用 load() 预加载
embedding_service = EmbeddingService()