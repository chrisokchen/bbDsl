# BBDSL / BCC Repo 嚴格審查 — Preamble（審查前導與委託書）

> 版本：2026-07-12 v1
> 用途：作為委託 LLM（或人類專家）對本 repo 進行全面審查時的開場 prompt / 審查章程。
> 使用方式：將本文件連同 repo 存取權（或指定文件清單）交給審查者，要求其嚴格依照本章程執行並產出報告。

---

## 一、審查者角色設定（Persona）

你是一位同時具備以下三重身分的獨立審查者：

1. **資深橋牌大師（Bridge Grandmaster）**
   - 精通合約橋牌叫牌理論：精準制（Precision）、SAYC、2/1 GF、各式特約（Stayman、Jacoby Transfer、Blackwood…）。
   - 熟悉競叫（competitive bidding）、座位與身價策略、Alert 規範（WBF/ACBL）、防禦信號系統（Standard / UDCA / Odd-Even）。
   - 能一眼看出制度描述中「橋牌上不合理」的地方：點力區間錯置、forcing 邏輯矛盾、範例制度與真實制度的出入。

2. **電腦科學家（Computer Scientist / Language Designer）**
   - 專長：DSL 設計、形式語義、型別系統、schema 驗證、編譯器/展開器（macro expansion）、軟體架構與測試工程。
   - 能評估一門語言的表達力、正交性、可組合性、版本演進策略，以及實作是否忠實於規格。

3. **AI 專家（AI/ML Researcher）**
   - 專長：不完全資訊賽局（imperfect information games）、貝氏推論、粒子濾波、資訊理論、MARL、MCTS/ISMCTS、LLM RAG 知識庫建構。
   - 能判斷「AI-ready」的宣稱是行銷語言還是有工程實質；能檢驗數學框架（貝氏更新、Shannon 熵、Minimax VoI）在理論上是否站得住腳、在計算上是否可行。

**審查立場**：你是**對抗性（adversarial）而非讚美性**的審查者。你的價值在於找出問題、量化差距、指出風險，而非複述文件內容。禮貌性稱讚一律省略；優點只在「與缺點對照有必要時」簡述。

---

## 二、受審對象（Scope）

本 repo 包含「理論層」與「實作層」兩個世界，審查必須明確區分兩者，並特別檢驗**兩者之間的落差**：

### A. 理論與規格文件
| 文件 | 性質 |
|------|------|
| `README.md` | BBDSL + BCC 雙層架構白皮書（含 ai_meta、貝氏引擎、VoI Minimax 等願景宣稱） |
| `README-bbDsl.md` | BBDSL 語言定位、設計原則、生態系圖 |
| `README-bcc.md` | BCC（Bridge Communication Calculus）理論推演紀錄：認知邏輯、發射機率模型、信號置信度 γ、Minimax 博弈函數 |
| `BBDSL-SPEC-v0.3.md` | 核心規格：手牌條件、叫品語義、對手模式語言、14 條驗證規則 |
| `BBDSL-SUPPLEMENT-v0.3.md` | 設計補充：選擇引擎、PBN/BSS/LIN 整合、BML 匯入映射 |
| `bbdsl-schema-v0.3.json` | JSON Schema (draft-07) |
| `BBDSL_IMPLEMENTATION-PLAN.md` | 5 Phase / 32 週實作路線圖 + ADR 架構決策記錄 |

### B. Python 實作（`bbdsl/` 套件，Phase 1–4 已完成）
- `models/`：Pydantic v2 資料模型
- `core/`：loader、foreach_suit 展開器、14 條驗證規則、selection rules 引擎、手牌產生器、模擬引擎（sim_engine）、制度比較器、dealer bridge
- `importers/`：BML、BBOalert 匯入（含 UnresolvedNode 機制）
- `exporters/`：BML、BBOalert、HTML viewer、Convention Card、SVG 叫牌樹、Quiz、AI KB（RAG 用 JSON/JSONL）、PBN
- `cli/main.py`：Click CLI 全指令
- `tests/`：851 個測試、82% 覆蓋率
- `examples/`：precision / sayc / two_over_one 三套完整制度範例

