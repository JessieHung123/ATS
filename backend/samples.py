"""課堂用範例職缺與範例履歷（虛構內容）。"""

JOBS = [
    {
        "id": "marketing",
        "label": "行銷企劃",
        "fields": {
            "title": "行銷企劃專員",
            "years": "2 年以上行銷相關工作經驗",
            "education": "大學以上，行銷、傳播、商管相關科系尤佳",
            "required": "社群經營與內容規劃\n數位廣告投放（Meta / Google Ads）\n活動企劃與執行\nExcel 數據整理",
            "bonus": "熟悉 Google Analytics\n具 Photoshop / Canva 設計能力\n有電商行銷經驗",
        },
        "jd": (
            "【工作內容】\n"
            "1. 負責品牌社群平台（Facebook、Instagram、LINE）經營與內容規劃，提升粉絲互動與轉換。\n"
            "2. 規劃並執行數位廣告投放（Meta Ads、Google Ads），追蹤成效並優化預算分配。\n"
            "3. 策劃線上與線下行銷活動，與業務、設計、外部廠商跨部門協作，確保活動如期上線。\n"
            "4. 以 Excel 與 Google Analytics 整理行銷數據，產出月報並提出改善建議。\n\n"
            "【我們希望你】\n"
            "- 2 年以上行銷相關工作經驗，大學以上學歷。\n"
            "- 具備良好的溝通協調能力與團隊合作精神，能在時程壓力下解決問題。\n"
            "- 有電商行銷經驗、會使用 Photoshop 或 Canva 者尤佳。"
        ),
    },
    {
        "id": "data",
        "label": "資料分析師",
        "fields": {
            "title": "資料分析師",
            "years": "3 年以上資料分析相關經驗",
            "education": "大學以上，統計、資訊、數學或相關科系",
            "required": "熟悉 SQL 與 Python 資料處理\n具備統計分析能力\n能使用 Tableau 或 Power BI 製作儀表板",
            "bonus": "具機器學習建模經驗\n熟悉 A/B 測試設計\n有雲端資料倉儲（BigQuery）經驗",
        },
        "jd": (
            "【工作內容】\n"
            "1. 使用 SQL、Python 從資料倉儲擷取與清理資料，支援產品與營運決策。\n"
            "2. 建立 Tableau / Power BI 儀表板，追蹤關鍵營運指標（KPI）。\n"
            "3. 設計 A/B 測試並以統計方法分析結果，向主管與跨部門團隊簡報洞察。\n"
            "4. 與工程團隊合作優化資料流程，提升報表自動化程度。\n\n"
            "【必要條件】\n"
            "- 3 年以上資料分析相關經驗，大學以上學歷。\n"
            "- 熟悉 SQL、Python（pandas），具統計分析能力。\n"
            "- 具備清楚的溝通與簡報能力，能主動發現並解決問題。\n\n"
            "【加分條件】\n"
            "- 有機器學習建模、BigQuery 或其他雲端資料倉儲經驗。"
        ),
    },
    {
        "id": "swe",
        "label": "軟體工程師",
        "fields": {
            "title": "後端軟體工程師",
            "years": "3 年以上後端開發經驗",
            "education": "大學以上，資訊工程或相關科系",
            "required": "熟悉 Python 或 Java 後端開發\n具 RESTful API 設計經驗\n熟悉 MySQL / PostgreSQL\n熟悉 Git 版本控制",
            "bonus": "有 Docker / Kubernetes 經驗\n熟悉 AWS 或 GCP 雲端服務\n有 CI/CD 建置經驗",
        },
        "jd": (
            "【工作內容】\n"
            "1. 設計、開發與維護後端服務及 RESTful API。\n"
            "2. 規劃資料庫結構（MySQL / PostgreSQL），優化查詢效能。\n"
            "3. 與前端、產品、QA 團隊協作，參與 Code Review 與系統架構討論。\n"
            "4. 建置自動化測試與 CI/CD 流程，提升部署穩定度。\n\n"
            "【必要條件】\n"
            "- 3 年以上後端開發經驗，大學以上資訊相關科系。\n"
            "- 熟悉 Python 或 Java、Git 版本控制。\n"
            "- 具備良好的團隊合作與問題解決能力，樂於學習新技術。\n\n"
            "【加分條件】\n"
            "- Docker、Kubernetes、AWS / GCP 雲端服務、CI/CD 經驗。"
        ),
    },
]

