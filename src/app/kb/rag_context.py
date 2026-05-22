from src.app.kb.schemas import Hit
from src.app.llm.schemas import Citation

# 构建RAG上下文 + 生成引用列表
def build_rag_context(hits: list[Hit], max_chars: int = 3000) -> tuple[str, list[Citation]]:
    """
    拼接RAG检索结果为上下文文本，并生成引用列表
    :param hit: 检索命中结果列表，每个元素包含内容文本，文档元数据
    :param max_chars: 最大字符长度，防止prompt过长
    :return: 拼接后的上下文文本，引用列表
    """
    if not hits:
        return "", []

    context_parts = []
    citations = []
    total_length = 0

    for idx, hit in enumerate(hits, start=1):
        chunk_text = hit.text
        citation_header = f"[{idx}] (doc_id={hit.doc_id}, chunk_id={hit.chunk_id}, source={hit.source}, title={hit.title})"
        chunk_content = f"{citation_header}\n{chunk_text}\n"

        if total_length + len(chunk_content) > max_chars:
            remaining = max_chars - total_length
            if remaining > 0:
                context_parts.append(chunk_content[:remaining])
            break

        context_parts.append(chunk_content)
        total_length += len(chunk_content)

        # 构建引用列表
        citations.append(Citation(
            doc_id = hit.doc_id,
            chunk_id = hit.chunk_id,
            source = hit.source,
            title = hit.title
        ))

    final_context = "".join(context_parts)
    return final_context, citations