# BBDSL / BCC Repo 嚴格審查報告（Codex GPT-5.6）

> 審查日期：2026-07-13（Asia/Taipei）  
> 審查章程：`ccwLog/reviewPreamble.md`  
> 核心 repo：`5985c08`；Phase 5 子 repo：`bbdsl-platform@f5230fc`  
> 審查立場：橋牌領域正確性 × DSL／語言設計 × AI／不完全資訊賽局；採對抗性審查  
> 判定標記：`CONFIRMED`＝已由程式碼或實際執行確認；`PLAUSIBLE`＝具充分理由但未完成端到端驗證

---

## 一、執行摘要

### 1.1 整體判定：本專案「是什麼」與「宣稱是什麼」

本專案實際上是一套**涵蓋面廣的橋牌制度結構化資料模型、CLI 與格式匯出工具**。Pydantic 模型、YAML loader、14 條驗證規則、selection rules、模擬、題庫、兩種匯入器與多種匯出器均存在；核心測試可重現為 **908 passed、85% coverage**。先前審查所指出的開叫死碼、BML `hearts` 被誤判為 `art`、PBN 莊家判定、不足額叫品及 `eval()` 等問題，從目前程式碼與迴歸測試看來確已修正。

但它**還不是語義可靠的「完整叫牌模擬／教學／AI 推理核心」**。目前最嚴重的差距不是尚未實作 BCC，而是已標示完成的 Phase 3–4 功能會產出錯誤答案：

- 模擬器完全不執行 `forcing` 義務，會在 Stayman、transfer、game force 後讓被迫叫牌者 Pass，卻把拍賣標為完成。
- 題庫逐節點獨立發牌，不經制度的 selection／priority 消歧；本次抽樣中，三套制度的開叫題有 **13.6%–24.4%**、回應題有 **16.8%–24.1%** 的「正解」與引擎自己的選擇不一致。
- `HandConstraint` 暴露的多個欄位和自訂 shape 會被手牌生成器與模擬器靜默忽略；使用者可得到明確違反原約束、卻被引擎判定為符合的牌。
- 手寫 JSON Schema、Pydantic 生成 schema 與實際 loader 是三套不同契約；loader 接受 `bbdsl: "9.9"`、缺少 `bid` 的節點及字串到整數的 coercion。
- Phase 5 平台目前無法從乾淨環境解析後端依賴，前端缺 `package-lock.json`；安全邊界也尚未形成。

因此，本次整體結論為：

| 面向 | 判定 |
|---|---|
| 結構化描述／瀏覽／一般匯出 | **可試用，但需把 Pydantic loader 視為實際契約** |
| 語義驗證 | **部分可用；不能把 14/14 當成制度正確證明** |
| 模擬、比較、PBN 拍賣、Quiz | **不可作為橋牌正解或訓練資料來源** |
| BML/BBOalert 互通 | **可作輔助轉換；存在已量化語義損耗** |
| AI KB | **資料扁平化器成立；「理解」宣稱未被證明** |
| BCC | **概念／研究提案，非可執行理論或引擎** |
| Phase 5 平台 | **開發骨架；不可部署** |

### 1.2 Top 5 風險

| 排名 | 風險 | 等級 |
|---:|---|---|
| 1 | forcing 叫品後可 Pass；「完整叫牌拍賣」核心宣稱不成立 | **Critical** |
| 2 | Quiz 正解與同一制度選擇器不一致，會直接教錯 | **Critical** |
| 3 | 多個 HandConstraint／自訂 shape 被靜默忽略，生成與模擬結果不符合 DSL | **Major** |
| 4 | 手寫 schema、生成 schema、Pydantic loader 漂移；錯版本與缺 bid 文件仍可載入 | **Major** |
| 5 | 平台依賴不可重現，加上預設 JWT、OAuth state 缺失、無請求大小／工作量上限 | **Major** |

### 1.3 Top 3 優勢

1. **核心測試數與 coverage 可重現**：`908 passed in 38.89s`、總 coverage 85%，且三套範例皆為 13 passed / 1 skipped / 0 warnings / 0 errors。
2. **先前 Critical 修正有實質成果**：100 副雙方制度模擬未再出現不足額叫品；PBN 已分離 `[Contract]`／`[Declarer]`；BML round-trip 與詞界測試存在。
3. **架構邊界大致清楚**：models、core、importers、exporters、CLI 與 platform service adapter 分層明確，後續修語義不必推翻整體結構。

---

## 二、審查方法與實測摘要

### 2.1 實際執行

| 指令／探針 | 實際結果 |
|---|---|
| `uv run pytest tests/` | `908 passed in 38.89s`；3488 statements、540 missed、85% |
| `uv run bbdsl validate examples/{precision,sayc,two_over_one}.bbdsl.yaml` | 三者皆 13 passed、1 skipped（val-009）、0 warning、0 error |
| `uv run bbdsl simulate examples/sayc... -n 100 --seed 42` | 可執行；多副 forcing 拍賣錯誤終止 |
| `uv run bbdsl simulate precision --ew-system sayc -n 100 --seed 7` | 未發現不足額叫品；但兩方各走自己的無干擾樹 |
| `uv run bbdsl export pbn ... --deals 10 --seed 42` | PBN 基本 tags 與牌張格式可人工閱讀；內容繼承 forcing 模擬錯誤 |
| BML fixture 匯入後 validate | 26 個 bid nodes 中 3 個 unresolved（11.5%）；5 passed、5 skipped、3 warnings、1 error |
| `uv run ruff check bbdsl tests` | **118 errors**（66 可自動修） |
| `cd bbdsl-platform/backend; uv run pytest` | 依賴解析失敗：registry 找不到 `bbdsl>=0.4.0` |
| `cd bbdsl-platform/frontend; npm test -- --run` | `vitest is not recognized`；且 repo 無 `package-lock.json` |

