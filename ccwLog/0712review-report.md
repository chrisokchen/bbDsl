# BBDSL / BCC 嚴格審查報告

> 審查日期：2026-07-12　|　依據：`ccwLog/reviewPreamble.md`
> 審查者視角：資深橋牌大師 × 電腦科學家（DSL/語言設計）× AI 研究者
> 受審版本：main @ `ac78c9c`（含未提交的 `bbdsl-platform` 修改）

---

## 一、執行摘要

### 整體判定：這個專案「是什麼」vs「宣稱是什麼」

**它實際是**：一個**語法層完成度很高的橋牌制度描述語言與匯出工具鏈**。Pydantic 模型、YAML loader、foreach_suit 展開器、8 種匯出器、2 種匯入器、CLI 都確實存在且可執行，868 個測試全數通過（比宣稱的 851 更多），85% 覆蓋率（比宣稱的 82% 更高）。JSON Schema 能正確驗證三套範例。**作為「把制度寫成結構化 YAML 並轉成 BML/HTML/Convention Card」的工具，它是可用的。**

**它宣稱是**：「讓 AI 能理解而非複述制度」的知識庫核心、具備「模糊邊界與戰術彈性」的 AI-first 語言、具備「模擬對練引擎」與「情境感知」的推理平台。

**兩者之間的落差是本報告的核心發現**。落差不在「還沒做」，而在**已經標記為「✅ 完成」的功能，其語義正確性未達可用標準**：

- 模擬引擎產出的叫牌**在橋牌上是錯的**——SAYC 範例跑 300 副牌，1NT / 1H / 1S / 2NT **從未被叫出過一次**（見 F-1）。這不是邊界案例，是主線行為。
- BML 匯入器把**所有自然紅心叫都標記為「人工叫、需 Alert」**，因為 `'art'` 是 `'hearts'` 的子字串（見 F-2）。這在真實牌桌上等同於給對手錯誤資訊。
- 白皮書 README 的旗艦 AI 功能 `ai_meta`（tolerances / psych_probability / leakage_risk）在 SPEC、JSON Schema、Pydantic 模型中出現次數為 **0**（見 F-9）。
- 「情境感知」（座位、身價、對手行為 9 種模式）在模型層存在，但 ADR-5 指定的 `core/opponent_matcher.py` **這個檔案不存在**，`context_overrides` 除了被檢查「有無重複」外，**沒有任何引擎會套用它**（見 F-4）。

### Top 5 風險

| # | 風險 | 嚴重度 |
|---|------|--------|
| 1 | 模擬/比較/PBN/Quiz 四項功能全部建立在一個會產出錯誤叫牌的選擇器上 → garbage in, garbage out（F-1） | **Critical** |
| 2 | BML 匯入把自然叫標為 alertable，違反橋牌資訊揭露規範（F-2） | **Critical** |
| 3 | 「14/14 規則通過」有相當比例是空跑通過（vacuous pass），給出虛假的品質信號（F-3） | **Major** |
| 4 | 白皮書 AI 宣稱在程式碼中無對應物，若對外發布會構成 overclaim（F-9） | **Major** |
| 5 | 匯出器靜默丟棄無法表達的約束（Dealer bridge 回傳空字串、PBN 產出非法 tag），使用者不會知道語義已遺失（F-6、F-7） | **Major** |

### Top 3 優勢

1. **語法層與工具鏈的工程品質確實紮實**：868 測試全綠、模組邊界清楚、CLI exit code 語義正確（errors→2 已實測）、JSON Schema 與三套範例一致。
2. **BML round-trip 的結構保真度高**：9 個開叫的 HCP 區間與回應樹結構在 BBDSL→BML→BBDSL 來回後完整保留（唯獨旗標被 F-2 汙染）。
3. **問題集中且可修**：本報告的 Critical 問題根因都很集中（一個選擇器、一個子字串比對），不是架構性腐爛。F-1 與 F-2 合計預估 1–2 天可修到「不再產出錯誤橋牌語義」的水準。

---

## 二、宣稱對照表（Claims Audit）

