"""評分：規則式履歷分析（無 API 時）＋ 權重加總、門檻、缺口分析（永遠由這裡計算）。"""
import datetime as dt
import re

from ats.keywords import _pattern

from .matrix import DEGREE_ALIASES, DEGREES

GROUP_LABELS = {"skill": "專業技能", "experience": "專案經驗", "soft": "軟實力"}
IMPORTANCE_WEIGHT = {"必備": 2.0, "加分": 1.0}
LEVEL_TO_SCORE = {"green": 3, "yellow": 2, "red": 1, "info": 1}

EDU_LINE = re.compile(r"學系|大學|學士|碩士|博士|研究所|高中|高職|專科|university|college", re.I)
RANGE = re.compile(
    r"((?:19|20)\d{2})(?:\s*[./年-]\s*(\d{1,2}))?\s*[–—\-~～至到]+\s*"
    r"(?:((?:19|20)\d{2})(?:\s*[./年-]\s*(\d{1,2}))?|(至今|現在|present))",
    re.I,
)
EXPLICIT_YEARS = re.compile(r"(\d+(?:\.\d+)?)\s*年(?:以上)?(?:的)?(?:相關|工作)?(?:經驗|經歷)")


# ---------------- 規則式履歷分析 ----------------

def _matches(sentence: str, keywords: list[str]) -> bool:
    return any(k.strip() and _pattern(k).search(sentence) for k in keywords)


def rule_score_items(matrix: dict, sentences: list[dict]) -> list[dict]:
    items = []
    for comp in matrix["competencies"]:
        keywords = [comp["name"], *comp.get("keywords", [])]
        hits = [s for s in sentences if _matches(s["text"], keywords)]
        if not hits:
            items.append({"id": comp["id"], "score": 0, "evidence": [],
                          "reason": "履歷中找不到此職能或其同義詞"})
            continue
        best = max(hits, key=lambda s: LEVEL_TO_SCORE[s["level"]])
        score = LEVEL_TO_SCORE[best["level"]]
        reason = {
            3: "有句子同時具備行動、成果與量化數據",
            2: "有具體行動描述，但缺少成果或數字",
            1: "只在技能清單或空泛句中提到，缺乏佐證",
        }[score]
        hits.sort(key=lambda s: -LEVEL_TO_SCORE[s["level"]])
        items.append({"id": comp["id"], "score": score, "evidence": [h["text"] for h in hits[:3]],
                      "reason": f"（規則判斷）{reason}"})
    return items


def estimate_years(resume: str) -> float:
    explicit = [float(m.group(1)) for m in EXPLICIT_YEARS.finditer(resume)]
    today = dt.date.today()
    months = 0
    for line in resume.splitlines():
        if EDU_LINE.search(line):
            continue
        for m in RANGE.finditer(line):
            y1, m1 = int(m.group(1)), int(m.group(2) or 1)
            if m.group(5):
                y2, m2 = today.year, today.month
            else:
                y2, m2 = int(m.group(3)), int(m.group(4) or 12)
            months += max(0, (y2 - y1) * 12 + (m2 - m1))
    return round(max([months / 12, *explicit]), 1)


def highest_degree(resume: str) -> str:
    low = resume.lower()
    for degree in ["博士", "碩士", "學士", "專科", "高中"]:
        if any(alias in low for alias in DEGREE_ALIASES[degree]):
            return degree
    return "不限"


def rule_check_knockouts(matrix: dict, resume: str) -> list[dict]:
    out = []
    for ko in matrix["knockouts"]:
        if ko["kind"] == "years" and ko.get("min_years"):
            years = estimate_years(resume)
            if years == 0:
                out.append({"id": ko["id"], "status": "unknown", "evidence": "",
                            "reason": "履歷中找不到可計算的工作期間"})
            else:
                status = "met" if years >= ko["min_years"] else "not_met"
                out.append({"id": ko["id"], "status": status, "evidence": f"工作期間合計約 {years} 年",
                            "reason": f"（規則判斷）要求 {ko['min_years']} 年，估算 {years} 年"})
        elif ko["kind"] == "education" and ko.get("min_degree", "不限") != "不限":
            degree = highest_degree(resume)
            if degree == "不限":
                out.append({"id": ko["id"], "status": "unknown", "evidence": "", "reason": "履歷中找不到學歷資訊"})
            else:
                status = "met" if DEGREES.index(degree) >= DEGREES.index(ko["min_degree"]) else "not_met"
                out.append({"id": ko["id"], "status": status, "evidence": f"最高學歷：{degree}",
                            "reason": f"（規則判斷）要求 {ko['min_degree']} 以上"})
        else:
            hit = _matches(resume, [ko["name"], ko.get("requirement", "")])
            out.append({"id": ko["id"], "status": "met" if hit else "unknown",
                        "evidence": ko["name"] if hit else "",
                        "reason": "（規則判斷）此類門檻需人工或 AI 判斷"})
    return out


