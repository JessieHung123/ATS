"""PDF 履歷文字擷取與基本 ATS 格式檢查。"""
import io
import re
from dataclasses import dataclass, field

import pdfplumber

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE_RE = re.compile(r"(\+?886[\s-]?|0)9\d{2}[\s-]?\d{3}[\s-]?\d{3}|\(?0\d{1,2}\)?[\s-]?\d{3,4}[\s-]?\d{4}")

# 擷取到的文字少於此字數，視為掃描圖片型 PDF（ATS 讀不到）
MIN_TEXT_CHARS = 80


@dataclass
class ParsedResume:
    filename: str
    text: str
    pages: int
    warnings: list[str] = field(default_factory=list)

    @property
    def readable(self) -> bool:
        return len(self.text.strip()) >= MIN_TEXT_CHARS


def parse_pdf(filename: str, data: bytes) -> ParsedResume:
    warnings = []
    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            pages = len(pdf.pages)
            text = "\n".join((page.extract_text() or "") for page in pdf.pages)
    except Exception as e:  # 損毀或加密的 PDF
        return ParsedResume(filename, "", 0, [f"無法讀取 PDF：{e}"])

    if len(text.strip()) < MIN_TEXT_CHARS:
        warnings.append("幾乎擷取不到文字，可能是掃描圖片型 PDF，一般 ATS 無法解析")
    else:
        if not EMAIL_RE.search(text):
            warnings.append("找不到 Email")
        if not PHONE_RE.search(text):
            warnings.append("找不到電話號碼")
        if pages > 3:
            warnings.append(f"履歷長達 {pages} 頁，建議精簡至 1–2 頁")
    return ParsedResume(filename, text, pages, warnings)
