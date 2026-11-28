"""職缺草稿、AI 備援與既有評分契約的回歸檢查（不呼叫外部 AI）。"""
import io
import asyncio
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from starlette.datastructures import UploadFile

from backend import ai, main, samples
from backend.main import AnalyzeRequest, JobFields, JobRequest, MatrixRequest, ScoreRequest
from backend.scoring import compute


class WorkflowTests(unittest.TestCase):
    def test_autofill_preserves_existing_content(self):
        generated = dict(years="不限", education="不限", required="SQL", bonus="Python", jd="分析資料")
        req = JobRequest(fields=JobFields(title="資料分析師", years="3 年以上"), jd="既有 JD")
        with patch.object(main, "get_client", return_value=object()), patch.object(ai, "_call", return_value=generated):
            result = main.autofill_job(req)
        self.assertEqual(result["fields"]["years"], "3 年以上")
        self.assertEqual(result["fields"]["required"], "SQL")
        self.assertEqual(result["jd"], "既有 JD")

    def test_autofill_errors(self):
        with self.assertRaises(HTTPException) as error:
            main.autofill_job(JobRequest())
        self.assertEqual(error.exception.status_code, 400)
        req = JobRequest(fields=JobFields(title="分析師"))
        with patch.object(main, "get_client", return_value=None), self.assertRaises(HTTPException) as error:
            main.autofill_job(req)
        self.assertEqual(error.exception.status_code, 503)
        for response in [{"years": "不限"}, {k: "" for k in ("years", "education", "required", "bonus", "jd")}]:
            with patch.object(main, "get_client", return_value=object()), patch.object(ai, "_call", return_value=response), self.assertRaises(HTTPException) as error:
                main.autofill_job(req)
            self.assertEqual(error.exception.status_code, 502)

    def test_autofill_reports_api_failure_without_key_or_fallback(self):
        req = JobRequest(fields=JobFields(title="人力資源主管"))
        with patch.object(main, "get_client", return_value=object()), patch.object(main, "env_key", return_value="test-secret"), patch.object(ai, "_call", side_effect=ai.AIError("模型不存在（404） test-secret")):
            with self.assertRaises(HTTPException) as error:
                main.autofill_job(req)
        self.assertEqual(error.exception.status_code, 502)
        self.assertIn("404", error.exception.detail)
        self.assertNotIn("test-secret", error.exception.detail)

    def test_autofill_jd_basis_and_prompt(self):
        generated = dict(years="未載明", education="未載明", required="招募", bonus="未載明", jd="草稿")
        req = JobRequest(jd="管理招募流程", fields=JobFields(title="人力資源主管", required="保留原文"))
        with patch.object(main, "get_client", return_value=object()), patch.object(ai, "_call", return_value=generated) as call:
            result = main.autofill_job(req)
        self.assertEqual(result["basis"], "jd")
        self.assertEqual(result["fields"]["required"], "保留原文")
        self.assertEqual(result["jd"], req.jd)
        self.assertIn("優先且僅依 JD", call.call_args.args[1])

    def test_legacy_individual_weights_do_not_change_scores(self):
        matrix = {"competencies": [
            {"id": "a", "name": "SQL", "group": "skill", "importance": "必備", "weight": 3},
            {"id": "b", "name": "Python", "group": "skill", "importance": "加分", "weight": 1},
        ], "knockouts": []}
        analysis = {"items": [{"id": "a", "score": 3, "evidence": ["SQL 成果"]},
                              {"id": "b", "score": 0, "evidence": []}]}
        self.assertEqual(compute(matrix, {"skill": 100}, analysis)["total"], 50)
        matrix["competencies"][0]["weight"] = 100
        self.assertEqual(compute(matrix, {"skill": 100}, analysis)["total"], 50)

    def test_equal_competency_and_group_weight_scoring(self):
        matrix = {"competencies": [
            {"id": "a", "name": "SQL", "group": "skill", "importance": "必備", "weight": 3},
            {"id": "b", "name": "Python", "group": "skill", "importance": "加分", "weight": 1},
            {"id": "c", "name": "溝通", "group": "soft", "importance": "必備", "weight": 100},
        ], "knockouts": []}
        analysis = {"items": [{"id": "a", "score": 3, "evidence": ["SQL 成果"]},
                              {"id": "b", "score": 0, "evidence": []},
                              {"id": "c", "score": 0, "evidence": []}]}
        result = compute(matrix, {"skill": 80, "soft": 20}, analysis)
        self.assertEqual(result["total"], 40)
        self.assertEqual(result["group_scores"]["skill"], 50)
        self.assertEqual(result["effective_weights"], {"skill": 80, "soft": 20})

    def test_non_100_category_weights_block_resume_scoring(self):
        matrix = {"competencies": [{"id": "a", "name": "SQL", "group": "skill", "importance": "必備"}],
                  "knockouts": []}
        analysis = {"items": [{"id": "a", "score": 3, "evidence": ["SQL"]}]}
        for weights in [
            {"skill": 26, "experience": 35, "soft": 50},
            {"skill": 30, "experience": 35, "soft": 25},
        ]:
            with self.subTest(weights=weights):
                with self.assertRaises(HTTPException) as error:
                    main.score(ScoreRequest(matrix=matrix, weights=weights, analyses=[analysis]))
                self.assertEqual(error.exception.status_code, 400)
                self.assertIn("總權重", error.exception.detail)
                request = AnalyzeRequest(matrix=matrix, weights=weights, resume="使用 SQL", use_ai=False)
                with self.assertRaises(HTTPException) as error:
                    main.analyze_resume(request)
                self.assertEqual(error.exception.status_code, 400)

    def test_invalid_legacy_individual_weights_are_ignored(self):
        for weight in [0, -1, 101, "invalid", None, float("nan"), float("inf")]:
            req = ScoreRequest(matrix={"competencies": [{"id": "a", "name": "SQL", "group": "skill",
                                                         "importance": "必備", "weight": weight}],
                                       "knockouts": []}, weights={"skill": 100},
                               analyses=[{"items": [{"id": "a", "score": 3, "evidence": ["SQL"]}]}])
            result = main.score(req)["results"][0]
            self.assertEqual(result["total"], 100)

    def test_resume_upload_formats(self):
        import docx
        text = "使用 SQL 製作報表"
        word = docx.Document()
        word.add_paragraph(text)
        buf = io.BytesIO()
        word.save(buf)
        for name, data in [("resume.txt", text.encode()), ("resume.docx", buf.getvalue())]:
            result = asyncio.run(main.parse_resume(UploadFile(filename=name, file=io.BytesIO(data))))
            self.assertIn(text, result["text"])
        content = b"BT /F1 12 Tf 50 750 Td (SQL reporting experience) Tj ET"
        objects = [b"<< /Type /Catalog /Pages 2 0 R >>",
                   b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
                   b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
                   b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
                   b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream"]
        pdf, offsets = b"%PDF-1.4\n", [0]
        for i, obj in enumerate(objects, 1):
            offsets.append(len(pdf))
            pdf += str(i).encode() + b" 0 obj\n" + obj + b"\nendobj\n"
        start = len(pdf)
        pdf += b"xref\n0 6\n0000000000 65535 f \n"
        pdf += b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets[1:])
        pdf += f"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{start}\n%%EOF".encode()
        result = asyncio.run(main.parse_resume(UploadFile(filename="resume.pdf", file=io.BytesIO(pdf))))
        self.assertIn("SQL reporting experience", result["text"])

    def test_ai_matrix_keeps_rubric_and_reason(self):
        raw = {"job_title": "分析師", "competencies": [{"name": "SQL", "category": "tools", "type": "hard", "group": "skill",
               "importance": "必備", "keywords": ["SQL"], "description": "用於查詢職缺要求的業務資料"}], "knockouts": []}
        with patch.object(main, "get_client", return_value=object()), patch.object(ai, "_call", return_value=raw):
            data = main.build_matrix(MatrixRequest(jd="查詢業務資料，需使用 SQL"))
        self.assertEqual(data["source"], "ai")
        comp = data["matrix"]["competencies"][0]
        self.assertEqual(comp["category"], "tools")
        self.assertIn("業務資料", comp["description"])
        self.assertEqual(len(comp["rubric"]), 4)
        with patch.object(main, "get_client", return_value=object()), patch.object(ai, "_call", side_effect=ai.AIError("失敗")):
            self.assertEqual(main.build_matrix(MatrixRequest(jd="SQL"))["source"], "rule")

    def test_title_draft_is_general(self):
        for title in ["行銷企劃", "資料分析師", "軟體工程師", "未知職稱"]:
            data = main.suggest_job(JobRequest(fields=JobFields(title=title), use_ai=False))
            self.assertEqual(data["basis"], "title")
            self.assertIn("一般性建議", data["notice"])
            self.assertTrue(data["draft"]["responsibilities"])

    def test_jd_rule_does_not_invent_requirements(self):
        jd = "使用 SQL 整理報表\n跨部門溝通"
        data = main.suggest_job(JobRequest(jd=jd, fields=JobFields(title="軟體工程師"), use_ai=False))
        self.assertEqual(data["basis"], "jd")
        self.assertEqual(data["draft"]["responsibilities"], jd.splitlines())
        self.assertNotIn("Git 版本控制", data["draft"]["skills"])

    def test_empty_job_rejected(self):
        with self.assertRaises(HTTPException):
            main.suggest_job(JobRequest(use_ai=False))

    def test_existing_ai_adapter_and_failure_fallback(self):
        draft = {"responsibilities": ["分析資料"], "skills": ["SQL"], "abilities": ["溝通"]}
        req = JobRequest(fields=JobFields(title="資料分析師"))
        with patch.object(main, "get_client", return_value=object()), patch.object(ai, "_call", return_value=draft) as call:
            self.assertEqual(main.suggest_job(req)["source"], "ai")
            self.assertEqual(call.call_args.args[3], ai.JOB_SCHEMA)
        for output in [{}, {"responsibilities": [], "skills": [], "abilities": []}]:
            with patch.object(main, "get_client", return_value=object()), patch.object(ai, "_call", return_value=output):
                self.assertEqual(main.suggest_job(req)["source"], "rule")
        with patch.object(main, "get_client", return_value=object()), patch.object(ai, "_call", side_effect=ai.AIError("private diagnostic")):
            data = main.suggest_job(req)
            self.assertEqual(data["source"], "rule")
            self.assertNotIn("private diagnostic", data["warning"])

    def test_existing_samples_matrix_scoring_interview(self):
        for job in samples.JOBS:
            matrix = main.build_matrix(MatrixRequest(jd=job["jd"], fields=JobFields(**job["fields"]), use_ai=False))["matrix"]
            self.assertTrue(matrix["competencies"])
            for comp in matrix["competencies"]:
                self.assertIn(comp["category"], ("hard", "tools", "knowledge", "soft"))
                self.assertTrue(comp["description"])
                self.assertEqual(len(comp["rubric"]), 4)
            analysis = main.analyze_resume(AnalyzeRequest(matrix=matrix, weights={"skill": 40, "experience": 35, "soft": 25},
                                                          resume="使用 SQL 製作報表，提升效率 30%。", use_ai=False))
            result = main.score(ScoreRequest(matrix=matrix, weights={"skill": 40, "experience": 35, "soft": 25}, analyses=[analysis]))["results"][0]
            self.assertTrue(0 <= result["total"] <= 100)
            self.assertIn("behavioral", ai.rule_interview(matrix, analysis, result))

    def test_unverified_ai_evidence_cannot_eliminate(self):
        matrix = {"competencies": [{"id": "c", "name": "SQL", "importance": "必備", "group": "skill"}],
                  "knockouts": [{"id": "k", "name": "證照", "mode": "eliminate"}]}
        fake = {"candidate_name": "未知", "items": [{"id": "c", "score": 3, "evidence": ["虛構成果"], "reason": ""}],
                "knockouts": [{"id": "k", "status": "not_met", "evidence": "虛構證據", "reason": ""}]}
        with patch.object(ai, "_call", return_value=fake):
            analysis = ai.score_resume(object(), "", matrix, "履歷內容未載明")
        self.assertEqual(analysis["items"][0]["score"], 0)
        self.assertEqual(analysis["knockouts"][0]["status"], "unknown")
        result = compute(matrix, {"skill": 100}, analysis)
        self.assertFalse(result["eliminated"])
        self.assertEqual(result["recommendation"], "待人工確認")


if __name__ == "__main__":
    unittest.main()