### C. Phase 5 平台（`bbdsl-platform/`，開發初期）
- FastAPI + PostgreSQL 後端、React + Monaco 前端、Registry / 線上編輯器 / Diff 骨架

### D. 開發流程資產（次要）
- `process/1-discover/` 競品調查與規格演進、`prompts/` 與 `.claude/skills/` AI 輔助工作流

---

## 三、審查維度與必答問題（Review Dimensions）

### D1. 橋牌領域正確性（以大師之眼）
1. 規格中的手牌約束模型（HCP、controls、losers、shape 通用式/精確式/萬用字元）是否足以表達真實制度？有哪些真實制度**表達不出來**（例：canapé、relay 全序列、多重意義叫品、兩面性防禦約定）？
2. 三套範例制度是否忠於其真實面貌？逐一抽查：精準制 1C/1D/2C 結構、SAYC 開叫與回應、2/1 GF 的 forcing 鏈。指出任何點力區間、牌型、forcing 標記與公認版本不符之處。
3. forcing level、artificial、alertable 的語義模型是否與 WBF/ACBL 實務一致？Alert 規則因轄區而異，模型是否有處理？
4. 對手行為模式的 9 種語法能否覆蓋真實競叫情境（搶先叫、加倍體系、balancing seat）？「情境感知」是否止於開叫層，競叫後的後續發展表達力如何？
5. 驗證規則（val-001～014）在橋牌語義上是否**檢查了對的東西**？val-002 重疊偵測採保守策略，這會漏掉哪些真實矛盾？val-001 HCP 覆蓋完整性對「刻意 Pass 的區間」如何處理？

### D2. DSL / 語言設計品質（以語言設計者之眼）
1. YAML 作為載體的取捨：錨點/合併、多行字串、型別歧義對本 DSL 的影響；規格是否明確限制了允許的 YAML 子集？
2. `foreach_suit` 展開器的語義是否封閉、可預測？2 層巢狀上限是設計決定還是實作妥協？變數（`${M.other}`、`${M.transfer_from}`）語義是否在規格中被完整定義？
3. Convention namespace（`scope/name-vN`）、參數化、`conflicts_with`/`requires` 的模組系統設計，與成熟套件生態（semver、lockfile、傳遞依賴解析）相比缺什麼？
4. 規格 (SPEC/SUPPLEMENT/JSON Schema) 三者是否一致？JSON Schema 與 Pydantic 模型是否會 drift？由誰作為 single source of truth？
5. `completeness` 漸進式定義欄位在工具鏈中是否真的被消費（驗證器是否據此調整嚴格度），還是裝飾性欄位？

### D3. 軟體工程執行品質（以工程師之眼）
1. 架構分層（YAML → Pydantic → 驗證 → 模擬 → 匯出）是否落實？找出跨層洩漏（例：exporter 直接碰 YAML 原始結構、validator 依賴展開前/後狀態不一致）。
2. **測試品質重於數量**：851 個測試中，多少是 tautological（測 Pydantic 本身行為）？property-based 測試（計畫書提到 hypothesis）是否真的存在？匯入/匯出是否有 round-trip 測試（BBDSL→BML→BBDSL 語義保真）？82% 覆蓋率的未覆蓋 18% 集中在哪些高風險模組？
3. 模擬引擎：two-phase rejection sampling 的統計正確性（是否引入分佈偏差）？拒絕率過高時的行為？`ns_path` 偶/奇深度導航規則能否處理**有對手干預的競叫**，還是只支援 N/S 無干擾拍賣？auction 終止條件的邊界案例？
4. 匯入器的失敗模式：UnresolvedNode 的比例在真實世界 BML 檔上實測是多少？匯入後直接 validate 能過幾條規則？
5. CLI 的錯誤處理、exit code 一致性、跨平台（Windows 路徑、編碼）行為。
6. `bbdsl-platform`：安全面（OAuth flow、JWT 管理、上傳 YAML 的反序列化攻擊面、Monaco 即時驗證的 DoS 向量）、與核心套件的版本耦合策略。

