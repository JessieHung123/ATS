"""關鍵字比對：傳統 ATS 的核心邏輯，結果可解釋、不需 API。"""
import re
from collections import Counter
from dataclasses import dataclass

IMPORTANCE_WEIGHT = {"必要": 2.0, "加分": 1.0}

_STOPWORDS = {
    "and", "or", "the", "a", "an", "to", "of", "in", "for", "with", "on", "at", "by", "is",
    "are", "be", "as", "we", "you", "our", "your", "will", "this", "that", "from", "have",
    "has", "able", "need", "must", "plus", "experience", "years", "year", "team", "work", "skills", "strong", "good",
}


@dataclass
class Keyword:
    term: str
    synonyms: list[str]
    importance: str  # "必要" | "加分"

    @property
    def weight(self) -> float:
        return IMPORTANCE_WEIGHT.get(self.importance, 1.0)

    def variants(self) -> list[str]:
        return [v for v in [self.term, *self.synonyms] if v.strip()]


def _pattern(term: str) -> re.Pattern:
    escaped = re.escape(term.strip())
    # 英數詞要整字比對（避免 "R" 命中 "React"）；中文直接子字串比對
    if re.fullmatch(r"[\w.+#\- ]+", term.strip(), re.ASCII):
        return re.compile(rf"(?<![A-Za-z0-9]){escaped}(?![A-Za-z0-9])", re.IGNORECASE)
    return re.compile(escaped, re.IGNORECASE)


def match_keywords(text: str, keywords: list[Keyword]) -> tuple[float, list[str], list[str]]:
    """回傳 (關鍵字分數 0–100, 命中清單, 缺少清單)。"""
    if not keywords:
        return 0.0, [], []
    matched, missing = [], []
    got = total = 0.0
    for kw in keywords:
        total += kw.weight
        if any(_pattern(v).search(text) for v in kw.variants()):
            matched.append(kw.term)
            got += kw.weight
        else:
            missing.append(kw.term)
    return round(got / total * 100, 1), matched, missing


def naive_extract(jd: str, top_n: int = 15) -> list[Keyword]:
    """沒有 API key 時的備案：抓 JD 中重複出現的英數專有名詞，再由使用者手動增修。"""
    tokens = (t.strip(".-") for t in re.findall(r"[A-Za-z][A-Za-z0-9.+#\-]*", jd))
    # 專有名詞多為大寫開頭或縮寫，全小寫的一般英文字略過
    counts = Counter(t for t in tokens if t[:1].isupper() and t.lower() not in _STOPWORDS and len(t) > 1)
    return [Keyword(term, [], "加分") for term, _ in counts.most_common(top_n)]
