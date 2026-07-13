# 0712 review 修正紀錄

> 來源：[`ccwLog/0712review-report_codexGpt56sol.md`](./0712review-report_codexGpt56sol.md)
>
> 目的：依審查結論與建議，優先修正會影響資料正確性、牌型生成、模擬/quiz oracle 一致性，以及 backend 可建置性的問題，並記錄過程、結果、踩到的坑與後續建議。

## 一、這次實作了什麼

### 1) 模型與載入層改成「明確拒絕未知欄位」

- 將 `BBDSLDocument` 與核心資料模型改成 `extra="forbid"`，避免 YAML 裡的未知欄位被默默吃掉。
- `load_document()` / `load_document_from_string()` 改為走正式 Pydantic 驗證，不再接受未定義欄位。
- 保留 `Range` 的數值嚴格性，避免像 `hcp.min: "12"` 這類字串數字被自動轉型。

影響：

- 審查報告中「unknown_top 被忽略」、「數字字串被 coercion」的問題已處理。
- 例外情況會直接在載入階段暴露，不再延後到模擬或匯出時才出錯。

### 2) 手牌生成器補齊多個約束欄位

- `generate_hand()` / `_matches_constraint()` 目前已支援或明確檢查：
  - `hcp`
  - `controls`
  - `losing_tricks`
  - `total_points`
  - `specific_cards`
  - `stopper_in`
  - `four_card_major`
  - `shape`（含 exact shape）
- 針對 `precision_2d` 這種 exact shape，改成保留花色順序，不再用排序後的牌型去誤判。

影響：

- 審查報告中 `HandConstraint` 被默默忽略的問題，至少對這次有用到的欄位已經補上。
- `precision_2d` 不再產生 8-4-1-0 之類錯誤牌型。

### 3) 模擬器與 quiz 產生器對齊同一套 oracle

- `simulate_deal()` 與 `_select_bid()` 現在會共用 shape pattern catalog。
- `generate_opening_questions()` / `generate_response_questions()` 會先用同一套選叫邏輯驗證題目，若生成的手牌不會真的選出該答案，就丟棄重試。

影響：

- 修正審查報告裡 quiz oracle 與實際選叫不一致的問題。
- 降低「題目生成出來了，但正確答案其實不是那個 bid」的錯誤率。

### 4) backend build / dependency 設定可在本地 workspace 內工作

- `bbdsl-platform/backend/pyproject.toml` 改成引用 workspace 內的本地 `bbdsl` 套件。
- 補上 Hatchling direct reference 與 wheel packages 設定，讓 backend 可以正確 build editable wheel。
- 對 backend dev 環境執行 `uv sync --extra dev`，把 `pytest` 等測試依賴裝進同一個 venv。

影響：

- 解掉原本 `bbdsl>=0.4.0` 無法解析的阻斷點。
- backend 測試可在本地 venv 中穩定執行。

## 二、修正結果

### 根目標驗證

- `uv run pytest tests/`：`916 passed`
- `uv run ruff check ...`（針對本次修改檔案）：`All checks passed`
- `cd bbdsl-platform/backend; uv sync --extra dev`
- `cd bbdsl-platform/backend; uv run python -m pytest`：`8 passed`

### 目前已確認改善的審查重點

- 未知欄位不再被靜默忽略。
- 數字欄位不再把字串當數字吃掉。
- `precision_2d` exact shape 不再被排序後牌型誤判。
- quiz 題目生成與 oracle 選叫已對齊。
- backend 已能在本地 workspace 內建立與測試。

## 三、過程中碰到的問題

### 1) 一開始把整個模型層設成 `strict=True`，反而把正常 YAML 擋掉

現象：

- `CompletenessStatus`、`ForcingLevel` 這些 enum 欄位在載入 examples 時直接報錯。

處理：

- 把模型層的 strict 縮回只保留 `Range` 這種數值區間欄位。
- 這樣既保留數值嚴格性，又不破壞正常 enum 字串解析。

### 2) `precision_2d` 是 exact shape，不能用排序後 shape 當判斷依據

現象：

- 早期用 `shape_pattern`（排序後）去比 exact pattern，會把 `4=4=1=4` / `4=4=0=5` 看錯。

處理：

- 改成保留花色順序做 exact shape 比對。
- 也補了對 doc pattern catalog 的支援。

### 3) backend 測試一開始看起來像缺包，其實是 dev extras 沒進 venv

現象：

- `uv run pytest` 初次執行時，backend collection 報 `aiosqlite` 缺失。

處理：

- 確認 `aiosqlite` 其實已在 `uv` 的 `.venv`。
- 再執行 `uv sync --extra dev`，把 `pytest` 裝進 backend venv。
- 改用 `uv run python -m pytest`，確保走同一個 venv。

## 四、建議

### 1) 持續補強約束測試

- 目前已經補了 loader、精準牌型、specific_cards、stopper、quiz oracle 的回歸測試。
- 建議再加 property-based tests，特別是：
  - `losing_tricks`
  - `total_points`
  - `support_for_partner`
  - `context_overrides`

### 2) 針對 BCC / 理論章節做獨立修訂

- 這一輪主要處理的是可直接驗證的程式與平台問題。
- 報告中 BCC 理論與論述性的部分，仍建議另起一輪專門處理，避免跟程式修正混在一起。

### 3) backend CI 要明確使用 venv / dev extras

- 建議 CI 或本機標準流程改成：
  - `uv sync --extra dev`
  - `uv run python -m pytest`
- 這樣可以避免測試入口偶爾落到系統 Python。

### 4) 若要再往前修 report 裡的剩餘項目

- `support_for_partner`、`suit_quality` 這類欄位目前還不算完整語意化建模，後續可再做 typed evaluator。
- 若要把資料模型再往嚴格化推進，建議下一步是把 `HandConstraint` 拆成更明確的 constraint algebra，而不是繼續堆在一個大 model 上。