| 出處 | 宣稱 | 實作現況 | 判定 |
|------|------|----------|------|
| README.md:150 | 「851 個測試通過、82% 覆蓋率」 | 實測 **868 passed**、**85%** | ✅ 成立（且低報） |
| README-bbDsl.md:120 | 「14 條驗證規則」 | 14 條均有實作，三範例 14/14 通過 | ⚠️ 部分成立 — 多條為空跑通過（F-3） |
| README.md:183 | 「模擬對練引擎：完整叫牌拍賣模擬」 | 引擎可執行，但選擇邏輯產出錯誤叫牌 | ❌ 不成立（F-1） |
| README-bbDsl.md:104 | 「Dealer 相容：hand constraint 對應 Dealer 函數」 | hcp/suit/shape/controls/losers 可轉；stopper/specific_cards/suit_quality **靜默回傳空字串** | ⚠️ 部分成立（F-6） |
| CLAUDE.md | 「PBN Note tag 嵌入 BBDSL 語義」 | [Note] 有寫入，但 [Contract] 值非法且無 [Declarer] tag | ⚠️ 部分成立（F-7） |
| README-bbDsl.md:109-111 | 「情境感知：座位／身價／對手行為 9 種模式」 | 模型層有 `OpponentPattern`；**無任何匹配引擎**，`context_overrides` 從未被套用 | ❌ 不成立 — 純資料（F-4） |
| ADR-5（CLAUDE.md） | 「匹配邏輯位於 `core/opponent_matcher.py`」 | **該檔案不存在** | ❌ 不成立（F-4） |
| README.md:35-61 | `ai_meta` 區塊（tolerances / psych_probability / leakage_risk） | SPEC 出現 0 次、JSON Schema 出現 0 次、Pydantic 模型無此欄位 | ❌ 未實作（純願景，且未標示為願景）（F-9） |
| README-bbDsl.md:150 | 技術基礎含「pytest + **hypothesis**」 | hypothesis 在 `pyproject.toml:25` 宣告為依賴，**測試中 0 處使用** | ❌ 不成立（F-5） |
| README-bbDsl.md:126 | 「AI KB 匯出讓 AI 理解叫牌邏輯而非只記住叫品」 | 匯出器存在，產出扁平化 JSONL；**無任何實驗證據**支持「理解」 | ⚠️ 未經驗證的宣稱（F-10） |
| README-bbDsl.md:167 | SAYC 範例位於 `process/1-discover/sayc.bbdsl.yaml` | 該路徑確實存在，但**正式範例在 `examples/`**，README 指向舊路徑 | ⚠️ Doc drift（F-11） |
| README-bbDsl.md:185 | CC-BY-SA 適用於 `registry/`、`examples/conventions/` | 兩個目錄**均不存在**；LICENSE 與 LICENSE-CC-BY-SA-4.0 檔案存在 | ⚠️ 部分成立（F-12） |
| README.md:111-116 | BCC Phase 2–4（粒子濾波／MARL／self-play） | 無任何程式碼（README 誠實標記為未勾選） | ✅ 誠實標示為未完成 |

---

## 三、分維度發現

### F-1【Critical / CONFIRMED / 實作缺陷 + 橋牌語義錯誤】模擬引擎的叫牌選擇器使大多數開叫永遠不可能被叫出

**證據**：`bbdsl/core/sim_engine.py:297-321` 的 `_select_bid()` 對候選節點做**宣告順序的 first-match-wins**，完全不參考 `BidNode.priority`（`models/bid.py:72` 有此欄位）也不參考 `doc.selection_rules`（`core/selector.py` 的整個選擇引擎）。

由於範例中最寬鬆的約束排在最前面（SAYC `1C` = 12–21 HCP + 1+ 梅花，幾乎任何開叫手牌都滿足），它會吃掉所有後續開叫。

**重現**（300 副牌，seed=1）：

```
examples/sayc.bbdsl.yaml
  declared openings: [1C, 1D, 1H, 1S, 1NT, 2C, 2D, 2H, 2S, 2NT, 3C, 3D, 3H, 3S]
  actually used    : {1C: 170, PASSED_OUT: 92, 2H: 13, 2D: 8, 2C: 5, 2S: 3, ...}
  NEVER OPENED     : [1H, 1S, 1NT, 2NT]      ← 一次都沒出現

examples/precision.bbdsl.yaml
  NEVER OPENED     : [1H, 1S, 1NT, 2C, 2D]   ← 9 個開叫中 5 個是死碼
```

具體案例：16 HCP 平均牌 4-3-3-3（教科書級的 1NT 開叫）——`sim_engine` 叫 **1C**。

**橋牌影響**：這不是「近似」或「簡化」，這是錯的。一個不會開 1NT 的 SAYC 不是 SAYC。

**連鎖影響**：`compare`（制度比較）、`export pbn`（牌譜）、`quiz`（教學題庫）全部以此引擎為基礎 → 這三項產出的資料**在橋牌上均不可信**。`bbdsl compare precision sayc` 報告的「制度差異」量測的其實是兩份 YAML 的**開叫宣告順序差異**，而非制度差異。

