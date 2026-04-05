# src/ai/pdf_loader.py
import os
import re
from pypdf import PdfReader

def extract_text_from_pdf(pdf_path: str, max_chars: int = 8000) -> list[dict]:
    """
    提取PDF文本，按页分段，并做基础清洗
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF文件不存在: {pdf_path}")

    reader = PdfReader(pdf_path)
    pages = []

    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        # 清洗：合并多余换行，去除纯空白行
        text = re.sub(r'\n\s*\n', '\n', text).strip()
        if len(text) > max_chars:
            text = text[:max_chars] + "\n...(超长内容已截断，实际项目将接入语义分段)"

        pages.append({
            "page_num": i + 1,
            "content": text,
            "char_count": len(text)
        })

    return pages
