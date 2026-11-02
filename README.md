# ATS 職能評分教學系統

HR 課堂用的 ATS 模擬系統（FastAPI 後端 + 原生 JS 前端）：把職缺拆成職能矩陣、設定權重與評分尺度、為履歷逐項評分，最後產生面試問題。

## 執行

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --port 8000
```

開啟 http://localhost:8000 。

- **有 API Key**（右上角「設定」輸入，或設定環境變數 `ANTHROPIC_API_KEY`）：職能拆解、逐職能評分、面試問題由 Claude（`claude-opus-5-5`）產生。
- **沒有 API Key** 或取消勾選「使用 AI」：全部改用規則式（職能字典、關鍵字比對、範本題目），課堂上不產生任何費用。
- 「動詞 + 成果 + 量化數據」偵測器永遠是規則式，判斷理由逐句列出，方便學生理解。
- 資料存在瀏覽器 localStorage，重新整理不會遺失；「設定 → 清除所有資料」可重來。

## 四個模組

| 模組 | 功能 |
|---|---|
| 1 職缺拆解 | 3 個範例職缺一鍵帶入；結構化欄位（職稱、年資、學歷、必備、加分）；拆解為硬實力／軟實力／門檻條件；可新增、刪除、改名職能 |
| 2 權重與評分標準 | 專業技能／專案經驗／軟實力權重滑桿（總和固定 100%）；均衡／重技術／重經驗／重潛力預設組合；同一批履歷在各組合下的分數與名次變化；0–3 分 Rubric（全域與個別職能）；門檻「直接淘汰／扣分」 |
| 3 履歷評分 | 貼上文字或上傳 PDF／Word；逐句 🟢🟡🔴 標色；每個職能的得分卡（分數、佐證原文、判斷理由）；Match Score、雷達圖與大類長條圖；多份履歷排名；缺口分析 |
| 4 面試問題 | 驗證型、補洞型、STAR 行為面試題，每題附「面試官想聽到什麼」與評分要點；可列印 |

### 計分方式

- 每個職能 0–3 分；必備職能權重 ×2、加分 ×1，算出各大類得分（0–100）。
- Match Score = Σ（大類權重 × 大類得分）；沒有職能的大類，其權重平均分給其他大類。
- 門檻條件「確定不符合」時：直接淘汰，或扣設定的分數；無法判斷時不扣分，但列入缺口分析。

## 專案結構

```
backend/main.py       FastAPI 路由，並提供前端靜態檔
backend/ai.py         Claude 呼叫：職能拆解、履歷評分、面試問題（含範本備案）
backend/matrix.py     職能矩陣結構、規則式拆解（職能字典）
backend/scoring.py    規則式評分、權重加總、門檻、缺口分析
backend/sentences.py  動詞＋成果＋數據偵測器
backend/samples.py    範例職缺與範例履歷（虛構）
frontend/             index.html、app.js、styles.css
ats/                  PDF 解析與關鍵字比對（與舊版共用）
app.py                舊版 Streamlit 介面（streamlit run app.py）
```

> 評分結果僅供教學與初篩參考，最終錄用決策應由 HR 與用人主管判斷。AI 已被要求忽略年齡、性別、婚姻等與職務無關的特徵。