**建議修法**：`_select_bid` 改為（優先序）：① 若 `doc.selection_rules` 存在 → 呼叫 `selector.select_opening()`；② 否則若節點有 `priority` → 依 priority 排序後 first-match；③ 否則 → 依「約束特異性」（specificity：約束欄位數 / 區間窄度）排序。同時三套範例應補上 `selection_rules`（目前皆為 0 條，見 F-3）。

---

### F-2【Critical / CONFIRMED / 實作缺陷 + 橋牌規範違反】BML 匯入器把所有自然紅心叫標記為人工叫且需 Alert

**根因**：`bbdsl/importers/bml_importer.py:232-235` 用裸子字串比對關鍵字：

```python
for kw in ARTIFICIAL_KEYWORDS:      # {'art', 'artificial', 'relay', 'puppet', 'transfer', ...}
    if kw in desc_lower:            # ← 'art' 是 'hearts' 的子字串！
        result['artificial'] = True
```

`'art' in 'he`**`art`**`s'` → True。接著 `:242-243` 讓人工叫預設 `alertable=True`。

**最小重現**：

```
'11-15 HCP, 5+ hearts'      -> artificial=True  alertable=True
'11-15 HCP, 5+ spades'      -> artificial=None  alertable=None   ← 黑桃不受影響
'6-9 HCP, 3+ heart support' -> artificial=True  alertable=True
```

**橋牌影響**：這是本報告中橋牌後果最嚴重的一項。把自然的 1♥ 開叫標記為 alertable，若此輸出被餵入 BBOalert 供線上對打使用，等於**對對手發出錯誤的制度揭露資訊**——在真實比賽中這是可裁罰的行為。

**同類風險**：`PREEMPTIVE_KEYWORDS` 含 `'wk'`（會誤中含 "wk" 的任意字串）、`ARTIFICIAL_KEYWORDS` 含 `'asking'`/`'waiting'` 也可能誤中。

**建議修法**：改為詞界比對，例如 `re.search(rf'\b{re.escape(kw)}\b', desc_lower)`；並為此加一組反例測試（"hearts" 不得觸發 artificial）。

---

### F-3【Major / CONFIRMED / 品質信號失真】「14/14 規則通過」包含大量空跑通過

**證據**：三套範例的驗證報告中，以下規則的「PASSED」是在**沒有任何東西可檢查**的情況下取得的：

```
val-014: "No selection_rules defined (skipped)."   ← 三套範例的 selection_rules 皆為 0 條
val-009: "No duplicate seat/vulnerability context overrides found."  ← 無 context_overrides 可檢查
val-010: "No bid conflicts after foreach_suit expansion."            ← 範例未使用 foreach_suit
```

`core/validator.py:858-867`：`val-014` 在 `selection_rules` 為空時直接回傳 `passed=True`。這使得「選擇規則窮盡性」這條規則對三套旗艦範例**完全沒有把關作用**——而諷刺的是，正因為範例沒有 selection_rules，F-1 的錯誤選擇行為才會發生。

**val-002（重疊偵測）的漏網**：`validator.py:260-262` 在任一叫品有 `shape` ref 時直接放棄檢查。因此 Precision 中 `1D`（11–15 HCP，無牌型限制）與 `1NT`（15–17 HCP，balanced）在 **15 HCP 平均牌**上的真實重疊**不會被偵測**——而這正是 F-1 中 1NT 變成死碼的原因之一。驗證器報告「No HCP/shape overlaps found」，但重疊確實存在。

**建議修法**：(a) 空跑時 severity 應標為 `info` 或 `skipped`，不得計入「N/N passed」；(b) 摘要行改為 `14 rules run: 9 passed, 5 skipped`；(c) val-002 對 shape ref 應解析 `definitions.patterns` 展開為具體 shape 集合後判斷交集，而非放棄。

---

### F-4【Major / CONFIRMED / 宣稱不成立】「情境感知」是純資料，無任何引擎消費

**證據**：
- `bbdsl/models/context.py:13` 的 docstring 宣告「matching logic in core/opponent_matcher.py (ADR-5)」→ **`bbdsl/core/opponent_matcher.py` 不存在**（`ls` 確認，core/ 下只有 10 個檔案）。
- 全域搜尋 `context_overrides` 的所有使用點：`models/bid.py:73`（欄位宣告）、`validator.py:582`（只檢查重複）、`bboalert_exporter.py:157`（一個未使用的參數名）。**沒有任何地方讀取 override 的內容並套用**。
- `sim_engine.simulate_deal()` 接受 `dealer` 參數，但從不將座位或身價傳入 `_select_bid()`。

