"""職能矩陣：資料結構預設值 + 無 API 時的規則式拆解。"""
import re
import uuid

from ats.keywords import _pattern

DEFAULT_RUBRIC = [
    "未提及：履歷完全沒有出現此職能",
    "有提及但無佐證：只列在技能清單或空泛帶過",
    "有具體行動：描述了做過的事情，但沒有成果或數字",
    "有量化成果：具體行動＋可衡量的成果（數字、比例、規模）",
]

DEGREES = ["不限", "高中", "專科", "學士", "碩士", "博士"]
DEGREE_ALIASES = {
    "博士": ["博士", "ph.d", "phd"],
    "碩士": ["碩士", "研究所", "master", "mba"],
    "學士": ["學士", "大學", "bachelor", "學系", "科技大學"],
    "專科": ["專科", "二專", "五專"],
    "高中": ["高中", "高職"],
}

# (名稱, 同義詞/關鍵字, type, group)
SKILL_LIBRARY = [
    ("Python", ["python", "pandas"], "hard", "skill"),
    ("SQL", ["sql", "mysql", "postgresql", "bigquery"], "hard", "skill"),
    ("Excel", ["excel", "試算表"], "hard", "skill"),
    ("Tableau / Power BI", ["tableau", "power bi", "powerbi", "儀表板", "dashboard"], "hard", "skill"),
    ("統計分析", ["統計", "a/b 測試", "a/b測試", "ab test", "檢定", "迴歸"], "hard", "skill"),
    ("機器學習", ["機器學習", "machine learning", "預測模型", "xgboost", "scikit-learn", "建模"], "hard", "skill"),
    ("BigQuery / 雲端資料倉儲", ["bigquery", "資料倉儲", "snowflake", "redshift"], "hard", "skill"),
    ("Java", ["java"], "hard", "skill"),
    ("RESTful API 設計", ["restful", "rest api", "api"], "hard", "skill"),
    ("MySQL / PostgreSQL", ["mysql", "postgresql", "資料庫"], "hard", "skill"),
    ("Git 版本控制", ["git", "github", "gitlab"], "hard", "skill"),
    ("Docker / Kubernetes", ["docker", "kubernetes", "k8s", "容器"], "hard", "skill"),
    ("AWS / GCP 雲端服務", ["aws", "gcp", "azure", "雲端"], "hard", "skill"),
    ("CI/CD", ["ci/cd", "github actions", "jenkins", "自動化部署"], "hard", "skill"),
    ("社群經營", ["社群", "instagram", "facebook", "粉絲", "小編", "line"], "hard", "skill"),
    ("數位廣告投放", ["廣告投放", "meta ads", "google ads", "roas", "廣告"], "hard", "skill"),
    ("Google Analytics", ["google analytics", "ga4", "ga "], "hard", "skill"),
    ("Photoshop / Canva", ["photoshop", "canva", "illustrator", "設計素材"], "hard", "skill"),
    ("內容企劃與文案", ["文案", "內容規劃", "內容策略", "短影音"], "hard", "skill"),
    ("電商行銷", ["電商", "e-commerce", "購物車", "結帳"], "hard", "experience"),
    ("活動企劃與執行", ["活動", "週年慶", "展覽", "記者會"], "hard", "experience"),
    ("專案管理", ["專案管理", "pmp", "專案", "時程"], "hard", "experience"),
    ("後端開發經驗", ["後端", "backend", "fastapi", "django", "spring"], "hard", "experience"),
    ("資料分析實務經驗", ["資料分析", "數據分析", "報表", "data analysis"], "hard", "experience"),
    ("溝通與簡報", ["溝通", "簡報", "表達", "說服", "presentation"], "soft", "soft"),
    ("團隊合作與跨部門協作", ["團隊", "合作", "協作", "跨部門", "協調"], "soft", "soft"),
    ("解決問題", ["解決問題", "問題解決", "改善", "優化", "排除"], "soft", "soft"),
    ("主動學習", ["學習", "自學", "新技術", "進修"], "soft", "soft"),
    ("領導與帶人", ["帶領", "領導", "主導", "mentor", "指導"], "soft", "soft"),
    ("抗壓與時間管理", ["抗壓", "時程", "壓力", "deadline"], "soft", "soft"),
    ("創意發想", ["創意", "發想", "創新"], "soft", "soft"),
]

