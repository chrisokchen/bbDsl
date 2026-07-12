# 審查修正紀錄（0712review-report.md 逐項處置）

> 日期：2026-07-12　|　依據：`ccwLog/0712review-report.md` 的優先行動清單
> 結果：**10 項全數完成**。測試 868 → **908 passed**（+40），覆蓋率 82% → **85%**，lint 未新增問題（基準 25 → 23）。

---

## 一、總覽

| # | 行動 | 對應發現 | 狀態 | 驗證方式 |
|---|------|----------|------|----------|
| 1 | BML 匯入器改詞界比對 | F-2 (Critical) | ✅ | 最小重現 + 9 條反例測試 |
| 2 | 修 `_select_bid`；三範例補 `selection_rules` | F-1 (Critical) | ✅ | 500 副牌開叫可達性測試 |
| 3 | BBDSL→BML→BBDSL 語義 round-trip 測試 | F-5 | ✅ | 新檔 18 個測試 |
| 4 | 修正範例的橋牌錯誤 | A-1 / A-2 | ✅ | convcard 測試更新為正確事實 |
| 5 | 驗證器區分 passed / skipped | F-3 | ✅ | CLI 摘要行 + 測試 |
| 6 | README `ai_meta` 標註為未實作 | F-9 | ✅ | 文件 |
| 7 | PBN `[Contract]`/`[Declarer]` + 莊家判定 | F-7 | ✅ | 200 副牌 0 誤判 |
| 8 | Dealer bridge 降級改為回報 | F-6 | ✅ | 單元驗證 |
| 9 | 模擬加入叫品足額性檢查 | F-8 | ✅ | 15/30 → 0/200 不合法 |
| 10 | `evaluate_condition` 以 AST 白名單取代 `eval` | F-13 | ✅ | 3 種逃逸手法均被擋 |

**額外處理**：F-4（`opponent_matcher.py` 不存在的宣稱）、F-11（文件漂移）、F-12（授權範圍）一併修正。

---

## 二、逐項修正過程

### #1　F-2：BML 匯入器把自然紅心叫標成人工叫

**根因**（`bbdsl/importers/bml_importer.py:232`）：`if kw in desc_lower` 是裸子字串比對，而 `'art'` 是 `'he`**`art`**`s'` 的子字串。

**修法**：新增 `_kw_match()`（`(?<!\w)kw(?!\w)` 詞界比對）與 `_first_kw()`（長鍵優先）。長鍵優先是必要的——連字號本身就是詞界，所以 `\bforcing\b` **也會**命中 `game-forcing` 內部，若不按長度排序，`game-forcing` 會被誤判為 `one_round` 而非 `game`。這一點原本是靠 dict 插入順序「碰巧」正確的，現在變成明確保證。

**修正前後**：

```
'11-15 HCP, 5+ hearts'       art=True  → art=None     ← 自然叫不再被標人工
'6-9 HCP, 3+ heart support'  art=True  → art=None
'Transfer to spades, art, f1' art=True → art=True     ← 真陽性保留
'game-forcing'               F=game    → F=game       ← 長鍵優先仍正確
```

真實 BML 檔（`sayc_opening.bml`）匯入後，現在只有真正人工的 `2C` 帶 art/alert 旗標，其餘 8 個自然開叫全部乾淨。

---

### #2　F-1：模擬引擎讓多數開叫變成死碼（本次最大工程）

**根因**（`bbdsl/core/sim_engine.py`）：`_select_bid()` 依**宣告順序** first-match-wins，既不看 `BidNode.priority`，也不呼叫已經寫好的 `selector.py`。而制度檔的慣例是把最寬鬆的開叫寫在最前面（1C），於是它吃掉所有牌。

**修法**：改為三段式解析，並在 docstring 寫清楚為什麼宣告順序不能當作選擇規則：

1. **`selection_rules`**（僅開叫）— 人工授權的優先序階梯，最權威。
2. **`priority`**（節點層）— 兄弟節點的明示順序。
3. **`_specificity()`**（後備）— 估算約束的限制性；區間越窄、花色要求越長 → 越優先。刻意把「1–2 張的花色下限」視為無效約束，因為它本來就是（幾乎每手牌都有 2 張梅花）。

**同時補上三套範例缺失的 `selection_rules`**（原本全部是 0 條，這才是 F-1 的真正病灶——叫牌樹只描述「每個叫品是什麼」，從未描述「同時成立時該叫哪一個」）。

**效果（500 副牌，seed=1）**：

| 制度 | 修正前從未叫出的開叫 | 修正後 |
|------|----------------------|--------|
| SAYC | `1H` `1S` `1NT` `2NT` | 無死碼 |
| Precision | `1H` `1S` `1NT` `2C` `2D` | 無死碼 |
| 2/1 GF | （同類問題） | 無死碼 |

