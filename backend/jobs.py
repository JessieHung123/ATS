"""可供 HR 審閱的職缺條件草稿；不直接修改職缺或職能矩陣。"""
import re

from .matrix import rule_extract

CATEGORIES = {"hard": "硬實力", "tools": "工具技能", "knowledge": "專業知識", "soft": "工作相關軟實力"}
TOOLS = {"Python", "SQL", "Excel", "Tableau / Power BI", "Java", "Git 版本控制",
         "Docker / Kubernetes", "AWS / GCP 雲端服務", "CI/CD", "Google Analytics", "Photoshop / Canva"}


def category_for(comp: dict) -> str:
    if comp.get("type") == "soft":
        return "soft"
    if comp.get("name") in TOOLS:
        return "tools"
    if comp.get("name") in {"統計分析", "機器學習", "電商行銷"}:
        return "knowledge"
    return "hard"


def complete_matrix(matrix: dict) -> dict:
    for comp in matrix["competencies"]:
        comp.setdefault("weight", 1)
        comp.setdefault("category", category_for(comp))
        if not comp.get("description"):
            comp["description"] = f"輸入條件提及「{comp['name']}」或其關鍵字；請確認實際工作用途及評估行為。"
    return matrix


def rule_job(jd: str, fields: dict) -> dict:
    """有 JD 時只整理輸入；職稱範本明確視為一般建議。"""
    title = fields.get("title", "").strip()
    if jd.strip():
        duties = [line.strip(" -•\t") for line in re.split(r"[\n。]", jd) if line.strip()]
        comps = rule_extract(jd, fields)["competencies"]
        skills = [c["name"] for c in comps if c["type"] == "hard"]
        abilities = [c["name"] for c in comps if c["type"] == "soft"]
    elif "行銷" in title:
        duties = ["規劃與執行行銷活動", "追蹤活動成果並提出改善建議"]
        skills, abilities = ["內容企劃與文案", "社群經營", "成效分析"], ["跨部門溝通與協作"]
    elif "分析" in title:
        duties = ["整理與分析業務資料", "製作報表並說明分析結果"]
        skills, abilities = ["SQL", "統計分析", "資料視覺化"], ["問題釐清與分析簡報"]
    elif "工程" in title or "軟體" in title:
        duties = ["依需求設計與開發軟體", "執行測試、維護與問題排除"]
        skills, abilities = ["程式設計", "Git 版本控制", "軟體測試"], ["技術溝通與團隊協作"]
    else:
        duties = [f"執行{title}相關任務（請依實際工作補充）"]
        skills, abilities = [], []
    return {"responsibilities": duties, "skills": skills, "abilities": abilities}
