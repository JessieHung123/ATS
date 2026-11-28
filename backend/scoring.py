"""評分：規則式履歷分析（無 API 時）＋ 權重加總、門檻、缺口分析（永遠由這裡計算）。"""
import math
import re

from ats.keywords import _pattern

from .matrix import DEGREE_ALIASES, DEGREES
from .sentences import calculate_work_experience_months, format_work_experience

GROUP_LABELS = {"skill": "專業技能", "experience": "專案經驗", "soft": "軟實力"}
LEVEL_TO_SCORE = {"green": 3, "yellow": 2, "red": 1, "info": 1}

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
                          "reason": "待人工確認：履歷未提及此職能或同義詞，不代表不具備此能力"})
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
    months = calculate_work_experience_months(resume) or 0
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
            months = calculate_work_experience_months(resume)
            if years == 0:
                out.append({"id": ko["id"], "status": "unknown", "evidence": "",
                            "reason": "履歷中找不到可計算的工作期間"})
            else:
                status = "met" if years >= ko["min_years"] else "not_met"
                duration = format_work_experience(months)
                out.append({"id": ko["id"], "status": status, "evidence": f"累計工作年資：{duration}",
                            "reason": f"（規則判斷）要求 {ko['min_years']} 年，日期合計 {duration}"})
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


def validate_weights(weights: dict) -> None:
    try:
        values = [float(weights.get(key, 0)) for key in GROUP_LABELS]
    except (AttributeError, TypeError, ValueError):
        raise ValueError("三大類權重必須是 0–100 的數字，且總和需為 100。") from None
    if any(not math.isfinite(value) or value < 0 or value > 100 for value in values):
        raise ValueError("三大類權重必須介於 0–100，且總和需為 100。")
    total = sum(values)
    if not math.isclose(total, 100, rel_tol=0, abs_tol=1e-9):
        difference = abs(100 - total)
        if total < 100:
            raise ValueError(f"目前總權重為 {total:g}，尚差 {difference:g}，請調整至 100。")
        raise ValueError(f"目前總權重為 {total:g}，超出 {difference:g}，請調整至 100。")
def compute(matrix: dict, weights: dict, analysis: dict) -> dict:
    validate_weights(weights)
    scores = {i["id"]: i for i in analysis.get("items", [])}
    groups = {}
    missing_ids = []
    for comp in matrix["competencies"]:
        item = scores.get(comp["id"])
        if item is None:
            missing_ids.append(comp["id"])
        s = max(0, min(3, int(item["score"]))) if item else 0
        g = groups.setdefault(comp["group"], {"got": 0.0, "total": 0.0, "count": 0})
        g["got"] += s / 3
        g["total"] += 1
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
        if res["status"] == "not_met" and not res.get("evidence", "").strip():
            res = {**res, "status": "unknown", "reason": "待人工確認：缺少證據"}
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
    stale = bool(missing_ids) or bool(analysis.get("stale"))
    needs_review = (stale or not matrix["competencies"]
                    or any(k["status"] == "unknown" for k in ko_view)
                    or any(not scores.get(c["id"], {}).get("evidence") for c in matrix["competencies"]))
    if stale:
        eliminated = False
    return {
        "raw_score": round(raw, 1),
        "penalty": penalty,
        "total": total,
        "eliminated": eliminated,
        "recommendation": "待人工確認" if needs_review else recommendation(total, eliminated),
        "group_scores": group_scores,
        "effective_weights": {k: round(w / weight_sum * 100, 1) for k, w in active.items()} if weight_sum else {},
        "knockouts": ko_view,
        "gaps": gap_analysis(matrix, scores, ko_view),
        "stale": stale,
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
