"""灵声 VoiceForge - 文档解析（txt / docx / pdf）"""
from __future__ import annotations

import io


def parse_text(data: bytes) -> str:
    """txt：自动识别编码（UTF-8 / GBK / GB18030 / UTF-16 / latin-1 兜底）"""
    for enc in ("utf-8", "gb18030", "utf-16", "big5"):
        try:
            return data.decode(enc)
        except (UnicodeDecodeError, ValueError):
            continue
    return data.decode("latin-1", errors="replace")


def parse_docx(data: bytes) -> str:
    """docx：按段落提取文本"""
    from docx import Document
    try:
        doc = Document(io.BytesIO(data))
        paras = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
        # 表格内容也纳入
        for table in doc.tables:
            for row in table.rows:
                cells = [c.text.strip() for c in row.cells if c.text.strip()]
                if cells:
                    paras.append("，".join(cells))
        return "\n".join(paras)
    except Exception as e:
        raise ValueError("文件格式无效或已损坏（docx 解析失败）") from e


def parse_pdf(data: bytes) -> str:
    """pdf：提取文本层（扫描件无法提取，返回提示）"""
    from pypdf import PdfReader
    try:
        reader = PdfReader(io.BytesIO(data))
        pages = []
        for page in reader.pages:
            t = page.extract_text() or ""
            if t.strip():
                pages.append(t.strip())
        return "\n\n".join(pages)
    except Exception as e:
        raise ValueError("文件格式无效或已损坏（pdf 解析失败）") from e


def parse_file(filename: str, data: bytes) -> str:
    """FIX-021：magic bytes 优先嗅探，扩展名兜底，防止改名绕过类型校验。"""
    if not data:
        raise ValueError("文件内容为空")
    # PDF: %PDF
    if data[:4] == b"%PDF":
        return parse_pdf(data)
    # docx/zip: PK\x03\x04（也可能是普通 zip）
    if data[:2] == b"PK":
        try:
            return parse_docx(data)
        except ValueError:
            # 是 zip 但不是合法 docx，落到扩展名/文本兜底
            pass
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext == "docx":
        return parse_docx(data)
    if ext == "pdf":
        return parse_pdf(data)
    return parse_text(data)
