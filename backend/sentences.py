"""「動詞 + 成果 + 量化數據」偵測器：逐句分類為 green / yellow / red / info。

規則式、可解釋、不需 API，學生可以直接看到每句為什麼被判成某個顏色。
"""
import re

ACTION_VERBS = [
    "優化", "提升", "建立", "建置", "設計", "開發", "導入", "規劃", "主導", "帶領", "領導", "執行", "分析",
    "推動", "整合", "撰寫", "策劃", "企劃", "改善", "降低", "縮短", "增加", "達成", "完成", "協調", "管理",
    "拓展", "談判", "重構", "部署", "自動化", "訓練", "籌辦", "舉辦", "經營", "製作", "簡化", "架設", "實作",
    "串聯", "說服", "爭取", "創立", "發起", "改造", "精簡", "研發", "測試", "評估", "簡報", "預測", "上線",
    "led", "built", "designed", "developed", "improved", "increased", "reduced", "launched", "implemented",
    "created", "managed", "optimized", "analyzed", "automated", "delivered", "drove", "established",
]
RESULT_WORDS = [
    "提升", "增加", "成長", "降低", "減少", "縮短", "節省", "達成", "達到", "突破", "帶來", "創造", "獲得",
    "挽回", "下降", "上升", "超過", "累計", "覆蓋", "轉換率", "營收", "效率", "成本", "獲獎", "第一名", "使", "讓", "達", "降至", "提高", "從",
    "increase", "reduce", "result", "saved", "grew", "growth", "improv",
]
# 含成果字但不是成果的常見詞（「使用」的「使」、「表達」的「達」）
FALSE_RESULT = re.compile(r"使用|表達|傳達|送達|從事")
VAGUE_WORDS = ["負責", "協助", "參與", "相關", "業務", "處理", "配合", "支援", "等工作", "日常", "熟悉", "具備", "幫忙"]

SECTION_HEADERS = {
    "學歷", "經歷", "工作經歷", "工作經驗", "技能", "專長", "證照", "自傳", "聯絡資訊", "個人資料", "專案",
    "專案經驗", "社團經歷", "語言能力", "得獎", "獲獎", "education", "experience", "skills", "projects",
}
LABEL_PREFIX = re.compile(r"^(技能|專長|證照|語言|工具|Email|E-mail|電話|地址|Skills?)\s*[:：]", re.I)
CONTACT = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+|09\d{2}[\s-]?\d{3}[\s-]?\d{3}")
# 日期與年份不算「量化成果」
DATE = re.compile(r"(19|20)\d{2}\s*([./年-]\s*\d{1,2}\s*月?)?|\d{1,2}\s*月|至今|現在")
NUMBER = re.compile(r"\d|[一二三四五六七八九十百千萬兩]+\s*(倍|成|位|人|場|件|萬|個|次|家)|[%％]")
EDU_MARK = re.compile(r"學系|學士|碩士|博士|研究所|高中|高職|university|college", re.I)
SELF_PRAISE = re.compile(r"能力(佳|強|好)|精神|個性|熱愛|抗壓性|願意學習|有興趣|積極|認真負責")
BULLET = re.compile(r"^\s*([-•·●▪*‧]|\d+[.、)])\s*")
SPLIT = re.compile(r"(?<=[。；;!！?？])")


def _contains(text: str, words: list[str]) -> list[str]:
    low = text.lower()
    return [w for w in words if w.lower() in low]


def split_sentences(resume: str) -> list[str]:
    out = []
    for line in resume.splitlines():
        line = line.strip()
        if not line:
            continue
        for part in SPLIT.split(line):
            part = part.strip()
            if part:
                out.append(part)
    return out


def classify(sentence: str) -> dict:
    body = BULLET.sub("", sentence).strip()
    plain = body.rstrip("。；;.")
    base = {"text": sentence, "verbs": [], "results": [], "has_number": False, "vague": []}

    has_verb = bool(_contains(plain, ACTION_VERBS))
    parts = [x for x in re.split(r"[、,/]", plain) if x.strip()]
    is_list = len(parts) >= 3 and not re.search(r"[，。]", plain) and all(len(x.strip()) <= 20 for x in parts)
    if (
        plain.lower() in SECTION_HEADERS
        or LABEL_PREFIX.match(plain)
        or CONTACT.search(plain)
        or (("｜" in plain or "|" in plain) and DATE.search(plain))
        or (EDU_MARK.search(plain) and (DATE.search(plain) or not has_verb))
        or (len(plain) <= 12 and not has_verb and not _contains(plain, VAGUE_WORDS))
    ):
        return {**base, "level": "info", "reason": "標題、聯絡資訊、學歷或職稱列，不納入判斷"}
    if is_list:
        return {**base, "level": "info", "reason": "技能清單：只列名詞，視為「有提及但無佐證」"}

    if SELF_PRAISE.search(plain) and not NUMBER.search(DATE.sub("", plain)):
        return {**base, "level": "red", "reason": "自我形容（如「溝通能力佳」），沒有事例佐證；改寫成一次具體經驗"}

    verbs = _contains(plain, ACTION_VERBS)
    results = _contains(FALSE_RESULT.sub("", plain), RESULT_WORDS)
    vague = _contains(plain, VAGUE_WORDS)
    has_number = bool(NUMBER.search(DATE.sub("", plain)))
    info = {**base, "verbs": verbs, "results": results, "has_number": has_number, "vague": vague}

    if any(plain.startswith(v) for v in VAGUE_WORDS) and not has_number:
        return {**info, "level": "red",
                "reason": f"以「{vague[0]}」開頭的空泛描述，看不出你個人做了什麼；改用具體動詞＋成果＋數字"}
    if verbs and results and has_number:
        return {**info, "level": "green", "reason": f"完整：有動作（{verbs[0]}）、有成果、有量化數據"}
    if verbs:
        missing = []
        if not results:
            missing.append("成果")
        if not has_number:
            missing.append("量化數據")
        return {**info, "level": "yellow",
                "reason": f"有動作（{verbs[0]}），但缺少{'與'.join(missing)}；可補上「使…提升／縮短 X%」"}
    if vague:
        return {**info, "level": "red",
                "reason": f"空泛描述（{'、'.join(vague[:3])}），看不出你做了什麼；改用具體動詞＋成果＋數字"}
    return {**info, "level": "red", "reason": "沒有具體行動動詞，難以判斷貢獻"}


def analyze_sentences(resume: str) -> dict:
    sentences = [classify(s) for s in split_sentences(resume)]
    stats = {k: sum(1 for s in sentences if s["level"] == k) for k in ("green", "yellow", "red", "info")}
    judged = stats["green"] + stats["yellow"] + stats["red"]
    stats["quality"] = round((stats["green"] + 0.5 * stats["yellow"]) / judged * 100) if judged else 0
    return {"sentences": sentences, "stats": stats}