**影響**：README-bbDsl 列為核心特性的「座位 1st/2nd/3rd/4th 不同開叫策略」「身價調整激進度」「對手行為 9 種模式」，目前只是**能通過 schema 驗證的裝飾性 YAML**。使用者寫了 context_overrides，工具鏈會安靜地忽略它。

**建議修法**：短期——在 README 與 SPEC 明確標示「情境模型為 v0.3 資料層，引擎支援待 Phase 6」；中期——實作 `opponent_matcher.py` 並讓 `sim_engine` 在有干擾叫時查詢 overrides。

---

### F-5【Major / CONFIRMED / 測試品質】宣稱的 property-based 測試不存在；無 BBDSL↔BML 語義 round-trip 測試

- `pyproject.toml:25` 宣告 `hypothesis>=6.70` 為 dev 依賴，但 `grep -rl hypothesis tests/` → **0 個檔案**。README-bbDsl:150 把 hypothesis 列為技術基礎，屬不成立。
- `tests/` 中的 round-trip 測試僅存在於 `test_dealer_bridge.py` 與 `test_bboalert_importer.py`；**沒有 BBDSL→BML→BBDSL 的語義保真測試**。若有，F-2（紅心被標人工）會在第一次執行時就被抓到。
- 覆蓋率的缺口集中在正確的地方值得注意：`cli/main.py` 僅 **47%**、`core/loader.py` 僅 **52%**、`cli/registry_client.py` 僅 **44%**——即使用者實際接觸的入口層測試最薄。

**建議修法**：加一條 round-trip property test（對三套範例：export→import→比對每個 BidNode 的 `artificial`/`alertable`/`forcing`/`hcp`），這一條測試就能守住 F-2 這類迴歸。

---

### F-6【Major / CONFIRMED / 靜默語義遺失】Dealer bridge 對無法表達的約束回傳空字串

**證據**（`core/dealer_bridge.py`，實測 `constraint_to_dealer()`）：

| 約束 | 產出 |
|------|------|
| `hcp=16+` | `hcp(south) >= 16` ✅ |
| `hcp 11-15 + hearts 5+` | `hcp(south) >= 11 && hcp(south) <= 15 && hearts(south) >= 5` ✅ |
| `shape ref: balanced` | `shape(south, any 4333 + any 4432 + any 5332)` ✅ |
| `stopper_in: hearts` | `''` ❌ **整個約束消失** |
| `specific_cards: [AS, KH]` | `''` ❌ |
| `suit_quality: {hearts: good}` | `''` ❌ |

回傳空字串在 Dealer script 語義中等同「無條件」——使用者拿這份 script 去發牌，會得到**不符合原始約束**的牌，且**沒有任何警告**。

**建議修法**：無法表達時應回傳 `None` 並由呼叫端收集為 `DegradationWarning`，CLI 輸出 `⚠ 3 constraint(s) could not be expressed in Dealer syntax and were dropped: ...`。

---

### F-7【Major / CONFIRMED / 互通性】PBN 輸出的 [Contract] 值非法且缺 [Declarer] tag；莊家判定違反橋牌規則

**證據**（`exporters/pbn_exporter.py:148`，實測輸出）：

```
[Contract "2NT by South"]     ← 非法。PBN 標準要求 [Contract "2NT"] + [Declarer "S"]
                              ← 檔案中完全沒有 [Declarer] tag
```

檔頭宣告 `% PBN 2.1`，但 `Contract` 欄位夾帶 "by South" 字串，主流工具（BBO / BridgeComposer / Deep Finesse）解析時會失敗或忽略該欄位。

**橋牌規則層面**：`sim_engine.py:328-344` 的 `_final_contract()` 把**最後一個非 Pass 叫牌者**當作莊家。橋牌規則是「**該方第一個叫出該定約花色者**」為莊家。實測 200 副牌中有 2 副誤判：

```
Deal 37: auction 1C(S) 2C(N) | reported "2C by North" | 正確莊家 = South
```

目前誤判率低（2/162）僅因 F-1 導致拍賣普遍很短；一旦 F-1 修好、拍賣變長，誤判率會顯著上升。

**建議修法**：`_final_contract()` 依規則掃描該方第一個叫出該 strain 的座位；PBN 匯出改為 `[Contract "2NT"]` + `[Declarer "S"]`。