### 2.2 未審查或有限審查

- 未取得真正外部、未為本 repo 編寫的大型 BML/BBOalert corpus；匯入率只可稱「內建 fixture 結果」，不可外推真實世界成功率。
- 未安裝 Phase 5 前端依賴，故未做瀏覽器互動與視覺回歸；缺 lockfile 本身已阻止可重現安裝。
- 未以 BBO、Bridge Composer 等第三方產品實際載入 PBN/BBOalert；PBN 僅按輸出結構與標準文件人工抽查。
- WBF/ACBL 規範採文件對照，未涵蓋所有 NBO／賽事的地方規則。
- Nook 並無足以重建其方法的公開技術規格，本報告只作能力邊界比較，不推測其內部實作。

---

## 三、宣稱對照表（Claims Audit）

| 出處 | 可驗證宣稱 | 實作／實測 | 判定 |
|---|---|---|---|
| `README.md:156` | 908 tests、85% coverage | 實測完全一致 | **成立** |
| `README.md:165`、`README-bbDsl.md:123` | 14 條語義驗證規則 | 14 個 rule handlers 存在；但 val-007 不驗 forcing 後續義務 | **部分成立** |
| `README.md:189` | 「完整叫牌拍賣模擬」 | 1NT–2C/2D/2H 後可三 Pass；無 forcing 執行 | **不成立** |
| `README-bbDsl.md:160` | 三套「完整制度範例」 | metadata 自稱多區 partial/todo；SAYC 與 2/1 有主流制度錯置 | **不成立** |
| `CLAUDE.md:20,122` | Pydantic v2 strict | models 未設定 `strict=True`；`"12"` 被 coercion 成 int | **不成立** |
| `README.md:115` | JSON Schema 驗證器完成 | loader 只呼叫 Pydantic；`jsonschema` 在套件中零使用 | **部分／誤導** |
| `README-bbDsl.md:20,129` | AI 能「理解」而非複述 | AI KB 產生 66 筆扁平 JSONL；無 eval 或對照實驗 | **未證實** |
| `README.md:44-45` | ai_meta 尚未實作 | SPEC/schema/models 均無；文件已誠實警示 | **成立（願景）** |
| `README-bbDsl.md:106-115` | context 資料層有、引擎未實作 | 模型與 val-009 存在，無 matcher | **成立（限制已揭露）** |
| `README-bbDsl.md:104` | Dealer constraint 對映 | 可表達部分欄位；不可表達欄位已有 dropped warning | **部分成立** |
| `README-bbDsl.md:150` | PBN 匯出完成、LIN 整合在 roadmap | 核心 PBN 存在；核心無 LIN/BSS，平台 fallback 丟棄 auction | **PBN 部分成立；LIN 未成立** |
| `CLAUDE.md:110-112` | all openings reachable | 以 500 副迴歸測試守住「曾出現」；不證明分佈或語義正確 | **狹義成立** |
| `README.md:184-190` | Phase 4 AI 整合完成 | AI KB/Dealer/模擬/compare 程式存在，但模擬與 quiz 語義錯 | **功能存在，品質門檻不成立** |
| `bbdsl-platform/README.md` | Docker 快速啟動 | backend build context 無法取得未發布的 bbdsl；seed 指令路徑不存在 | **不成立** |
| `bbdsl-platform/README.md` | OAuth、Registry、即時驗證 | skeleton 存在；無 OAuth state/PKCE，無工作量限制，測試環境不可解析 | **骨架成立，不可部署** |

---

## 四、分維度發現

## D1. 橋牌領域正確性

### D1-F1【Major／CONFIRMED／領域錯誤】SAYC 範例混入 2/1 GF，且高花 1NT 回應錯標 forcing

**證據**：

