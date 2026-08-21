"""轻量文本工具（无第三方依赖，便于单测直接导入）。"""


def norm_text(text: str) -> str:
    """内容归一化：去空白/转小写，用于判重。"""
    return "".join((text or "").strip().split()).lower()