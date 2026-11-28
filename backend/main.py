"""ATS 教學系統後端（FastAPI）。執行：uvicorn backend.main:app --reload"""
import io
import re
from pathlib import Path

from fastapi import FastAPI, File, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from ats.gemini import MODELS, env_key, make_client, resolve_model
from ats.pdf_parser import parse_pdf

from . import ai, samples
from .matrix import DEFAULT_RUBRIC, rule_extract
from .scoring import compute, rule_check_knockouts, rule_score_items, validate_weights
from .sentences import analyze_sentences
from .jobs import complete_matrix, rule_job

FRONTEND = Path(__file__).resolve().parent.parent / "frontend"

app = FastAPI(title="ATS 職能評分教學系統")

PRESETS = {
    "balanced": {"label": "均衡型", "weights": {"skill": 40, "experience": 35, "soft": 25}},
    "tech": {"label": "重技術型", "weights": {"skill": 60, "experience": 25, "soft": 15}},
    "experience": {"label": "重經驗型", "weights": {"skill": 25, "experience": 55, "soft": 20}},
    "potential": {"label": "重潛力型", "weights": {"skill": 20, "experience": 15, "soft": 65}},
}


get_client = make_client  # get_client(api_key, model)

AI_ERRORS = (ai.AIError, ValueError, KeyError, TypeError, AttributeError)


# ---------------- 資料模型 ----------------

class JobFields(BaseModel):
    title: str = ""
    years: str = ""
    education: str = ""
    required: str = ""
    bonus: str = ""


class MatrixRequest(BaseModel):
    jd: str
    fields: JobFields = Field(default_factory=JobFields)
    use_ai: bool = True


class JobRequest(BaseModel):
    jd: str = ""
    fields: JobFields = Field(default_factory=JobFields)
    use_ai: bool = True


class AnalyzeRequest(BaseModel):
    jd: str = ""
    matrix: dict
    weights: dict
    resume: str
    use_ai: bool = True


class ScoreRequest(BaseModel):
    matrix: dict
    weights: dict
    analyses: list[dict]


class InterviewRequest(BaseModel):
    jd: str = ""
    matrix: dict
    weights: dict
    analysis: dict
    resume: str = ""
    use_ai: bool = True


# ---------------- API ----------------

@app.post("/api/job/suggest")
def suggest_job(req: JobRequest, x_model: str | None = Header(default=None)):
    if not req.jd.strip() and not req.fields.title.strip():
        raise HTTPException(400, "請輸入職缺名稱或 JD")
    fields = req.fields.model_dump()
    client = get_client(model=x_model) if req.use_ai else None
    source, warning = "rule", None
    draft = rule_job(req.jd, fields)
    if client:
        try:
            data = ai.generate_job(client, req.jd, fields)
            if not all(isinstance(data.get(k), list) and all(isinstance(v, str) for v in data[k])
                       for k in draft) or not any(v.strip() for values in data.values() for v in values):
                raise ValueError("職缺草稿格式不完整")
            draft, source = data, "ai"
        except AI_ERRORS:
            warning = "AI 產生失敗，改用規則式草稿，請人工補充確認。"
    return {"draft": draft, "source": source, "warning": warning,
            "basis": "jd" if req.jd.strip() else "title",
            "notice": "依 JD 整理的建議，尚待 HR 確認" if req.jd.strip() else "一般性建議，並非企業已確認的招募條件"}

@app.post("/api/job/autofill")
def autofill_job(req: JobRequest, x_model: str | None = Header(default=None)):
    if not req.fields.title.strip():
        raise HTTPException(400, "請先輸入職稱")
    if not req.use_ai:
        raise HTTPException(400, "請先開啟「使用 AI」")
    client = get_client(model=x_model)
    if not client:
        raise HTTPException(503, "尚未設定 API Key，請在伺服器設定 GEMINI_API_KEY 或 GOOGLE_API_KEY")
    fields = req.fields.model_dump()
    try:
        data = ai.autofill_job(client, req.jd, fields)
        keys = ("years", "education", "required", "bonus", "jd")
        if not isinstance(data, dict) or not all(isinstance(data.get(k), str) and data[k].strip() for k in keys):
            raise ValueError("職缺欄位格式不完整")
    except ai.AIError as exc:
        # AIError 是共用串接轉換後的錯誤，不回傳 SDK 原始回應或金鑰。
        detail = str(exc)
        if env_key():
            detail = detail.replace(env_key(), "[已隱藏金鑰]")
        detail = re.sub(r"AIza[\w-]+", "[已隱藏金鑰]", detail)
        raise HTTPException(502, f"AI 填寫失敗：{detail}；原有內容已保留") from None
    except (ValueError, KeyError, TypeError, AttributeError):
        raise HTTPException(502, "Gemini 回傳格式不完整：年資、學歷、必備條件、加分條件與 JD 必須是非空文字；原有內容已保留") from None
    return {"fields": {k: fields[k] if fields[k].strip() else data[k].strip() for k in keys if k != "jd"},
            "jd": req.jd if req.jd.strip() else data["jd"].strip(), "source": "ai", "model": resolve_model(x_model),
            "basis": "jd" if req.jd.strip() else "title",
            "notice": "依提供的 JD 整理，未載明條件不另設門檻；尚待 HR 確認。" if req.jd.strip() else "一般性建議，並非企業已確認的招募條件；尚待 HR 確認。"}