教科書案例驗證：16 HCP 平均牌 4-3-3-3，SAYC 修正前叫 **1C**，修正後叫 **1NT** ✅

修正後的 SAYC 開叫分佈（500 副）也合乎橋牌直覺：Pass 148、1D 77、1C 58、1NT 56、1S 55、1H 41、弱二與阻擊叫各數次。

---

### #3　F-5：補上會抓到 F-2 的那條測試

新增 `tests/test_importers/test_bml_roundtrip.py`（18 個測試，三套範例 × 6 項）：匯出 BML 再匯入，逐一比對 `hcp` / `artificial` / `alertable` / `forcing` / 回應數 / 開叫集合。

其中 `test_artificial_flag_not_invented` 正是**修正前必定失敗**的那條——F-2 若沒被人工審查抓到，這條測試會在第一次執行時就擋下它。這是本次投資報酬率最高的一項。

（順帶確認：`hypothesis` 在 `pyproject.toml` 宣告為依賴但零測試使用，已從 README 技術基礎移除，不再宣稱。）

---

### #4　A-1 / A-2：範例制度的橋牌錯誤

| 檔案 | 修正前 | 修正後 | 理由 |
|------|--------|--------|------|
| precision | `1NT` = 15–17 | **13–15** | 經典精準制是弱無王；16+ 平均牌走 1C。15–17 是 SAYC 的區間 |
| precision | `2C` = 22+ 人工 GF | **11–15, 6+ 梅花，自然叫** | 精準制的強牌一律走 1C，不另設強 2C。連同回應樹一併重寫（2D 詢問 / 2NT 邀請 / 3C 加叫），否則回應語義會與新的開叫語義不符 |
| precision | `1D` 無牌型限制 | **加 `diamonds: min 2`** | 標為剩餘叫（residual）；「無法開其他一線叫」的語義由 `selection_rules` 的順序表達，不寫進 hand 條件 |
| sayc | `1C`/`1D` = **1+** 低花 | **3+** | 任何主流 SAYC 文獻都不承認「1+ 梅花」。這個過寬下限是 1C 吞掉 170/300 副牌的直接原因 |
| sayc | `3C` = exactly 7 | `min: 7` | 與 3D/3H/3S 的 `min: 7` 寫法不一致，疑似手誤 |

---

### #5　F-3：驗證器的空跑通過

**修法**：`ValidationResult` 新增 `skipped` 欄位；5 個「沒東西可檢查」的 return 點（val-001/005/011/012/014）與 val-009（無 context_overrides 時）標為 skipped。`ValidationReport` 新增 `passed_count` / `skipped_count`。CLI 摘要改為：

```
Summary: 14 rule(s) run — 13 passed, 1 skipped, 0 warning(s), 0 error(s)
  A skipped rule found nothing to check — it is not a guarantee.
```

**val-002 一併重寫**（原本只要任一叫品有 shape ref 就整個放棄檢查）：現在正確判斷「是否存在一手牌同時滿足兩個叫品」＝ HCP 交集 ∩ shape 集合交集 ∩ **每個**花色的長度區間交集。原本的「至少一個共同花色」邏輯是錯的——缺少約束不是不匹配，它是「接受一切」，這正是寬鬆叫品會吞掉嚴格叫品的原因。

---

### #7　F-7：PBN 合約/莊家

- `[Contract "2NT by South"]` → `[Contract "2NT"]` + `[Declarer "S"]`（原值不是任何 PBN reader 接受的格式）。
- 新增 `declarer_of()`：依橋牌規則（Law 54）取「該方**第一個**叫出最終定約花色者」，而非最後叫牌者。

實測 300 副（含 E/W 競叫）：莊家誤判 **0/296**（修正前 2/162，且因當時拍賣被 F-1 壓得很短而低估）。

---

### #8　F-6：Dealer bridge 靜默丟棄約束

- `specific_cards` 原本回傳空字串 → 現在正確產出 Dealer 原生的 `hascard(south, AS)`（README 本來就宣稱支援 `hascard`）。
- 其餘無法表達的欄位（`suit_quality` / `stopper_in` / `four_card_major` / …）改由 `dropped` 參數回報，`openings_to_dealer_script()` 寫入 script 註解，CLI 以黃字警告：

```
⚠ 2 constraint(s) could not be expressed in Dealer syntax and were dropped —
  the script is looser than the system:
    1NT: dropped stopper_in
```

回傳空字串在 Dealer 語義中等於「無條件」，使用者會拿到不符合原始約束的牌卻毫無所覺。

