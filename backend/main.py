"""ATS 教學系統後端（FastAPI）。執行：uvicorn backend.main:app --reload"""
import io
import os
from pathlib import Path

import anthropic
from fastapi import FastAPI, File, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from ats.pdf_parser import parse_pdf

from . import ai, samples
from .matrix import DEFAULT_RUBRIC, rule_extract
from .scoring import compute, rule_check_knockouts, rule_score_items
from .sentences import analyze_sentences

FRONTEND = Path(__file__).resolve().parent.parent / "frontend"

app = FastAPI(title="ATS 職能評分教學系統")

PRESETS = {
    "balanced": {"label": "均衡型", "weights": {"skill": 40, "experience": 35, "soft": 25}},
    "tech": {"label": "重技術型", "weights": {"skill": 60, "experience": 25, "soft": 15}},
    "experience": {"label": "重經驗型", "weights": {"skill": 25, "experience": 55, "soft": 20}},
    "potential": {"label": "重潛力型", "weights": {"skill": 20, "experience": 15, "soft": 65}},
}


def get_client(api_key: str | None) -> anthropic.Anthropic | None:
    key = (api_key or "").strip() or os.environ.get("ANTHROPIC_API_KEY", "")
    return anthropic.Anthropic(api_key=key) if key else None


AI_ERRORS = (ai.AIError, anthropic.APIError, ValueError, KeyError)


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


class AnalyzeRequest(BaseModel):
    jd: str = ""
    matrix: dict
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

@app.get("/api/status")
def status(x_api_key: str | None = Header(default=None)):
    return {"ai_available": get_client(x_api_key) is not None, "model": ai.MODEL,
            "env_key": bool(os.environ.get("ANTHROPIC_API_KEY"))}


@app.get("/api/samples")
def get_samples():
    return {"jobs": samples.JOBS, "resumes": samples.RESUMES, "presets": PRESETS, "rubric": DEFAULT_RUBRIC}


@app.post("/api/matrix")
def build_matrix(req: MatrixRequest, x_api_key: str | None = Header(default=None)):
    if not req.jd.strip() and not req.fields.required.strip():
        raise HTTPException(400, "請輸入 JD 或必備條件")
    fields = req.fields.model_dump()
    client = get_client(x_api_key) if req.use_ai else None
    if client:
        try:
            return {"matrix": ai.extract_matrix(client, req.jd, fields), "source": "ai"}
        except AI_ERRORS as e:
            return {"matrix": rule_extract(req.jd, fields), "source": "rule", "warning": f"AI 拆解失敗，改用規則式：{e}"}
    return {"matrix": rule_extract(req.jd, fields), "source": "rule"}


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
        except Exception as e:  # 損毀或非 docx
            raise HTTPException(400, f"無法讀取 Word 檔：{e}")
        lines = [p.text for p in doc.paragraphs]
        for table in doc.tables:
            for row in table.rows:
                lines.append("　".join(c.text for c in row.cells))
        return {"text": "\n".join(lines), "warnings": []}
    if name.endswith(".txt"):
        return {"text": data.decode("utf-8", errors="replace"), "warnings": []}
    raise HTTPException(400, "僅支援 PDF、Word（.docx）或 .txt")


@app.post("/api/resume/analyze")
def analyze_resume(req: AnalyzeRequest, x_api_key: str | None = Header(default=None)):
    if not req.resume.strip():
        raise HTTPException(400, "履歷內容是空的")
    detector = analyze_sentences(req.resume)
    client = get_client(x_api_key) if req.use_ai else None
    warning = None
    if client:
        try:
            scored = ai.score_resume(client, req.jd, req.matrix, req.resume)
            return {**scored, **detector, "source": "ai"}
        except AI_ERRORS as e:
            warning = f"AI 評分失敗，改用規則式：{e}"
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
    return {"results": [compute(req.matrix, req.weights, a) for a in req.analyses]}


@app.post("/api/interview")
def interview(req: InterviewRequest, x_api_key: str | None = Header(default=None)):
    result = compute(req.matrix, req.weights, req.analysis)
    client = get_client(x_api_key) if req.use_ai else None
    if client:
        try:
            return {**ai.interview_questions(client, req.jd, req.matrix, req.analysis, result, req.resume), "source": "ai"}
        except AI_ERRORS as e:
            return {**ai.rule_interview(req.matrix, req.analysis, result), "source": "rule",
                    "warning": f"AI 生成失敗，改用範本：{e}"}
    return {**ai.rule_interview(req.matrix, req.analysis, result), "source": "rule"}


# ---------------- 前端 ----------------

app.mount("/static", StaticFiles(directory=FRONTEND), name="static")


@app.get("/")
def index():
    return FileResponse(FRONTEND / "index.html")
