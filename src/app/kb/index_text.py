import re

def extract_index_text(raw_text: str) -> str:
    """
    KB 标准化文本预处理：抽取用于向量索引的纯净文本
    规则：
    1. 统一换行符：\r\n → \n
    2. 优先按 --- 截断（取第一个分段）
    3. 无 --- 则按指定标题截断：# Keywords / # QA Seeds / # Appendix / # Changelog
    4. 返回清理后的索引文本（用于切块、嵌入、向量入库）
    """
    if not raw_text:
        return ""

    text = raw_text.replace("\r\n", "\n")

    m = re.search(r'(?m)^\s*---\s*$', text)
    if m:
        text = text[:m.start()]

    pattern = re.compile(r'(?mi)^\s*#\s*(Keywords|QA Seeds|Appendix|Changelog)\b')
    match = pattern.search(text)
    if match:
        text = text[:match.start()]

    return text.strip()