---

### #9　F-8：不合法拍賣

**根因**：N/S 與 E/W 各自維護獨立的叫牌樹路徑，各自挑叫，從不檢查新叫品是否高於當前最高叫。

**修法**：加入 `_is_sufficient()` 閘門，候選叫品不足額時回退為 Pass。

實測：`precision` vs `sayc` 對戰，不合法拍賣 **15/30 → 0/200**。

---

### #10　F-13：`eval()` → AST 白名單

清空 `__builtins__` 不是沙箱——透過 `().__class__.__mro__` 之類的屬性鏈仍可逃逸。這在條件只來自本地檔案時無所謂，但 **Phase 5 平台接受使用者上傳的 YAML**，屆時 `selection_rules[].condition` 就是不可信輸入。

**修法**：`_safe_eval()` 以 `ast.parse` + 節點白名單（`Compare` / `BoolOp` / `UnaryOp` / `Name` / `Constant`）實作，移除 `eval`。

```
blocked: ().__class__.__mro__[1].__subclasses__()
blocked: __import__('os').system('x')
blocked: open('f','w')
```

**順帶修掉一個潛在 bug**：`!expr` 轉換後會產生前導空白（`" not (hcp >= 20)"`），Python 會解析成縮排錯誤。這在舊的 `eval` 下同樣會壞，只是從來沒有測試碰過開頭的 `!`。已加 `.strip()`。

---

## 三、過程中碰到的問題

### 3.1　ruamel.yaml 重排整份檔案（已回退重做）

第一次為範例加 `priority` 時，我用 `ruamel.yaml` 的 round-trip 模式載入再 dump。結果它**重排了整份檔案的序列縮排**，並把一段註解錯位到相鄰節點。語義正確、驗證通過，但 diff 是 **1712 insertions / 1355 deletions**——實際語義只改了約 40 行。這種 diff 會把真正的變更淹沒，review 時等於看不見。

**處置**：把改好的內容存到 scratchpad 當參考，`git checkout` 回退三個範例，改用**逐行文字插入**重做（正則比對 `- bid: "X"` 的縮排後插入 `priority:`）。最終 diff 降為 387 insertions，且原檔案的註解、引號、縮排風格全部保留。

**教訓**：對「人類會讀、會 review」的 YAML，不要用 round-trip 程式庫重寫整檔；針對性的文字編輯才是對的工具。

### 3.2　更嚴格的 val-002 抓出範例的真實重疊——但不該是 error

修好 val-002 後，它立刻在三套範例抓到回應層的重疊。抽查後確認**這些是真的**，例如 SAYC 1C 的回應：一手 16–18 點、平均牌、含 4 張方塊的牌，**同時滿足** `1D`（6+ 點、4+ 方塊）與 `3NT`（16–18 平均牌）。

但這類重疊在橋牌裡是**正常且必然**的——真實制度靠「優先順序」消歧，不是靠互斥條件。所以我把 val-002 定為：

- 有宣告 tie-break（開叫看 `selection_rules`、回應看兩個節點的 `priority`）→ **通過**
- 沒有任何 tie-break → **warning**（引擎仍以 specificity 確定性地解決，但文件從未說明意圖）

然後替受影響的回應群組**補上 `priority`**，套用一致的橋牌原則：**先示高花 → 再平均牌 NT 跳叫 → 再低花 → 最後加叫**。（例：有 4 張紅心就先叫 1H 找高花吻合，沒有高花才跳 3NT，有 4 張方塊但已無高花可示才叫 1D。）

三套範例現在 `validate` 皆 exit=0。

### 3.3　7 個測試失敗——全部是「測試把錯誤的事實寫死了」

改完核心後有 7 個測試失敗，逐一檢視後**沒有一個是新 bug**：

- 4 個 `convcard` 測試斷言「Precision 的 1NT 是 15–17」「Precision 有強 2C」——這正是我修掉的兩個橋牌錯誤。測試把錯誤事實固化了。已更新為正確斷言（並把 `test_precision_has_strong_2c` 改名為 `test_precision_has_no_strong_2c`，附上「強牌走 1C」的理由註解）。
- `test_matches_first_valid_candidate` 的前提（first-match wins）**就是 F-1 這個 bug 本身**。已重寫為 `test_more_specific_candidate_wins_over_declaration_order`，並補一條 `test_explicit_priority_beats_specificity`。
- 2 個 validator 測試斷言舊的 severity 與「無 selection_rules 算 passed」。已更新。

**這件事本身值得記錄**：測試套件當時是 868 全綠，卻同時鎖住了兩個橋牌錯誤和一個 Critical 選擇 bug。綠燈不等於正確——它只保證行為沒變，不保證行為是對的。