---

### F-8【Minor / CONFIRMED / 實作缺陷】E/W 使用制度時模擬產出不合法拍賣（叫品不足額）

**重現**：`bbdsl simulate examples/precision.bbdsl.yaml --ew-system examples/sayc.bbdsl.yaml -n 30 --seed 7` → **15/30 副牌含不合法叫品**：

```
Deal 6:  1D 1C 1NT 1H Pass Pass Pass     ← 1C 低於 1D；1H 低於 1NT
Deal 9:  Pass Pass 2H 1C 2NT 2C ...      ← 1C 低於 2H
```

**根因**：`sim_engine.simulate_deal()` 為 N/S 與 E/W 各維護獨立的 `ns_path` / `ew_path`，兩方各自在**自己的**叫牌樹中挑叫，**從不檢查新叫品是否高於當前最高叫**（無 legality gate）。N/S 單獨模擬（E/W 全 Pass）時 100/100 副合法，因為單方叫牌樹天然遞增。

**建議修法**：在 `_select_bid` 外層加一道 `_is_sufficient(bid, highest_bid_so_far)` 過濾；候選全部不足額時回退為 Pass。

---

### F-9【Major / CONFIRMED / Overclaim】白皮書的 `ai_meta` 在整條工具鏈中不存在

`README.md:51-61` 以「====== AI 擴充區塊 ======」呈現 `ai_meta`，包含 `tolerances`（模糊邊界、gaussian 分佈）、`information_profile.leakage_risk`、`psych_probability`——這是整份白皮書用來區隔 BBDSL 與 BML 的**核心賣點**。

實測：`grep -c ai_meta BBDSL-SPEC-v0.3.md bbdsl-schema-v0.3.json` → **0 / 0**。Pydantic 模型 `BidMeaning`（`models/bid.py:43-53`）無此欄位。

由於 `HandConstraint.model_config = {"extra": "allow"}`，使用者寫了 `ai_meta` **不會報錯**，但也**永遠不會被任何程式碼讀取**——這是最糟的組合：既不拒絕，也不生效，使用者無從得知。

**建議修法**：二選一——(a) 在 README 的該區塊明確標注「⚠️ Phase 6 願景，v0.3 尚未實作」；(b) 若要保留宣稱，最小可行實作是把 `tolerances.hcp.margin` 接進 `hand_generator` 的拒絕取樣（允許邊界外 margin 點以低機率通過），這是 1 天的工作量且能讓宣稱成真。

---

### F-10【Suggestion / PLAUSIBLE / AI 宣稱】AI KB 匯出的 RAG 優勢缺乏任何證據

`export ai-kb` 產出扁平化 JSONL + 自然語言描述。宣稱「讓 AI 理解叫牌邏輯而非只記住叫品」（README-bbDsl:126）。

**問題**：檢索式知識庫本質上只能讓 LLM **複述**檢索到的片段。「理解」需要的是可執行的推理（給定手牌 → 推導叫品；給定叫序 → 推導手牌分佈），這正是 `selector` + `sim_engine` 該提供的能力——而它們目前是壞的（F-1）。**目前工具鏈距離「理解」還差的不是 KB 格式，而是一個正確的推理引擎。**

無任何 A/B 實驗（YAML 直餵 vs JSONL RAG）證據。建議：不要在無證據下宣稱 RAG 優勢；若要證明，做一個小型 eval（50 題「給定手牌選開叫」，比較兩種餵法的正確率）。

---

### F-11【Minor / CONFIRMED / Doc Drift】文件與現實不一致

| 位置 | 問題 |
|------|------|
| `README-bbDsl.md:167` | 指向 `process/1-discover/sayc.bbdsl.yaml`（探索階段舊檔），正式範例在 `examples/sayc.bbdsl.yaml` |
| `README-bbDsl.md:152-163` | 「專案結構」圖完全沒有 `bbdsl/` 套件本體、`examples/`、`tests/` |
| `README.md:150` / `CLAUDE.md` | 「851 tests, 82%」實為 868 / 85%（低報，但仍是 drift） |
| `CLAUDE.md` ADR-5 | 指向不存在的 `core/opponent_matcher.py` |
| `README-bbDsl.md:146` | 「驗證器 (8 規則)」與他處「14 條」不一致 |

---

### F-12【Minor / CONFIRMED / 授權】雙軌授權的 CC-BY-SA 範圍目錄不存在

