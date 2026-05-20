from src.app.core.settings import settings
from src.app.kb.schemas import Chunk

# 文本切分函数，将文本切分成块
def split_text(text: str, chunk_size: int | None = None, overlap: int | None = None) -> list[Chunk]:
    if chunk_size is None:
        chunk_size = settings.KB_CHUNK_SIZE
    if overlap is None:
        overlap = settings.KB_CHUNK_OVERLAP

    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")
    chunks_list = []
    text_length = len(text)
    current_start = 0
    idx = 0
    # 判断是否已经将text切分完毕
    while current_start < text_length:
        start = current_start
        end = min(current_start + chunk_size, text_length)
        chunk_text = text[start:end]
        chunk = Chunk(chunk_id=str(idx), text=chunk_text, start=start, end=end, idx=idx)
        chunks_list.append(chunk)
        next_start = end -overlap
        if next_start <= current_start:
            next_start = end
        current_start = next_start
        idx += 1
        if end == text_length:
            break
    return chunks_list