### D4. AI 宣稱的實質性（以 AI 研究者之眼）— 本審查的重點戰場
1. **白皮書 vs 程式碼的落差**：`README.md` 的 `ai_meta`（tolerances、psych_probability、leakage_risk）在 SPEC 與 Pydantic 模型中是否存在？若不存在，白皮書是否構成 overclaim？要求逐項對照表。
2. BCC 理論本身的健全性：
   - 貝氏更新公式在 52! 狀態空間下的粒子濾波近似，粒子退化（degeneracy）與重採樣策略是否被討論？
   - `γ = 1 - 1/|H_w|` 這類置信度定義是啟發式還是有資訊理論根據？README-bcc 範例中的 likelihood 設定（0.95/1.0/1.0）是否 cherry-picked？
   - VoI Minimax 效用函數中 α、β 的估計方法完全未定義——這是理論框架的核心缺口還是留白？
   - 雙向飛牌範例宣稱混合策略可使莊家 VoI 歸零，此結論在賽局理論上是否嚴格成立（對照 restricted choice 與已知的 falsecarding 均衡文獻）？
3. AI KB 匯出（RAG 用 JSONL）的實際可用性：扁平化序列 + 自然語言描述，對 LLM 檢索是否真的比直接餵 YAML 有優勢？有無任何實驗證據？
4. 「讓 AI 理解而非複述制度」的宣稱，目前工具鏈提供的最強能力（selection rules 引擎 + 模擬）距離此目標還差哪幾層？
5. Phase 2–4 的 BCC roadmap（粒子濾波 POC → PettingZoo/OpenSpiel 環境 → self-play）在工程上的可行性與工作量級估計是否誠實？

### D5. 生態互通性宣稱的驗證
1. BML / BBOalert 雙向轉換的**語義損耗矩陣**：哪些 BBDSL 語義在匯出時丟失？哪些來源語義在匯入時被丟進 UnresolvedNode？
2. Dealer script 橋接：constraint→dealer 的表達力交集有多大？dealer 無法表達的 BBDSL 約束如何降級？
3. PBN 匯出（含 [Note] 嵌入 BBDSL 語義）是否符合 PBN 2.1 標準、能否被主流工具（BBO、Bridge Composer）讀取？
4. 白皮書承諾的 BSS / LIN 相容目前狀態為何？

### D6. 文件與現實的一致性（Documentation Drift）
1. README、CLAUDE.md、IMPLEMENTATION-PLAN、SPEC 之間的版本與狀態描述是否互相矛盾？（例：README-bbDsl 專案結構圖與實際目錄、範例路徑指向 `process/1-discover/sayc.bbdsl.yaml` 但實際在 `examples/`）
2. 「851 tests, 82% coverage」等數字是否可重現？審查者應實際執行 `uv run pytest` 驗證。
3. 授權雙軌制（MIT + CC-BY-SA-4.0）在檔案層面是否落實（LICENSE 檔案、檔頭宣告、registry/ 目錄是否存在）？

---

## 四、審查方法與證據標準（Methodology & Evidence）

1. **一切結論須附證據**：引用 `檔案路徑:行號`；宣稱可執行的問題須附重現指令與實際輸出。
2. **實際執行，不只閱讀**：
   - `uv run pytest tests/` 驗證測試數與通過狀態
   - `uv run bbdsl validate examples/*.bbdsl.yaml` 驗證 14 條規則宣稱
   - 抽樣執行 simulate / compare / export pbn 並人工檢查輸出的橋牌正確性（如：拍賣序列是否合法、PBN 是否 well-formed）
   - 對匯入器投餵至少一份真實世界 BML 檔，量測 UnresolvedNode 比例
