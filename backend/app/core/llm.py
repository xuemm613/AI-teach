"""大模型调用封装：兼容 OpenAI API 接口的第三方模型。

通过环境变量 LLM_API_BASE / LLM_API_KEY / LLM_MODEL_NAME 灵活切换
（DeepSeek、通义千问、智谱 GLM 等）。
"""
import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

from openai import AsyncOpenAI

from app.core.config import settings

logger = logging.getLogger(__name__)


def parse_json(text: str) -> Any:
    """稳健解析模型输出的 JSON（支持 markdown 代码块包裹 / 前后杂质）。"""
    if not text:
        raise ValueError("模型返回为空，无法解析 JSON")
    text = text.strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except Exception:
            pass
    raise ValueError("无法将模型输出解析为 JSON")


def extract_sql(text: str) -> str:
    """从模型输出中提取 SQL 语句。"""
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("sql"):
            text = text[3:]
        text = text.strip()
    # 取第一个 SELECT / WITH 到结尾
    lower = text.lower()
    start = lower.find("select")
    if start == -1:
        start = lower.find("with")
    if start == -1:
        raise ValueError("模型未生成有效 SQL")
    return text[start:].strip()


class LLMClient:
    """OpenAI 兼容异步客户端。"""

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self.base_url = (base_url or settings.LLM_API_BASE).rstrip("/")
        self.api_key = api_key or settings.LLM_API_KEY
        self.model = model or settings.LLM_MODEL_NAME
        self._client: Optional[AsyncOpenAI] = None

    def _get_client(self) -> AsyncOpenAI:
        if self._client is None:
            self._client = AsyncOpenAI(
                base_url=self.base_url,
                api_key=self.api_key,
                timeout=settings.LLM_TIMEOUT,
                max_retries=2,
            )
        return self._client

    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        json_mode: bool = False,
        max_tokens: int = 2048,
    ) -> str:
        """普通对话，返回文本。json_mode=True 时要求模型输出 JSON 对象。"""
        kwargs: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": settings.LLM_TEMPERATURE if temperature is None else temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        # 大模型偶发返回空内容或网络抖动：自动重试
        last_error = "未知错误"
        for attempt in range(3):
            try:
                resp = await self._get_client().chat.completions.create(**kwargs)
                content = (resp.choices[0].message.content or "").strip()
                if content:
                    return content
                last_error = "模型返回空内容"
                logger.warning("LLM 返回空内容（第 %s 次），重试中", attempt + 1)
            except Exception as exc:
                last_error = str(exc)
                logger.warning("LLM 调用失败（第 %s 次）: %s", attempt + 1, exc)
            await asyncio.sleep(1)
        raise RuntimeError(f"大模型调用失败：{last_error}")

    async def chat_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: int = 2048,
    ):
        """流式对话：逐段产出文本（async generator），供 SSE 流式接口使用。"""
        kwargs: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": settings.LLM_TEMPERATURE if temperature is None else temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        stream = await self._get_client().chat.completions.create(**kwargs)
        async for chunk in stream:
            delta = chunk.choices[0].delta
            if delta and delta.content:
                yield delta.content

    async def chat_json(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: int = 2048,
    ) -> Dict[str, Any]:
        """要求模型输出严格 JSON 并解析返回 dict。"""
        text = await self.chat(
            messages, temperature=temperature, json_mode=True, max_tokens=max_tokens
        )
        return parse_json(text)


llm_client = LLMClient()