RESUMES = [
    {
        "id": "data_strong",
        "job_id": "data",
        "label": "資料分析師－王小明（成果具體）",
        "name": "王小明",
        "text": (
            "王小明\nEmail：ming.wang@example.com　電話：0912-345-678\n\n"
            "學歷\n國立臺灣大學 統計學系 學士（2016–2020）\n\n"
            "工作經歷\n"
            "ABC 電商公司｜資料分析師｜2021/03 – 至今\n"
            "- 以 SQL 與 Python 建立每日營運報表自動化流程，使報表製作時間從 6 小時縮短至 30 分鐘。\n"
            "- 主導 12 場首頁 A/B 測試，以統計檢定評估成效，使結帳轉換率提升 8%。\n"
            "- 設計 Tableau 營運儀表板，供 5 個部門、超過 60 位同仁每週使用。\n"
            "- 建立顧客流失預測模型（XGBoost），協助行銷團隊挽回 15% 高風險顧客。\n"
            "- 與工程團隊協作將資料遷移至 BigQuery，查詢成本降低 40%。\n\n"
            "XYZ 顧問公司｜數據分析助理｜2020/07 – 2021/02\n"
            "- 協助整理客戶問卷資料。\n"
            "- 使用 Excel 製作分析圖表，並向客戶簡報調查結果。\n\n"
            "技能\nSQL、Python（pandas、scikit-learn）、Tableau、Power BI、BigQuery、統計分析"
        ),
    },
    {
        "id": "data_weak",
        "job_id": "data",
        "label": "資料分析師－李美華（描述空泛）",
        "name": "李美華",
        "text": (
            "李美華\nEmail：mei.lee@example.com\n\n"
            "學歷\n私立某某大學 企業管理學系 學士（2019–2023）\n\n"
            "工作經歷\n"
            "DEF 零售公司｜營運專員｜2023/08 – 至今\n"
            "- 負責公司相關數據業務。\n"
            "- 協助主管處理報表。\n"
            "- 參與部門專案。\n"
            "- 使用 Excel 整理銷售資料並製作週報。\n\n"
            "自傳\n我個性開朗，溝通能力佳，具有團隊合作精神，學習能力強，對數據分析很有興趣。\n\n"
            "技能\nExcel、Python（自學中）、SQL 基礎"
        ),
    },
    {
        "id": "data_mid",
        "job_id": "data",
        "label": "資料分析師－陳建志（有行動少數據）",
        "name": "陳建志",
        "text": (
            "陳建志\nEmail：chen.jc@example.com　電話：0922-111-222\n\n"
            "學歷\n國立成功大學 資訊管理研究所 碩士（2018–2020）\n\n"
            "工作經歷\n"
            "GHI 金融科技｜數據工程師｜2020/09 – 2024/06\n"
            "- 使用 Python 與 SQL 開發資料清理流程。\n"
            "- 建立 Power BI 儀表板追蹤放款業務指標。\n"
            "- 規劃信用評分模型的特徵工程，與風控團隊討論模型成效。\n"
            "- 帶領 3 人小組導入 Airflow 排程，使每日批次作業失敗率下降 70%。\n"
            "- 負責跨部門溝通與需求訪談。\n\n"
            "技能\nPython、SQL、Power BI、Airflow、機器學習、統計"
        ),
    },
    {
        "id": "mkt_strong",
        "job_id": "marketing",
        "label": "行銷企劃－林雅婷（成果具體）",
        "name": "林雅婷",
        "text": (
            "林雅婷\nEmail：yating.lin@example.com　電話：0933-456-789\n\n"
            "學歷\n國立政治大學 廣告學系 學士（2017–2021）\n\n"
            "工作經歷\n"
            "JKL 美妝品牌｜行銷企劃｜2021/07 – 至今\n"
            "- 規劃 Instagram 內容策略與短影音企劃，半年內追蹤數從 2 萬成長至 6.5 萬。\n"
            "- 優化 Meta Ads 受眾設定與素材測試，使廣告 ROAS 由 2.1 提升至 3.8。\n"
            "- 策劃週年慶線上線下整合活動，串聯 8 家門市與 3 位 KOL，活動營收達 1,200 萬元，較去年成長 35%。\n"
            "- 以 Google Analytics 與 Excel 建立月報模板，協助主管將預算重新分配至高轉換渠道。\n"
            "- 使用 Canva 製作社群素材，縮短設計外包時間 50%。\n\n"
            "技能\nMeta Ads、Google Ads、Google Analytics、Excel、Canva、Photoshop、電商行銷"
        ),
    },
    {
        "id": "mkt_weak",
        "job_id": "marketing",
        "label": "行銷企劃－張家豪（描述空泛）",
        "name": "張家豪",
        "text": (
            "張家豪\nEmail：hao.chang@example.com\n\n"
            "學歷\n某某科技大學 行銷與流通管理系 學士（2022–2024）\n\n"
            "工作經歷\n"
            "MNO 旅行社｜行銷助理｜2024/07 – 至今\n"
            "- 負責社群小編相關工作。\n"
            "- 協助活動執行。\n"
            "- 配合主管處理廣告業務。\n\n"
            "自傳\n我熱愛行銷，具備創意與溝通能力，抗壓性高，願意學習。"
        ),
    },
    {
        "id": "swe_strong",
        "job_id": "swe",
        "label": "軟體工程師－黃志偉（成果具體）",
        "name": "黃志偉",
        "text": (
            "黃志偉\nEmail：wei.huang@example.com　電話：0955-666-777\n\n"
            "學歷\n國立清華大學 資訊工程學系 學士（2015–2019）\n\n"
            "工作經歷\n"
            "PQR 雲端服務｜後端工程師｜2019/08 – 至今\n"
            "- 以 Python（FastAPI）重構訂單服務 RESTful API，使平均回應時間從 800ms 降至 120ms。\n"
            "- 優化 PostgreSQL 索引與查詢，尖峰時段資料庫 CPU 使用率降低 45%。\n"
            "- 導入 Docker 與 Kubernetes 部署，並以 GitHub Actions 建置 CI/CD，部署時間從 1 小時縮短至 10 分鐘。\n"
            "- 主導每週 Code Review，帶領 2 位新進工程師，3 個月內獨立負責模組開發。\n"
            "- 參與 AWS 遷移專案。\n\n"
            "技能\nPython、Java、FastAPI、PostgreSQL、MySQL、Docker、Kubernetes、AWS、Git、CI/CD"
        ),
    },
]