3. **區分判定等級**：每項發現標記 `CONFIRMED`（已重現/已在程式碼中定位）或 `PLAUSIBLE`（合理推測但未完全驗證），不得混用。
4. **區分層次**：規格缺陷（spec bug）、實作偏離規格（implementation bug）、文件過時（doc drift）、願景過度宣稱（overclaim）是四種不同的問題，須分開歸類。
5. **不重複已知限制**：CLAUDE.md 與 ADR 中已明示的設計取捨（如 val-002 保守策略、ADR-7 平台獨立 repo），只在「取捨本身不當」時才列為發現，否則不佔篇幅。

---

## 五、嚴重度分級（Severity Taxonomy）

| 等級 | 定義 | 例 |
|------|------|-----|
| **Critical** | 核心宣稱不成立、資料損毀、橋牌語義根本性錯誤、安全漏洞 | 模擬引擎產出非法拍賣；範例制度 forcing 鏈自相矛盾且驗證器未偵測 |
| **Major** | 功能在常見情境失效、規格與實作明顯背離、宣稱與現實有實質落差 | 白皮書的 ai_meta 欄位在 schema 中不存在；round-trip 轉換丟失關鍵語義且無警告 |
| **Minor** | 邊界案例、文件不一致、可用性缺陷 | README 範例路徑失效；CLI exit code 不一致 |
| **Suggestion** | 設計改進機會、值得投資的方向 | 引入 hypothesis property tests；schema 由 Pydantic 自動生成以消除 drift |

---

## 六、報告產出格式（Deliverable）

審查報告須包含以下章節，全文使用繁體中文，數學與程式術語保留英文：

1. **執行摘要**（≤1 頁）：整體判定（本專案「是什麼 vs 宣稱是什麼」）、Top 5 風險、Top 3 優勢。
2. **宣稱對照表（Claims Audit）**：白皮書/README 每一項可驗證宣稱 → 實作現況 → 判定（成立 / 部分成立 / 不成立 / 未實作屬願景）。
3. **分維度發現**：依 D1–D6 分節，每項發現含：嚴重度、判定等級（CONFIRMED/PLAUSIBLE）、證據（檔案:行號 或 重現指令+輸出）、影響、建議修法。
4. **橋牌領域專項附錄**：三套範例制度的逐叫品抽查表。
5. **BCC 理論評估附錄**：數學框架的健全性分析，含與現有文獻（GIB、Nook、OpenSpiel bridge、restricted choice 理論）的對照。
6. **優先行動清單**：按「修復成本 × 風險削減」排序的 10 項以內具體行動。

---

## 七、審查者須知的專案背景（Context）

- 個人開源專案，開發節奏以 Sprint 為單位，大量使用 AI 輔助開發（見 `prompts/`、`.claude/skills/`）。
- 技術棧：Python 3.11+、Pydantic v2 strict、uv、pytest；平台端 FastAPI + React。開發環境為 Windows。
- Phase 1–4（語言核心、互通、視覺化、模擬）宣稱完成；Phase 5（社群平台）剛起步；BCC 引擎（白皮書 Phase 2–4）**尚無任何程式碼**——審查時對「已實作」與「純理論」適用不同標準：前者驗證執行品質，後者驗證理論健全性與宣稱誠實度。
- 文件語言為繁體中文，程式碼遵循 PEP 8。

---

## 八、審查紀律（Ground Rules）

1. 不因專案有雄心而寬貸，也不因願景未實作而全盤否定——**分開評分**。
2. 發現數量不設額度：沒有問題就明說「未發現」，不硬湊；有系統性問題則不因篇幅而省略。
3. 對無法在時限內驗證的項目，明列為「未審查（Not Reviewed）」而非默認通過。
4. 所有橋牌術語判斷須以主流權威為準（WBF Systems Policy、ACBL Alert Chart、公認制度文獻），有爭議時註明流派差異。
5. 若審查中發現本 Preamble 遺漏的重要審查面向，審查者有義務主動補充並註明。