@app.get("/api/status")
def status(x_api_key: str | None = Header(default=None), x_model: str | None = Header(default=None)):
    return {"ai_available": get_client(model=x_model) is not None, "model": resolve_model(x_model), "models": MODELS,
            "env_key": bool(env_key())}


@app.get("/api/samples")
def get_samples():
    return {"jobs": samples.JOBS, "resumes": samples.RESUMES, "presets": PRESETS, "rubric": DEFAULT_RUBRIC}


@app.post("/api/matrix")
def build_matrix(req: MatrixRequest, x_api_key: str | None = Header(default=None),
                 x_model: str | None = Header(default=None)):
    if not req.jd.strip() and not req.fields.required.strip():
        raise HTTPException(400, "請輸入 JD 或必備條件")
    fields = req.fields.model_dump()
    client = get_client(model=x_model) if req.use_ai else None
    if client:
        try:
            matrix = ai.extract_matrix(client, req.jd, fields)
            return {"matrix": complete_matrix(matrix), "source": "ai"}
        except AI_ERRORS:
            return {"matrix": complete_matrix(rule_extract(req.jd, fields)), "source": "rule", "warning": "AI 拆解失敗，改用規則式，請確認職能與理由。"}
    return {"matrix": complete_matrix(rule_extract(req.jd, fields)), "source": "rule"}


@app.post("/api/resume/parse")
async def parse_resume(file: UploadFile = File(...)):
    data = await file.read()
    name = (file.filename or "").lower()
    if name.endswith(".pdf"):
        parsed = parse_pdf(file.filename, data)
        return {"text": parsed.text, "warnings": parsed.warnings}
    if name.endswith(".docx"):
        import docx

        try:
            doc = docx.Document(io.BytesIO(data))
        except Exception:  # 損毀或非 docx
            raise HTTPException(400, "無法讀取 Word 檔，請確認檔案格式與內容")
        lines = [p.text for p in doc.paragraphs]
        for table in doc.tables:
            for row in table.rows:
                lines.append("　".join(c.text for c in row.cells))
        return {"text": "\n".join(lines), "warnings": []}
    if name.endswith(".txt"):
        return {"text": data.decode("utf-8", errors="replace"), "warnings": []}
    raise HTTPException(400, "僅支援 PDF、Word（.docx）或 .txt")


@app.post("/api/resume/analyze")
def analyze_resume(req: AnalyzeRequest, x_api_key: str | None = Header(default=None),
                   x_model: str | None = Header(default=None)):
    try:
        validate_weights(req.weights)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None
    if not req.resume.strip():
        raise HTTPException(400, "履歷內容是空的")
    detector = analyze_sentences(req.resume)
    client = get_client(model=x_model) if req.use_ai else None
    warning = None
    if client:
        try:
            scored = ai.score_resume(client, req.jd, req.matrix, req.resume)
            return {**scored, **detector, "source": "ai"}
        except AI_ERRORS:
            warning = "AI 評分失敗，改用規則式，請人工確認結果。"
    return {
        "candidate_name": "",
        "items": rule_score_items(req.matrix, detector["sentences"]),
        "knockouts": rule_check_knockouts(req.matrix, req.resume),
        **detector,
        "source": "rule",
        "warning": warning,
    }


@app.post("/api/score")
def score(req: ScoreRequest):
    try:
        return {"results": [compute(req.matrix, req.weights, a) for a in req.analyses]}
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None


@app.post("/api/interview")
def interview(req: InterviewRequest, x_api_key: str | None = Header(default=None),
              x_model: str | None = Header(default=None)):
    try:
        result = compute(req.matrix, req.weights, req.analysis)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None
    client = get_client(model=x_model) if req.use_ai else None
    if client:
        try:
            return {**ai.interview_questions(client, req.jd, req.matrix, req.analysis, result, req.resume), "source": "ai"}
        except AI_ERRORS:
            return {**ai.rule_interview(req.matrix, req.analysis, result), "source": "rule",
                    "warning": "AI 生成失敗，改用範本，請人工確認。"}
    return {**ai.rule_interview(req.matrix, req.analysis, result), "source": "rule"}


# ---------------- 前端 ----------------

app.mount("/static", StaticFiles(directory=FRONTEND), name="static")


@app.get("/")
def index():
    return FileResponse(FRONTEND / "index.html")