---

## 四、新增的迴歸防線

| 測試 | 防止什麼 |
|------|----------|
| `test_bml_roundtrip.py`（18 條） | F-2 類：匯入匯出間旗標／點力被竄改 |
| `TestKeywordWordBoundaries`（9 條） | `art` 再次命中 `hearts`；長鍵優先失效 |
| `test_every_declared_opening_is_reachable`（3 條） | **F-1 類：任何開叫變成死碼**（500 副牌） |
| `test_no_insufficient_bids`（3 條） | F-8 類：不合法拍賣 |
| `test_declarer_is_first_to_name_the_strain` | F-7 類：莊家判定違反規則 |
| `test_no_selection_rules_is_skipped_not_passed` | F-3 類：空跑通過偽裝成保證 |

---

## 五、文件與授權（F-4 / F-9 / F-11 / F-12）

- **README.md**：`ai_meta` 區塊加上顯著警告——它是 Phase 6 願景，不存在於 SPEC / JSON Schema / Pydantic 模型；因 `extra="allow"` 你寫了不會報錯，但**沒有任何程式碼會讀取它**。測試數更新為 908 / 85%。
- **README-bbDsl.md**：「情境感知」改標為「資料層已定義，引擎尚未實作」；範例路徑從 `process/1-discover/` 改指 `examples/`（三套齊列）；專案結構補上 `bbdsl/`、`examples/`、`tests/`、`bbdsl-platform/`；移除 hypothesis 宣稱；「驗證器 (8 規則)」修正為 14。
- **CLAUDE.md**：ADR-5 註明 `opponent_matcher.py` **尚未實作**；補上「選擇順序絕非宣告順序」「skipped ≠ passed」「莊家依 Law 54」「BML 詞界比對」「Dealer 降級須回報」等實作要點。
- **`models/context.py`**：docstring 從「matching logic in core/opponent_matcher.py」改為明確標示 NOT YET CONSUMED。
- **授權**：三個 `examples/*.bbdsl.yaml` 加上 `# SPDX-License-Identifier: CC-BY-SA-4.0`；README 的 CC-BY-SA 範圍從不存在的 `registry/`、`examples/conventions/` 改為實際存在的 `examples/*.bbdsl.yaml`。

---

## 六、仍待處理 / 建議

以下**不在**本次修正範圍，建議列為後續工作：

1. **回應層的選擇仍只靠 `priority` 與 specificity**，沒有 `selection_rules` 等級的表達力。目前三套範例的回應 priority 是我依「先高花 → NT → 低花」原則指派的，**建議請橋牌專家覆核**——尤其 2/1 的 `1H` 回應群組（`1S` vs `3H` 限制加叫的取捨）與 SAYC 1C 回應的「up the line」慣例（我採高花優先，某些流派主張最便宜的 4 張套先叫）。

2. **`context_overrides` 仍然無人消費**（F-4）。已在文件誠實標示，但要讓「情境感知」名副其實，需要實作 `core/opponent_matcher.py`，並讓 `sim_engine` 在有干擾叫時查詢 overrides。目前模擬中 E/W 的叫牌完全不影響 N/S 的選擇——這是模擬引擎最大的剩餘缺口。

3. **`ai_meta` 若要成真**，最小可行實作是把 `tolerances.hcp.margin` 接進 `hand_generator` 的拒絕取樣（允許邊界外 margin 點以低機率通過）。約 1 天工作量，能讓白皮書的核心宣稱從「願景」變成「已實作」。

4. **BCC** 仍無任何程式碼。審查報告附錄 B 的建議不變：收斂到「用資訊效率量化比較 UDCA vs 標準信號」這個可完成、可發表的子問題，而非直接衝 self-play 超人 AI。

5. **`cli/main.py` 覆蓋率仍偏低**（47%）。使用者實際接觸的入口層測試最薄，值得補。

6. **既有 lint 問題**（全 repo 118 項，多為 F541 f-string 無佔位符與 I001 import 排序）本次未清理，以免與語義修正混在同一個 diff。建議獨立跑一次 `ruff check --fix`。

---

## 七、最終狀態

```
測試      868 passed  →  908 passed   (+40，全綠)
覆蓋率    82%         →  85%
lint      25          →  23           (未新增；皆為既有問題)

三套範例  validate exit=0
          開叫死碼    5 / 4 / — → 0 / 0 / 0
          不合法拍賣  15/30     → 0/200
          莊家誤判    2/162     → 0/296

CLI       11 個指令端到端全數通過
```

變更範圍：7 個核心模組、3 個範例、4 個測試檔（+1 新檔）、4 份文件。