`README-bbDsl.md:185` 指定 CC-BY-SA-4.0 適用於 `registry/` 與 `examples/conventions/`。兩個目錄**都不存在**。`LICENSE` 與 `LICENSE-CC-BY-SA-4.0` 檔案本身存在。

現況下 `examples/*.bbdsl.yaml`（三套制度檔）落在哪個授權下是**未定義的**——而這正是最需要 CC-BY-SA 保護的內容。建議：把三套範例移入 `examples/conventions/` 或直接在 YAML 檔頭加 `# SPDX-License-Identifier: CC-BY-SA-4.0`（`system.license` 欄位已有 `CC-BY-SA-4.0`，但那是 metadata 不是法律聲明）。

---

### F-13【Suggestion / CONFIRMED / 安全】`selector.evaluate_condition` 使用 `eval()`

`core/selector.py:126`：`eval(python_expr, {'__builtins__': _SAFE_BUILTINS}, ctx)`。

目前 `__builtins__` 被清空，且輸入來自本地 YAML，風險有限。**但 Phase 5 平台（`bbdsl-platform`）允許使用者上傳 YAML 並在伺服器端驗證**——屆時 `selection_rules[].condition` 就成了使用者可控的 `eval` 輸入。清空 `__builtins__` 並非完整沙箱（可透過 `().__class__.__mro__` 等途徑逃逸）。

平台後端目前掃描未發現 `yaml.load` / `eval` / 硬編碼 secret（clean）。

**建議修法**：在平台上線前，把 `evaluate_condition` 改為 AST 白名單解析（`ast.parse` + 只允許 `Compare`/`BoolOp`/`Name`/`Num` 節點），移除 `eval`。這是平台安全的前置條件。

---

## 四、附錄 A：三套範例制度逐叫品抽查（橋牌大師之眼）

### A-1 Precision Club（`examples/precision.bbdsl.yaml`）

| 叫品 | YAML 定義 | 橋牌評價 |
|------|-----------|----------|
| 1C | 16+ HCP, artificial, F1 | ✅ 正確 |
| 1D | 11–15 HCP，**無牌型限制** | ⚠️ 真實精準制 1D 是「11–15，2+ 方塊，未能開其他一線叫」的**剩餘叫**（residual）。此處寫成無限制，使其在 first-match 選擇下吞噬所有 11–15 手牌（F-1 主因） |
| 1H / 1S | 11–15, 5+ | ✅ 定義正確，但實際不可達（F-1） |
| 1NT | **15–17**, balanced | ❌ 經典精準制 1NT 為 **13–15**（部分流派 14–16）。15–17 是 SAYC 的區間，混入精準制後與 1D（11–15）在 15 點重疊，且與 1C（16+）在 16–17 點重疊 |
| 2C | **22+ HCP, artificial, GF** | ❌ **嚴重**。精準制的 2C 是**自然的 6+ 梅花、11–15 HCP**；22+ 的強牌走 1C。此處的 2C 定義是 SAYC 的強 2C 直接搬過來，且因 1C(16+) 排在前面，2C **永遠不可能被叫出**（實測為死碼） |
| 2D | 11–15, `precision_2d` (4=4=1=4 / 4=4=0=5), art | ✅ 概念正確（Precision 2D 確為特殊牌型叫），但實際不可達（F-1） |
| 2H / 2S | 5–10, 6+ | ✅ 弱二叫合理 |

**綜評**：這份「精準制」的 1NT 與 2C 實際上是 SAYC 的定義。作為 repo 的旗艦範例（README 快速開始第一行就用它），這會誤導學習者。

### A-2 SAYC（`examples/sayc.bbdsl.yaml`）

| 叫品 | YAML 定義 | 橋牌評價 |
|------|-----------|----------|
| 1C / 1D | 12–21, **1+ / 1+** | ⚠️ SAYC 的一線低花承諾 **3+**（1C 可短到 3 張，1D 通常 3+；「1+」在任何主流 SAYC 文獻中都不成立）。這個過寬的下限是 F-1 中 1C 吞噬 170/300 副牌的直接原因 |
| 1H / 1S | 12–21, 5+ | ✅ 正確（5 張高花制） |
| 1NT | 15–17, balanced | ✅ 正確 |
| 2C | 22+, art, GF | ✅ 正確 |
| 2D/2H/2S | 6–11, **exactly 6** | ⚠️ 弱二叫是 6 張**或更多**在部分流派；寫死 `exactly 6` 排除了 7 張弱二（雖然 7 張通常開三線，可接受）。點力 6–11 合理 |
| 2NT | 20–21, balanced | ✅ 正確，但不可達（F-1） |
| 3C | 5–10, **exactly 7** | ⚠️ 三線阻擊通常 7+；`exactly 7` 排除 8 張。而 3D/3H/3S 寫的是 `min: 7`（不含 max）——**同一制度內同類叫品的定義風格不一致**，疑似手誤 |