# JD 中出現這些字才會觸發對應職能（避免 "line"、"api" 這種短詞誤觸）
TRIGGERS = {
    "Python": ["python"], "SQL": ["sql"], "Excel": ["excel"],
    "Tableau / Power BI": ["tableau", "power bi"], "統計分析": ["統計", "a/b"],
    "機器學習": ["機器學習", "machine learning"], "BigQuery / 雲端資料倉儲": ["bigquery", "資料倉儲"],
    "Java": ["java"], "RESTful API 設計": ["restful", "api"], "MySQL / PostgreSQL": ["mysql", "postgresql"],
    "Git 版本控制": ["git"], "Docker / Kubernetes": ["docker", "kubernetes"], "AWS / GCP 雲端服務": ["aws", "gcp"],
    "CI/CD": ["ci/cd"], "社群經營": ["社群"], "數位廣告投放": ["廣告"], "Google Analytics": ["google analytics"],
    "Photoshop / Canva": ["photoshop", "canva"], "內容企劃與文案": ["內容規劃", "文案"], "電商行銷": ["電商"],
    "活動企劃與執行": ["活動"], "專案管理": ["專案管理", "pmp"], "後端開發經驗": ["後端"],
    "資料分析實務經驗": ["資料分析", "數據分析"], "溝通與簡報": ["溝通", "簡報"],
    "團隊合作與跨部門協作": ["團隊", "合作", "協作", "跨部門"], "解決問題": ["解決問題", "問題解決"],
    "主動學習": ["學習"], "領導與帶人": ["領導", "帶領"], "抗壓與時間管理": ["抗壓", "壓力"],
    "創意發想": ["創意"],
}

BONUS_MARKERS = ["尤佳", "加分", "優先", "為佳", "plus", "preferred"]


def new_id() -> str:
    return uuid.uuid4().hex[:8]


def make_competency(name, keywords, ctype, group, importance="必備", description=""):
    return {
        "id": new_id(), "name": name, "type": ctype, "group": group, "importance": importance,
        "keywords": keywords, "description": description, "rubric": list(DEFAULT_RUBRIC),
    }


def parse_min_years(text: str) -> int:
    m = re.search(r"(\d+)\s*(年|years?)\s*(以上)?", text or "", re.I)
    return int(m.group(1)) if m else 0


def parse_min_degree(text: str) -> str:
    text = (text or "").lower()
    for degree in ["博士", "碩士", "學士", "專科", "高中"]:
        if any(alias in text for alias in DEGREE_ALIASES[degree]):
            return degree
    return "不限"


def default_knockouts(fields: dict, jd: str) -> list[dict]:
    years_src = fields.get("years") or jd
    edu_src = fields.get("education") or jd
    out = []
    years = parse_min_years(years_src)
    if years:
        out.append({"id": new_id(), "name": f"{years} 年以上相關經驗", "kind": "years", "min_years": years,
                    "min_degree": "不限", "requirement": (fields.get("years") or f"{years} 年以上").strip(),
                    "mode": "deduct", "penalty": 15})
    degree = parse_min_degree(edu_src)
    if degree != "不限":
        out.append({"id": new_id(), "name": f"{degree}以上學歷", "kind": "education", "min_years": 0,
                    "min_degree": degree, "requirement": (fields.get("education") or f"{degree}以上").strip(),
                    "mode": "eliminate", "penalty": 15})
    return out


def rule_extract(jd: str, fields: dict) -> dict:
    """規則式拆解：以職能字典比對 JD 與必備／加分欄位。"""
    required_text = (fields.get("required") or "").lower()
    bonus_text = (fields.get("bonus") or "").lower()
    jd_low = (jd or "").lower()
    # JD 中「尤佳／加分」所在的句子視為加分條件
    jd_bonus = " ".join(s for s in re.split(r"[\n。]", jd_low) if any(b in s for b in BONUS_MARKERS))
    sections = re.split(r"【([^】]*)】", jd_low)
    for i in range(1, len(sections) - 1, 2):
        if "加分" in sections[i]:
            jd_bonus += " " + sections[i + 1]

    competencies = []
    for name, keywords, ctype, group in SKILL_LIBRARY:
        triggers = TRIGGERS.get(name, [name.lower()])
        def found(text):
            return any(_pattern(t).search(text) for t in triggers)

        in_required = found(required_text)
        in_bonus = found(bonus_text) or found(jd_bonus)
        in_jd = found(jd_low)
        if not (in_required or in_bonus or in_jd):
            continue
        importance = "必備" if in_required or (in_jd and not in_bonus) else "加分"
        competencies.append(make_competency(name, list(keywords), ctype, group, importance))

    return {
        "job_title": fields.get("title") or "未命名職缺",
        "competencies": competencies,
        "knockouts": default_knockouts(fields, jd),
        "rubric": list(DEFAULT_RUBRIC),
    }
