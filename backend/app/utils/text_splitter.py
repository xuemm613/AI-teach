"""文本切分：递归字符切分（RecursiveCharacterTextSplitter 兼容实现）。

块大小 500~1000 tokens（中文按字符数约 800），重叠 100 字符。
"""
from typing import Dict, List, Optional

from app.utils.document_parser import PageContent


class RecursiveCharacterTextSplitter:
    """递归字符切分器：按分隔符优先级递归切分，控制块大小与重叠。"""

    def __init__(
        self,
        chunk_size: int = 800,
        chunk_overlap: int = 100,
        separators: Optional[List[str]] = None,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = separators or [
            "\n\n", "\n", "。", "！", "？", "；", "，", " ", ""
        ]

    def split_text(self, text: str) -> List[str]:
        text = (text or "").strip()
        if not text:
            return []
        return self._split(text, self.separators)

    def _split(self, text: str, separators: List[str]) -> List[str]:
        if len(text) <= self.chunk_size:
            return [text]

        # 选择第一个出现在文本中的分隔符（优先级从高到低）
        sep = ""
        for s in separators:
            if s and s in text:
                sep = s
                break

        pieces = text.split(sep) if sep else list(text)

        chunks: List[str] = []
        current = ""
        for piece in pieces:
            if current == "":
                current = piece
                continue
            sep_len = len(sep) if sep else 0
            if len(current) + sep_len + len(piece) > self.chunk_size:
                chunks.append(current)
                overlap = current[-self.chunk_overlap:] if self.chunk_overlap > 0 else ""
                current = overlap + (sep + piece if sep else piece)
            else:
                current = current + (sep + piece if sep else piece)
        if current:
            chunks.append(current)

        # 仍超大的块继续递归（降级分隔符优先级）
        result: List[str] = []
        for chunk in chunks:
            if len(chunk) > self.chunk_size:
                next_seps = separators[:-1] if len(separators) > 1 else separators
                result.extend(self._split(chunk, next_seps))
            else:
                result.append(chunk)
        return [c for c in result if c]


def split_document(
    pages: List[PageContent],
    splitter: RecursiveCharacterTextSplitter,
    filename: str,
) -> List[Dict]:
    """将整份文档切分为带元数据（文件名/页码）的块。"""
    chunks: List[Dict] = []
    idx = 0
    for page in pages:
        if not (page.text or "").strip():
            continue
        for chunk in splitter.split_text(page.text):
            chunks.append(
                {
                    "content": chunk,
                    "metadata": {
                        "filename": filename,
                        "page": page.page,
                        "chunk_index": idx,
                    },
                }
            )
            idx += 1
    return chunks