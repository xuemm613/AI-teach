"""Milvus Lite 封装：本地 .db 文件即向量数据库，无需独立 Docker 服务。

集合字段：id (INT64 主键自增), content (VARCHAR), metadata (JSON),
embedding (FLOAT_VECTOR)。
- 集合不存在时自动创建；维度变化时自动重建。
- 若 pymilvus / milvus-lite 不可用（如平台不支持），自动降级为
  LocalVectorStore（JSON 持久化 + 余弦检索），保证断网/离线环境全流程可运行。
"""
import json
import logging
import math
import re
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

try:  # pymilvus 与 milvus-lite 为可选依赖（降级方案不需要）
    from pymilvus import DataType, MilvusClient  # type: ignore
    PYMILVUS_AVAILABLE = True
except Exception:  # noqa: BLE001
    DataType = None
    MilvusClient = None
    PYMILVUS_AVAILABLE = False
    logger.warning("pymilvus 不可用，将使用本地简易向量存储（LocalVectorStore）")


def _cosine(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    return dot / (na * nb) if na and nb else 0.0


class LocalVectorStore:
    """milvus-lite 不可用时的降级向量存储（JSON 持久化 + 暴力余弦检索）。"""

    def __init__(self, db_path: str, collection: str, dimension: int):
        self.collection = collection
        self.dimension = dimension
        self._db_path = Path(db_path)
        self._data_file = self._db_path.with_suffix(".local_store.json")
        self._rows: List[Dict[str, Any]] = []
        self._next_id = 1
        self._lock = threading.Lock()
        self._load()

    def _load(self) -> None:
        try:
            if self._data_file.exists():
                data = json.loads(self._data_file.read_text(encoding="utf-8"))
                self._rows = data.get("rows", [])
                self._next_id = data.get("next_id", 1)
        except Exception as exc:  # noqa: BLE001
            logger.warning("加载本地向量存储失败（重置）: %s", exc)
            self._rows = []
            self._next_id = 1

    def _save(self) -> None:
        self._data_file.parent.mkdir(parents=True, exist_ok=True)
        self._data_file.write_text(
            json.dumps({"next_id": self._next_id, "rows": self._rows}, ensure_ascii=False),
            encoding="utf-8",
        )

    def ensure_collection(self, dim: int) -> bool:
        created = not self._rows
        self.dimension = dim
        return created

    def insert(self, contents, embeddings, metadata) -> List[int]:
        with self._lock:
            ids = []
            for content, emb, meta in zip(contents, embeddings, metadata):
                row = {
                    "id": self._next_id,
                    "content": content,
                    "metadata": meta,
                    "embedding": emb,
                }
                self._rows.append(row)
                ids.append(self._next_id)
                self._next_id += 1
            self._save()
        return ids

    def search(self, vector, top_k, expr=None) -> List[Dict[str, Any]]:
        with self._lock:
            scored = []
            for row in self._rows:
                if expr:
                    m = re.match(r'metadata\["([^"]+)"\]\s*==\s*"?([^"]*)"?', expr)
                    if m:
                        key, value = m.group(1), m.group(2)
                        if str(row.get("metadata", {}).get(key, "")) != str(value):
                            continue
                scored.append((_cosine(vector, row["embedding"]), row))
            scored.sort(key=lambda t: t[0], reverse=True)
            return [
                {
                    "id": row["id"],
                    "score": round(score, 6),
                    "content": row["content"],
                    "metadata": row.get("metadata", {}),
                }
                for score, row in scored[:top_k]
            ]

    def count(self) -> int:
        return len(self._rows)

    def delete_by_metadata(self, key: str, value: Any) -> int:
        with self._lock:
            before = len(self._rows)
            self._rows = [r for r in self._rows if str(r.get("metadata", {}).get(key, "")) != str(value)]
            removed = before - len(self._rows)
            if removed:
                self._save()
            return removed

    def list_chunks(self, limit: int = 100) -> List[Dict[str, Any]]:
        return [
            {"id": r["id"], "content": r["content"], "metadata": r.get("metadata", {})}
            for r in self._rows[:limit]
        ]


class MilvusLiteClient:
    def __init__(
        self,
        uri: Optional[str] = None,
        collection: Optional[str] = None,
    ):
        self.uri = uri or settings.MILVUS_URI
        self.collection = collection or settings.MILVUS_COLLECTION
        self._client: Optional[Any] = None
        self._fallback: Optional[LocalVectorStore] = None
        self._fallback_lock = threading.Lock()

    # ---------- 底层客户端 ----------
    def get_client(self) -> Any:
        if not PYMILVUS_AVAILABLE:
            return self._get_fallback()
        if self._client is None:
            self._client = MilvusClient(self.uri)
        return self._client

    def _get_fallback(self) -> LocalVectorStore:
        with self._fallback_lock:
            if self._fallback is None:
                self._fallback = LocalVectorStore(self.uri, self.collection, settings.EMBEDDING_DIM)
                logger.warning(
                    "使用本地简易向量存储 LocalVectorStore（文件: %s）",
                    self._fallback._data_file,
                )
            return self._fallback

    def is_fallback(self) -> bool:
        return self._fallback is not None or not PYMILVUS_AVAILABLE

    # ---------- 集合管理 ----------
    def _collection_dim(self) -> Optional[int]:
        try:
            info = self.get_client().describe_collection(self.collection)
            for field in info.get("fields", []):
                if field.get("name") == "embedding":
                    return field["params"]["dim"]
        except Exception:  # noqa: BLE001
            return None
        return None

    def ensure_collection(self, dim: int) -> bool:
        """确保集合存在（不存在则自动创建）。返回 True 表示本次新建。"""
        if self.is_fallback():
            return self._get_fallback().ensure_collection(dim)

        client = self.get_client()
        if client.has_collection(self.collection):
            current_dim = self._collection_dim()
            if current_dim is not None and current_dim != dim:
                logger.warning(
                    "集合 %s 维度 %s 与当前模型维度 %s 不一致，重建集合",
                    self.collection, current_dim, dim,
                )
                client.drop_collection(self.collection)
            else:
                logger.info("Milvus 集合已存在: %s (dim=%s)", self.collection, current_dim)
                return False

        schema = MilvusClient.create_schema(auto_id=True, enable_dynamic_field=False)
        schema.add_field(field_name="id", datatype=DataType.INT64, is_primary=True, auto_id=True)
        schema.add_field(field_name="content", datatype=DataType.VARCHAR, max_length=65535)
        schema.add_field(field_name="metadata", datatype=DataType.JSON)
        schema.add_field(field_name="embedding", datatype=DataType.FLOAT_VECTOR, dim=dim)

        index_params = MilvusClient.prepare_index_params()
        index_params.add_index(field_name="embedding", index_type="AUTOINDEX", metric_type="COSINE")

        client.create_collection(collection_name=self.collection, schema=schema, index_params=index_params)
        logger.info("已自动创建 Milvus 集合 %s (dim=%s)", self.collection, dim)
        return True

    # ---------- 数据操作 ----------
    def insert(self, contents, embeddings, metadata) -> List[int]:
        if self.is_fallback():
            return self._get_fallback().insert(contents, embeddings, metadata)
        rows = [
            {"content": c, "metadata": m, "embedding": e}
            for c, m, e in zip(contents, embeddings, metadata)
        ]
        if not rows:
            return []
        res = self.get_client().insert(collection_name=self.collection, data=rows)
        return res.get("ids", [])

    def search(self, vector, top_k: int = settings.RAG_TOP_K, expr: Optional[str] = None) -> List[Dict[str, Any]]:
        if self.is_fallback():
            return self._get_fallback().search(vector, top_k, expr)
        params: Dict[str, Any] = {
            "collection_name": self.collection,
            "data": [vector],
            "limit": top_k,
            "output_fields": ["content", "metadata"],
        }
        if expr:
            params["filter"] = expr
        res = self.get_client().search(**params)
        hits = res[0] if res else []
        result = []
        for hit in hits:
            entity = hit.get("entity") or {}
            result.append(
                {
                    "id": hit.get("id"),
                    "score": float(hit.get("distance", 0.0)),
                    "content": entity.get("content", ""),
                    "metadata": entity.get("metadata", {}),
                }
            )
        return result

    def count(self) -> int:
        if self.is_fallback():
            return self._get_fallback().count()
        return self.get_client().get_collection_stats(self.collection).get("row_count", 0)

    def delete_by_metadata(self, key: str, value: Any) -> int:
        """按 metadata 字段删除（如 file_key），用于删除某文件的所有分块。"""
        if self.is_fallback():
            return self._get_fallback().delete_by_metadata(key, value)
        filter_expr = f'{key} == "{value}"'
        try:
            res = self.get_client().delete(collection_name=self.collection, filter=filter_expr)
            return len(res) if res else 0
        except Exception as exc:  # noqa: BLE001
            logger.warning("按 metadata 删除失败（%s），请手动清理: %s", filter_expr, exc)
            return 0

    def list_chunks(self, limit: int = 100) -> List[Dict[str, Any]]:
        if self.is_fallback():
            return self._get_fallback().list_chunks(limit)
        res = self.get_client().query(
            collection_name=self.collection,
            filter="",
            output_fields=["id", "content", "metadata"],
            limit=limit,
        )
        return list(res)


# 全局单例
milvus_client = MilvusLiteClient()