- `examples/sayc.bbdsl.yaml:251-258` 把 `1H-1NT` 定義為 6–12 HCP、`forcing: one_round`；`1S-1NT` 亦同（`:314-321`）。
- `examples/sayc.bbdsl.yaml:259-276,322-348` 把高花開叫後二線新花定為 13+、`forcing: game`，description 甚至寫 `(2/1)`。
- ACBL 官方 SAYC booklet 明定高花後 1NT 為 **6–9、NOT forcing**；二線新花為 **10+ 且 forcing one round**，不是自動 game force（[ACBL SAYC System Booklet](https://web2.acbl.org/documentLibrary/play/sayc_book.pdf)）。

**影響**：旗艦 `sayc` 範例在制度身份上錯誤；AI KB、Convention Card、BML 匯出及題庫會一致複製錯誤資訊。

**建議**：SAYC 與 2/1 共用 opening structure 可以，但 responses 必須分離；SAYC 改回 1NT non-forcing 6–9、二線新花 10+ F1，補 Jacoby 2NT／標記未涵蓋項目。若刻意採混合制，system name 不得稱純 SAYC。

### D1-F2【Major／CONFIRMED／領域錯誤】SAYC 低花回應 priority 違反 up-the-line；範例說明與 hand constraints 多處不一致

`examples/sayc.bbdsl.yaml:109-138` 對 1C 回應給 1S priority 10、1H priority 20、1D priority 50，會在 4-4 高花時先叫 1S。ACBL SAYC 對一線回應採 **up-the-line in principle**。此外：

- `1H-1NT` description 否認三張支持與四張黑桃，但 hand 僅限制 HCP（`:251-258`）。
- 1NT 後 Stayman 節點沒有 responder hand（`:389-397`），模擬把它當 catch-all；100 副中 5 次 Stayman，有 2 次無四張高花、3 次低於 8 HCP。
- 弱二後 2NT feature ask 無任何 game-interest 約束（`:501-509,530-538,558-566`）。ACBL SAYC 明示 2NT forcing 且顯示 game interest，開叫者必須再叫。

**影響**：即使 selection rules 正常，條件本身也不足以表達 description，機器行為與人類讀到的語義分裂。

**建議**：所有自然語言 deny 條件必須進入可執行 constraint；新增「description 與 formal constraint 對照」人工審查清單，不能由 val-002 取代。

### D1-F3【Major／CONFIRMED／規格缺陷】Alert 只有單一布林值，無法表達規範轄區與模式

`BidMeaning.alertable: bool`（`bbdsl/models/bid.py:48-53`）沒有 `authority`、`event_profile`、screens／online 模式或 explain/announce 類型。WBF 明示自身政策不覆蓋各 Zone/NBO 規範，且「人工叫應 Alert、自然叫通常不 Alert」仍有特別約定例外（[WBF Alerting Policy](https://championships.worldbridge.org/wp-content/uploads/2024/01/WBFAlertingPolicy.pdf)）。

**影響**：同一份 BBDSL 無法可靠產出 WBF、ACBL 或地方賽事都正確的 alert 資料；boolean 容易被誤認為普世規則。

**建議**：改為 `disclosure: {profile, action: alert|announce|none, explanation, effective_from}`；`alertable` 僅保留為相容欄位。

### D1-F4【Major／CONFIRMED／表達力缺口】HandConstraint 是寬鬆欄位袋，不足以表示真實制度的互斥與路徑語義

`HandConstraint`（`bbdsl/models/bid.py:12-40`）主要是欄位 conjunction；`conditions` 只是 `list[dict]`，無型別與語義。缺少可執行的 `all_of/any_of/not`、relative suit、先前叫牌否定、牌序 captaincy 與 relay state。canapé（第二套長於第一套）、multi-meaning call、兩面性防禦、完整 relay 問答及 balancing seat 均只能靠自然語言、priority 或外部程式補洞。

**影響**：目前能良好表示「單一節點的點力＋牌長」，不能聲稱已形成一般橋牌制度的形式語義。

**建議**：先定義 typed constraint algebra 與 auction-state predicates，再擴展 examples；不可繼續以 `extra="allow"`／任意 dict 當作語言演進機制。

## D2. DSL／語言設計品質

### D2-F1【Major／CONFIRMED／實作偏離規格】實際 loader 不使用手寫 JSON Schema，且接受錯版本、缺 bid 與型別 coercion

**程式證據**：`load_document()` 只做 `BBDSLDocument.model_validate(data)`（`bbdsl/core/loader.py:52-55`）；套件內搜尋不到任何 `jsonschema` 使用。`BBDSLDocument.bbdsl` 只是預設字串，沒有 `Literal["0.3"]`（`bbdsl/models/system.py:113-121`）；`BidNode.bid` 可為 None（`bbdsl/models/bid.py:63-76`）。

**最小重現結果**：

```text
輸入：bbdsl: "9.9"；opening 無 bid；hcp.min: "12"；另有 unknown_top
結果：version='9.9'；bid=None；hcp_min=12 (int)；unknown_top 被靜默忽略
```

手寫 `bbdsl-schema-v0.3.json` 則要求 version const、頂層 required；與 `schema/bbdsl-v0.3-generated.json` 的 `git diff --no-index --stat` 為 **2540 行差異（1961 insertions, 579 deletions）**。

**影響**：外部工具依手寫 schema 拒絕的文件，官方 CLI 可能接受；未知欄位可能被忽略或因不同 model 的 `extra` 設定而保留，行為不可預測。

**建議**：指定唯一 source of truth。推薦 Pydantic model 採 strict + forbid，補 version Literal 與 BidNode discriminator，再由它生成並 snapshot-test canonical schema；若堅持手寫 schema，loader 必須先以 Draft-07 驗證。

### D2-F2【Major／CONFIRMED／模組系統未落實】Convention ref 只驗「存在」，不會解析或接入叫牌樹

`val-004` 只收集 ref 名稱（`bbdsl/core/validator.py:390-447`）；core 中沒有 convention expansion/linker。模擬器 `_navigate_tree` 只走 inline `responses/continuations`（`bbdsl/core/sim_engine.py:237-290`）。因此 SAYC 的 Stayman 正式 responses 雖定義於 `conventions.stayman`（`examples/sayc...:50-83`），`1NT-2C` inline ref 沒有 continuations，開叫者隨即 Pass。

`parameters`、`requires`、`recommends` 亦僅為資料欄位；registry install 沒有 semver constraint、lockfile 或傳遞依賴解析。

**影響**：namespace 目前是標籤與下載索引，不是可組合模組系統。

**建議**：新增 linker phase：resolve ref → instantiate parameters → resolve dependency DAG/conflicts → materialize immutable expanded tree；輸出 lockfile，所有 validator/simulator/exporter 共用同一 resolved IR。

### D2-F3【Minor／CONFIRMED／規格缺陷】`completeness` 不控制工具嚴格度，YAML 子集也未定義

`completeness` 只在 summary／視覺輸出被讀取；Validator 不依 complete/partial/todo 調整 rule severity。SAYC metadata 明列 responses partial、defensive/competitive todo（`examples/sayc...:21-27`），README 卻稱「完整制度」。規格也未說明 aliases、merge keys、多文件 YAML、scalar coercion 等是否屬合法 BBDSL 子集。

**建議**：把 completeness 變成可驗證 contract，例如 `openings: complete` 時禁止 coverage gap，`competitive: todo` 時 simulation 明示降級；制定 YAML 1.2 safe subset，禁止 merge/alias 或在展開後保存 provenance。

## D3. 軟體工程執行品質

### D3-F1【Critical／CONFIRMED／實作缺陷】模擬器不執行 forcing，卻宣稱產生完整拍賣

`simulate_deal()` 選出 bid 後只檢查足額性與三 Pass 終止（`bbdsl/core/sim_engine.py:572-625`），全檔沒有讀取 `meaning.forcing`。當 forcing 節點沒有 inline children，下一輪 candidates 為空，搭檔直接 Pass。

實測 SAYC 100 副中反覆出現：

```text
Deal 6 : Pass Pass 1NT Pass 2C Pass Pass Pass  -> 2C
Deal 22: 1NT Pass 2D Pass Pass Pass           -> 2D
Deal 54: 1NT Pass 2H Pass Pass Pass           -> 2H
Deal 44: 1S Pass 2C Pass Pass Pass             -> 2C
```

其中 2C Stayman、2D/2H transfer、二線新花均由檔案標為 forcing。`val-007` 也未攔截：它只在 parent=`game` 且 child 明寫 `signoff/none` 時報錯（`bbdsl/core/validator.py:573-605`）；不檢查 forcing node 是否有合法 continuation，也把 child forcing 缺省視為延續，不驗實際拍賣。

**影響**：simulate、compare、PBN、任何下游 AI 資料均可把違反制度義務的拍賣當成完成結果。這符合章程對 Critical 的定義。

**建議**：auction state 加入 forcing obligation；forcing call 後禁止該方 Pass，若 tree/linker 無合法續叫應回報 `IncompleteSystemError`，不可悄悄 Pass。val-007 必須做 path-level obligation analysis，並新增 `1NT-P-2C-P-P` 必敗的端到端測試。

### D3-F2【Major／CONFIRMED／靜默語義遺失】發牌器／模擬器忽略大部分 HandConstraint；自訂 shape 亦不生效

模型宣告 `losing_tricks`、`total_points`、`bid_suit`、`longest_suit`、`second_suit`、`suit_quality`、`four_card_major`、`support_for_partner`、`stopper_in`、`specific_cards`、`conditions`（`bbdsl/models/bid.py:12-40`）。但：

- `generate_hand()` 只檢查 HCP、hard-coded shape、四花牌長與 controls（`bbdsl/core/hand_generator.py:281-300`）。
- simulator `_matches_constraint()` 也只檢查相同子集（`bbdsl/core/sim_engine.py:163-193`）。
- `_check_shape()` 對非 `balanced`／`semi_balanced` 的 ref 直接回 True（`hand_generator.py:147-160`）。

最小重現：宣告 `specific_cards=[AS,KH]`、`losing_tricks=0`、`stopper_in=diamonds`，生成牌為 `S:T H:Q D:KQT9542 C:J654`；沒有 AS/KH，仍得到 `_matches_constraint(...)=True`。對 Precision 2D 的 `precision_2d` shape，seed 0–2 分別生成 8-4-1-0、7-4-1-1、5-5-2-1，沒有一手是宣告的 4=4=1=4／4=4=0=5。

**影響**：題庫、任何直接使用 hand_generator 的工具、沒有 selection_rules 保護的模擬節點會產生虛假合規資料。

**建議**：建立單一 `ConstraintEvaluator`，每個 model field 必須是「已實作」或明確拒絕，禁止 silent ignore；shape ref 由 definitions 統一解析，並以 property-based tests 驗證「生成結果必滿足 evaluator」。

### D3-F3【Critical／CONFIRMED／教學資料錯誤】Quiz 逐節點發牌，未用制度消歧，造成大量錯標答案

`generate_opening_questions()` 對每個 opening 的局部 hand constraint 發牌（`bbdsl/core/quiz_generator.py:172-185`），不呼叫 selection_rules；response 題同樣對每個 response 獨立生成（`:262-275`），不檢查 sibling priority／specificity。重現探針把每題再送回正式選擇器：

| 制度 | 開叫題錯標 | 回應題錯標 |
|---|---:|---:|
| Precision | 44 / 180（24.4%） | 74 / 440（16.8%） |
| SAYC | 38 / 280（13.6%） | 154 / 760（20.3%） |
| 2/1 GF | 37 / 180（20.6%） | 183 / 760（24.1%） |

例：題目先依 1D 局部條件發牌，但 selection rules 判定應開 2C；回應題標 1C-1D，priority 卻判定應答 1H/1S。

**影響**：Phase 3「教學模式」會把系統自身認為錯的叫品當正解；不應發布或拿來訓練模型。

**建議**：以「先隨機發完整牌 → 呼叫唯一 BidDecisionEngine → 以結果分桶」生成題目；每題建立 oracle invariant：`engine(hand,state) == correct_bid`。修好前停用 quiz 發布。

### D3-F4【Major／CONFIRMED／模擬模型缺口】有競叫時只是兩棵無干擾樹交錯，對手行為不影響制度語義

N/S 與 E/W 分別維護 `ns_path`、`ew_path`（`sim_engine.py:565-592`），對手叫品不進入另一方 path；補丁只在最後用 shared `highest_bid` 過濾不足額（`:595-609`）。因此競叫結果在規則上合法，卻不是 competitive bidding：沒有 double/redouble、negative double、cuebid、balancing、context_overrides 或「對手叫後 conventions off」。

**影響**：`--ew-system` 不能用來評估兩制度對抗；compare 也只比較各自對同一副牌的獨白。

**建議**：公開 API 改名為 `interleaved_noncompetitive_demo` 或加顯著 warning；真正模擬需以完整 auction history 作 decision state，讓 opponent matcher 與 legality/forcing 共用同一 state machine。

### D3-F5【Major／CONFIRMED／測試品質】908 綠燈未覆蓋核心語義 invariant，且 property-based testing 為零

- `hypothesis` 是 dev dependency，但 tests 中 `from hypothesis`／`@given` 為 0。
- `tests/test_core/test_sim_engine.py:466-480` 只驗「會終止」「最後三個是 Pass」「SAYC no crash」，反而把 forcing 後 Pass 視為成功。
- `tests/test_exporters/test_svg_tree.py:102` 使用 `assert ... or True`，永遠通過。
- 多個 exporter 與 system 測試名稱是 `*_no_crash`，只驗型別／存在。
- coverage 缺口集中於 `cli/main.py` 46%、`cli/registry_client.py` 44%、`core/loader.py` 52%。

**影響**：測試數量高，但沒有守住「合法、符合制度、round-trip 不失義、題庫答案等於決策引擎」等真正品質門檻。

**建議**：將測試 KPI 從數量改為 invariant matrix；至少引入 Hypothesis 驗牌張唯一性、constraint satisfaction、schema/model 等價、合法 auction、forcing、quiz oracle 與 round-trip loss contract。

### D3-F6【Major／CONFIRMED／可重現性】Phase 5 乾淨環境不能安裝／測試

- `bbdsl-platform/backend/pyproject.toml` 依賴 `bbdsl>=0.4.0`，但該套件在 resolver registry 不存在；`uv run pytest` 在收集前失敗。
- backend Dockerfile 以 `backend/` 為 build context，無法 COPY 父層核心 package（`backend/Dockerfile:1-9`）。
- frontend CI 使用 `npm ci`，但 `frontend/package-lock.json` 不存在；本機 `npm test -- --run` 亦找不到 vitest。
- platform README 的 seed 指令是 `python -m app.seed`，實際檔案為 `seed/load_seed.py`。

**影響**：README、Docker 與 CI 的 happy path 均不可重現；平台測試結果未知。

**建議**：若維持獨立 repo，先發布／以 git SHA 固定核心套件；開發期用 uv source/path override。提交 lockfile，CI 第一關驗 Docker build 與 clean checkout install。

### D3-F7【Major／CONFIRMED／安全與 API 設計】平台沒有部署安全邊界，且部分 API 參數／格式宣稱不生效

**安全證據**：

- JWT secret 預設為公開字串 `change-me-in-production`，compose 也保留此 fallback（`backend/app/core/config.py:12-15`、`docker-compose.yml`）。無 production startup guard。
- GitHub／Google OAuth flow 沒有 state 或 PKCE；前端 authorize URL 也沒有 state（`frontend/src/App.tsx:50-59`），callback 只取 code（`AuthCallback.tsx:16-30`）。有 login CSRF／session swapping 風險。
- WebSocket 無認證、origin、message size、rate/concurrency limit，並在 event loop 同步執行 YAML parse+14 rules（`backend/app/api/v1/validate.py:12-31`）。
- anonymous share 可永久寫入任意大小字串，無 validation／quota（`share.py:21-67`）；compare 的 `n_deals` 無上限（`compare.py:13-30`）。

**功能證據**：

- ExportRequest 有 `n_deals`、`seed`，handler 卻只轉交 locale（`export.py:16-38`），參數完全被忽略。
- LIN fallback 明寫 `mb|` 空拍賣，且 loop 只保留最後一副 PBN 資料（`services/bbdsl_service.py:121-163`），不能稱 LIN 互通。

**建議**：Phase 5 上線前建立 threat model；secret 必填且做 entropy check；OAuth state+PKCE；所有 body 限長、n_deals 限上界、validation 移到 bounded worker；anonymous storage 加 quota/TTL。移除假的 LIN 或明標 preview-only。

## D4. AI 宣稱與 BCC 理論

### D4-F1【Major／CONFIRMED／Overclaim】AI KB 是可用的扁平資料格式，不是「理解」證據

`export ai-kb` 對 SAYC 產出 66 筆 JSONL，每筆是 path、formal fields 與一段 `context_text`；核心函式正是 `_flatten_to_rules`／`_build_context_text`（`bbdsl/exporters/ai_kb_exporter.py:135-230`）。它適合索引，但沒有：

- retrieval／embedding 設計與 eval；
- 給定手牌選叫、給定叫序推斷分佈的準確率；
- 與直接檢索 YAML／BML 的 A/B；
- schema version、source hash、loss/provenance 欄位。

因此 `README-bbDsl.md:20,129` 的「理解而非複述」未被證明。更嚴重的是它會忠實放大 D1 的錯誤 SAYC 與 D3 的 forcing 缺口。

**建議**：建立最小 eval：50–200 題 bid selection／meaning inference，對照 YAML direct、JSONL RAG、executable engine；在達標前改寫為「RAG-friendly export」。

### D4-F2【Major／CONFIRMED／理論錯誤】BCC 對狀態空間與 coverage 的敘述不精確

`README-bcc.md:18` 把 `52!/(13!)^4` 稱為「對搭檔的牌」可能數；它其實是四個有標籤座位的完整發牌數。已知自己的 13 張牌後，搭檔單手候選是 `C(39,13)`；若還要分配另兩手才是 multinomial。`:81` 又宣稱以叫牌路徑「積分」覆蓋全部發牌，卻未定義 measure、opponent policy、seat/vulnerability 或 stochastic strategy。

**建議**：把狀態定義為 information set／belief state，明確區分 full deal、player observation、partnership convention 與 opponent model；coverage 應針對可達 decision states，而非把所有 full deals 面積相加。

### D4-F3【Major／CONFIRMED／理論缺口】`γ = 1 - 1/|H_w|` 不是資訊理論置信度

文件先稱 γ 為後驗／先驗資訊增益（`README-bcc.md:382-386`），卻改以手牌張數 heuristic 定義（`:388-393`）。此式不含 observation、intent、emission distribution 或 context；五張牌也不代表五個有區辨力的合法 action。真正可比較的量應是 posterior entropy reduction、KL divergence 或 mutual information，例如 `I(Intent; Card | Γ)`。

**建議**：將目前 γ 改名 `choice_freedom_heuristic`，不要稱「嚴格／資訊理論」；以 emission model 導出的 expected information gain 取代。

### D4-F4【Major／CONFIRMED／理論缺口】Bayesian 範例的 likelihood／prior 是任意示意，不能支持 32.2% 結論

`README-bcc.md:402-417` 只列三個等先驗世界，likelihood 直接設 0.95/1/1；未按組合數、已知牌、合法跟牌、玩家策略或 signal agreement 校準。Bayes 公式本身正確，但 32.2% 是輸入假設的代數結果，不是橋牌結論。

**建議**：把例子標為 toy illustration；由完整條件生成器計算 prior，從可估計 policy 產生 likelihood，並作 sensitivity analysis。

### D4-F5【Major／CONFIRMED／理論缺口】VoI utility 並非已可計算的 Minimax；50/50 使 VoI 歸零未被證明

`README-bcc.md:469-499` 需要 single-dummy value function、兩套 belief、α/β criticality 與 declarer strategy，但均未定義估計方法；α、β甚至重複縮放了已以 expected tricks 定義的 VoI。`:527-531` 從單一 Q42 世界猜測 50/50 mixed strategy，直接宣稱各世界發射機率相同與 VoI=0，沒有解完整 payoff matrix／information sets，也沒有證明其他 Q 位置世界採相同 likelihood。

限制選擇本身確是 Bayesian updating；但 falsecard equilibrium 必須在所有相關 holding／observation 上同時求解，不能由局部隨機化推出。可參考 restricted choice 的 Bayes 表述（[Miller & Sanjurjo, 2019](https://www.aeaweb.org/articles?id=10.1257/jep.33.3.144)）。

**建議**：先做單一花色小型 extensive-form game，以 CFR／sequence form 解 equilibrium，再比較 heuristic；不要先寫「理論聖杯」。

### D4-F6【Major／PLAUSIBLE／工程規模】Particle filter → OpenSpiel → self-play 超人 AI 的 roadmap 嚴重低估工作量

文件只以「維持代表性樣本」處理狀態爆炸（`README-bcc.md:185-190`），沒有 ESS、weight degeneracy、resampling、rejuvenation、proposal distribution 或 likelihood calibration。GIB 本身結合多項搜尋與工程技術（[Ginsberg, GIB](https://arxiv.org/abs/1106.0669)）；determinization 在 imperfect-information game 有 strategy fusion／non-locality 問題（[Frank & Basin](https://doi.org/10.1016/S0304-3975(00)00083-9)）。OpenSpiel 是一般框架，不會替專案提供 bridge belief model、system semantics 或 reward/evaluation（[OpenSpiel paper](https://arxiv.org/abs/1908.09453)）。Nook 公開挑戰主要是受限 declarer-play，不等同完整叫牌＋防守。

**建議**：收斂為可驗證子題：「單一花色 signal emission + posterior calibration + Standard/UDCA information-efficiency comparison」；先交付 simulator、dataset、metrics 與 baseline，再談 MARL。

## D5. 生態互通性

### D5-F1【Major／CONFIRMED】BML/BBOalert 並非語義無損雙向格式

| 語義 | BML | BBOalert | 備註 |
|---|---|---|---|
| bid path／自然語言 | 大致保留 | context/call/explanation | 可讀性層 |
| HCP／簡單牌長 | heuristic 可來回 | 只進 explanation | 非 formal round-trip |
| artificial/alertable/forcing | 關鍵字 heuristic | 文字化 | 目前詞界 bug 已修，但仍非 schema mapping |
| priority／selection_rules | **丟失** | **丟失** | 回匯後無消歧 |
| custom shape／conditions | 多數丟失或 unresolved | 丟失 | |
| convention parameter/dependencies | 註解或丟失 | 丟失 | |
| context_overrides／seat/vulnerability | 丟失 | exporter 有限文字化 | |
| i18n/provenance/license | 部分選 locale，其他丟失 | 丟失 | |

內建 `sayc_opening.bml` 匯入：26 nodes 中 3 unresolved（Stayman、兩個 transfer，11.5%），validate 後 1 個 error（missing pattern refs）、3 warnings、5 skipped。這還是簡化 fixture，不是真實世界成功率。

**建議**：每個 exporter 提供 machine-readable `LossReport`；round-trip tests 比較 resolved IR，而非只比局部欄位。對匯入產物自動補 definitions 或把 shape 保留為 unresolved，不能留下 dangling ref。

### D5-F2【Major／CONFIRMED】PBN 格式修正成立，但輸入拍賣語義不可靠；LIN fallback 不是互通

PBN 抽樣已見合法分離的 `[Contract "4H"]`、`[Declarer "N"]`、`[Auction "N"]` 與 52 張唯一牌；這部分比先前版本進步。PBN 2.1 參考文件可見 [Portable Bridge Notation 2.1](https://www.sackab.fi/data/PBN/PBN21a_1.pdf)。但 PBN 內容來自 D3-F1 的錯誤 forcing auction，格式合規不等於橋牌語義正確。

核心沒有 BSS／LIN exporter；平台 `_pbn_to_lin()` 只產生一筆、`mb|` 為空，應視為 mock，不是 LIN support。

### D5-F3【Minor／CONFIRMED】Dealer 降級已可見，但各工具的 constraint coverage 不一致

Dealer bridge 現在對不可表達欄位回報 dropped/warning，`specific_cards` 可轉 `hascard()`；這項先前缺陷已修。然而同一欄位在 Dealer 可被處理，卻在 hand_generator／simulator 被忽略（D3-F2）。

**建議**：建立全工具 `ConstraintCapabilityMatrix`，CI 強制每欄在 validate/generate/simulate/export 的狀態一致：supported、rejected 或 degraded，禁止某工具默默忽略。

## D6. 文件與現實一致性

### D6-F1【Minor／CONFIRMED】文件仍有多處 drift

- `CLAUDE.md:20,122` 宣稱 strict mode，實際非 strict。
- `BBDSL_IMPLEMENTATION-PLAN.md:20-24` 還稱 val-001/003 為 stub；`:91` 稱 8 rules，`:128` 又稱 14 rules。
- `BBDSL_IMPLEMENTATION-PLAN.md:13`、`LICENSING.md` 仍把 CC-BY-SA 範圍寫成不存在的 `registry/`、`examples/conventions/`；README 已改為實際 `examples/*.bbdsl.yaml`。
- `examples/sayc.bbdsl.yaml:98,177` 註解仍寫 1+ minor，實際 constraint 已是 3+。
- `README.md:189` 的「完整拍賣」與 D3-F1 衝突；`README-bbDsl.md:160` 稱三套「完整制度」，YAML metadata 自稱 partial/todo。

**建議**：把 implementation plan 標成歷史計畫並加 status matrix；以 docs tests 驗 CLI examples、數字、路徑與授權範圍。

### D6-F2【Minor／CONFIRMED】Lint gate 未達標

`uv run ruff check bbdsl tests` 回報 118 項：unused imports/variables、import order、line length、ambiguous names；其中包括 `sim_engine.py` 未使用的 `ns_responder`，與測試中的永真 assertion。這不直接造成核心語義錯，但顯示 CI 未把文件宣告的 lint command 當 gate。

---

## 五、橋牌領域專項附錄：三套範例逐叫品抽查

### 5.1 Precision Club

| 叫品 | YAML | 評價 |
|---|---|---|
| 1C | 16+，人工，F1 | 主流 Precision 核心合理；但所有續叫幾乎無 opener rebid，模擬會在 response 後停 |
| 1D | 11–15、2+ D、residual | 可視為特定 Precision 變體；residual 依 selection_rules 而非 constraint |
| 1H/1S | 11–15、5+ | 合理 |
| 1NT | 13–15 balanced | 經典弱 NT 版本合理 |
| 2C | 11–15、6+ C natural | 修正後合理；2D inquiry 的 11+ 是變體，需標資料來源 |
| 2D | 11–15、4=4=1=4／4=4=0=5 | 制度概念合理；hand_generator 完全不執行 custom shape |
| 2H/2S | 5–10、6+ weak | 合理變體；2NT feature ask 缺 game-interest constraint 與續叫 |

### 5.2 SAYC

| 叫品／序列 | YAML | 主流 SAYC 對照 |
|---|---|---|
| 1C/1D | 12–21、3+ | 基本合理；註解的 1+ 已過時 |
| 1H/1S | 12–21、5+ | 基本合理 |
| 1H/1S–1NT | 6–12、F1 | **錯**：ACBL SAYC 為 6–9、non-forcing |
| 1M–2m | 13+、GF | **錯置 2/1**：SAYC 為約 10+、forcing one round |
| 1C responses | S→H→D priority | **不符 up-the-line** |
| 1NT | 15–17 balanced | 合理 |
| 1NT–2C/2D/2H | convention 基本名稱正確 | responder constraint/continuation 不完整；實測會錯用並在 forcing call 後 Pass |
| 2C | 22+ artificial | 合理簡化，但 opening 標 `forcing: game` 對某些強、長套牌的制度語義過度簡化 |
| weak two | 6–11 exactly 6 | 可接受的簡化；官方 SAYC 容許少數好五張／差七張，且 2NT 後必再叫 |
| 3-level preempt | 5–10、7+ | 可作簡化，未建模 vulnerability/seat 的 soundness |

### 5.3 Two-over-One Game Force

| 叫品／序列 | YAML | 評價 |
|---|---|---|
| 1M–1NT | 6–12 F1 | 常見 2/1 版本合理；但第三／四家通常不適用，context engine 缺失 |
| 1M–2m | 13+ GF | 核心概念合理，但現代流派常以 12+／opening values；應標 variant |
| 1C–2C、1D–2D | 標成 2/1 GF | **概念錯置**：同花 raise 不是「two-over-one new suit」；若採 inverted minors 應另名與另定義 |
| 1H–3H | 10–12、4+ limit | 可作變體；常見 2/1 會以 Jacoby 2NT 表 game-forcing raise，3M 的意義依 Bergen 等約定而異 |
| 1S–2S | description 寫 limit，constraint 6–9 | **文件內部矛盾**，應為 simple raise 或修改區間 |
| 2C／weak twos | 與 SAYC 類似 | 可作簡化；仍缺 forcing continuation |

---

## 六、BCC 理論評估附錄

### 6.1 與既有工作對照

| 既有工作 | 已解／重點 | 對 BCC 的含意 |
|---|---|---|
| GIB | sampling、partition search、achievable sets 等多技術整合 | 「有粒子＋Minimax」遠不足以重現 expert bridge |
| Frank & Basin | 指出 determinization 在不完全資訊搜尋的根本問題 | BCC 必須處理 information set 與策略一致性，不可每世界獨立最佳化 |
| OpenSpiel | 一般 extensive-form game／算法框架 | 可作環境基礎，但 BBDSL semantics、belief/emission、reward 都要自行定義 |
| Nook | 公開挑戰聚焦受限 declarer play | 不能當作完整 bidding/defense/self-play 已被解決的證據 |
| Restricted choice | Bayes odds update 的經典應用 | 支持用 likelihood ratio，但不支持目前任意 γ 或局部 50/50 即 VoI=0 |

### 6.2 可成立的最小研究命題

BCC 最有價值、也最可交付的部分是：給定一個**小型、完整、可校準的 emission policy**，比較不同 signal convention 對 partner 與 declarer 的 posterior／decision value。建議第一篇工作只做：

1. 單一花色、已知 lead/context 的有限世界生成器；
2. Standard 與 UDCA 的 stochastic emission policy；
3. posterior calibration、mutual information、partner/declarer decision regret；
4. forced play／falsecard 的小型 equilibrium；
5. 與 exact enumeration 對照 particle approximation 的 ESS／bias。

在此之前，`γ`、α/β、VoI=0 與「世界級 AI」均應標示 hypothesis，而非理論結論。

---

## 七、優先行動清單（風險削減 ÷ 成本）

| # | 行動 | 成本估計 | 主要風險削減 |
|---:|---|---:|---|
| 1 | forcing obligation state machine；缺 continuation 時 hard fail；補端到端測試 | 2–4 天 | **極高**：修 D3-F1 |
| 2 | Quiz 改為由唯一 DecisionEngine 產生答案，加入 oracle invariant；修前停用發布 | 1–2 天 | **極高**：停止教錯 |
| 3 | 建立單一 ConstraintEvaluator；未支援欄位拒絕；解析 custom shape | 3–5 天 | **極高**：消除 silent semantic loss |
| 4 | 統一 schema/model/loader，strict+forbid+version Literal，snapshot diff gate | 1–2 天 | 高：建立語言契約 |
| 5 | 修正 SAYC／2/1 範例；逐項引用制度來源並標 variant/completeness | 1–2 天＋專家覆核 | 高：避免所有匯出放大錯誤 |
| 6 | 實作 convention linker/resolved IR，ref/parameter/dependency 真正生效 | 1–2 週 | 高：修模組與續叫 |
| 7 | 平台依賴改為可解析 pin/path、提交 lockfile、clean build CI | 0.5–1 天 | 高：恢復可測性 |
| 8 | 平台安全基線：secret guard、OAuth state/PKCE、限長／限量／worker | 2–4 天 | 高：避免部署事故 |
| 9 | 建立 interoperability LossReport 與 capability matrix；移除假 LIN | 2–3 天 | 中高：防止靜默損耗 |
| 10 | BCC 收斂到單花色 emission/equilibrium POC，建立可重現 eval | 2–4 週 | 中：讓 AI 宣稱有實證基礎 |

---

## 八、最終結論

先前修正讓專案從「明顯產生不足額叫品與錯誤 BML flags」進步到「結構與局部選擇大致穩定」，但本輪顯示更深一層的問題：**資料模型、驗證器、決策器、生成器與教學器並未共享同一套可執行語義**。只要這五者各自解讀 YAML，908 個測試仍可全綠、三套範例仍可 14/14（含 skipped）通過，同時產生 forcing 違規拍賣與錯標題庫。

本專案下一階段最重要的工作不是再增加 exporter、平台頁面或 BCC 方程式，而是建立一個權威的 resolved IR + ConstraintEvaluator + AuctionState/DecisionEngine，讓 validate、simulate、quiz、compare、PBN 與 AI KB 都消費同一語義。完成這一步後，BBDSL 才能從「結構化橋牌文件格式」進入「可被信任的橋牌制度執行語言」。