### A-3 2/1 Game Force（`examples/two_over_one.bbdsl.yaml`）

開叫定義大致合理（1C/1D 承諾 2+，較 SAYC 版本合理）。但 **2/1 制度的靈魂是「一線高花開叫後，二線非跳非高花回應 = 建立 GF」的 forcing 鏈**——這需要在 `responses` 中正確標記 `forcing: game`。範例中 1H/1S 各有 6–7 條 responses，結構存在，但由於 F-1 使 1H/1S **永遠不會被開叫**，這條 forcing 鏈在模擬中從未被走過，因此其正確性**從未被任何測試或模擬實際驗證過**。

---

## 五、附錄 B：BCC 理論評估（AI 研究者之眼）

BCC 目前**無任何程式碼**（README 誠實標為未勾選），故僅評估理論健全性與宣稱誠實度。

### B-1 值得肯定的部分

「把叫牌/信號視為受限通道通訊，用貝氏後驗更新可能世界」的框架方向是**正確且與現有文獻一致**的。它本質上是不完全資訊賽局的 belief-state 表述，與 OpenSpiel 的 bridge 環境、以及 Nook/GIB 之後的推論式 AI 研究是同一條路。把「誠實的代價」形式化為 $\beta \cdot VoI(\text{Opp})$ 也是合理的建模直覺。

### B-2 理論缺口（若要寫成論文，這些是審稿人會攻擊的點）

1. **$\gamma = 1 - 1/|H_w|$ 是啟發式，不是資訊理論量**（`README-bcc.md:389`）。真正的信號置信度應是**互信息** $I(\text{Intent}; C \mid \Gamma)$ 或後驗-先驗的 KL 散度。目前的公式只反映「手牌張數」，與「該張牌在不同意圖下的發射機率差異」無關——而後者才是信號資訊量的本質。單張 → γ=0 恰好對，純屬巧合（單張時 likelihood 在所有意圖下都是 1，互信息確實為 0）；但雙張 → 0.5 沒有任何理論依據。

2. **雙向飛牌範例的「VoI 歸零」結論不嚴格成立**（`README-bcc.md:531`）。宣稱防禦方以 π(♠4)=0.5, π(♠2)=0.5 混合可使莊家 VoI = 0。**這只在防禦方持 Q42 的世界中成立**。莊家的貝氏更新是跨所有可能世界的：若防禦方在**不持 Q** 的世界中仍依標準張數信號誠實出牌，那麼「出 4」這個觀察在「持 Q」與「不持 Q」的世界間仍有 likelihood 差異，VoI ≠ 0。要真正讓 VoI = 0，需要的是**跨所有世界的 likelihood 對齊**（即在所有相關世界中以相同機率出 4），這是一個全域均衡約束，遠強於範例中的局部 50/50。這個錯誤在賽局理論上是實質的。

3. **$\alpha$、$\beta$ 的估計方法完全未定義**（`README-bcc.md:485-489` 僅說「決策關鍵度」）。這不是留白，是**核心缺口**：$\mathcal{U}$ 的整個行為由這兩個係數決定，而它們本身依賴「下一墩誰做決策」——這是遞迴的（要算 α 就要先解賽局）。標準解法是把它們吸收進 ISMCTS 的 rollout value，不要顯式估計。目前的公式形式上優雅但**不可計算**。

4. **粒子退化（degeneracy）未被討論**。README 說「維護上萬個粒子」，但在橋牌的長叫牌序列 + 13 墩打牌中，重要性權重會迅速集中到少數粒子上。缺少重採樣（resampling）與 roughening 策略的討論，是粒子濾波實作必然撞牆的地方。

5. **範例中的 likelihood 設定（0.95 / 1.0 / 1.0）確有 cherry-pick 之嫌**（`README-bcc.md:411-413`）。結論「32.2%」對這三個數字極度敏感；若 $w_2$（J8 被迫打 8）的先驗機率按實際組合數計算而非「三個世界等機率」，結論會大幅改變。這個範例作為**直覺說明**是好的，作為**數學論證**是不成立的。

### B-3 工程可行性判斷

