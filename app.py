"""ATS 履歷評分系統 — Streamlit 介面。執行：streamlit run app.py"""
import os
from concurrent.futures import ThreadPoolExecutor

import anthropic
import pandas as pd
import streamlit as st

from ats.ai_scorer import ScoringError, evaluate_resume, extract_jd_keywords
from ats.keywords import Keyword, match_keywords, naive_extract
from ats.pdf_parser import parse_pdf

DIMENSION_LABELS = {"skills": "技能", "experience": "經驗", "education": "學歷", "achievements": "成果"}
KW_COLUMNS = ["關鍵字", "同義詞（逗號分隔）", "重要性"]

st.set_page_config(page_title="ATS 履歷評分系統", page_icon="📄", layout="wide")
st.session_state.setdefault("keywords_df", pd.DataFrame(columns=KW_COLUMNS))
st.session_state.setdefault("results", [])


def keywords_to_df(keywords: list[Keyword]) -> pd.DataFrame:
    return pd.DataFrame(
        [[k.term, ", ".join(k.synonyms), k.importance] for k in keywords], columns=KW_COLUMNS
    )


def df_to_keywords(df: pd.DataFrame) -> list[Keyword]:
    keywords = []
    for _, row in df.iterrows():
        term = str(row[KW_COLUMNS[0]] or "").strip()
        if not term or term == "nan":
            continue
        synonyms = [s.strip() for s in str(row[KW_COLUMNS[1]] or "").replace("，", ",").split(",")]
        importance = row[KW_COLUMNS[2]] if row[KW_COLUMNS[2]] in ("必要", "加分") else "加分"
        keywords.append(Keyword(term, [s for s in synonyms if s and s != "nan"], importance))
    return keywords


def score_one(client, jd, keywords, filename, data, effort) -> dict:
    parsed = parse_pdf(filename, data)
    kw_score, matched, missing = match_keywords(parsed.text, keywords)
    result = {
        "file": filename, "kw_score": kw_score, "matched": matched, "missing": missing,
        "warnings": list(parsed.warnings), "ai": None,
    }
    if client and parsed.readable:
        try:
            result["ai"] = evaluate_resume(client, jd, keywords, parsed.text, effort)
        except (ScoringError, anthropic.APIError) as e:
            result["warnings"].append(f"AI 評分失敗：{e}")
    return result


def final_score(r: dict, kw_weight: float) -> float:
    if r["ai"] is None:
        return r["kw_score"]
    return round(kw_weight * r["kw_score"] + (1 - kw_weight) * r["ai"]["overall_score"], 1)


# ---------------- 側邊欄 ----------------
with st.sidebar:
    st.header("⚙️ 設定")
    default_key = os.environ.get("ANTHROPIC_API_KEY", "")
    api_key = st.text_input("Anthropic API Key", value=default_key, type="password",
                            help="留空則只使用關鍵字比對（不呼叫 AI）")
    effort = st.select_slider("AI 評估深度", options=["low", "medium", "high"], value="medium",
                              help="越深越精準，但較慢、費用較高")
    kw_weight = st.slider("關鍵字分數權重", 0.0, 1.0, 0.4, 0.05,
                          help="總分 = 關鍵字分數 × 權重 + AI 分數 × (1 − 權重)")
    st.caption(f"總分 = 關鍵字 × {kw_weight:.2f} + AI × {1 - kw_weight:.2f}")
    st.divider()
    st.caption("AI 已設定為忽略年齡、性別、婚姻等與職務無關的個人特徵。評分僅供參考，最終決策請由 HR 判斷。")

client = anthropic.Anthropic(api_key=api_key) if api_key else None

st.title("📄 ATS 履歷評分系統")
st.caption("貼上職缺描述、上傳候選人履歷（PDF），系統以「關鍵字比對 + AI 語意評估」為候選人評分排名。")

# ---------------- Step 1：JD ----------------
st.subheader("1. 職缺描述（JD）")
jd = st.text_area("貼上職缺描述", height=200, placeholder="例：我們正在尋找一位資料分析師，需具備 SQL、Python…")