# ---------------- 權重加總（AI 或規則結果都走這裡） ----------------

def recommendation(total: float, eliminated: bool) -> str:
    if eliminated:
        return "淘汰（未達門檻）"
    if total >= 75:
        return "強烈建議面試"
    if total >= 60:
        return "建議面試"
    if total >= 40:
        return "待評估"
    return "不建議"


def compute(matrix: dict, weights: dict, analysis: dict) -> dict:
    scores = {i["id"]: i for i in analysis.get("items", [])}
    groups = {}
    missing_ids = []
    for comp in matrix["competencies"]:
        item = scores.get(comp["id"])
        if item is None:
            missing_ids.append(comp["id"])
        s = max(0, min(3, int(item["score"]))) if item else 0
        g = groups.setdefault(comp["group"], {"got": 0.0, "total": 0.0, "count": 0})
        w = IMPORTANCE_WEIGHT.get(comp["importance"], 1.0)
        g["got"] += w * s / 3
        g["total"] += w
        g["count"] += 1

    group_scores = {}
    for key in GROUP_LABELS:
        g = groups.get(key)
        group_scores[key] = round(g["got"] / g["total"] * 100, 1) if g and g["total"] else None

    active = {k: float(weights.get(k, 0)) for k, v in group_scores.items() if v is not None}
    weight_sum = sum(active.values())
    raw = sum(group_scores[k] * w for k, w in active.items()) / weight_sum if weight_sum else 0.0

    ko_results = {k["id"]: k for k in analysis.get("knockouts", [])}
    eliminated, penalty, ko_view = False, 0, []
    for ko in matrix["knockouts"]:
        res = ko_results.get(ko["id"], {"status": "unknown", "evidence": "", "reason": "尚未判斷"})
        effect = "—"
        if res["status"] == "not_met":
            if ko.get("mode") == "eliminate":
                eliminated, effect = True, "直接淘汰"
            else:
                penalty += int(ko.get("penalty", 0))
                effect = f"扣 {int(ko.get('penalty', 0))} 分"
        elif res["status"] == "unknown":
            effect = "待確認"
        ko_view.append({**res, "id": ko["id"], "name": ko["name"], "effect": effect})

    total = round(max(0.0, raw - penalty), 1)
    return {
        "raw_score": round(raw, 1),
        "penalty": penalty,
        "total": total,
        "eliminated": eliminated,
        "recommendation": recommendation(total, eliminated),
        "group_scores": group_scores,
        "effective_weights": {k: round(w / weight_sum * 100, 1) for k, w in active.items()} if weight_sum else {},
        "knockouts": ko_view,
        "gaps": gap_analysis(matrix, scores, ko_view),
        "stale": bool(missing_ids),
    }


def gap_analysis(matrix: dict, scores: dict, ko_view: list[dict]) -> list[dict]:
    gaps = []
    for comp in matrix["competencies"]:
        s = int(scores[comp["id"]]["score"]) if comp["id"] in scores else 0
        if s <= 1:
            gaps.append({
                "id": comp["id"], "name": comp["name"], "importance": comp["importance"],
                "group": GROUP_LABELS.get(comp["group"], comp["group"]), "score": s,
                "issue": "履歷未提及" if s == 0 else "有提及但沒有具體佐證",
            })
    gaps.sort(key=lambda g: (g["importance"] != "必備", g["score"]))
    for ko in ko_view:
        if ko["status"] in ("not_met", "unknown"):
            gaps.insert(0, {"id": ko["id"], "name": ko["name"], "importance": "門檻", "group": "門檻條件",
                            "score": None, "issue": "未達門檻" if ko["status"] == "not_met" else "履歷無法確認"})
    return gaps