README Roadmap 的 Phase 2（粒子濾波 POC）→ Phase 4（self-play 超人 AI）**在工作量級上被嚴重低估**。參考點：OpenSpiel 的 bridge 環境本身即為多人年工作；達到 WBridge5 水準的 self-play 需要的算力與工程規模，遠超一個個人開源專案的 4 個 Phase 所能涵蓋。

**建議**：把 BCC 的目標收斂到一個**可發表、可完成**的子問題——例如僅做「單一花色的防禦信號貝氏推論引擎 + 與標準/UDCA 信號系統的資訊效率量化比較」。這是 README-bcc.md 第 181 行自己提出的目標（「數學上證明 UDCA 是否優於標準信號」），**它是本專案 AI 部分唯一真正可交付且有學術價值的目標**，且不需要超人 AI。

---

## 六、優先行動清單（按 風險削減 ÷ 修復成本 排序）

| # | 行動 | 對應發現 | 預估成本 | 風險削減 |
|---|------|----------|----------|----------|
| 1 | BML 匯入器關鍵字改為詞界比對（`\b{kw}\b`），加反例測試 | F-2 | **~1 小時** | **極高**（消除橋牌規範違反） |
| 2 | `sim_engine._select_bid` 改為 selection_rules → priority → specificity 三段式；三套範例補上 selection_rules | F-1 | 1–2 天 | **極高**（讓 simulate/compare/pbn/quiz 的產出恢復可信） |
| 3 | 加一條 BBDSL→BML→BBDSL 語義 round-trip property test（守住 artificial/alertable/forcing/hcp） | F-5 | 半天 | 高（把 F-2 這類迴歸永久擋掉） |
| 4 | 修正 Precision 範例的 1NT（→13–15）與 2C（→自然 6+ 梅花 11–15）；SAYC 1C/1D 下限（1+→3+） | A-1, A-2 | 半天 | 高（旗艦範例的橋牌可信度） |
| 5 | 驗證器區分 `passed` 與 `skipped`，摘要改為「N run: X passed, Y skipped」 | F-3 | 2 小時 | 高（消除虛假品質信號） |
| 6 | 在 README.md 的 `ai_meta` 區塊加註「⚠️ Phase 6 願景，v0.3 未實作」；或把 `tolerances.hcp.margin` 接進 hand_generator | F-9 | 10 分鐘 / 1 天 | 高（誠實度） |
| 7 | PBN 改為 `[Contract "2NT"]` + `[Declarer "S"]`；`_final_contract` 依規則判定莊家 | F-7 | 半天 | 中（互通性 + 橋牌正確性） |
| 8 | Dealer bridge 無法表達的約束改為回傳 None 並向 CLI 冒泡 degradation warning | F-6 | 半天 | 中（消除靜默語義遺失） |
| 9 | 模擬加入叫品足額性檢查（legality gate） | F-8 | 2 小時 | 中（E/W 對戰模式才合法） |
| 10 | 平台上線前，`evaluate_condition` 以 AST 白名單取代 `eval` | F-13 | 1 天 | 中（Phase 5 的前置安全條件） |

**建議的執行順序**：#1 → #3 → #2 → #5 → #4。前三項合計約 2–3 天，能把本專案從「產出橋牌上錯誤的資料」修到「產出可信的資料」——這是所有後續 AI 工作（BCC、RAG、self-play）的必要前提。在 #1/#2 修好之前，任何以 `simulate` / `compare` / `export pbn` 產出的資料做的下游分析，結論都不可信。

---

## 七、未審查項目（Not Reviewed）

誠實列出本次未能驗證的範圍，不默認通過：

- `bbdsl-platform/` 的前端（React/Monaco）、OAuth flow 實際行為、WebSocket 端點——僅做了後端的靜態安全模式掃描。
- `foreach_suit` 2 層巢狀上限的邊界行為（三套範例均未使用 foreach_suit，故無實例可測）。
- HTML viewer / Convention Card / SVG tree / Quiz 四個匯出器的**視覺輸出正確性**（僅確認能執行且有測試覆蓋，未人工檢視渲染結果）。
- BBOalert 匯出檔是否能被 BBO 實際載入（無 BBO 環境）。
- 真實世界大型 BML 檔的匯入成功率——僅測試了 repo 內建的 fixture（`sayc_opening.bml`：9 開叫、3 個 UnresolvedNode，匯入後 validate 為 11/14 通過 + 1 error）。
- BBDSL-SPEC-v0.3.md / SUPPLEMENT 的**逐條規格內容**與實作的細部對照（僅做了 `ai_meta` 等關鍵宣稱的抽查）。