if st.button("🔍 分析 JD 關鍵字", disabled=not jd.strip()):
    if client:
        with st.spinner("Claude 正在萃取關鍵字…"):
            try:
                st.session_state.keywords_df = keywords_to_df(extract_jd_keywords(client, jd, effort))
            except (ScoringError, anthropic.APIError) as e:
                st.error(f"AI 萃取失敗，改用簡易萃取：{e}")
                st.session_state.keywords_df = keywords_to_df(naive_extract(jd))
    else:
        st.info("未設定 API Key，使用簡易萃取（只抓英文詞），請手動補充中文關鍵字。")
        st.session_state.keywords_df = keywords_to_df(naive_extract(jd))

st.markdown("**ATS 關鍵字**（可直接編輯、新增或刪除列）")
edited_df = st.data_editor(
    st.session_state.keywords_df,
    num_rows="dynamic",
    width="stretch",
    column_config={
        KW_COLUMNS[2]: st.column_config.SelectboxColumn(options=["必要", "加分"], default="加分", required=True),
    },
    key="kw_editor",
)
keywords = df_to_keywords(edited_df)

# ---------------- Step 2：履歷 ----------------
st.subheader("2. 上傳候選人履歷")
files = st.file_uploader("可一次選取多份 PDF", type=["pdf"], accept_multiple_files=True)

can_run = bool(jd.strip() and keywords and files)
if st.button("🚀 開始評分", type="primary", disabled=not can_run):
    progress = st.progress(0.0, text="評分中…")
    results = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(score_one, client, jd, keywords, f.name, f.getvalue(), effort) for f in files]
        for i, fut in enumerate(futures, 1):
            results.append(fut.result())
            progress.progress(i / len(futures), text=f"已完成 {i}/{len(futures)} 份")
    progress.empty()
    st.session_state.results = results
if not can_run:
    st.caption("需要：JD、至少一個關鍵字、至少一份履歷。")

# ---------------- Step 3：結果 ----------------
results = st.session_state.results
if results:
    st.subheader("3. 評分結果")
    ranked = sorted(results, key=lambda r: final_score(r, kw_weight), reverse=True)
    table = pd.DataFrame([
        {
            "排名": i,
            "候選人": r["ai"]["candidate_name"] if r["ai"] else "—",
            "檔案": r["file"],
            "總分": final_score(r, kw_weight),
            "關鍵字分數": r["kw_score"],
            "AI 分數": r["ai"]["overall_score"] if r["ai"] else None,
            "建議": r["ai"]["recommendation"] if r["ai"] else "—",
            "缺少關鍵字": "、".join(r["missing"]),
            "警示": "；".join(r["warnings"]),
        }
        for i, r in enumerate(ranked, 1)
    ])
    st.dataframe(
        table, width="stretch", hide_index=True,
        column_config={"總分": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.1f")},
    )
    st.download_button(
        "⬇️ 下載結果 CSV", table.to_csv(index=False).encode("utf-8-sig"),
        file_name="ats_results.csv", mime="text/csv",
    )

    st.markdown("#### 候選人詳細報告")
    for i, r in enumerate(ranked, 1):
        ai = r["ai"]
        name = ai["candidate_name"] if ai else r["file"]
        with st.expander(f"#{i}　{name}　—　{final_score(r, kw_weight)} 分"):
            c1, c2, c3 = st.columns(3)
            c1.metric("總分", final_score(r, kw_weight))
            c2.metric("關鍵字分數", r["kw_score"])
            c3.metric("AI 分數", ai["overall_score"] if ai else "—")
            for w in r["warnings"]:
                st.warning(w)

            k1, k2 = st.columns(2)
            k1.markdown("**✅ 命中關鍵字**")
            k1.write("、".join(r["matched"]) or "（無）")
            k2.markdown("**❌ 缺少關鍵字**")
            k2.write("、".join(r["missing"]) or "（無）")

            if ai:
                st.markdown(f"**建議：{ai['recommendation']}**　{ai['summary']}")
                for key, label in DIMENSION_LABELS.items():
                    d = ai["dimensions"][key]
                    st.progress(d["score"] / 100, text=f"{label}　{d['score']} 分 — {d['comment']}")
                s1, s2 = st.columns(2)
                s1.markdown("**優勢**")
                s1.markdown("\n".join(f"- {s}" for s in ai["strengths"]))
                s2.markdown("**待確認 / 不足**")
                s2.markdown("\n".join(f"- {g}" for g in ai["gaps"]))
                st.markdown("**建議面試問題**")
                st.markdown("\n".join(f"{n}. {q}" for n, q in enumerate(ai["interview_questions"], 1)))
